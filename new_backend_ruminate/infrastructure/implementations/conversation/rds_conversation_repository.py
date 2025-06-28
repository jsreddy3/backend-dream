# new_backend_ruminate/infrastructure/repositories/rds_conversation_repository.py
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import (
    select,
    update,
    text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from new_backend_ruminate.domain.conversation.entities.message import Message
from new_backend_ruminate.domain.conversation.repo import (
    ConversationRepository,
)

class RDSConversationRepository(ConversationRepository):
    # ─────────────────────────────── creation / reads ───────────────────────────── #

    async def create(self, conv: Conversation, session: AsyncSession) -> Conversation:
        session.add(conv)
        await session.flush()               # let PKs materialise
        return conv

    async def get(self, cid: UUID, session: AsyncSession) -> Optional[Conversation]:
        return await session.get(Conversation, cid)

    async def latest_thread(self, cid: UUID, session: AsyncSession) -> List[Message]:
        dialect: Dialect = session.bind.dialect        # ← runtime dialect

        if getattr(dialect, "supports_distinct_on", False):      # PostgreSQL path
            sql = text(
                """
                WITH RECURSIVE thread AS (
                  SELECT * FROM messages
                  WHERE  conversation_id = :cid AND parent_id IS NULL
                  UNION ALL
                  SELECT m.* FROM messages m
                  JOIN   thread t ON t.active_child_id = m.id
                  WHERE  m.conversation_id = :cid
                  UNION ALL
                  SELECT m.* FROM messages m
                  JOIN   thread t ON t.id = m.parent_id
                  WHERE  m.conversation_id = :cid
                  AND    t.active_child_id IS NULL
                  AND    m.version = (
                         SELECT max(version) FROM messages
                         WHERE parent_id = m.parent_id
                         )
                )
                SELECT * FROM thread ORDER BY created_at;
                """
            )
        else:                                           # SQLite (no DISTINCT ON)
            sql = text(
                """
                WITH RECURSIVE thread AS (
                  SELECT * FROM messages
                  WHERE  conversation_id = :cid AND parent_id IS NULL
                  UNION ALL
                  SELECT m.* FROM messages m
                  JOIN   thread t ON t.active_child_id = m.id
                  WHERE  m.conversation_id = :cid
                  UNION ALL
                  SELECT m.* FROM messages m
                  JOIN   thread t ON t.id = m.parent_id
                  WHERE  m.conversation_id = :cid
                  AND    t.active_child_id IS NULL
                  AND    NOT EXISTS (
                      SELECT 1 FROM messages m2
                      WHERE  m2.parent_id = m.parent_id
                      AND    m2.version   > m.version
                  )
                )
                SELECT * FROM thread ORDER BY created_at;
                """
            )

        rows = (await session.execute(sql, {"cid": cid})).mappings()
        return [Message(**r) for r in rows]

    async def full_tree(self, cid: UUID, session: AsyncSession) -> List[Message]:
        stmt = select(Message).where(Message.conversation_id == cid)
        return list((await session.scalars(stmt)).all())

    async def message_versions(
        self, mid: UUID, session: AsyncSession
    ) -> List[Message]:
        """
        Returns **all** siblings that share the same parent, ordered by version.
        """
        me: Message | None = await session.get(Message, mid)
        if me is None:
            return []

        # root messages (parent_id is NULL) are considered un-versioned
        if me.parent_id is None:
            return [me]

        stmt = (
            select(Message)
            .where(Message.parent_id == me.parent_id)
            .order_by(Message.version)
        )
        return list((await session.scalars(stmt)).all())

    # ──────────────────────────────── mutations ────────────────────────────────── #

    async def add_message(self, msg: Message, session: AsyncSession) -> None:
        session.add(msg)
        await session.flush()

    async def edit_message(
        self, msg_id: UUID, new_content: str, session: AsyncSession
    ) -> Tuple[Message, str]:
        """
        Creates a **sibling version** of `msg_id` (version + 1) and returns it.
        """
        original: Message | None = await session.get(Message, msg_id)
        if original is None:
            raise ValueError(f"message {msg_id!r} not found")

        if original.parent_id is None:
            next_version = 0
        else:
            next_version = (
                await session.scalar(
                    select(func.coalesce(func.max(Message.version), 0))
                    .where(Message.parent_id == original.parent_id)
                )
            ) + 1

        sibling = Message(
            conversation_id=original.conversation_id,
            parent_id=original.parent_id,
            version=next_version,
            role=original.role,
            content=new_content,
        )
        session.add(sibling)

        # Flip parent pointer in the same transaction (if parent exists)
        if original.parent_id:
            await self.set_active_child(original.parent_id, sibling.id, session)

        await session.flush()
        return sibling, sibling.id

    async def set_active_child(
        self,
        parent_id: UUID,
        child_id: UUID,
        session: AsyncSession,
    ) -> None:
        """
        Set `parent_id` → `child_id` and, in the same statement, repair every
        ancestor’s `active_child_id` so the entire root-to-leaf path is again
        consistent.  A recursive CTE climbs the parent links in-database, which
        means one round-trip and row-level locks held for the shortest time
        possible.
        """
        sql = text(
            """
            WITH RECURSIVE path AS (
                -- anchor: the parent we were given
                SELECT id          AS anc_id,
                      :child_id   AS child_id
                FROM   messages
                WHERE  id = :parent_id

                UNION ALL

                -- climb: for each current ancestor, fetch its own parent
                SELECT m.parent_id AS anc_id,
                      m.id        AS child_id
                FROM   messages m
                JOIN   path     p ON m.id = p.anc_id
                WHERE  m.parent_id IS NOT NULL
            )
            UPDATE messages AS tgt
            SET    active_child_id = path.child_id
            FROM   path
            WHERE  tgt.id = path.anc_id;
            """
        )
        await session.execute(sql, {"parent_id": parent_id, "child_id": child_id})

    async def update_message_content(
        self, mid: UUID, new: str, session: AsyncSession
    ) -> None:
        await session.execute(
            update(Message)
            .where(Message.id == mid)
            .values(content=new)
        )

    async def update_active_thread(
        self, cid: UUID, thread: list[UUID], session: AsyncSession
    ) -> None:
        """
        Stores the entire active thread array on the conversation row.
        Converts python list → Postgres JSON automatically.
        """
        await session.execute(
            update(Conversation)
            .where(Conversation.id == cid)
            .values(active_thread_ids=thread)
        )
