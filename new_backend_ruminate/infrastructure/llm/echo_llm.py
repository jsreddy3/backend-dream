# new_backend_ruminate/infrastructure/llm/echo_llm.py

from __future__ import annotations
from typing import AsyncGenerator, List

from new_backend_ruminate.domain.conversation.entities.message import Message
from new_backend_ruminate.domain.ports.llm import LLMService


class EchoLLM(LLMService):
    async def generate_response_stream(
        self, messages: List[Message]
    ) -> AsyncGenerator[str, None]:
        user_text = messages[-1].content if messages else "(empty)"
        for token in user_text.split():
            yield token + " "
    
    async def generate_structured_response(self, messages, *, response_format, json_schema=None):
        return {"thought": "echoing", "response_type": "answer",
                "answer": "stub answer"}