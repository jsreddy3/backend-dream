"""SQL implementation of ProfileRepository."""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.user.profile_repo import ProfileRepository
from new_backend_ruminate.domain.user.profile import DreamSummary, UserProfile, EmotionalMetric, DreamTheme


class SqlProfileRepository(ProfileRepository):
    """SQL implementation of ProfileRepository using raw SQL queries."""
    
    # Dream Summary methods
    async def get_dream_summary(self, user_id: UUID, session: AsyncSession) -> Optional[DreamSummary]:
        """Get dream summary for a user."""
        result = await session.execute(
            text("SELECT * FROM dream_summaries WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        row = result.first()
        
        if not row:
            return None
        
        return DreamSummary(
            id=row.id,
            user_id=row.user_id,
            dream_count=row.dream_count,
            total_duration_seconds=row.total_duration_seconds,
            last_dream_date=row.last_dream_date,
            dream_streak_days=row.dream_streak_days,
            theme_keywords=row.theme_keywords or {},
            emotion_counts=row.emotion_counts or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    
    async def create_dream_summary(self, summary: DreamSummary, session: AsyncSession) -> DreamSummary:
        """Create a new dream summary."""
        await session.execute(
            text("""
                INSERT INTO dream_summaries 
                (id, user_id, dream_count, total_duration_seconds, last_dream_date, 
                 dream_streak_days, theme_keywords, emotion_counts, created_at, updated_at)
                VALUES (:id, :user_id, :dream_count, :total_duration_seconds, :last_dream_date,
                        :dream_streak_days, :theme_keywords, :emotion_counts, :created_at, :updated_at)
            """),
            {
                "id": summary.id,
                "user_id": summary.user_id,
                "dream_count": summary.dream_count,
                "total_duration_seconds": summary.total_duration_seconds,
                "last_dream_date": summary.last_dream_date,
                "dream_streak_days": summary.dream_streak_days,
                "theme_keywords": json.dumps(summary.theme_keywords),
                "emotion_counts": json.dumps(summary.emotion_counts),
                "created_at": summary.created_at,
                "updated_at": summary.updated_at,
            }
        )
        await session.commit()
        return summary
    
    async def update_dream_summary(self, summary: DreamSummary, session: AsyncSession) -> DreamSummary:
        """Update an existing dream summary."""
        await session.execute(
            text("""
                UPDATE dream_summaries 
                SET dream_count = :dream_count,
                    total_duration_seconds = :total_duration_seconds,
                    last_dream_date = :last_dream_date,
                    dream_streak_days = :dream_streak_days,
                    theme_keywords = :theme_keywords,
                    emotion_counts = :emotion_counts,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {
                "id": summary.id,
                "dream_count": summary.dream_count,
                "total_duration_seconds": summary.total_duration_seconds,
                "last_dream_date": summary.last_dream_date,
                "dream_streak_days": summary.dream_streak_days,
                "theme_keywords": json.dumps(summary.theme_keywords),
                "emotion_counts": json.dumps(summary.emotion_counts),
            }
        )
        await session.commit()
        return summary
    
    async def get_or_create_dream_summary(self, user_id: UUID, session: AsyncSession) -> DreamSummary:
        """Get existing dream summary or create a new one."""
        summary = await self.get_dream_summary(user_id, session)
        if summary:
            return summary
        
        # Create new summary
        new_summary = DreamSummary(
            id=uuid4(),
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        return await self.create_dream_summary(new_summary, session)
    
    # User Profile methods
    async def get_user_profile(self, user_id: UUID, session: AsyncSession) -> Optional[UserProfile]:
        """Get user profile."""
        result = await session.execute(
            text("SELECT * FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        row = result.first()
        
        if not row:
            return None
        
        # Parse emotional landscape
        emotional_landscape = []
        for metric_data in (row.emotional_landscape or []):
            emotional_landscape.append(EmotionalMetric(
                name=metric_data["name"],
                intensity=metric_data["intensity"],
                color=metric_data["color"]
            ))
        
        # Parse top themes
        top_themes = []
        for theme_data in (row.top_themes or []):
            top_themes.append(DreamTheme(
                name=theme_data["name"],
                percentage=theme_data["percentage"]
            ))
        
        return UserProfile(
            id=row.id,
            user_id=row.user_id,
            archetype=row.archetype,
            archetype_confidence=row.archetype_confidence,
            archetype_metadata=row.archetype_metadata or {},
            emotional_landscape=emotional_landscape,
            top_themes=top_themes,
            recent_symbols=row.recent_symbols or [],
            calculation_version=row.calculation_version,
            last_calculated_at=row.last_calculated_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    
    async def create_user_profile(self, profile: UserProfile, session: AsyncSession) -> UserProfile:
        """Create a new user profile."""
        # Serialize complex types
        emotional_landscape_data = [
            {"name": m.name, "intensity": m.intensity, "color": m.color}
            for m in profile.emotional_landscape
        ]
        
        top_themes_data = [
            {"name": t.name, "percentage": t.percentage}
            for t in profile.top_themes
        ]
        
        await session.execute(
            text("""
                INSERT INTO user_profiles 
                (id, user_id, archetype, archetype_confidence, archetype_metadata,
                 emotional_landscape, top_themes, recent_symbols, calculation_version,
                 last_calculated_at, created_at, updated_at)
                VALUES (:id, :user_id, :archetype, :archetype_confidence, :archetype_metadata,
                        :emotional_landscape, :top_themes, :recent_symbols, :calculation_version,
                        :last_calculated_at, :created_at, :updated_at)
            """),
            {
                "id": profile.id,
                "user_id": profile.user_id,
                "archetype": profile.archetype,
                "archetype_confidence": profile.archetype_confidence,
                "archetype_metadata": json.dumps(profile.archetype_metadata),
                "emotional_landscape": json.dumps(emotional_landscape_data),
                "top_themes": json.dumps(top_themes_data),
                "recent_symbols": json.dumps(profile.recent_symbols),
                "calculation_version": profile.calculation_version,
                "last_calculated_at": profile.last_calculated_at,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
        )
        await session.commit()
        return profile
    
    async def update_user_profile(self, profile: UserProfile, session: AsyncSession) -> UserProfile:
        """Update an existing user profile."""
        # Serialize complex types
        emotional_landscape_data = [
            {"name": m.name, "intensity": m.intensity, "color": m.color}
            for m in profile.emotional_landscape
        ]
        
        top_themes_data = [
            {"name": t.name, "percentage": t.percentage}
            for t in profile.top_themes
        ]
        
        await session.execute(
            text("""
                UPDATE user_profiles 
                SET archetype = :archetype,
                    archetype_confidence = :archetype_confidence,
                    archetype_metadata = :archetype_metadata,
                    emotional_landscape = :emotional_landscape,
                    top_themes = :top_themes,
                    recent_symbols = :recent_symbols,
                    calculation_version = :calculation_version,
                    last_calculated_at = :last_calculated_at,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {
                "id": profile.id,
                "archetype": profile.archetype,
                "archetype_confidence": profile.archetype_confidence,
                "archetype_metadata": json.dumps(profile.archetype_metadata),
                "emotional_landscape": json.dumps(emotional_landscape_data),
                "top_themes": json.dumps(top_themes_data),
                "recent_symbols": json.dumps(profile.recent_symbols),
                "calculation_version": profile.calculation_version,
                "last_calculated_at": profile.last_calculated_at,
            }
        )
        await session.commit()
        return profile
    
    async def get_or_create_user_profile(self, user_id: UUID, session: AsyncSession) -> UserProfile:
        """Get existing user profile or create a new one."""
        profile = await self.get_user_profile(user_id, session)
        if profile:
            return profile
        
        # Create new profile
        new_profile = UserProfile(
            id=uuid4(),
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        return await self.create_user_profile(new_profile, session)