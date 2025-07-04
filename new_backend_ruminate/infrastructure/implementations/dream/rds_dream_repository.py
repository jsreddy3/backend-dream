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

    async def create_dream(self, user_id: UUID, dream: Dream, session: AsyncSession) -> Dream:
        """Insert dream; if already exists return existing (idempotent)."""
        try:
            dream.user_id = user_id
            session.add(dream)
            await session.commit()
            await session.refresh(dream, attribute_names=["segments"])
            return dream
        except IntegrityError:
            await session.rollback()
            return await self.get_dream(user_id, dream.id, session)

    async def get_dream(self, user_id: Optional[UUID], did: UUID, session: AsyncSession) -> Optional[Dream]:
        """Fetch a dream. If ``user_id`` is ``None`` the lookup is not constrained to a specific user
        (useful for internal services / admin paths). Otherwise the dream **must** belong to the
        given ``user_id``.
        """
        query = select(Dream).where(Dream.id == did).options(selectinload(Dream.segments))
        if user_id is not None:
            query = query.where(Dream.user_id == user_id)
        result = await session.execute(query)
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
        return await self.get_dream(user_id, did, session)

    async def update_summary(
        self, user_id: UUID, did: UUID, summary: str, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(summary=summary)
        )
        await session.commit()
        return await self.get_dream(user_id, did, session)

    async def update_title_and_summary(
        self, user_id: UUID, did: UUID, title: str, summary: str, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(title=title, summary=summary)
        )
        await session.commit()
        return await self.get_dream(user_id, did, session)

    async def set_state(
        self, user_id: UUID, did: UUID, state: str, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(state=state)
        )
        await session.commit()
        return await self.get_dream(user_id, did, session)

    async def delete_dream(
        self, user_id: UUID, did: UUID, session: AsyncSession
    ) -> Optional[Dream]:
        dream = await self.get_dream(user_id, did, session)
        if not dream or dream.user_id != user_id:
            return None
        await session.delete(dream)
        await session.commit()
        return dream

    # ───────────────────────────── segments CRUD ────────────────────────────── #

    async def create_segment(
        self, user_id: UUID, segment: AudioSegment, session: AsyncSession
    ) -> AudioSegment:
        try:
            segment.user_id = user_id
            session.add(segment)
            await session.commit()
            await session.refresh(segment)
            return segment
        except IntegrityError:
            await session.rollback()
            return await self.get_segment(user_id, segment.dream_id, segment.id, session)

    async def get_segment(
        self, user_id: UUID, did: UUID, sid: UUID, session: AsyncSession
    ) -> Optional[AudioSegment]:
        result = await session.execute(
            select(AudioSegment).where(
                AudioSegment.id == sid, AudioSegment.dream_id == did, AudioSegment.user_id == user_id
            )
        )
        return result.scalars().first()

    async def delete_segment(
        self, user_id: UUID, did: UUID, sid: UUID, session: AsyncSession
    ) -> Optional[AudioSegment]:
        seg = await self.get_segment(user_id, did, sid, session)
        if not seg:
            return None
        await session.delete(seg)
        await session.commit()
        return seg

    async def update_segment_transcript(
        self, user_id: UUID, did: UUID, sid: UUID, transcript: str, session: AsyncSession
    ) -> Optional[AudioSegment]:
        await session.execute(
            update(AudioSegment)
            .where(AudioSegment.id == sid, AudioSegment.dream_id == did, AudioSegment.user_id == user_id)
            .values(transcript=transcript, transcription_status='completed')
        )
        await session.commit()
        return await self.get_segment(user_id, did, sid, session)
    
    async def update_segment_transcription_status(
        self, user_id: UUID, did: UUID, sid: UUID, status: str, session: AsyncSession
    ) -> Optional[AudioSegment]:
        await session.execute(
            update(AudioSegment)
            .where(AudioSegment.id == sid, AudioSegment.dream_id == did, AudioSegment.user_id == user_id)
            .values(transcription_status=status)
        )
        await session.commit()
        return await self.get_segment(user_id, did, sid, session)

    # ─────────────────────────────── getters ────────────────────────────────── #

    async def get_video_url(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(user_id, did, session)
        return dream.segments[0].video_url if dream else None  # placeholder

    async def get_transcript(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(user_id, did, session)
        return dream.transcript if dream else None

    async def get_audio_url(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(user_id, did, session)
        return dream.segments[0].s3_key if dream and dream.segments else None

    async def get_status(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(user_id, did, session)
        return dream.state if dream else None