# tests/agent/test_loop_decision.py
import pytest, asyncio, json
from new_backend_ruminate.services.agent.service import AgentService, _AGENT_SCHEMA
from new_backend_ruminate.domain.ports.llm import LLMService
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.infrastructure.implementations.conversation.rds_conversation_repository import RDSConversationRepository
from new_backend_ruminate.context.builder import ContextBuilder
from new_backend_ruminate.domain.conversation.entities.message import Message
from typing import AsyncGenerator, List, Dict
from new_backend_ruminate.domain.conversation.entities.message import Role
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation, ConversationType

class OneShotLLM(LLMService):
    async def generate_structured_response(self, messages, *, response_format, json_schema=None):
        # first request returns tool call, second returns answer
        if not hasattr(self,"_hit"): self._hit=False
        self._hit=not self._hit
        return {"thought":"x","response_type":"answer","answer":"done"} if self._hit \
            else {"thought":"t","response_type":"action","action":{"name":"echo","arguments":{"text":"t"}}}

    async def generate_response_stream(self,messages)->AsyncGenerator[str,None]:
        yield "never "

@pytest.mark.asyncio
async def test_loop_minimal(db_session):
    repo,hub=RDSConversationRepository(),EventStreamHub()
    svc=AgentService(repo,OneShotLLM(),hub,ContextBuilder())
    conv=Conversation(type=ConversationType.AGENT); db_session.add(conv); await db_session.commit()
    uid,pid=await svc.send_agent_message(conv_id=conv.id,user_content="hi",parent_id=None)
    await asyncio.sleep(0)          # allow background task to run one loop
