from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from uuid import uuid4
from new_backend_ruminate.infrastructure.db.meta import Base

class Device(Base):
    __tablename__ = "devices"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    token      = Column(String(400), nullable=False)
    sandbox    = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")