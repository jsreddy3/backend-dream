# new_backend_ruminate/domain/conversation/entities/conversation.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from new_backend_ruminate.infrastructure.db.meta import Base


class ConversationType(str, Enum):
    CHAT = "chat"                 # extend with more categories whenever you need
    AGENT = "agent"

class Conversation(Base):
    """
    A single threaded or branching conversation.
    No document, page, or block coupling.
    """

    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("id", name="uq_conversation_id"),)

    id: Mapped[PYUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    root_message_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    active_thread_ids: Mapped[list[UUID]] = mapped_column(JSON, default=list)

    type: Mapped[ConversationType] = mapped_column(
        SAEnum(ConversationType), default=ConversationType.CHAT, nullable=False
    )
