# new_backend_ruminate/context/renderers/agent.py

from __future__ import annotations
import json, textwrap
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.context.registry import (
    register_renderer,
    register_retriever,
    retriever_registry,
)

_TRUNC = 1024


class _DefaultToolResultRetriever:
    async def fetch(self, ref: str, *, session: AsyncSession) -> str:
        return textwrap.shorten(ref, _TRUNC, placeholder=" …")
        


register_retriever("tool_result_default", _DefaultToolResultRetriever())


async def _assistant_renderer(
    msg: Message, conv: Conversation, *, session: AsyncSession
) -> str:
    meta = msg.meta_data if isinstance(msg.meta_data, dict) else {}
    tc   = meta.get("tool_call")
    if tc:
        name = tc.get("name", "tool")
        args = json.dumps(tc.get("arguments", {}), ensure_ascii=False)
        return f"<thought> call {name} with {args}"
    return msg.content


async def _tool_renderer(
    msg: Message, conv: Conversation, *, session: AsyncSession
) -> str:
    retriever = retriever_registry["tool_result_default"]
    snippet = await retriever.fetch(msg.content, session=session)
    return f"<tool_result[{msg.parent_id}]> {snippet}"


async def _user_renderer(
    msg: Message, conv: Conversation, *, session: AsyncSession
) -> str:
    return msg.content


def register_agent_renderers() -> None:
    register_renderer("agent.assistant", _assistant_renderer)
    register_renderer("agent.tool", _tool_renderer)
    register_renderer("agent.user", _user_renderer)
