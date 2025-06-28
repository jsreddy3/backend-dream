import pytest, asyncio
from fastapi import BackgroundTasks
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.tests.stubs import StubLLM, StubContextBuilder
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation

@pytest.mark.asyncio
async def test_hub_fanout_and_termination(db_session):
    repo = RDSConversationRepository()
    llm  = StubLLM()
    hub  = EventStreamHub()
    builder = StubContextBuilder()
    svc  = ConversationService(repo, llm, hub, builder)

    conv = Conversation(id="fan")
    db_session.add(conv); await db_session.commit()

    bg = BackgroundTasks()
    _, ai_id = await svc.send_message(
        background=bg, conv_id=conv.id, user_content="hi", parent_id=None
    )

    # two independent consumers
    gen1 = hub.register_consumer(ai_id)
    gen2 = hub.register_consumer(ai_id)
    task1 = asyncio.create_task(_collect(gen1))
    task2 = asyncio.create_task(_collect(gen2))
    await asyncio.sleep(0)

    # drive background publishing
    for t in bg.tasks: await t.func(*t.args, **t.kwargs)
    chunks1, chunks2 = await asyncio.gather(task1, task2)
    assert chunks1 == chunks2 == ["foo ", "bar"]

async def _collect(gen):
    buf = []
    async for c in gen: buf.append(c)
    return buf
