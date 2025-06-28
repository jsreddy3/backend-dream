# new_backend/domain/models/message.py

from __future__ import annotations
from datetime import datetime
from enum import Enum
from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates

from sqlalchemy import (
    Column, DateTime, Enum as SAEnum, ForeignKey,
    Integer, Text, JSON, UniqueConstraint, Index, desc
)
from new_backend_ruminate.infrastructure.db.meta import Base


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(Base):                               # pure ORM, no Pydantic
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("parent_id", "version", name="uq_parent_version"),
        Index("ix_conv_parent", "conversation_id", "parent_id"),
        Index("ix_parent_version_desc", "parent_id", desc("version")),
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), index=True)
    parent_id       = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True, index=True)
    version         = Column(Integer, nullable=True)
    role            = Column(SAEnum(Role), nullable=False)
    content         = Column(Text, default="")
    meta_data       = Column(JSON, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    active_child_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    @validates("meta_data")
    def _as_dict(self, _, val):
        return {} if val in ("", None) else val
