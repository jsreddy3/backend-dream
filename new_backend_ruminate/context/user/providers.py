"""Context providers for user profile analysis."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.user.repo import UserRepository
from new_backend_ruminate.domain.dream.repo import DreamRepository
from new_backend_ruminate.domain.checkin.repo import CheckInRepository
from new_backend_ruminate.domain.user.profile_repo import ProfileRepository
from new_backend_ruminate.domain.checkin.entities import DailyCheckIn


class UserPreferencesProvider:
    """Provides user psychological profile and preferences."""
    
    def __init__(self, profile_repo: ProfileRepository):
        self._repo = profile_repo
        
    async def get_preferences(self, user_id: UUID, session: AsyncSession) -> Dict[str, Any]:
        """Get user preferences and psychological profile."""
        preferences = await self._repo.get_user_preferences(user_id, session)
        if not preferences:
            return {}
            
        return {
            "mbti_type": preferences.mbti_type,
            "horoscope_data": preferences.horoscope_data,
            "ocean_scores": preferences.ocean_scores,
            "primary_goal": preferences.primary_goal,
            "personality_traits": preferences.personality_traits,
            "interests": preferences.interests,
            "common_dream_themes": preferences.common_dream_themes,
            "initial_archetype": preferences.initial_archetype
        }


class UserDreamsProvider:
    """Provides recent dreams context for personalized insights."""
    
    def __init__(self, dream_repo: DreamRepository):
        self._repo = dream_repo
        
    async def get_recent_dreams(
        self, 
        user_id: UUID, 
        session: AsyncSession, 
        limit: int = 3,
        analyzed_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get recent dreams for context."""
        dreams = await self._repo.list_dreams_by_user(user_id, session)
        
        recent_dreams = []
        for dream in dreams[:limit]:
            # Skip dreams without analysis if requested
            if analyzed_only and not dream.analysis:
                continue
                
            dream_data = {
                "date": dream.created_at.date().isoformat(),
                "title": dream.title or "Untitled Dream",
                "summary": dream.summary,
                "analysis": dream.analysis
            }
            
            # Add key themes/symbols if available in metadata
            if dream.analysis_metadata and isinstance(dream.analysis_metadata, dict):
                dream_data["themes"] = dream.analysis_metadata.get("themes", [])
                dream_data["symbols"] = dream.analysis_metadata.get("symbols", [])
                dream_data["emotions"] = dream.analysis_metadata.get("emotions", [])
                
            recent_dreams.append(dream_data)
            
        return recent_dreams


class UserCheckinProvider:
    """Provides check-in data and context."""
    
    def __init__(self, checkin_repo: CheckInRepository):
        self._repo = checkin_repo
        
    async def get_checkin(
        self, 
        user_id: UUID, 
        checkin_id: UUID, 
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Get specific check-in for insight generation."""
        return await self._repo.get_checkin(user_id, checkin_id, session)
    
    async def get_recent_checkins(
        self, 
        user_id: UUID, 
        session: AsyncSession, 
        limit: int = 5
    ) -> List[DailyCheckIn]:
        """Get recent check-ins for pattern analysis."""
        return await self._repo.list_checkins_by_user(user_id, session, limit=limit)
            
    async def get_mood_patterns(
        self, 
        user_id: UUID, 
        session: AsyncSession, 
        days: int = 7
    ) -> Dict[str, Any]:
        """Analyze mood patterns over recent days."""
        checkins = await self._repo.list_checkins_by_user(user_id, session, limit=days)
        
        if not checkins:
            return {}
            
        mood_trends = {}
        total_checkins = len(checkins)
        
        # Aggregate mood scores
        for checkin in checkins:
            if checkin.mood_scores:
                for mood, score in checkin.mood_scores.items():
                    if mood not in mood_trends:
                        mood_trends[mood] = []
                    mood_trends[mood].append(score)
                    
        # Calculate averages
        mood_averages = {}
        for mood, scores in mood_trends.items():
            mood_averages[mood] = sum(scores) / len(scores)
            
        return {
            "total_checkins": total_checkins,
            "mood_averages": mood_averages,
            "date_range": {
                "from": checkins[-1].created_at.date().isoformat() if checkins else None,
                "to": checkins[0].created_at.date().isoformat() if checkins else None
            }
        }