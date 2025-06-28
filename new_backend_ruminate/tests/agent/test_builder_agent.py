# tests/agent/test_builder_agent.py
import pytest
from new_backend_ruminate.context.builder import ContextBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation, ConversationType

@pytest.mark.asyncio
async def test_builder_with_tool_rows(db_session: AsyncSession):
    conv = Conversation(type=ConversationType.AGENT)
    user = Message(role=Role.USER, content="hi")
    call = Message(role=Role.ASSISTANT, content="", meta_data={"tool_call":{"name":"foo","arguments":{}}})
    tool = Message(role=Role.TOOL, content="result")
    built = await ContextBuilder().build(conv, [user, call, tool], session=db_session)
    assert built[2]["content"].startswith("<tool_result[") and "result" in built[2]["content"]

