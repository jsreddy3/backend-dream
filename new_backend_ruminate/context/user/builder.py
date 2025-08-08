"""User profile context builder orchestrates all providers."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.user.repo import UserRepository
from new_backend_ruminate.domain.dream.repo import DreamRepository
from new_backend_ruminate.domain.checkin.repo import CheckInRepository
from new_backend_ruminate.domain.user.profile_repo import ProfileRepository
from .providers import (
    UserPreferencesProvider,
    UserDreamsProvider, 
    UserCheckinProvider
)
from .context_window import UserProfileContextWindow
from .prompts import UserProfilePrompts

logger = logging.getLogger(__name__)


class UserProfileContextBuilder:
    """Orchestrates context building for user-personalized insights."""
    
    def __init__(
        self, 
        profile_repo: ProfileRepository,
        dream_repo: DreamRepository,
        checkin_repo: CheckInRepository
    ):
        self._dream_repo = dream_repo
        self._checkin_repo = checkin_repo
        
        # Initialize providers
        self._preferences_provider = UserPreferencesProvider(profile_repo)
        self._dreams_provider = UserDreamsProvider(dream_repo) 
        self._checkin_provider = UserCheckinProvider(checkin_repo)
    
    async def build_for_daily_insight(
        self,
        user_id: UUID,
        checkin_id: UUID,
        session: AsyncSession
    ) -> Optional[UserProfileContextWindow]:
        """Build context for daily insight generation."""
        logger.debug(f"Building context for daily insight for user {user_id}, checkin {checkin_id}")
        
        # Fetch components sequentially to avoid shared-session concurrency issues
        checkin = await self._checkin_provider.get_checkin(user_id, checkin_id, session)
        if not checkin:
            logger.error(f"No check-in found for {checkin_id}")
            return None
        preferences = await self._preferences_provider.get_preferences(user_id, session)
        recent_dreams = await self._dreams_provider.get_recent_dreams(user_id, session, limit=3)
        
        return UserProfileContextWindow(
            user_id=str(user_id),
            checkin_id=str(checkin_id),
            checkin_text=checkin.checkin_text,
            checkin_date=checkin.created_at,
            mood_scores=checkin.mood_scores,
            
            # Psychological profile
            mbti_type=preferences.get("mbti_type"),
            horoscope_data=preferences.get("horoscope_data"),
            ocean_scores=preferences.get("ocean_scores"),
            primary_goal=preferences.get("primary_goal"),
            personality_traits=preferences.get("personality_traits"),
            interests=preferences.get("interests"),
            common_themes=preferences.get("common_dream_themes"),
            
            # Dreams context
            recent_dreams=recent_dreams,
            
            task_type="daily_insight"
        )

    async def build_for_personalized_analysis(
        self,
        user_id: UUID,
        dream_id: UUID,
        session: AsyncSession
    ) -> Optional[UserProfileContextWindow]:
        """Build context for personalized dream interpretation."""
        logger.debug(f"Building context for personalized analysis for user {user_id}, dream {dream_id}")
        
        # Get user preferences and the specific dream (sequential to avoid concurrent ops on one session)
        preferences = await self._preferences_provider.get_preferences(user_id, session)
        dream = await self._dream_repo.get_dream(user_id, dream_id, session)
        
        if not dream:
            logger.error(f"No dream found for {dream_id}")
            return None
            
        return UserProfileContextWindow(
            user_id=str(user_id),
            
            # Dream being analyzed (stored in metadata)
            metadata={
                "dream_id": str(dream_id),
                "dream_transcript": dream.transcript,
                "dream_title": dream.title,
                "dream_summary": dream.summary,
                "dream_date": dream.created_at
            },
            
            # Psychological profile
            mbti_type=preferences.get("mbti_type"),
            horoscope_data=preferences.get("horoscope_data"),
            ocean_scores=preferences.get("ocean_scores"),
            primary_goal=preferences.get("primary_goal"),
            personality_traits=preferences.get("personality_traits"),
            interests=preferences.get("interests"),
            common_themes=preferences.get("common_dream_themes"),
            
            task_type="personalized_analysis"
        )
    
    async def build_for_profile_summary(
        self,
        user_id: UUID,
        session: AsyncSession,
        dream_days: int = 30
    ) -> Optional[UserProfileContextWindow]:
        """Build context for comprehensive profile summary."""
        logger.debug(f"Building context for profile summary for user {user_id}")
        
        # Fetch comprehensive profile data (sequential to avoid session concurrency conflicts)
        preferences = await self._preferences_provider.get_preferences(user_id, session)
        recent_dreams = await self._dreams_provider.get_recent_dreams(
            user_id, session, limit=10, analyzed_only=True
        )
        mood_patterns = await self._checkin_provider.get_mood_patterns(user_id, session, days=dream_days)
        
        return UserProfileContextWindow(
            user_id=str(user_id),
            
            # Psychological profile
            mbti_type=preferences.get("mbti_type"),
            horoscope_data=preferences.get("horoscope_data"),
            ocean_scores=preferences.get("ocean_scores"),
            primary_goal=preferences.get("primary_goal"),
            personality_traits=preferences.get("personality_traits"),
            interests=preferences.get("interests"),
            common_themes=preferences.get("common_dream_themes"),
            
            # Extended context
            recent_dreams=recent_dreams,
            metadata={
                "mood_patterns": mood_patterns,
                "analysis_period_days": dream_days
            },
            
            task_type="profile_summary"
        )
    
    def prepare_llm_messages(
        self, 
        context_window: UserProfileContextWindow,
        task_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Prepare LLM messages based on context window and task type."""
        task_type = task_type or context_window.task_type
        context_components = context_window.get_context_components()
        
        # Get appropriate prompts
        if task_type == "daily_insight":
            system_prompt = UserProfilePrompts.DAILY_INSIGHT_SYSTEM
            user_prompt = UserProfilePrompts.build_daily_insight_prompt(context_components)
            
        elif task_type == "personalized_analysis":
            system_prompt = UserProfilePrompts.PERSONALIZED_ANALYSIS_SYSTEM
            dream_context = self._format_dream_context(context_window.metadata)
            user_prompt = UserProfilePrompts.build_personalized_interpretation_prompt(
                dream_context, context_components
            )
            
        elif task_type == "profile_summary":
            system_prompt = UserProfilePrompts.PROFILE_SUMMARY_SYSTEM
            user_prompt = UserProfilePrompts.PROFILE_INSIGHTS_USER.format(
                psychological_profile=context_components.get("psychological_profile", {}),
                dream_summary=self._summarize_dreams(context_window.recent_dreams),
                mood_patterns=context_window.metadata.get("mood_patterns", {})
            )
            
        else:
            raise ValueError(f"Unknown task type: {task_type}")
            
        return context_window.to_llm_messages(system_prompt, user_prompt)
    
    def get_json_schema_for_task(self, task_type: str) -> Optional[Dict[str, Any]]:
        """Get the JSON schema for structured responses."""
        return UserProfilePrompts.get_json_schema_for_task(task_type)
    
    def _format_dream_context(self, metadata: Dict[str, Any]) -> str:
        """Format dream data for personalized interpretation."""
        dream_parts = []
        
        if metadata.get("dream_title"):
            dream_parts.append(f"Title: {metadata['dream_title']}")
            
        if metadata.get("dream_summary"):
            dream_parts.append(f"Summary: {metadata['dream_summary']}")
            
        if metadata.get("dream_transcript"):
            dream_parts.append(f"Full Dream:\n{metadata['dream_transcript']}")
            
        return "\n\n".join(dream_parts) if dream_parts else "No dream content available"
    
    def _summarize_dreams(self, dreams: Optional[List[Dict[str, Any]]]) -> str:
        """Create a summary of recent dreams."""
        if not dreams:
            return "No recent dreams with analysis available."
            
        summaries = []
        for dream in dreams:
            summary = f"• {dream.get('date')}: {dream.get('title', 'Untitled')}"
            if dream.get('themes'):
                summary += f" (Themes: {', '.join(dream['themes'][:3])})"
            summaries.append(summary)
            
        return "\n".join(summaries)