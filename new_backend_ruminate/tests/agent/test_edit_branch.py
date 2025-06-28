# tests/agent/test_edit_branch.py
import asyncio, pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.context.builder import ContextBuilder
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.services.agent.service import AgentService
from new_backend_ruminate.domain.ports.llm import LLMService
import new_backend_ruminate.infrastructure.tools.echo_tool          # registers "echo"

# ───────── stub LLM ───────── #

class TwoTurnLLM(LLMService):
    def __init__(self): self._hit = False
    async def generate_structured_response(self, *_, **__):
        if not self._hit:
            self._hit = True
            return {"thought":"t","response_type":"action",
                    "action":{"name":"echo","arguments":{"text":"hi"}}}
        return {"thought":"done","response_type":"answer","answer":"hi"}
    async def generate_response_stream(self,*a,**k): yield "unused "

# ───────── helpers ───────── #

async def drain_background():
    await asyncio.gather(
        *[t for t in asyncio.all_tasks() if t is not asyncio.current_task()],
        return_exceptions=True,
    )

# ───────── tests ───────── #

@pytest.mark.asyncio
async def test_edit_branch_creates_new_path(db_session: AsyncSession):
    repo, hub, llm, b = RDSConversationRepository(), EventStreamHub(), TwoTurnLLM(), ContextBuilder()
    chat  = ConversationService(repo, llm, hub, b)
    agent = AgentService(repo, llm, hub, b)

    cid, root_id = await chat.create_conversation(conv_type="agent")

    # original user + loop
    u0, ph0 = await agent.send_agent_message(conv_id=cid, user_content="hi", parent_id=root_id)
    await drain_background()

    # branch: edit the user turn
    sib_id, ph1 = await agent.edit_agent_message(conv_id=cid, msg_id=u0, new_content="hi – edited")
    await drain_background()

    # active thread ends with new placeholder patched to "hi"
    db_session.expire_all()
    latest = await repo.latest_thread(cid, db_session)
    assert latest[-1].id == ph1 and latest[-1].content == "hi"

    # confirm sibling version number = 2
    versions = await repo.message_versions(sib_id, db_session)
    assert [m.version for m in versions] == [0, 1]

@pytest.mark.asyncio
async def test_continue_old_branch(db_session: AsyncSession):
    repo, hub, llm, b = RDSConversationRepository(), EventStreamHub(), TwoTurnLLM(), ContextBuilder()
    chat  = ConversationService(repo, llm, hub, b)
    agent = AgentService(repo, llm, hub, b)

    cid, root_id = await chat.create_conversation(conv_type="agent")
    u0, ph0 = await agent.send_agent_message(conv_id=cid, user_content="hi", parent_id=root_id)
    await drain_background()

    # branch off
    sib, ph1 = await agent.edit_agent_message(conv_id=cid, msg_id=u0, new_content="hi – edited")
    await drain_background()

    # now extend the *original* branch (parent = u0)
    u2, ph2 = await agent.send_agent_message(conv_id=cid, user_content="follow-up", parent_id=ph0)
    await drain_background()

    latest = await repo.latest_thread(cid, db_session)
    assert latest[-1].id == ph2                      # active thread followed old branch
    assert latest[-2].id == u2

@pytest.mark.asyncio
async def test_edit_root_level_user(db_session: AsyncSession):
    repo, hub, llm, b = RDSConversationRepository(), EventStreamHub(), TwoTurnLLM(), ContextBuilder()
    chat  = ConversationService(repo, llm, hub, b)
    agent = AgentService(repo, llm, hub, b)

    cid, _ = await chat.create_conversation(conv_type="agent")

    # first user turn is root (parent_id=None)
    u0, ph0 = await agent.send_agent_message(conv_id=cid, user_content="root Q", parent_id=None)
    await drain_background()

    # edit that root message
    sib, ph1 = await agent.edit_agent_message(conv_id=cid, msg_id=u0, new_content="root Q – edited")
    await drain_background()

    latest = await repo.latest_thread(cid, db_session)
    assert [m.id for m in latest][-2:] == [sib, ph1]
    assert latest[-1].content == "hi"                # answer patched
