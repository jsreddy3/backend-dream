"""Video generation service that queues video creation jobs."""
import logging
from datetime import datetime
from uuid import UUID

from new_backend_ruminate.domain.dream.entities.dream import GenerationStatus
from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
from new_backend_ruminate.infrastructure.celery.adapter import CeleryVideoQueueAdapter
from new_backend_ruminate.infrastructure.db.bootstrap import session_scope

logger = logging.getLogger(__name__)


async def create_video(user_id: UUID, dream_id: UUID):
    """
    Queue a video generation job for the given dream.
    
    This function:
    1. Retrieves the dream and its transcript
    2. Queues the video generation job
    3. Updates the dream with the job ID and status
    """
    try:
        async with session_scope() as session:
            # Get dream repository
            dream_repo = RDSDreamRepository()
            
            # Fetch the dream
            dream = await dream_repo.get_dream(user_id, dream_id, session)
            if not dream:
                logger.error(f"Dream {dream_id} not found")
                return
            
            # Check if video generation is already in progress
            if dream.video_status in [GenerationStatus.QUEUED, GenerationStatus.PROCESSING]:
                logger.warning(f"Video generation already in progress for dream {dream_id}")
                return
            
            # Get transcript and segments
            logger.info(f"Processing dream {dream_id} for video generation")
            logger.info(f"Dream transcript field: '{dream.transcript}'")
            logger.info(f"Dream has {len(dream.segments)} segments")
            
            transcript = dream.transcript or ""
            
            # If no transcript, try to build from segments
            if not transcript and dream.segments:
                logger.info(f"No main transcript, checking {len(dream.segments)} segments...")
                segment_transcripts = []
                for i, s in enumerate(dream.segments):
                    logger.info(f"Segment {i} (order={s.order}): transcript='{s.transcript}', has_transcript={bool(s.transcript)}")
                    if s.transcript:
                        segment_transcripts.append(s.transcript)
                
                if segment_transcripts:
                    transcript = " ".join(segment_transcripts)
                    logger.info(f"Built transcript from {len(segment_transcripts)} segments: '{transcript[:100]}...'")
                else:
                    logger.warning(f"No segment transcripts found for dream {dream_id}")
            
            # If still no transcript, raise an error
            if not transcript:
                error_msg = f"No transcript available for dream {dream_id}. Cannot generate video without transcript."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            segments = [
                {
                    "order": s.order,
                    "transcript": s.transcript,
                    "s3_key": s.s3_key,
                }
                for s in dream.segments
            ]
            
            # Queue the video generation job
            video_queue = CeleryVideoQueueAdapter()
            job_id = await video_queue.enqueue_video_generation(
                user_id=user_id,
                dream_id=dream_id,
                transcript=transcript,
                segments=segments
            )
            
            # Update dream with job information
            dream.video_job_id = job_id
            dream.video_status = GenerationStatus.QUEUED
            dream.video_started_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"Queued video generation job {job_id} for dream {dream_id}")
            
    except Exception as e:
        logger.error(f"Failed to queue video generation for dream {dream_id}: {str(e)}")
        raise
