# new_backend_ruminate/infrastructure/implementations/dream/rds_dream_repository.py
from __future__ import annotations

from typing import List, Optional, Any
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from sqlalchemy import select, update, delete, func, insert, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from new_backend_ruminate.domain.dream.entities.dream import Dream
from new_backend_ruminate.domain.dream.entities.segments import Segment
from new_backend_ruminate.domain.dream.entities.interpretation import InterpretationQuestion, InterpretationChoice, InterpretationAnswer
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

    async def update_additional_info(
        self, user_id: UUID, did: UUID, additional_info: str, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(additional_info=additional_info)
        )
        await session.commit()
        return await self.get_dream(user_id, did, session)

    async def update_analysis(
        self, user_id: UUID, did: UUID, analysis: str, metadata: dict, session: AsyncSession
    ) -> Optional[Dream]:
        await session.execute(
            update(Dream)
            .where(Dream.id == did, Dream.user_id == user_id)
            .values(
                analysis=analysis,
                analysis_generated_at=datetime.utcnow(),
                analysis_metadata=metadata
            )
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
        self, user_id: UUID, segment: Segment, session: AsyncSession
    ) -> Segment:
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
    ) -> Optional[Segment]:
        result = await session.execute(
            select(Segment).where(
                Segment.id == sid, Segment.dream_id == did, Segment.user_id == user_id
            )
        )
        return result.scalars().first()

    async def delete_segment(
        self, user_id: UUID, did: UUID, sid: UUID, session: AsyncSession
    ) -> Optional[Segment]:
        seg = await self.get_segment(user_id, did, sid, session)
        if not seg:
            return None
        await session.delete(seg)
        await session.commit()
        return seg

    async def update_segment_transcript(
        self, user_id: UUID, did: UUID, sid: UUID, transcript: str, session: AsyncSession
    ) -> Optional[Segment]:
        await session.execute(
            update(Segment)
            .where(Segment.id == sid, Segment.dream_id == did, Segment.user_id == user_id)
            .values(transcript=transcript, transcription_status='completed')
        )
        await session.commit()
        return await self.get_segment(user_id, did, sid, session)
    
    async def update_segment_transcription_status(
        self, user_id: UUID, did: UUID, sid: UUID, status: str, session: AsyncSession
    ) -> Optional[Segment]:
        await session.execute(
            update(Segment)
            .where(Segment.id == sid, Segment.dream_id == did, Segment.user_id == user_id)
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
        if dream and dream.segments:
            # Return s3_key of first audio segment (text segments have s3_key=None)
            for segment in dream.segments:
                if segment.modality == "audio" and segment.s3_key:
                    return segment.s3_key
        return None

    async def get_status(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]:
        dream = await self.get_dream(user_id, did, session)
        return dream.state if dream else None
    
    async def update_summary_status(self, user_id: UUID, did: UUID, status: str, session: AsyncSession) -> Optional[Dream]:
        """Update the summary generation status."""
        dream = await self.get_dream(user_id, did, session)
        if dream:
            dream.summary_status = status
            await session.commit()
            await session.refresh(dream)
        return dream
    
    async def try_start_summary_generation(self, user_id: UUID, did: UUID, session: AsyncSession) -> bool:
        """Atomically try to start summary generation. Returns True if successful, False if already in progress."""
        from new_backend_ruminate.domain.dream.entities.dream import SummaryStatus
        
        # Try to atomically update from None to PENDING
        stmt = (
            update(Dream)
            .where(
                and_(
                    Dream.id == did,
                    Dream.user_id == user_id,
                    or_(
                        Dream.summary_status.is_(None),
                        Dream.summary_status == SummaryStatus.FAILED
                    )
                )
            )
            .values(summary_status=SummaryStatus.PENDING)
        )
        
        result = await session.execute(stmt)
        await session.commit()
        
        # If we updated a row, we successfully acquired the lock
        return result.rowcount > 0
    
    # ───────────────────────── interpretation questions ────────────────────────── #
    
    async def create_interpretation_questions(
        self, user_id: UUID, did: UUID, questions: List[InterpretationQuestion], session: AsyncSession
    ) -> List[InterpretationQuestion]:
        """Create multiple questions with their choices for a dream."""
        # Verify dream exists and belongs to user
        dream = await self.get_dream(user_id, did, session)
        if not dream:
            raise ValueError(f"Dream {did} not found for user {user_id}")
        
        # Add all questions and choices
        for question in questions:
            question.dream_id = did
            session.add(question)
            # Choices are added automatically due to cascade
        
        await session.commit()
        
        # Refresh all questions to get their IDs and relationships
        for question in questions:
            await session.refresh(question, attribute_names=["choices"])
        
        return questions
    
    async def get_interpretation_questions(
        self, user_id: UUID, did: UUID, session: AsyncSession
    ) -> List[InterpretationQuestion]:
        """Get all interpretation questions for a dream with their choices."""
        # Verify dream belongs to user
        dream = await self.get_dream(user_id, did, session)
        if not dream:
            return []
        
        result = await session.execute(
            select(InterpretationQuestion)
            .where(InterpretationQuestion.dream_id == did)
            .options(selectinload(InterpretationQuestion.choices))
            .order_by(InterpretationQuestion.question_order)
        )
        return list(result.scalars().all())
    
    async def record_interpretation_answer(
        self, user_id: UUID, answer: InterpretationAnswer, session: AsyncSession
    ) -> InterpretationAnswer:
        """Record or update a user's answer to an interpretation question."""
        # Check if answer already exists (upsert)
        existing = await session.execute(
            select(InterpretationAnswer).where(
                InterpretationAnswer.question_id == answer.question_id,
                InterpretationAnswer.user_id == user_id
            )
        )
        existing_answer = existing.scalars().first()
        
        if existing_answer:
            # Update existing answer
            existing_answer.selected_choice_id = answer.selected_choice_id
            existing_answer.custom_answer = answer.custom_answer
            existing_answer.answered_at = datetime.utcnow()
            await session.commit()
            await session.refresh(existing_answer)
            return existing_answer
        else:
            # Create new answer
            answer.user_id = user_id
            session.add(answer)
            await session.commit()
            await session.refresh(answer)
            return answer
    
    async def get_interpretation_answers(
        self, user_id: UUID, did: UUID, session: AsyncSession
    ) -> List[InterpretationAnswer]:
        """Get all interpretation answers for a dream by the user."""
        result = await session.execute(
            select(InterpretationAnswer)
            .join(InterpretationQuestion)
            .where(
                InterpretationQuestion.dream_id == did,
                InterpretationAnswer.user_id == user_id
            )
            .options(
                selectinload(InterpretationAnswer.question),
                selectinload(InterpretationAnswer.selected_choice)
            )
            .order_by(InterpretationQuestion.question_order)
        )
        return list(result.scalars().all())