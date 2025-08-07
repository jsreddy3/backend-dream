"""Daily check-in domain entity."""
from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, DateTime, String, Text, JSON, ForeignKey, Integer
from sqlalchemy.orm import relationship

from new_backend_ruminate.infrastructure.db.meta import Base


class InsightStatus(str, Enum):
    """Status for insight generation."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DailyCheckIn(Base):
    """User's daily check-in for subconscious insights."""
    
    __tablename__ = "daily_checkins"
    
    # Primary key and relationships
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Input from user
    checkin_text = Column(Text, nullable=False)
    mood_scores = Column(JSON, nullable=True)  # Optional: {happy: 0.7, anxious: 0.3, etc}
    
    # Generated insight
    insight_text = Column(Text, nullable=True)
    insight_status = Column(String(20), default=InsightStatus.PENDING.value, nullable=False)
    insight_generated_at = Column(DateTime, nullable=True)
    
    # Extensibility and tracking
    insight_type = Column(String(50), default='subconscious', nullable=False)  # For future: weekly, moon_phase, etc
    insight_version = Column(Integer, default=1, nullable=False)
    context_metadata = Column(JSON, nullable=True)  # Track what dreams/data were used
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)