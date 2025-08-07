"""User preferences domain entity (SQLAlchemy model)."""
from __future__ import annotations

from datetime import datetime, time, timezone
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, DateTime, Boolean, Time, JSON, ForeignKey
from sqlalchemy.orm import relationship

from new_backend_ruminate.infrastructure.db.meta import Base
from new_backend_ruminate.domain.user.entities import User


class UserPreferences(Base):
    """User preferences collected during onboarding and updated over time."""
    
    __tablename__ = "user_preferences"
    
    # Primary key and relationships
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    
    # Sleep patterns
    typical_bedtime = Column(Time, nullable=True)
    typical_wake_time = Column(Time, nullable=True)
    sleep_quality = Column(String(20), nullable=True)  # poor/fair/good/excellent
    
    # Dream patterns
    dream_recall_frequency = Column(String(20), nullable=True)  # never/rarely/sometimes/often/always
    dream_vividness = Column(String(20), nullable=True)  # vague/moderate/vivid/very_vivid
    common_dream_themes = Column(JSON, default=list, nullable=False)  # ["flying", "family", "work", etc]
    
    # Goals & interests
    primary_goal = Column(String(50), nullable=True)  # self_discovery/creativity/problem_solving/emotional_healing
    interests = Column(JSON, default=list, nullable=False)  # ["lucid_dreaming", "symbolism", "emotional_processing"]
    
    # Notifications
    reminder_enabled = Column(Boolean, default=True, nullable=False)
    reminder_time = Column(Time, nullable=True)
    reminder_frequency = Column(String(20), default='daily', nullable=False)  # daily/weekly/custom
    reminder_days = Column(JSON, default=list, nullable=False)  # ["monday", "tuesday", etc] for custom frequency
    
    # Personalization
    initial_archetype = Column(String(50), nullable=True)  # Set during onboarding based on answers
    personality_traits = Column(JSON, default=dict, nullable=False)  # For AI prompt customization
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    
    # Onboarding journey tracking
    onboarding_journey = Column(JSON, default=None, nullable=True)  # Complete onboarding interaction data
    
    # Psychological profile data (extracted from onboarding for quick access)
    horoscope_data = Column(JSON, nullable=True)  # {sign: "Leo", moon: "Cancer", rising: "Virgo", traits: [...]}
    mbti_type = Column(String(4), nullable=True)  # "INTJ", "ENFP", etc.
    ocean_scores = Column(JSON, nullable=True)  # {openness: 0.8, conscientiousness: 0.6, ...}
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), nullable=False)
    
    # Relationship to user
    user = relationship(User, backref="preferences", uselist=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "typical_bedtime": self.typical_bedtime.isoformat() if self.typical_bedtime else None,
            "typical_wake_time": self.typical_wake_time.isoformat() if self.typical_wake_time else None,
            "sleep_quality": self.sleep_quality,
            "dream_recall_frequency": self.dream_recall_frequency,
            "dream_vividness": self.dream_vividness,
            "common_dream_themes": self.common_dream_themes,
            "primary_goal": self.primary_goal,
            "interests": self.interests,
            "reminder_enabled": self.reminder_enabled,
            "reminder_time": self.reminder_time.isoformat() if self.reminder_time else None,
            "reminder_frequency": self.reminder_frequency,
            "reminder_days": self.reminder_days,
            "initial_archetype": self.initial_archetype,
            "personality_traits": self.personality_traits,
            "onboarding_completed": self.onboarding_completed,
            "onboarding_journey": self.onboarding_journey,
            "horoscope_data": self.horoscope_data,
            "mbti_type": self.mbti_type,
            "ocean_scores": self.ocean_scores,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }