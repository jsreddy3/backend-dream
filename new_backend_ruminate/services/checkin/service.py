"""Check-in service for managing daily insights."""
from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.checkin.entities import DailyCheckIn, InsightStatus
from new_backend_ruminate.domain.checkin.repo import CheckInRepository
from new_backend_ruminate.domain.dream.repo import DreamRepository
from new_backend_ruminate.domain.user.repo import UserRepository
from new_backend_ruminate.infrastructure.llm.openai_llm import OpenAILLM
from new_backend_ruminate.context.user.builder import UserProfileContextBuilder

logger = logging.getLogger(__name__)


class CheckInService:
    """Service for managing daily check-ins and insight generation."""
    
    def __init__(
        self,
        checkin_repo: CheckInRepository,
        dream_repo: DreamRepository,
        user_repo: UserRepository,
        user_context_builder: UserProfileContextBuilder,
        llm_service: OpenAILLM
    ):
        self._checkin_repo = checkin_repo
        self._dream_repo = dream_repo
        self._user_repo = user_repo
        self._llm = llm_service
        
        # Initialize context builder
        self._context_builder = user_context_builder
    
    async def create_checkin(
        self,
        user_id: UUID,
        checkin_text: str,
        mood_scores: Optional[Dict[str, float]] = None,
        session: AsyncSession = None
    ) -> DailyCheckIn:
        """Create a new check-in."""
        checkin = DailyCheckIn(
            id=uuid4(),
            user_id=user_id,
            checkin_text=checkin_text,
            mood_scores=mood_scores,
            insight_status=InsightStatus.PENDING.value
        )
        return await self._checkin_repo.create_checkin(user_id, checkin, session)
    
    async def get_checkin(
        self,
        user_id: UUID,
        checkin_id: UUID,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Get a specific check-in."""
        return await self._checkin_repo.get_checkin(user_id, checkin_id, session)
    
    async def list_recent_checkins(
        self,
        user_id: UUID,
        session: AsyncSession,
        limit: int = 10
    ) -> List[DailyCheckIn]:
        """List recent check-ins for a user."""
        return await self._checkin_repo.list_checkins_by_user(
            user_id, session, limit=limit
        )
    
    async def generate_insight(
        self,
        user_id: UUID,
        checkin_id: UUID,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Generate insight for a check-in using context builder and LLM."""
        # Get the check-in
        checkin = await self._checkin_repo.get_checkin(user_id, checkin_id, session)
        if not checkin:
            logger.error(f"Check-in {checkin_id} not found for user {user_id}")
            return None
        
        # Skip if already processed
        if checkin.insight_status == InsightStatus.COMPLETED.value:
            logger.info(f"Check-in {checkin_id} already has insight")
            return checkin
        
        try:
            # Mark as processing
            checkin.insight_status = InsightStatus.PROCESSING.value
            await session.commit()
            
            # Build context using the context builder
            context_window = await self._context_builder.build_for_daily_insight(
                user_id=user_id,
                checkin_id=checkin_id,
                session=session
            )
            
            if not context_window:
                logger.error(f"Failed to build context for check-in {checkin_id}")
                raise ValueError("Unable to build insight context")
            
            # Prepare LLM messages
            messages = self._context_builder.prepare_llm_messages(context_window)
            
            # Get JSON schema for structured response
            json_schema = self._context_builder.get_json_schema_for_task("daily_insight")
            
            # Generate insight using structured response
            if json_schema:
                response = await self._llm.generate_structured_response(
                    messages=messages,
                    response_format={"type": "json_object"},
                    json_schema=json_schema
                )
                insight_text = response.get("insight", "")
                context_metadata = {
                    "key_themes": response.get("key_themes", []),
                    "confidence": response.get("confidence"),
                    "context_token_estimate": context_window.estimate_tokens()
                }
            else:
                # Fallback to unstructured response
                insight_text = await self._llm.generate_response(messages)
                context_metadata = {
                    "context_token_estimate": context_window.estimate_tokens()
                }
            
            # Update check-in with insight
            updated_checkin = await self._checkin_repo.update_insight(
                user_id=user_id,
                checkin_id=checkin_id,
                insight_text=insight_text,
                context_metadata=context_metadata,
                session=session
            )
            
            logger.info(f"Generated insight for check-in {checkin_id}")
            return updated_checkin
            
        except Exception as e:
            logger.error(f"Failed to generate insight for check-in {checkin_id}: {str(e)}")
            await self._checkin_repo.mark_insight_failed(
                user_id=user_id,
                checkin_id=checkin_id,
                error_message=str(e),
                session=session
            )
            return None
