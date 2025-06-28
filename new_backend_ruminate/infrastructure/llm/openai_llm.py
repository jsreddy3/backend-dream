from __future__ import annotations
import json, os
from typing import Any, AsyncGenerator, Dict, List, Union

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

from new_backend_ruminate.domain.conversation.entities.message import Message
from new_backend_ruminate.domain.ports.llm import LLMService


class OpenAILLM(LLMService):
    """Async wrapper around /v1/chat/completions that also understands function-calling."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self._model  = model

    async def _normalise(
        self, msgs: List[Union[Message, Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for m in msgs:
            if isinstance(m, Message):
                out.append({"role": m.role, "content": m.content})
            else:
                out.append(m)                          # already dict-shaped
        return out

    async def generate_response_stream(
        self, messages: List[Message]
    ) -> AsyncGenerator[str, None]:
        chat_msgs = await self._normalise(messages)
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=chat_msgs,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def generate_structured_response(
        self,
        messages: List[Union[Message, Dict[str, str]]],
        *,
        response_format: Dict[str, Any],
        json_schema: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        chat_msgs = await self._normalise(messages)
        tools = None
        tool_choice = None

        if json_schema is not None:
            tools = [{
                "type": "function",
                "function": {
                    "name": "output_structure",
                    "description": "Return the answer in the mandated JSON form",
                    "parameters": json_schema,
                },
            }]
            tool_choice = {"type": "function", "function": {"name": "output_structure"}}

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=chat_msgs,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
            stream=False,
        )

        msg: ChatCompletionMessage = resp.choices[0].message
        if msg.tool_calls:
            args = msg.tool_calls[0].function.arguments
            try:
                return json.loads(args)
            except Exception:
                return {"error": "malformed JSON", "raw": args}

        # fall-back for models that reply with plain JSON in content
        try:
            return json.loads(msg.content or "")
        except Exception:
            return {"error": "no structured data", "raw": msg.content}
