import pytest, asyncio
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import (
    RDSConversationRepository,
)
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.context.builder import ContextBuilder
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.ports.llm import LLMService

# ───────────────────────── stub LLM ───────────────────────── #

class SilentLLM(LLMService):
    async def generate_response_stream(self, messages):
        yield ""                               # one empty chunk ⇒ placeholder patched to ""
    async def generate_structured_response(self, *_, **__):
        return {"thought":"t","response_type":"action",
                "action":{"name":"echo","arguments":{"text":"hi"}}}

# ────────────────────── helpers / fixtures ─────────────────── #

async def run_background(bg: BackgroundTasks):
    """Execute every queued task immediately."""
    for task in bg.tasks:
        await task.func(*task.args, **task.kwargs)

@pytest.fixture
def chat_stack():
    repo   = RDSConversationRepository()
    hub    = EventStreamHub()
    llm    = SilentLLM()
    ctx    = ContextBuilder()
    svc    = ConversationService(repo, llm, hub, ctx)
    return repo, svc

# ───────────────────────── tests ──────────────────────────── #

@pytest.mark.asyncio
async def test_edit_branch_creates_new_path(chat_stack, db_session: AsyncSession):
    repo, svc = chat_stack
    cid, root = await svc.create_conversation()

    # root → user0 → ai0
    bg = BackgroundTasks()
    u0, ai0 = await svc.send_message(
        background=bg, conv_id=cid, user_content="hi", parent_id=root
    )
    await run_background(bg)

    # branch off user0
    bg = BackgroundTasks()
    sib, ai1 = await svc.edit_message_streaming(
        background=bg, conv_id=cid, msg_id=u0, new_content="hi edited"
    )
    await run_background(bg)

    latest = await repo.latest_thread(cid, db_session)
    assert latest[-2].id == sib and latest[-1].id == ai1

    versions = await repo.message_versions(sib, db_session)
    assert [m.version for m in versions] == [0, 1]

@pytest.mark.asyncio
async def test_continue_every_branch(chat_stack, db_session: AsyncSession):
    repo, svc = chat_stack
    cid, root = await svc.create_conversation()

    # create original path
    bg = BackgroundTasks()
    u0, ai0 = await svc.send_message(
        background=bg, conv_id=cid, user_content="Q", parent_id=root
    )
    await run_background(bg)

    # two edits → sib1, sib2
    for txt in ("Q v2", "Q v3"):
        bg = BackgroundTasks()
        sib, ai = await svc.edit_message_streaming(
            background=bg, conv_id=cid, msg_id=u0, new_content=txt
        )
        await run_background(bg)

    # follow each assistant leaf
    for parent in (ai0, ai):
        bg = BackgroundTasks()
        await svc.send_message(
            background=bg,
            conv_id=cid,
            user_content=f"follow-up under {parent[:4]}",
            parent_id=parent,
        )
        await run_background(bg)

    latest = await repo.latest_thread(cid, db_session)
    # last branch we touched is the active one
    assert latest[-1].role.lower() in (Role.ASSISTANT.value, Role.USER.value)

@pytest.mark.asyncio
async def test_double_edit_same_node(chat_stack, db_session: AsyncSession):
    repo, svc = chat_stack
    cid, root = await svc.create_conversation()

    bg = BackgroundTasks()
    uid, _ = await svc.send_message(
        background=bg, conv_id=cid, user_content="first", parent_id=root
    )
    await run_background(bg)

    # edit same node twice
    for txt in ("first v2", "first v3"):
        bg = BackgroundTasks()
        sib, _ = await svc.edit_message_streaming(
            background=bg, conv_id=cid, msg_id=uid, new_content=txt
        )
        await run_background(bg)

    root_row = await db_session.get(Message, root)
    assert root_row.active_child_id == sib               # newest edit active

    versions = await repo.message_versions(sib, db_session)
    assert [m.version for m in versions] == [0, 1, 2]
