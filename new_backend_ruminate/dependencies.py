# new_backend_ruminate/dependencies.py

"""
Centralised FastAPI dependency providers.

Lifetimes
---------
* module-level singletons → created once at import time
* request-scoped objects  → yielded by functions that FastAPI wraps
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
from new_backend_ruminate.infrastructure.implementations.object_storage.s3_storage_repository import S3StorageRepository
from new_backend_ruminate.infrastructure.implementations.user.rds_user_repository import RDSUserRepository
from new_backend_ruminate.infrastructure.implementations.user.profile_repository import SqlProfileRepository
from new_backend_ruminate.infrastructure.llm.openai_llm import OpenAILLM
from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.services.profile.service import ProfileService
from new_backend_ruminate.infrastructure.transcription.deepgram import DeepgramTranscriptionService
from new_backend_ruminate.infrastructure.transcription.whisper import WhisperTranscriptionService
from new_backend_ruminate.infrastructure.transcription.gpt4o import GPT4oTranscriptionService
from new_backend_ruminate.services.agent.service import AgentService
from new_backend_ruminate.context.builder import ContextBuilder
from new_backend_ruminate.infrastructure.db.bootstrap import get_session as get_db_session
from new_backend_ruminate.context.renderers.agent import register_agent_renderers
from new_backend_ruminate.infrastructure.celery.adapter import CeleryVideoQueueAdapter
from new_backend_ruminate.domain.ports.video_queue import VideoQueuePort
from jose import JWTError, jwt
from uuid import UUID
from typing import AsyncGenerator
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

register_agent_renderers()

# ────────────────────────── singletons ─────────────────────────── #

_hub = EventStreamHub()
_conversation_repo = RDSConversationRepository()
_dream_repo = RDSDreamRepository()
_user_repo = RDSUserRepository()
_profile_repo = SqlProfileRepository()
_llm  = OpenAILLM(
    api_key=settings().openai_api_key,
    model=settings().openai_model,
)
# Separate LLM instances for dream-specific tasks
_dream_summary_llm = OpenAILLM(
    api_key=settings().openai_api_key,
    model=settings().dream_summary_model,
)
_dream_question_llm = OpenAILLM(
    api_key=settings().openai_api_key,
    model=settings().dream_question_model,
)
_dream_analysis_llm = OpenAILLM(
    api_key=settings().openai_api_key,
    model=settings().dream_analysis_model,
)
_ctx_builder = ContextBuilder()
_conversation_service = ConversationService(_conversation_repo, _llm, _hub, _ctx_builder)
_agent_service = AgentService(_conversation_repo, _llm, _hub, _ctx_builder)
_storage_service = S3StorageRepository()
_transcribe = GPT4oTranscriptionService()
_dream_service = DreamService(_dream_repo, _storage_service, _user_repo, _transcribe, _hub, _dream_summary_llm, _dream_question_llm, _dream_analysis_llm)
_profile_service = ProfileService(_profile_repo, _dream_analysis_llm)
_video_queue = CeleryVideoQueueAdapter()

# ─────────────────────── DI provider helpers ───────────────────── #

def get_event_hub() -> EventStreamHub:
    """Return the process-wide in-memory hub (singleton)."""
    return _hub

def get_context_builder() -> ContextBuilder:
    """Return the singleton ContextBuilder; stateless, safe to share."""
    return _ctx_builder

def get_conversation_service() -> ConversationService:
    """Return the singleton ConversationService; stateless, safe to share."""
    return _conversation_service

def get_dream_service() -> DreamService:
    return _dream_service

def get_agent_service() -> AgentService:
    """Return the singleton AgentService; stateless, safe to share."""
    return _agent_service

def get_user_repository() -> RDSUserRepository:
    return _user_repo

def get_conversation_repository() -> RDSConversationRepository:
    return _conversation_repo

def get_dream_repository() -> RDSDreamRepository:
    return _dream_repo

def get_storage_service() -> S3StorageRepository:
    return _storage_service

def get_llm_service() -> OpenAILLM:
    return _llm

def get_dream_summary_llm() -> OpenAILLM:
    """Return the LLM instance specifically for dream summaries."""
    return _dream_summary_llm

def get_dream_question_llm() -> OpenAILLM:
    """Return the LLM instance specifically for dream interpretation questions."""
    return _dream_question_llm

def get_dream_analysis_llm() -> OpenAILLM:
    """Return the LLM instance specifically for dream analysis."""
    return _dream_analysis_llm

def get_video_queue() -> VideoQueuePort:
    """Return the singleton video queue adapter."""
    return _video_queue

def get_profile_service() -> ProfileService:
    """Return the singleton ProfileService."""
    return _profile_service

# ───────────────────────── auth helpers ───────────────────────── #
_security = HTTPBearer()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(_security)) -> dict:
    """Decode our own JWT and return its payload (sub, email, exp, …)."""
    try:
        payload = jwt.decode(token.credentials, settings().jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

async def get_current_user_id(
    token: HTTPAuthorizationCredentials = Depends(_security),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    """Return internal User.id for authenticated JWT; 401 if unknown/invalid."""
    try:
        payload = jwt.decode(token.credentials, settings().jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Prefer our internal `uid` (primary key) – issued by this API –
    # fallback to Google `sub` claim for tokens that come directly from Google.
    uid_str: str | None = payload.get("uid")
    sub_str: str | None = payload.get("sub")

    user = None
    if uid_str:
        try:
            user = await _user_repo.get_by_id(UUID(uid_str), session)
        except ValueError:
            # not a valid UUID, ignore and fall back
            pass

    if user is None and sub_str:
        user = await _user_repo.get_by_sub(sub_str, session)

    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")

    return user.id


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped database session (async).

    Delegates to *new_backend_ruminate.infrastructure.db.bootstrap.get_session* but
    preserves the required *async generator* signature so FastAPI can manage
    the lifecycle automatically (open → yield → close).
    """
    async for session in get_db_session():
        yield session
