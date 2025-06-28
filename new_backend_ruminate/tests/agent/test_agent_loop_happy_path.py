import asyncio, pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.context.builder import ContextBuilder
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.services.agent.service import AgentService
from new_backend_ruminate.domain.ports.llm import LLMService
from new_backend_ruminate.domain.ports.tool import tool_registry
import new_backend_ruminate.infrastructure.tools.echo_tool

# ───────────────────── stub LLM ───────────────────── #

class StubLLM(LLMService):
    def __init__(self): self._turn = 0

    async def generate_response_stream(self, messages):
        # never reached in this test
        yield "unused "

    async def generate_structured_response(
        self, messages, *, response_format, json_schema=None
    ):
        self._turn += 1
        if self._turn == 1:                                            # first round → tool
            return {
                "thought": "let me echo",
                "response_type": "action",
                "action": {"name": "echo", "arguments": {"text": "hi"}},
            }
        return {                                                       # second round → answer
            "thought": "done",
            "response_type": "answer",
            "answer": "hi",
        }

# ─────────────────── test proper ─────────────────── #

@pytest.mark.asyncio
async def test_agent_loop_happy_path(db_session: AsyncSession):
    repo   = RDSConversationRepository()
    hub    = EventStreamHub()
    llm    = StubLLM()
    builder= ContextBuilder()

    chat   = ConversationService(repo, llm, hub, builder)
    agent  = AgentService(repo, llm, hub, builder)

    # 1 ─ create an *agent* conversation (system prompt is hydrated with tools)
    cid, root_id = await chat.create_conversation(conv_type="agent")

    # 2 ─ register a consumer on the yet-to-exist placeholder stream
    stream_chunks = []
    async def _collector(gen):
        async for ch in gen: stream_chunks.append(ch)
    # we'll register after the placeholder id is known

    # 3 ─ send the user's question and start loop
    user_id, ph_id = await agent.send_agent_message(
        conv_id=cid, user_content="hi", parent_id=root_id
    )
    collector_task = asyncio.create_task(_collector(hub.register_consumer(ph_id)))

    # 4 ─ let background coroutine finish
    await asyncio.wait_for(collector_task, timeout=1)

    # wait for the agent loop task to finish as well
    await asyncio.gather(
        *[t for t in asyncio.all_tasks() if t is not asyncio.current_task()],
        return_exceptions=True,
    )

    db_session.expire_all()

    tool_row = (
        await db_session.execute(
            select(Message)
            .where(
                Message.conversation_id == cid,
                Message.role == Role.TOOL,
            )
        )
    ).scalar_one()
    assert tool_row.content == "hi"

    # SSE stream contained thought, call marker, result marker, final answer

    # NOTE: there is a race condition between what appears to be consumer registration and ACTUAL creation
    # this causes, in the test, the first chunk to be lost.
    joined = "".join(stream_chunks)
    assert "[call] echo" in joined
    assert "[result] hi" in joined
    assert joined.strip().endswith("hi")
