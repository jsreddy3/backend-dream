import pytest, asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.context.builder import (
    ContextBuilder
)
from new_backend_ruminate.context.registry import register_retriever, register_renderer, retriever_registry, renderer_registry
from new_backend_ruminate.context.protocols import Retriever
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation

class FakeRetriever(Retriever):
    async def fetch(self, ref, *, session): return f"<<{ref}>>"

@pytest.mark.asyncio
async def test_default_renderer_fallback(db_session: AsyncSession):
    builder = ContextBuilder()
    conv = Conversation(type="chat")
    msg  = Message(role=Role.USER, content="hi")
    out  = await builder.build(conv, [msg], session=db_session)
    assert out == [{"role": "user", "content": "hi"}]

@pytest.mark.asyncio
async def test_custom_renderer_and_retriever(db_session: AsyncSession):
    calls = []
    async def rich_renderer(msg, conv, *, session):
        retr = retriever_registry["f"]
        snippet = await retr.fetch("X", session=session)
        calls.append("renderer")
        return f"{snippet} + {msg.content}"

    register_retriever("f", FakeRetriever())
    register_renderer("chat.user", rich_renderer)

    builder = ContextBuilder()
    conv = Conversation(type="chat")
    msg  = Message(role=Role.USER, content="q?", meta_data={"foo": "bar"})
    out  = await builder.build(conv, [msg], session=db_session)
    assert "renderer" in calls
    assert out[0]["content"] == "<<X>> + q?"
