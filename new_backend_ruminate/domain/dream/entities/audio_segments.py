from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from new_backend_ruminate.infrastructure.db.meta import Base

class AudioSegment(Base):
    __tablename__ = "segments"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id  = Column(UUID(as_uuid=True), nullable=True)
    dream_id = Column(UUID(as_uuid=True), ForeignKey("dreams.id", ondelete="CASCADE"))
    filename = Column(String(255), nullable=True)
    duration = Column(Float, nullable=False)  # seconds
    order    = Column(Integer, nullable=False)
    s3_key   = Column(String(512), nullable=False)
    transcript = Column(Text, nullable=True)

    dream    = relationship("Dream", back_populates="segments")