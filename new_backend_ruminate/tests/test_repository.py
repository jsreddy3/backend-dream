import pytest, asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository

@pytest.mark.asyncio
async def test_latest_thread_linear(db_session: AsyncSession):
    repo = RDSConversationRepository()
    conv = Conversation(id="t1")
    db_session.add(conv)
    a = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.SYSTEM, content="root")  # root
    b = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.USER, parent_id=a.id, version=1)
    c = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.ASSISTANT, parent_id=b.id)
    db_session.add_all([a, b, c])
    await db_session.commit()

    latest = await repo.latest_thread(conv.id, db_session)
    assert [m.id for m in latest] == [a.id, b.id, c.id]

@pytest.mark.asyncio
async def test_latest_thread_branching_and_active_child(db_session: AsyncSession):
    repo = RDSConversationRepository()
    conv = Conversation(id="t2")
    db_session.add(conv)
    root = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.SYSTEM, content="root", version=0)
    u1   = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.USER, parent_id=root.id, version=1)
    a1   = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.ASSISTANT, parent_id=u1.id, version=1)
    # branch on u1
    u2   = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.USER,
                   parent_id=root.id, version=2, content="alt")
    db_session.add_all([root, u1, a1, u2])
    await db_session.flush()
    # flip pointer root → u2
    await repo.set_active_child(u1.id, a1.id, db_session)
    await repo.set_active_child(root.id, u2.id, db_session)
    await db_session.commit()

    latest = await repo.latest_thread(conv.id, db_session)
    assert [m.id for m in latest] == [root.id, u2.id]

@pytest.mark.asyncio
async def test_message_versions_root_and_children(db_session):
    repo = RDSConversationRepository()
    conv = Conversation(id="t3")
    db_session.add(conv)
    root = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.SYSTEM, content="root", version=0)
    v1   = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.USER, parent_id=root.id, version=1)
    v2   = Message(id=str(uuid4()), conversation_id=conv.id, role=Role.USER, parent_id=root.id, version=2)
    db_session.add_all([root, v1, v2]); await db_session.commit()

    versions = await repo.message_versions(v2.id, db_session)
    assert [m.version for m in versions] == [1, 2]
    # root is un-versioned, so asking for it yields just itself
    assert await repo.message_versions(root.id, db_session) == [root]
