from datetime import datetime
from enum import Enum
from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column, DateTime, String, Text, JSON, Index, desc
)
from sqlalchemy.orm import relationship
from new_backend_ruminate.infrastructure.db.meta import Base

class DreamStatus(str, Enum):
    PENDING = "draft"  # Match iOS app expectation
    TRANSCRIBED = "completed"  # Match iOS app expectation  
    VIDEO_READY = "video_generated"  # Match iOS app expectation

class GenerationStatus(str, Enum):
    """Generic status for any async generation task (video, summary, questions, analysis)"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Dream(Base):
    __tablename__ = "dreams"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id    = Column(UUID(as_uuid=True), nullable=True, index=True)
    transcript = Column(Text, nullable=True)
    state      = Column(String(20), default=DreamStatus.PENDING.value, nullable=False, index=True)
    created_at    = Column(DateTime, default=datetime.utcnow, index=True)
    title      = Column(String(255), nullable=True)
    summary    = Column(Text, nullable=True)
    summary_status = Column(String(20), nullable=True)  # GenerationStatus enum
    additional_info = Column(Text, nullable=True)
    
    # Questions fields
    questions_status = Column(String(20), nullable=True)  # GenerationStatus enum
    
    # Analysis fields
    analysis = Column(Text, nullable=True)
    analysis_status = Column(String(20), nullable=True)  # GenerationStatus enum
    analysis_generated_at = Column(DateTime, nullable=True)
    analysis_metadata = Column(JSON, nullable=True)
    
    # Expanded analysis fields
    expanded_analysis = Column(Text, nullable=True)
    expanded_analysis_status = Column(String(20), nullable=True)  # GenerationStatus enum
    expanded_analysis_generated_at = Column(DateTime, nullable=True)
    expanded_analysis_metadata = Column(JSON, nullable=True)
    
    # Video generation fields
    video_job_id     = Column(String(255), nullable=True)  # Celery task ID
    video_status     = Column(String(20), nullable=True)  # GenerationStatus enum
    video_url        = Column(String(500), nullable=True)  # S3 URL
    video_metadata   = Column(JSON, nullable=True)  # Metadata from pipeline
    video_started_at = Column(DateTime, nullable=True)  # When generation started
    video_completed_at = Column(DateTime, nullable=True)  # When generation completed
    
    # Image generation fields
    image_url        = Column(String(500), nullable=True)  # S3 URL
    image_prompt     = Column(Text, nullable=True)  # Generated prompt
    image_generated_at = Column(DateTime, nullable=True)  # When image was generated
    image_status     = Column(String(20), nullable=True)  # GenerationStatus enum
    image_metadata   = Column(JSON, nullable=True)  # Metadata (style, model, etc)

    segments  = relationship(
        "Segment",
        back_populates="dream",
        cascade="all, delete-orphan",
        order_by="Segment.order",
    )
    
    interpretation_questions = relationship(
        "InterpretationQuestion",
        back_populates="dream",
        cascade="all, delete-orphan",
        order_by="InterpretationQuestion.question_order",
    )
    
    __table_args__ = (
        # Composite index for the most common query pattern
        Index('ix_dreams_user_created', 'user_id', desc('created_at')),
    )