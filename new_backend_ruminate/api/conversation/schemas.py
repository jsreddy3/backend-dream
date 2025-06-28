# new_backend_ruminate/api/conversation/schema.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─────────────────────────────── Enums ──────────────────────────────── #

class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ─────────────────────── Transport-layer DTOs ───────────────────────── #

# --- requests --------------------------------------------------------- #
class SendMessageRequest(BaseModel):
    """
    Body for both
        • POST /conversations/{cid}/messages
        • PUT  /conversations/{cid}/messages/{mid}/edit_streaming
    """
    content: str
    parent_id: Optional[UUID] = None


# --- responses -------------------------------------------------------- #
class MessageIdsResponse(BaseModel):
    """
    What the create / edit endpoints return: the freshly‐created user
    message id and the assistant placeholder id that will stream chunks.
    """
    user_msg_id: UUID = Field(..., alias="user_id")
    ai_msg_id:   UUID = Field(..., alias="ai_id")

    class Config:
        allow_population_by_field_name = True


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    parent_id: Optional[UUID] = None
    active_child_id: Optional[UUID] = None
    version: int
    role: Role
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    id: UUID
    created_at: datetime
    root_message_id: Optional[UUID] = None
    active_thread_ids: List[UUID] = Field(default_factory=list)
    is_demo: bool = False
    meta_data: Optional[dict] = None

class ConversationInitResponse(BaseModel):
    conversation_id: str = Field(..., alias="conversation_id")
    system_msg_id:   str = Field(..., alias="system_msg_id")