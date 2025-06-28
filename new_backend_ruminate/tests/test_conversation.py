# tests/test_conversation.py
import asyncio
import pytest
import pytest_asyncio
from fastapi import BackgroundTasks

from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.domain.conversation.entities.message import Message 
from new_backend_ruminate.domain.conversation.entities.message import Role
import logging
from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
from new_backend_ruminate.tests.stubs import StubLLM, StubContextBuilder

logger = logging.getLogger(__name__)

async def collect_chunks(gen):
    buf = []
    async for c in gen:
        buf.append(c)
    return buf


@pytest_asyncio.fixture
async def svc():
    repo = RDSConversationRepository()
    llm  = StubLLM()
    hub  = EventStreamHub()
    ctx_builder = StubContextBuilder()
    return ConversationService(repo, llm, hub, ctx_builder)

@pytest.mark.asyncio
async def test_send_message_streams_and_commits(db_session, svc):
    conv = Conversation(id="c1")
    db_session.add(conv)
    await db_session.commit()

    bg = BackgroundTasks()
    user_id, ai_id = await svc.send_message(
        background=bg,
        conv_id=conv.id,
        user_content="hello",
        parent_id=None,
    )

    # 1 ─ register the stream and start consuming it right away
    consumer = svc._hub.register_consumer(ai_id)

    async def _drain(gen):
        chunks = []
        async for c in gen:
            chunks.append(c)
        return chunks

    collector = asyncio.create_task(_drain(consumer))
    await asyncio.sleep(0)

    # 2 ─ now drive the background task synchronously
    logger.info("driving background task")
    for task in bg.tasks:                       # only one in current design
        await task.func(*task.args, **task.kwargs)

    # 3 ─ wait for the collector to finish
    chunks = await collector

    # 4 ─ verify persistence and stream order
    ai_row = await db_session.get(Message, ai_id)
    assert ai_row.content == "foo bar"
    assert chunks == ["foo ", "bar"]

@pytest.mark.asyncio
async def test_edit_message_creates_branch_and_streams(db_session, svc):
    # conversation with explicit root system message
    conv = Conversation(id="c2")
    db_session.add(conv)

    root = Message(conversation_id=conv.id, role=Role.SYSTEM, content="root")
    db_session.add(root)
    await db_session.commit()

    # first user/assistant via service
    bg1 = BackgroundTasks()
    user_id, _ = await svc.send_message(
        background=bg1,
        conv_id=conv.id,
        user_content="hello",
        parent_id=root.id,
    )
    for task in bg1.tasks:
        await task.func(*task.args, **task.kwargs)

    # edit the user turn
    bg2 = BackgroundTasks()
    edited_id, ai2_id = await svc.edit_message_streaming(
        background=bg2,
        conv_id=conv.id,
        msg_id=user_id,
        new_content="hello – edited",
    )

    consumer = svc._hub.register_consumer(ai2_id)
    collector = asyncio.create_task(collect_chunks(consumer))
    await asyncio.sleep(0)

    for task in bg2.tasks:
        await task.func(*task.args, **task.kwargs)
    chunks = await collector

    new_ai = await db_session.get(Message, ai2_id)
    assert new_ai.content == "foo bar"
    assert chunks == ["foo ", "bar"]

    latest = await svc.get_latest_thread(conv.id, db_session)
    assert [m.id for m in latest][-2:] == [edited_id, ai2_id]


@pytest.mark.asyncio
async def test_message_versions_sorted(db_session, svc):
    conv = Conversation(id="c3")
    db_session.add(conv)

    base = Message(conversation_id=conv.id, role=Role.USER, content="q?", version=None)
    db_session.add(base)
    await db_session.flush()                       # materialise base.id

    v1 = Message(conversation_id=conv.id, parent_id=base.id,
                 role=Role.USER, content="v1", version=1)
    v2 = Message(conversation_id=conv.id, parent_id=base.id,
                 role=Role.USER, content="v2", version=2)
    db_session.add_all([v1, v2])
    await db_session.commit()

    versions = await svc.get_versions(v2.id, db_session)
    assert [m.version for m in versions] == [1, 2]

@pytest.mark.asyncio
async def test_create_conversation(db_session, svc):
    conv_id, root_id = await svc.create_conversation()

    # rows exist
    conv = await db_session.get(Conversation, conv_id)
    root = await db_session.get(Message, root_id)

    assert conv.root_message_id == root_id
    assert conv.active_thread_ids == [root_id]
    assert root.role is Role.SYSTEM
    assert root.content == "You are a helpful assistant."
