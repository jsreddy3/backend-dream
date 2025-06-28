from __future__ import annotations
import asyncio, json
from typing import Dict, List
from uuid import UUID, uuid4

from new_backend_ruminate.domain.conversation.entities.message import Message, Role
from new_backend_ruminate.domain.conversation.repo import ConversationRepository
from new_backend_ruminate.domain.ports.llm import LLMService
from new_backend_ruminate.domain.ports.tool import tool_registry
from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.context.builder import ContextBuilder

_MAX_STEPS = 6

_AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "response_type": {"enum": ["action", "answer"]},
        "action":     {"type": "object"},
        "arguments":  {"type": "object"},
        "answer":     {"type": "string"},
    },
    "required": ["thought", "response_type"],
}

class AgentService:
    def __init__(
        self,
        repo: ConversationRepository,
        llm:  LLMService,
        hub:  EventStreamHub,
        builder: ContextBuilder,
    ) -> None:
        self._repo, self._llm, self._hub, self._builder = repo, llm, hub, builder

    # ───────────────────────── API entry ───────────────────────── #

    async def send_agent_message(
        self, *, conv_id: UUID, user_content: str, parent_id: UUID | None
    ) -> tuple[UUID, UUID]:
        user_id, placeholder_id = await self._write_user_and_placeholder(
            conv_id, user_content, parent_id
        )
        prompt = await self._initial_prompt(conv_id, user_id)
        asyncio.create_task(self._loop(conv_id, placeholder_id, prompt))
        return user_id, placeholder_id

    # ────────────────────── helpers (unchanged) ─────────────────── #

    async def _write_user_and_placeholder(self, cid: UUID, content: str, parent: UUID | None):
        async with session_scope() as s:
            u = Message(id=uuid4(), conversation_id=cid, parent_id=parent,
                        role=Role.USER, content=content, version=0)
            p = Message(id=uuid4(), conversation_id=cid, parent_id=u.id,
                        role=Role.ASSISTANT, content="", version=0)
            await self._repo.add_message(u, s)
            await self._repo.add_message(p, s)
            if parent:
                await self._repo.set_active_child(parent, u.id, s)
            await self._repo.set_active_child(u.id, p.id, s)
            base = await self._repo.latest_thread(cid, s)
            await self._repo.update_active_thread(
                cid, [m.id for m in base] + [u.id, p.id], s
            )
        return u.id, p.id

    async def _initial_prompt(self, cid: UUID, user_id: UUID):
        async with session_scope() as s:
            conv  = await self._repo.get(cid, s)
            base  = await self._repo.latest_thread(cid, s)

            user = next((m for m in base if m.id == user_id), None)
            if user is None:                                   # off‐path branch
                user = await s.get(Message, user_id)           # guaranteed to exist

            return await self._builder.build(conv, base + [user], session=s)

    # ───────────────────────── agent loop ───────────────────────── #

    async def _loop(
        self,
        cid: UUID,
        ph_id: UUID,
        messages: List[Dict[str, str]],
    ) -> None:
        for _ in range(_MAX_STEPS):
            step = await self._llm.generate_structured_response(
                messages,
                response_format={"type": "json_object"},
                json_schema=_AGENT_SCHEMA,
            )

            # stream the thought AFTER we have the full JSON
            await self._hub.publish(ph_id, step["thought"] + "\n")

            if step["response_type"] == "answer":
                await self._stream_answer(ph_id, step["answer"])
                await self._finalise(ph_id, step["answer"])
                return

            # ───── tool branch ─────
            name  = step["action"]["name"]
            args  = step["action"]["arguments"]
            tool  = tool_registry[name]

            async with session_scope() as s:
                result = await tool.run(session=s, **args)

                call_msg = Message(
                    conversation_id=cid,
                    parent_id=ph_id,
                    role=Role.ASSISTANT,
                    content=step["thought"],
                    meta_data={"tool_call": step["action"]},
                )
                res_msg = Message(
                    conversation_id=cid,
                    parent_id=call_msg.id,
                    role=Role.TOOL,
                    content=result,
                )
                await self._repo.add_message(call_msg, s)
                await self._repo.add_message(res_msg,  s)

            # stream deterministic tool markers
            await self._hub.publish(ph_id, f"[call] {name}\n")
            await self._hub.publish(ph_id, f"[result] {result[:120]}…\n")

            # enqueue for next prompt
            messages.extend([
                {"role": "assistant", "name": name,
                 "content": None, "tool_call": step["action"]},
                {"role": "tool", "content": result},
            ])

        await self._finalise(ph_id, "I could not complete the task in time.")

        # ────────────────── public edit API ────────────────── #

    async def edit_agent_message(
        self,
        *,
        conv_id: UUID,
        msg_id: UUID,
        new_content: str,
    ) -> tuple[UUID, UUID]:
        """
        Creates a sibling version of `msg_id`, inserts a fresh assistant
        placeholder, rewires the active thread to the new branch, then
        restarts the agent loop from that point.

        Returns (edited_user_id, new_placeholder_id).
        """
        from uuid import uuid4

        async with session_scope() as s:
            # 1 ─ duplicate the user turn (repo auto-increments version)
            sibling, sib_id = await self._repo.edit_message(msg_id, new_content, s)

            # 2 ─ new placeholder under that sibling
            ph_id = str(uuid4())
            ph_row = Message(
                id=ph_id,
                conversation_id=conv_id,
                parent_id=sib_id,
                role=Role.ASSISTANT,
                content="",
            )
            await self._repo.add_message(ph_row, s)

            # 3 ─ truncate current active thread at parent, graft new branch
            prior = await self._repo.latest_thread(conv_id, s)
            try:
                cut = [m.id for m in prior].index(sibling.parent_id) + 1
            except ValueError:                                    # edited root?
                cut = len(prior)
            new_thread = [m.id for m in prior[:cut]] + [sib_id, ph_id]
            await self._repo.update_active_thread(conv_id, new_thread, s)

            # 4 ─ build prompt up to edited user message
            conv  = await self._repo.get(conv_id, s)
            prompt = await self._builder.build(
                conv, prior[:cut] + [sibling], session=s
            )

        # 5 ─ kick off a fresh agent loop in background
        asyncio.create_task(self._loop(conv_id, ph_id, prompt))

        return sib_id, ph_id


    # ───────────────────── utility helpers ─────────────────────── #

    async def _stream_answer(self, ph_id: UUID, text: str):
        for tok in text.split():
            await self._hub.publish(ph_id, tok + " ")
        await self._hub.terminate(ph_id)

    async def _finalise(self, mid: UUID, text: str):
        async with session_scope() as s:
            await self._repo.update_message_content(mid, text, s)
