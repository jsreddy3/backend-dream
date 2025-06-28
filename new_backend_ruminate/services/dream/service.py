"""Application layer orchestrating Dream use-cases.

All db persistence is delegated to DreamRepository; any S3/Deepgram calls are
made through the injected ports.  This layer contains *no* business rules – it
merely coordinates work and enforces idempotency.
"""
from __future__ import annotations

import uuid
import asyncio
from typing import Optional, List
from uuid import UUID
import json

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus
from new_backend_ruminate.domain.dream.entities.audio_segments import AudioSegment
from new_backend_ruminate.domain.dream.repo import DreamRepository
from new_backend_ruminate.domain.object_storage.repo import ObjectStorageRepository
from new_backend_ruminate.domain.ports.transcription import TranscriptionService  # optional
from new_backend_ruminate.dependencies import EventStreamHub


class DreamService:
    def __init__(
        self,
        dream_repo: DreamRepository,
        storage_repo: ObjectStorageRepository,
        transcription_svc: Optional[TranscriptionService] = None,
        event_hub: Optional[EventStreamHub] = None,
    ) -> None:
        self._repo = dream_repo
        self._storage = storage_repo
        self._transcribe = transcription_svc
        self._hub = event_hub

    # ─────────────────────────────── dreams ──────────────────────────────── #

    async def list_dreams(self, session: AsyncSession) -> List[Dream]:
        # user-scoping TBD; for now list all
        return await self._repo.list_dreams_by_user(None, session)

    async def create_dream(self, payload, session: AsyncSession) -> Dream:
        dream = Dream(id=payload.id or uuid.uuid4(), title=payload.title)
        return await self._repo.create_dream(dream, session)

    async def get_dream(self, did: UUID, session: AsyncSession) -> Optional[Dream]:
        return await self._repo.get_dream(did, session)

    async def update_title(self, did: UUID, title: str, session: AsyncSession) -> Optional[Dream]:
        return await self._repo.update_title(None, did, title, session)

    async def get_transcript(self, did: UUID, session: AsyncSession) -> Optional[str]:
        return await self._repo.get_transcript(did, session)

    # ───────────────────────────── segments ──────────────────────────────── #

    async def add_segment(
        self,
        did: UUID,
        seg_payload,
        session: AsyncSession,
    ) -> AudioSegment:
        seg = AudioSegment(
            id=seg_payload.segment_id,
            dream_id=did,
            filename=seg_payload.filename,
            duration=seg_payload.duration,
            order=seg_payload.order,
            s3_key=seg_payload.s3_key,
        )
        return await self._repo.create_segment(seg, session)

    async def delete_segment(self, did: UUID, sid: UUID, session: AsyncSession) -> bool:
        # need s3 key before deletion
        segment = await self._repo.get_segment(did, sid, session)
        if not segment:
            return False
        await self._repo.delete_segment(did, sid, session)
        # best-effort delete from storage
        try:
            await self._storage.delete_object(segment.s3_key)
        except Exception as _:
            # log in production
            pass
        return True

    # ---------------------------------------------------------------------- #
    # Background helpers
    # ---------------------------------------------------------------------- #

    # ---------------------------------------------------------------------- #
    # Dream finalisation / video                                             #
    # ---------------------------------------------------------------------- #

    async def finish_dream(self, did: UUID) -> None:
        """Mark dream as completed and kick off video generation async."""
        from new_backend_ruminate.services.video import create_video  # local import to avoid cycle
        # open own session
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        async with session_scope() as session:
            await self._repo.set_state(None, did, DreamStatus.TRANSCRIBED.value, session)
        # fire-and-forget video
        asyncio.create_task(create_video(did))

    async def mark_video_complete(self, did: UUID) -> None:
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        async with session_scope() as session:
            await self._repo.set_state(None, did, DreamStatus.VIDEO_READY.value, session)
    
    async def handle_video_completion(
        self, 
        dream_id: UUID,
        status: str,
        video_url: str | None = None,
        metadata: dict | None = None,
        error: str | None = None
    ) -> None:
        """Handle video generation completion callback from worker."""
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        from new_backend_ruminate.domain.dream.entities.dream import VideoStatus
        from datetime import datetime
        
        async with session_scope() as session:
            dream = await self._repo.get_dream(dream_id, session)
            if not dream:
                return
            
            # Update video fields based on status
            if status == "completed":
                dream.video_status = VideoStatus.COMPLETED
                dream.video_url = video_url
                dream.video_metadata = metadata
                dream.video_completed_at = datetime.utcnow()
                dream.state = DreamStatus.VIDEO_READY.value
            else:  # failed
                dream.video_status = VideoStatus.FAILED
                dream.video_metadata = {"error": error} if error else None
                dream.video_completed_at = datetime.utcnow()
            
            await session.commit()
    
    async def get_video_status(self, dream_id: UUID) -> dict:
        """Get the current status of video generation for a dream."""
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        from new_backend_ruminate.infrastructure.celery.adapter import CeleryVideoQueueAdapter
        from new_backend_ruminate.domain.dream.entities.dream import VideoStatus
        
        async with session_scope() as session:
            dream = await self._repo.get_dream(dream_id, session)
            if not dream:
                return {"job_id": None, "status": None, "video_url": None}
            
            # If we have a job ID and status is not final, check with Celery
            if dream.video_job_id and dream.video_status in [VideoStatus.QUEUED, VideoStatus.PROCESSING]:
                video_queue = CeleryVideoQueueAdapter()
                job_status = await video_queue.get_job_status(dream.video_job_id)
                
                # Update status if it changed
                if job_status["status"] == "PROCESSING" and dream.video_status == VideoStatus.QUEUED:
                    dream.video_status = VideoStatus.PROCESSING
                    await session.commit()
                
                return {
                    "job_id": dream.video_job_id,
                    "status": dream.video_status,
                    "video_url": dream.video_url
                }
            
            # Return stored status
            return {
                "job_id": dream.video_job_id,
                "status": dream.video_status,
                "video_url": dream.video_url
            }

    # ---------------------------------------------------------------------- #
    # Background helpers                                                     #
    # ---------------------------------------------------------------------- #

    async def transcribe_segment_and_store(self, did: UUID, sid: UUID, filename: str) -> None:
        """Background task: get presigned GET URL, call Deepgram, store transcript."""
        if self._transcribe is None:
            return  # transcription disabled in this deployment

        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        print("Generating url")
        key, url = await self._storage.generate_presigned_get(did, filename)
        print("Transcribing")
        transcript = await self._transcribe.transcribe(url)
        print("Transcript: ", transcript)
        if transcript:
            async with session_scope() as session:
                await self._repo.update_segment_transcript(did, sid, transcript, session)
            if self._hub:
                await self._hub.publish(
                    stream_id=did,
                    chunk=json.dumps({
                        "segment_id": str(sid),
                        "transcript": transcript,
                    })
                )
                