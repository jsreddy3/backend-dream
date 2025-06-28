# new_backend_ruminate/context/builder.py

from __future__ import annotations
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.conversation.entities.message import Message
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.context.registry import renderer_registry, ensure_default

class ContextBuilder:
    async def build(self, conv, thread, *, session):
        out: list[dict[str, str]] = []
        for msg in thread:
            conv_key = (conv.type.value if hasattr(conv.type, "value") else conv.type).lower()
            role_key = (msg.role.value if hasattr(msg.role, "value") else msg.role).lower()
            key = f"{conv_key}.{role_key}"
            ensure_default(key)
            txt = await renderer_registry[key](msg, conv, session=session)
            out.append({"role": role_key, "content": txt})
        return out
