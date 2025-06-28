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
from new_backend_ruminate.infrastructure.llm.openai_llm import OpenAILLM
from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.infrastructure.transcription.deepgram import DeepgramTranscriptionService
from new_backend_ruminate.services.agent.service import AgentService
from new_backend_ruminate.context.builder import ContextBuilder
from new_backend_ruminate.infrastructure.db.bootstrap import get_session as get_db_session
from new_backend_ruminate.context.renderers.agent import register_agent_renderers
from new_backend_ruminate.infrastructure.celery.adapter import CeleryVideoQueueAdapter
from new_backend_ruminate.domain.ports.video_queue import VideoQueuePort

register_agent_renderers()

# ────────────────────────── singletons ─────────────────────────── #

_hub = EventStreamHub()
_conversation_repo = RDSConversationRepository()
_dream_repo = RDSDreamRepository()
_llm  = OpenAILLM(
    api_key=settings().openai_api_key,
    model=settings().openai_model,
)
_ctx_builder = ContextBuilder()
_conversation_service = ConversationService(_conversation_repo, _llm, _hub, _ctx_builder)
_agent_service = AgentService(_conversation_repo, _llm, _hub, _ctx_builder)
_storage_service = S3StorageRepository()
_transcribe = DeepgramTranscriptionService()
_dream_service = DreamService(_dream_repo, _storage_service, _transcribe, _hub)   # _dream_repo = RDSDreamRepository()
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

def get_conversation_repository() -> RDSConversationRepository:
    return _conversation_repo

def get_dream_repository() -> RDSDreamRepository:
    return _dream_repo

def get_storage_service() -> S3StorageRepository:
    return _storage_service

def get_llm_service() -> OpenAILLM:
    return _llm

def get_video_queue() -> VideoQueuePort:
    """Return the singleton video queue adapter."""
    return _video_queue

from typing import AsyncGenerator

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped database session (async).

    Delegates to *new_backend_ruminate.infrastructure.db.bootstrap.get_session* but
    preserves the required *async generator* signature so FastAPI can manage
    the lifecycle automatically (open → yield → close).
    """
    async for session in get_db_session():
        yield session
