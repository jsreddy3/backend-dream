# tests/agent/test_renderers.py
import pytest, json
from new_backend_ruminate.context.renderers.agent import register_agent_renderers
from new_backend_ruminate.context.registry import renderer_registry
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from sqlalchemy.ext.asyncio import AsyncSession

register_agent_renderers()

@pytest.mark.asyncio
async def test_tool_call_renderer(db_session: AsyncSession):
    tc = {"name": "foo", "arguments": {"x": 1}}
    msg = Message(role=Role.ASSISTANT, content="ignored", meta_data={"tool_call": tc})
    txt = await renderer_registry["agent.assistant"](msg, Conversation(type="agent"), session=db_session)
    assert "<thought" in txt and "foo" in txt and "x" in txt

@pytest.mark.asyncio
async def test_tool_result_renderer(db_session: AsyncSession):
    tool = Message(role=Role.TOOL, content="A"*300)      # long body gets truncated
    txt = await renderer_registry["agent.tool"](tool, Conversation(type="agent"), session=db_session)
    assert txt.startswith("<tool_result") and len(txt) < 1050
