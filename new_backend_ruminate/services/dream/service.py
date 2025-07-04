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
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, VideoStatus
from new_backend_ruminate.domain.dream.entities.segments import Segment
from new_backend_ruminate.domain.dream.repo import DreamRepository
from new_backend_ruminate.domain.object_storage.repo import ObjectStorageRepository
from new_backend_ruminate.domain.user.repo import UserRepository
from new_backend_ruminate.domain.ports.transcription import TranscriptionService  # optional
from new_backend_ruminate.domain.ports.llm import LLMService
from new_backend_ruminate.dependencies import EventStreamHub

logger = logging.getLogger(__name__)


class DreamService:
    def __init__(
        self,
        dream_repo: DreamRepository,
        storage_repo: ObjectStorageRepository,
        user_repo: UserRepository,
        transcription_svc: Optional[TranscriptionService] = None,
        event_hub: Optional[EventStreamHub] = None,
        summary_llm: Optional[LLMService] = None,
        interpretation_llm: Optional[LLMService] = None,
    ) -> None:
        self._repo = dream_repo
        self._storage = storage_repo
        self._user_repo = user_repo
        self._transcribe = transcription_svc
        self._hub = event_hub
        self._summary_llm = summary_llm
        self._interpretation_llm = interpretation_llm

    # ─────────────────────────────── dreams ──────────────────────────────── #

    async def list_dreams(self, user_id: UUID, session: AsyncSession) -> List[Dream]:
        # user-scoping TBD; for now list all
        return await self._repo.list_dreams_by_user(user_id, session)

    async def create_dream(self, user_id: UUID, payload, session: AsyncSession) -> Dream:
        dream = Dream(id=payload.id or uuid.uuid4(), title=payload.title)
        return await self._repo.create_dream(user_id, dream, session)

    async def get_dream(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[Dream]:
        return await self._repo.get_dream(user_id, did, session)

    async def update_title(self, user_id: UUID, did: UUID, title: str, session: AsyncSession) -> Optional[Dream]:
        return await self._repo.update_title(user_id, did, title, session)

    async def get_transcript(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]:
        return await self._repo.get_transcript(user_id, did, session)

    async def update_summary(self, user_id: UUID, did: UUID, summary: str, session: AsyncSession) -> Optional[Dream]:
        return await self._repo.update_summary(user_id, did, summary, session)

    async def generate_title_and_summary(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[Dream]:
        """Generate AI title and summary from dream transcript."""
        if not self._summary_llm:
            logger.warning("Summary LLM service not available, cannot generate title and summary")
            return None
        
        # Get the dream and transcript
        dream = await self._repo.get_dream(user_id, did, session)
        if not dream:
            logger.error(f"Dream {did} not found for user {user_id}")
            return None
        
        transcript = await self._repo.get_transcript(user_id, did, session)
        if not transcript:
            logger.error(f"No transcript available for dream {did}")
            return None
        
        logger.info(f"Generating title and summary for dream {did}")
        
        # Prepare the prompt for the LLM
        messages = [
            {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries of dream recordings. Your task is to create a title and summary that accurately represents the dream content without adding any details, interpretations, or embellishments not present in the original transcript."},
            {"role": "user", "content": f"""Based on this dream transcript, create a short title and a clear summary. 

IMPORTANT RULES:
- The title should be 3-7 words that capture the main theme
- The summary should be a clear, factual description of what happened in the dream
- Do NOT add any details not mentioned in the transcript
- Do NOT interpret or analyze the dream
- Do NOT embellish or extrapolate
- Stay completely faithful to the original content
- Use present tense for the summary

Dream transcript:
{transcript}

Return a JSON object with 'title' and 'summary' fields."""}
        ]
        
        # Define the JSON schema for the response
        json_schema = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "A short title (3-7 words) capturing the main theme"
                },
                "summary": {
                    "type": "string", 
                    "description": "A clear, factual summary of the dream events"
                }
            },
            "required": ["title", "summary"]
        }
        
        try:
            # Use async LLM call with structured response using dedicated summary LLM
            result = await self._summary_llm.generate_structured_response(
                messages=messages,
                response_format={"type": "json_object"},
                json_schema=json_schema
            )
            
            logger.info(f"Generated title: {result.get('title')}, summary length: {len(result.get('summary', ''))}")
            
            # Update the dream with generated title and summary
            updated_dream = await self._repo.update_title_and_summary(
                user_id, did, 
                result['title'], 
                result['summary'], 
                session
            )
            
            return updated_dream
            
        except Exception as e:
            logger.error(f"Failed to generate title and summary for dream {did}: {str(e)}")
            return None

    # ───────────────────────────── segments ──────────────────────────────── #

    async def add_segment(
        self,
        user_id: UUID,
        did: UUID,
        seg_payload,
        session: AsyncSession,
    ) -> Segment:
        if seg_payload.modality == "text":
            # For text segments, store the text directly as transcript
            seg = Segment(
                id=seg_payload.segment_id,
                dream_id=did,
                modality="text",
                filename=None,  # No filename for text
                duration=None,  # No duration for text
                order=seg_payload.order,
                s3_key=None,  # No S3 key for text
                transcript=seg_payload.text,  # Store text directly
                transcription_status="completed",  # Already have the text
            )
        else:  # audio
            seg = Segment(
                id=seg_payload.segment_id,
                dream_id=did,
                modality="audio",
                filename=seg_payload.filename,
                duration=seg_payload.duration,
                order=seg_payload.order,
                s3_key=seg_payload.s3_key,
                transcript=None,  # Will be filled by transcription
                transcription_status="pending",  # Needs transcription
            )
        return await self._repo.create_segment(user_id, seg, session)

    async def delete_segment(self, user_id: UUID, did: UUID, sid: UUID, session: AsyncSession) -> bool:
        # need s3 key before deletion
        segment = await self._repo.get_segment(user_id, did, sid, session)
        if not segment:
            return False
        await self._repo.delete_segment(user_id, did, sid, session)
        # best-effort delete from storage (only for audio segments)
        if segment.modality == "audio" and segment.s3_key:
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

    async def finish_dream(self, user_id: UUID, did: UUID) -> None:
        """Mark dream as completed after all transcriptions are done."""
        logger.info(f"Finishing dream {did} for user {user_id}")
        
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        
        # Wait for all segments to be transcribed
        max_wait_seconds = 30
        check_interval = 0.5
        waited = 0
        
        while waited < max_wait_seconds:
            async with session_scope() as session:
                dream = await self._repo.get_dream(user_id, did, session)
                if not dream:
                    raise ValueError(f"Dream {did} not found")
                
                if not dream.segments:
                    logger.error(f"Dream {did} has no segments")
                    raise ValueError(f"Dream {did} has no audio segments")
                
                # Check transcription status of all segments
                pending_segments = []
                processing_segments = []
                failed_segments = []
                completed_segments = []
                
                for i, seg in enumerate(dream.segments):
                    status = seg.transcription_status
                    logger.info(f"  Segment {i} (order={seg.order}): status={status}, has_transcript={bool(seg.transcript)}")
                    
                    if status == "pending":
                        pending_segments.append(i)
                    elif status == "processing":
                        processing_segments.append(i)
                    elif status == "failed":
                        failed_segments.append(i)
                    elif status == "completed":
                        completed_segments.append(i)
                
                # Check if all segments are done (no pending or processing)
                if not pending_segments and not processing_segments:
                    # Check if any failed
                    if failed_segments:
                        logger.error(f"Dream {did} has {len(failed_segments)} failed segment(s): {failed_segments}")
                        raise ValueError(f"Cannot finish dream: {len(failed_segments)} segment(s) failed transcription")
                    
                    # All segments completed successfully
                    logger.info(f"All {len(completed_segments)} segments successfully transcribed for dream {did}")
                    break
                else:
                    logger.info(f"Waiting for transcription... {len(pending_segments)} pending, {len(processing_segments)} processing")
            
            await asyncio.sleep(check_interval)
            waited += check_interval
        
        if waited >= max_wait_seconds:
            logger.error(f"Timeout waiting for transcription of dream {did}")
            raise TimeoutError(f"Transcription did not complete within {max_wait_seconds} seconds")
        
        # Concatenate all segment transcripts and update dream
        async with session_scope() as session:
            dream = await self._repo.get_dream(user_id, did, session)
            if dream and dream.segments:
                # Sort segments by order and concatenate transcripts
                sorted_segments = sorted(dream.segments, key=lambda s: s.order)
                transcript_parts = []
                
                for seg in sorted_segments:
                    if seg.transcript:
                        transcript_parts.append(seg.transcript)
                
                # Join transcripts with space
                combined_transcript = " ".join(transcript_parts)
                logger.info(f"Combined {len(transcript_parts)} segment transcripts into dream transcript")
                
                # Update dream transcript and state
                dream.transcript = combined_transcript
                dream.state = DreamStatus.TRANSCRIBED.value
                await session.commit()
                logger.info(f"Updated dream {did} with combined transcript and state to TRANSCRIBED")
            else:
                # Just update state if no segments or dream not found
                await self._repo.set_state(user_id, did, DreamStatus.TRANSCRIBED.value, session)
                logger.info(f"Updated dream {did} state to TRANSCRIBED")

    async def generate_video(self, user_id: UUID, did: UUID) -> None:
        """Generate video for a transcribed dream."""
        logger.info(f"Generating video for dream {did} for user {user_id}")
        
        from new_backend_ruminate.services.video import create_video  # local import to avoid cycle
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        
        # Check if dream is ready for video generation
        async with session_scope() as session:
            dream = await self._repo.get_dream(user_id, did, session)
            if not dream:
                raise ValueError(f"Dream {did} not found")
            
            # Check if dream is transcribed
            if dream.state != DreamStatus.TRANSCRIBED.value:
                raise ValueError(f"Dream {did} is not ready for video generation. Current state: {dream.state}")
            
            # Check if video is already being generated
            if dream.video_status in [VideoStatus.QUEUED, VideoStatus.PROCESSING]:
                logger.warning(f"Video generation already in progress for dream {did}")
                return
        
        # Trigger video generation
        logger.info(f"Triggering video generation for dream {did}")
        await create_video(user_id, did)
    
    async def mark_video_complete(self, user_id: UUID, did: UUID) -> None:
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        async with session_scope() as session:
            await self._repo.set_state(user_id, did, DreamStatus.VIDEO_READY.value, session)
    
    async def handle_video_completion(
        self, 
        user_id: UUID,
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
            dream = await self._repo.get_dream(user_id, dream_id, session)
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
    
    async def get_video_status(self, user_id: UUID, dream_id: UUID) -> dict:
        """Get the current status of video generation for a dream."""
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        from new_backend_ruminate.infrastructure.celery.adapter import CeleryVideoQueueAdapter
        from new_backend_ruminate.domain.dream.entities.dream import VideoStatus
        
        async with session_scope() as session:
            dream = await self._repo.get_dream(user_id, dream_id, session)
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

    async def transcribe_segment_and_store(self, user_id: UUID, did: UUID, sid: UUID, filename: str) -> None:
        """Background task: get presigned GET URL, call Deepgram, store transcript."""
        logger.info(f"Starting transcription for segment {sid} of dream {did}")
        
        if self._transcribe is None:
            logger.warning("Transcription service not available, skipping transcription")
            return  # transcription disabled in this deployment

        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        
        # Update status to processing
        try:
            async with session_scope() as session:
                await self._repo.update_segment_transcription_status(user_id, did, sid, "processing", session)
                logger.info(f"Updated segment {sid} status to processing")
        except Exception as e:
            logger.error(f"Failed to update segment status to processing: {str(e)}")
        
        try:
            key, url = await self._storage.generate_presigned_get(did, filename)
            logger.info(f"Generated presigned URL for segment {sid}")
            
            transcript = await self._transcribe.transcribe(url)
            logger.info(f"Transcription result for segment {sid}: '{transcript[:100] if transcript else '(empty)'}...'")
            
            # Transcript can be empty string - that's still a valid result
            if transcript is not None:
                async with session_scope() as session:
                    # update_segment_transcript now sets status to 'completed' automatically
                    await self._repo.update_segment_transcript(user_id, did, sid, transcript, session)
                    logger.info(f"Updated segment {sid} transcript (length: {len(transcript)}) and status to completed")
                    
                if self._hub:
                    await self._hub.publish(
                        stream_id=did,
                        chunk=json.dumps({
                            "segment_id": str(sid),
                            "transcript": transcript,
                        })
                    )
                    logger.info(f"Published transcript to event hub for segment {sid}")
            else:
                # Only mark as failed if transcript is None (actual failure)
                logger.error(f"Transcription returned None for segment {sid}, marking as failed")
                async with session_scope() as session:
                    await self._repo.update_segment_transcription_status(user_id, did, sid, "failed", session)
        except Exception as e:
            logger.error(f"Error transcribing segment {sid}: {str(e)}")
            # Mark as failed on error
            try:
                async with session_scope() as session:
                    await self._repo.update_segment_transcription_status(user_id, did, sid, "failed", session)
            except Exception as update_error:
                logger.error(f"Failed to update segment status to failed: {str(update_error)}")
            raise
                