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
from new_backend_ruminate.infrastructure.llm.enhanced_openai import EnhancedOpenAILLM

logger = logging.getLogger(__name__)


class CheckInService:
    """Service for managing daily check-ins and insight generation."""
    
    def __init__(
        self,
        checkin_repo: CheckInRepository,
        dream_repo: DreamRepository,
        user_repo: UserRepository,
        llm_service: LLMService
    ):
        self._checkin_repo = checkin_repo
        self._dream_repo = dream_repo
        self._user_repo = user_repo
        self._llm = llm_service
    
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
        """Generate insight for a check-in using LLM."""
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
            
            # Gather context for the insight
            context = await self._gather_insight_context(user_id, checkin, session)
            
            # Build the prompt
            prompt = self._build_insight_prompt(checkin, context)
            
            # Generate insight
            insight_text = await self._llm.complete(
                prompt=prompt,
                max_tokens=300,  # Keep insights concise
                temperature=0.8  # Some creativity
            )
            
            # Update check-in with insight
            updated_checkin = await self._checkin_repo.update_insight(
                user_id=user_id,
                checkin_id=checkin_id,
                insight_text=insight_text,
                context_metadata=context,
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
    
    async def _gather_insight_context(
        self,
        user_id: UUID,
        checkin: DailyCheckIn,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Gather context for insight generation."""
        context = {
            "checkin_time": checkin.created_at.isoformat(),
            "mood_scores": checkin.mood_scores or {}
        }
        
        # Get user preferences
        preferences = await self._user_repo.get_preferences(user_id, session)
        if preferences:
            context["mbti"] = preferences.mbti_type
            context["horoscope"] = preferences.horoscope_data
            context["ocean_scores"] = preferences.ocean_scores
            context["primary_goal"] = preferences.primary_goal
        
        # Get recent dreams (last 3)
        recent_dreams = await self._dream_repo.list_dreams_by_user(
            user_id, session, limit=3
        )
        
        context["recent_dreams"] = []
        for dream in recent_dreams:
            if dream.analysis:  # Only include analyzed dreams
                context["recent_dreams"].append({
                    "date": dream.created_at.date().isoformat(),
                    "title": dream.title,
                    "summary": dream.summary,
                    "analysis": dream.analysis[:500]  # First 500 chars
                })
        
        return context
    
    def _build_insight_prompt(
        self,
        checkin: DailyCheckIn,
        context: Dict[str, Any]
    ) -> str:
        """Build the prompt for insight generation."""
        # Extract psychological profile
        mbti = context.get("mbti", "Unknown")
        horoscope = context.get("horoscope", {})
        ocean = context.get("ocean_scores", {})
        goal = context.get("primary_goal", "self-discovery")
        
        # Format recent dreams
        dreams_text = ""
        if context.get("recent_dreams"):
            dreams_text = "\n\nRecent dreams and their interpretations:\n"
            for dream in context["recent_dreams"]:
                dreams_text += f"- {dream['date']}: {dream['title']}\n"
                dreams_text += f"  Summary: {dream['summary']}\n"
                if dream.get('analysis'):
                    dreams_text += f"  Key insight: {dream['analysis'][:200]}...\n"
        
        # Build the prompt
        prompt = f"""You are the user's inner voice, providing deep, personalized insights based on their psychological profile and recent dreams.

User Profile:
- MBTI Type: {mbti}
- Primary Goal: {goal}
- Astrological Sign: {horoscope.get('sign', 'Unknown')}
- Big Five Traits: Openness: {ocean.get('openness', 'N/A')}, Conscientiousness: {ocean.get('conscientiousness', 'N/A')}, Extraversion: {ocean.get('extraversion', 'N/A')}, Agreeableness: {ocean.get('agreeableness', 'N/A')}, Neuroticism: {ocean.get('neuroticism', 'N/A')}

Today's Check-in:
"{checkin.checkin_text}"
{dreams_text}

Based on this holistic view of the user's inner world, write a brief, profound insight (120 words max) that:
1. Connects their current feelings to patterns in their dreams
2. Reflects their personality type and traits
3. Offers a compassionate, actionable perspective
4. Speaks as their subconscious wisdom

Start with "Deep down, you..." and write in second person. Be specific, not generic. Reference actual dream symbols or themes when relevant."""

        return prompt