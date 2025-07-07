from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from new_backend_ruminate.infrastructure.db.meta import Base

class Segment(Base):
    __tablename__ = "segments"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id  = Column(UUID(as_uuid=True), nullable=True, index=True)
    dream_id = Column(UUID(as_uuid=True), ForeignKey("dreams.id", ondelete="CASCADE"), index=True)
    modality = Column(String(10), nullable=False)  # "audio" or "text" - no default to avoid silent bugs
    filename = Column(String(255), nullable=True)  # Required for audio, null for text
    duration = Column(Float, nullable=True)  # Required for audio, null for text
    order    = Column(Integer, nullable=False)
    s3_key   = Column(String(512), nullable=True)  # Required for audio, null for text
    transcript = Column(Text, nullable=True)
    transcription_status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed

    dream    = relationship("Dream", back_populates="segments")
    
    __table_args__ = (
        # Composite index for ordered segment retrieval
        Index('ix_segments_dream_order', 'dream_id', 'order'),
    )