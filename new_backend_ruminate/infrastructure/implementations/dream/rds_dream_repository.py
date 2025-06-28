# new_backend_ruminate/infrastructure/implementations/dream/rds_dream_repository.py
from __future__ import annotations

from typing import List, Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from sqlalchemy import select, update, delete, func, insert
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from new_backend_ruminate.domain.dream.entities.dream import Dream
from new_backend_ruminate.domain.dream.entities.audio_segments import AudioSegment
from new_backend_ruminate.domain.dream.repo import DreamRepository


class RDSDreamRepository(DreamRepository):
    """Async SQLAlchemy implementation that honours idempotency and avoids lazy-load."""

    # ─────────────────────────────── dreams CRUD ────────────────────────────── #

    async def create_dream(self, dream: Dream, session: AsyncSession) -> Dream:
        """Insert dream; if already exists return existing (idempotent)."""
        try:
            session.add(dream)
            await session.commit()
            await session.refresh(dream, attribute_names=["segments"])
            return dream
        except IntegrityError:
            await session.rollback()
            return await self.get_dream(dream.id, session)

    async def get_dream(self, did: UUID, session: AsyncSession) -> Optional[Dream]:
        result = await session.execute(
            select(Dream)
            .where(Dream.id == did)
            .options(selectinload(Dream.segments))
        )
        return result.scalars().first()

    async def list_dreams_by_user(self, user_id: UUID, session: AsyncSession) -> List[Dream]:
        result = await session.execute(
            select(Dream)
            .where(Dream.user_id == user_id)
            .options(selectinload(Dream.segments))
            .order_by(Dream.created.desc())
        )
        return list(result.scalars().all())

    async def update_title(
        self, user_id: UUID, did: UUID, title: str, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(title=title)
        )
        await session.commit()
        return await self.get_dream(did, session)

    async def set_state(
        self, user_id: UUID, did: UUID, state: str, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(state=state)
        )
        await session.commit()
        return await self.get_dream(did, session)

    async def delete_dream(
        self, user_id: UUID, did: UUID, session: AsyncSession
    ) -> Optional[Dream]:
        dream = await self.get_dream(did, session)
        if not dream or dream.user_id != user_id:
            return None
        await session.delete(dream)
        await session.commit()
        return dream

    # ───────────────────────────── segments CRUD ────────────────────────────── #

    async def create_segment(
        self, segment: AudioSegment, session: AsyncSession
    ) -> AudioSegment:
        try:
            session.add(segment)
            await session.commit()
            await session.refresh(segment)
            return segment
        except IntegrityError:
            await session.rollback()
            return await self.get_segment(segment.dream_id, segment.id, session)

    async def get_segment(
        self, did: UUID, sid: UUID, session: AsyncSession
    ) -> Optional[AudioSegment]:
        result = await session.execute(
            select(AudioSegment).where(
                AudioSegment.id == sid, AudioSegment.dream_id == did
            )
        )
        return result.scalars().first()

    async def delete_segment(
        self, did: UUID, sid: UUID, session: AsyncSession
    ) -> Optional[AudioSegment]:
        seg = await self.get_segment(did, sid, session)
        if not seg:
            return None
        await session.delete(seg)
        await session.commit()
        return seg

    async def update_segment_transcript(
        self, did: UUID, sid: UUID, transcript: str, session: AsyncSession
    ) -> Optional[AudioSegment]:
        await session.execute(
            update(AudioSegment)
            .where(AudioSegment.id == sid, AudioSegment.dream_id == did)
            .values(transcript=transcript)
        )
        await session.commit()
        return await self.get_segment(did, sid, session)

    # ─────────────────────────────── getters ────────────────────────────────── #

    async def get_video_url(self, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(did, session)
        return dream.segments[0].video_url if dream else None  # placeholder

    async def get_transcript(self, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(did, session)
        return dream.transcript if dream else None

    async def get_audio_url(self, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(did, session)
        return dream.segments[0].s3_key if dream and dream.segments else None

    async def get_status(self, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(did, session)
        return dream.state if dream else None