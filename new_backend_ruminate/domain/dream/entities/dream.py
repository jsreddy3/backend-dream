from datetime import datetime
from enum import Enum
from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column, DateTime, String, Text, JSON
)
from sqlalchemy.orm import relationship
from new_backend_ruminate.infrastructure.db.meta import Base

class DreamStatus(str, Enum):
    PENDING = "draft"  # Match iOS app expectation
    TRANSCRIBED = "completed"  # Match iOS app expectation  
    VIDEO_READY = "video_generated"  # Match iOS app expectation

class VideoStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Dream(Base):
    __tablename__ = "dreams"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id    = Column(UUID(as_uuid=True), nullable=True)
    transcript = Column(Text, nullable=True)
    state      = Column(String(20), default=DreamStatus.PENDING.value, nullable=False)
    created    = Column(DateTime, default=datetime.utcnow)
    title      = Column(String(255), nullable=True)
    
    # Video generation fields
    video_job_id     = Column(String(255), nullable=True)  # Celery task ID
    video_status     = Column(String(20), nullable=True)  # VideoStatus enum
    video_url        = Column(String(500), nullable=True)  # S3 URL
    video_metadata   = Column(JSON, nullable=True)  # Metadata from pipeline
    video_started_at = Column(DateTime, nullable=True)  # When generation started
    video_completed_at = Column(DateTime, nullable=True)  # When generation completed

    segments  = relationship(
        "AudioSegment",
        back_populates="dream",
        cascade="all, delete-orphan",
        order_by="AudioSegment.order",
    )