# tests/test_create_and_send.py
import pytest
import pytest_asyncio
import asyncio
from fastapi import BackgroundTasks

from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.tests.stubs import StubLLM, StubContextBuilder
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub


@pytest_asyncio.fixture
async def svc():
    repo = RDSConversationRepository()
    llm  = StubLLM()
    hub  = EventStreamHub()
    ctx_builder = StubContextBuilder()
    return ConversationService(repo, llm, hub, ctx_builder)


@pytest.mark.asyncio
async def test_create_conversation_sets_root_and_thread(db_session, svc):
    conv_id, root_id = await svc.create_conversation()

    conv = await db_session.get(Conversation, conv_id)
    root = await db_session.get(Message, root_id)

    assert conv.root_message_id == root_id
    assert conv.active_thread_ids == [root_id]
    assert root.role is Role.SYSTEM
    assert root.content == "You are a helpful assistant."


@pytest.mark.asyncio
async def test_send_message_uses_context_builder(db_session, svc):
    # 1. bootstrap a conversation
    conv_id, root_id = await svc.create_conversation()

    # 2. send a user turn
    bg = BackgroundTasks()
    user_id, ai_id = await svc.send_message(
        background=bg,
        conv_id=conv_id,
        user_content="hi!",
        parent_id=root_id,
    )

    # 3. drain the background stream synchronously
    for task in bg.tasks:
        await task.func(*task.args, **task.kwargs)

    # 4. assert that the StubContextBuilder produced the prompt
    assert svc._ctx_builder.last_prompt is not None
    # and that the stub LLM rendered “foo bar” into the placeholder row
    ai_row = await db_session.get(Message, ai_id)
    assert ai_row.content == "foo bar"
