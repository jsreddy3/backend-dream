# new_backend_ruminate/api/dream/routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import logging
from datetime import datetime

from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.object_storage.repo import ObjectStorageRepository
from new_backend_ruminate.dependencies import (
    get_session,
    get_event_hub,
    get_dream_service,
    get_storage_service,
    get_current_user_id,
    get_profile_service,
)
import time
from sqlalchemy import text
from . import schemas
from .schemas import (
    DreamCreate, DreamUpdate, DreamRead,
    SegmentCreate, SegmentRead, TranscriptRead,
    UploadUrlResponse, VideoURLResponse,
    SummaryUpdate, GenerateSummaryResponse,
    GenerateQuestionsRequest, GenerateQuestionsResponse,
    RecordAnswerRequest, InterpretationQuestionRead,
    InterpretationAnswerRead, AdditionalInfoUpdate,
    GenerateAnalysisRequest, AnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dreams",
)

# ─────────────────────────────── dreams ─────────────────────────────── #

@router.get("/", name="list_dreams")
async def list_dreams(
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id)
):
    dreams = await svc.list_dreams(user_id, db)
    
    result = [DreamRead.model_validate(dream).model_dump() for dream in dreams]
    return result

@router.post("/", response_model=DreamRead, status_code=status.HTTP_201_CREATED)
async def create_dream(
    payload: DreamCreate,
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id)
):
    return await svc.create_dream(user_id, payload, db)

@router.get("/{did}")
async def read_dream(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    result = DreamRead.model_validate(dream).model_dump()
    analysis = result.get('analysis')
    logger.debug(f"GET dream returning - has analysis: {analysis is not None}, analysis length: {len(analysis) if analysis else 0}")
    return result

@router.patch("/{did}")
async def update_dream(
    did: UUID,
    patch: DreamUpdate,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    # Handle title and/or summary updates
    dream = None
    if patch.title is not None and patch.summary is not None:
        # Update both
        dream = await svc._repo.update_title_and_summary(user_id, did, patch.title, patch.summary, db)
    elif patch.title is not None:
        # Update title only
        dream = await svc.update_title(user_id, did, patch.title, db)
    elif patch.summary is not None:
        # Update summary only
        dream = await svc.update_summary(user_id, did, patch.summary, db)
    
    if not dream:
        raise HTTPException(404, "Dream not found")
    return DreamRead.model_validate(dream).model_dump()

@router.delete("/{did}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dream(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    ok = await svc.delete_dream(user_id, did, db)
    if not ok:
        raise HTTPException(404, "Dream not found")

@router.get("/{did}/transcript", response_model=TranscriptRead)
async def get_transcript(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    txt = await svc.get_transcript(user_id, did, db)  # transcript not scoped
    if txt is None:
        raise HTTPException(404, "Dream not found")
    return TranscriptRead(transcript=txt)

# ───────────────────────────── segments ─────────────────────────────── #

@router.post("/{did}/segments", response_model=SegmentRead)
async def add_segment(
    did: UUID,
    seg: SegmentCreate,
    tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession   = Depends(get_session),
):
    logger.info(f"Adding {seg.modality} segment to dream {did}: order={seg.order}")
    segment = await svc.add_segment(user_id, did, seg, db)
    logger.info(f"Segment {segment.id} created with modality={segment.modality}")
    
    # Only queue transcription for audio segments
    if seg.modality == "audio":
        logger.info(f"Queuing transcription for audio segment {segment.id}")
        tasks.add_task(svc.transcribe_segment_and_store, user_id, did, segment.id, seg.filename)
    else:
        logger.info(f"Text segment {segment.id} already has transcript")
    
    return segment

@router.delete("/{did}/segments/{sid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    did: UUID, sid: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService  = Depends(get_dream_service),
):
    ok = await svc.delete_segment(user_id, did, sid)
    if not ok:
        raise HTTPException(404, "Segment not found")

@router.get("/{did}/segments", response_model=list[SegmentRead])
async def list_segments(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession   = Depends(get_session),
):
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    return dream.segments

# --------------------------- dream stream ------------------------------ #

@router.get("/{did}/stream")
async def stream(did: UUID, hub: EventStreamHub = Depends(get_event_hub)):
    async def event_source():
        async for chunk in hub.register_consumer(did):
            yield f"data: {chunk}\n\n"
    return StreamingResponse(event_source(), media_type="text/event-stream")

# ─────────────────────────── presigned URL ─────────────────────────── #

@router.post("/{did}/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    did: UUID,
    filename: str,
    storage: ObjectStorageRepository = Depends(get_storage_service),
    user_id: UUID = Depends(get_current_user_id),
):
    key, url = await storage.generate_presigned_put(did, filename)
    logger.debug(f"Generated upload URL for key {key}")
    return UploadUrlResponse(upload_url=url, upload_key=key)

# ─────────────────────── finish & video complete ────────────────────── #

@router.post("/{did}/finish", response_model=DreamRead)
async def finish_dream(
    did: UUID,
    tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id), 
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session)
):
    logger.info(f"Finish dream endpoint called for dream {did}")
    await svc.finish_dream(user_id, did)
    logger.info(f"Dream {did} finished, transcription and summary generation completed")
    
    # Queue background profile update
    tasks.add_task(update_profile_after_dream, user_id, did)
    logger.info(f"Queued profile update for user {user_id} after dream {did} completion")
    
    # Return the updated dream with generated title and summary
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    return DreamRead.model_validate(dream).model_dump()

@router.post("/{did}/reprocess", response_model=DreamRead)
async def reprocess_incomplete_dream(
    did: UUID,
    tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session)
):
    """Reprocess an incomplete dream that has segments but no transcript."""
    logger.info(f"Reprocess dream endpoint called for dream {did}")
    
    # Check if dream exists and needs reprocessing
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    if dream.transcript:
        logger.info(f"Dream {did} already has transcript, returning current state")
        return DreamRead.model_validate(dream).model_dump()
    
    if not dream.segments or len(dream.segments) == 0:
        raise HTTPException(400, "Dream has no segments to process")
    
    # Process the incomplete dream
    try:
        await svc.finish_dream(user_id, did)
        logger.info(f"Dream {did} reprocessed successfully")
        
        # Queue background profile update
        tasks.add_task(update_profile_after_dream, user_id, did)
        logger.info(f"Queued profile update for user {user_id} after dream {did} reprocessing")
        
        # Return the updated dream
        updated_dream = await svc.get_dream(user_id, did, db)
        if not updated_dream:
            raise HTTPException(404, "Dream not found after processing")
        
        return DreamRead.model_validate(updated_dream).model_dump()
        
    except Exception as e:
        logger.error(f"Failed to reprocess dream {did}: {str(e)}")
        raise HTTPException(400, f"Failed to reprocess dream: {str(e)}")

@router.post("/{did}/generate-video")
async def generate_video(did: UUID, user_id: UUID = Depends(get_current_user_id), svc: DreamService = Depends(get_dream_service)):
    logger.info(f"Generate video endpoint called for dream {did}")
    await svc.generate_video(user_id, did)
    logger.info(f"Video generation triggered for dream {did}")
    return {"status": "video_queued"}

@router.post("/{did}/video-complete")
async def video_complete(
    did: UUID, 
    request: schemas.VideoCompleteRequest,
    svc: DreamService = Depends(get_dream_service),
    user_id: UUID = Depends(get_current_user_id),
):
    """Handle video generation completion callback from worker."""
    await svc.handle_video_completion(
        user_id=user_id,
        dream_id=did,
        status=request.status,
        video_url=request.video_url,
        metadata=request.metadata,
        error=request.error
    )
    return {"status": "ok"}

@router.get("/{did}/video-status", response_model=schemas.VideoStatusResponse)
async def get_video_status(
    did: UUID,
    svc: DreamService = Depends(get_dream_service),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get the current status of video generation for a dream."""
    status_info = await svc.get_video_status(user_id, did)
    return status_info

@router.get("/{did}/video-url/", response_model=VideoURLResponse)
async def get_video_url(
    did: UUID,
    svc: DreamService = Depends(get_dream_service),
    storage: ObjectStorageRepository = Depends(get_storage_service),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
):
    """Get a presigned URL for video playback."""
    # Get the dream to check if it has a video
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    if not dream.video_url or dream.state != "video_generated":
        raise HTTPException(404, "Video not available for this dream")
    
    # Extract S3 key from the video URL
    # Expected format: https://bucket.s3.region.amazonaws.com/dreams/uuid/video.mp4
    video_s3_key = dream.video_url.split('.com/')[-1]
    
    # Generate a presigned URL for viewing
    presigned_url = await storage.generate_presigned_get_by_key(video_s3_key)
    
    return VideoURLResponse(video_url=presigned_url, expires_in=3600)

# ───────────────────────────── AI Summary ─────────────────────────────── #

@router.post("/{did}/generate-summary", response_model=GenerateSummaryResponse)
async def generate_summary(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
):
    """Generate AI-powered title and summary from the dream transcript."""
    logger.info(f"Generate summary endpoint called for dream {did}")
    
    dream = await svc.generate_title_and_summary(user_id, did)
    if (not dream) or (dream.title is None) or (dream.summary is None):
        raise HTTPException(
            400,
            "Failed to generate summary. Check if transcript is available or if the AI generation returned empty values.",
        )

    return GenerateSummaryResponse(title=dream.title, summary=dream.summary)

@router.patch("/{did}/summary")
async def update_summary_only(
    did: UUID,
    summary_update: SummaryUpdate,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Update only the summary of a dream."""
    dream = await svc.update_summary(user_id, did, summary_update.summary, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    return DreamRead.model_validate(dream).model_dump()

# ───────────────────────── Interpretation Questions ─────────────────────── #

@router.post("/{did}/generate-questions", response_model=GenerateQuestionsResponse)
async def generate_interpretation_questions(
    did: UUID,
    request: GenerateQuestionsRequest,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
):
    """Generate interpretation questions for the dream."""
    logger.info(f"Generate questions endpoint called for dream {did}")
    
    questions = await svc.generate_interpretation_questions(
        user_id, did,
        num_questions=request.num_questions,
        num_choices=request.num_choices
    )
    
    if not questions:
        raise HTTPException(400, "Failed to generate questions. Check if transcript is available.")
    
    return GenerateQuestionsResponse(
        questions=[InterpretationQuestionRead.model_validate(q) for q in questions]
    )

@router.get("/{did}/questions", response_model=List[InterpretationQuestionRead])
async def get_interpretation_questions(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Get all interpretation questions for a dream."""
    questions = await svc.get_interpretation_questions(user_id, did, db)
    return [InterpretationQuestionRead.model_validate(q) for q in questions]

@router.post("/{did}/answer", response_model=InterpretationAnswerRead)
async def record_interpretation_answer(
    did: UUID,
    request: RecordAnswerRequest,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Record an answer to an interpretation question."""
    if not request.is_valid:
        raise HTTPException(400, "Either choice_id or custom_answer must be provided")
    
    answer = await svc.record_interpretation_answer(
        user_id,
        request.question_id,
        request.choice_id,
        request.custom_answer,
        db
    )
    
    if not answer:
        raise HTTPException(400, "Failed to record answer")
    
    return InterpretationAnswerRead.model_validate(answer)

@router.get("/{did}/answers", response_model=List[InterpretationAnswerRead])
async def get_interpretation_answers(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Get all interpretation answers for a dream by the current user."""
    answers = await svc.get_interpretation_answers(user_id, did, db)
    return [InterpretationAnswerRead.model_validate(a) for a in answers]

# ───────────────────────── Additional Info ─────────────────────────────── #

@router.put("/{did}/additional-info")
async def update_additional_info(
    did: UUID,
    info_update: AdditionalInfoUpdate,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Update additional information/notes about the dream."""
    dream = await svc.update_additional_info(user_id, did, info_update.additional_info, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    return DreamRead.model_validate(dream).model_dump()

# ───────────────────────── Dream Analysis ─────────────────────────────── #

@router.post("/{did}/generate-analysis", response_model=AnalysisResponse)
async def generate_analysis(
    did: UUID,
    request: GenerateAnalysisRequest,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
):
    """Generate comprehensive dream analysis based on all available information."""
    logger.info(f"Generate analysis endpoint called for dream {did}")
    
    dream = await svc.generate_analysis(
        user_id, did,
        force_regenerate=request.force_regenerate
    )
    
    if not dream:
        raise HTTPException(400, "Dream not found or could not be processed.")
    
    if not dream.analysis:
        # Check if dream has segments but no transcript (incomplete dream)
        if dream.segments and len(dream.segments) > 0 and not dream.transcript:
            raise HTTPException(400, "Dream is being processed. Segments are being transcribed, please try again in a few moments.")
        else:
            raise HTTPException(400, "Failed to generate analysis. Check if transcript is available.")
    
    return AnalysisResponse(
        analysis=dream.analysis,
        generated_at=dream.analysis_generated_at,
        metadata=dream.analysis_metadata
    )

@router.get("/{did}/analysis", response_model=AnalysisResponse)
async def get_analysis(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Get the dream analysis if it exists."""
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    if not dream.analysis:
        raise HTTPException(404, "Analysis not yet generated for this dream")
    
    return AnalysisResponse(
        analysis=dream.analysis,
        generated_at=dream.analysis_generated_at,
        metadata=dream.analysis_metadata
    )

@router.post("/{did}/generate-expanded-analysis", response_model=AnalysisResponse)
async def generate_expanded_analysis(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
):
    """Generate expanded dream analysis building on existing analysis."""
    logger.info(f"Generate expanded analysis endpoint called for dream {did}")
    
    dream = await svc.generate_expanded_analysis(user_id, did)
    
    if not dream or not dream.expanded_analysis:
        raise HTTPException(400, "Failed to generate expanded analysis. Check if initial analysis exists.")
    
    return AnalysisResponse(
        analysis=dream.expanded_analysis,
        generated_at=dream.expanded_analysis_generated_at,
        metadata=dream.expanded_analysis_metadata
    )

# ─────────────────────────── Image Generation ─────────────────────────── #

@router.post("/test-image-generation")
async def test_image_generation(
    user_id: UUID = Depends(get_current_user_id),
):
    """Test endpoint for DALL-E 3 integration"""
    from new_backend_ruminate.services.image_generation.service import ImageGenerationService
    
    logger.info("Test image generation endpoint called")
    
    service = ImageGenerationService()
    image_url = await service.test_generation()
    
    if not image_url:
        raise HTTPException(500, "Failed to generate test image")
    
    return {
        "url": image_url,
        "time": time.time(),
        "message": "Test image generated successfully"
    }

@router.post("/{did}/generate-image")
async def generate_dream_image(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Generate an image for a dream"""
    from new_backend_ruminate.services.image_generation.service import ImageGenerationService
    from new_backend_ruminate.domain.dream.entities.dream import GenerationStatus
    
    # Get the dream
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    # Check if image already exists
    if dream.image_url and dream.image_status == GenerationStatus.COMPLETED.value:
        return {
            "url": dream.image_url,
            "prompt": dream.image_prompt,
            "generated_at": dream.image_generated_at,
            "message": "Image already exists"
        }
    
    # Check if we have transcript or summary to work with
    if not dream.transcript and not dream.summary:
        raise HTTPException(400, "Dream must have transcript or summary before generating image")
    
    # Update status to processing
    dream.image_status = GenerationStatus.PROCESSING.value
    await db.commit()
    
    try:
        # Generate image (we'll improve the prompt in Phase 2)
        img_service = ImageGenerationService()
        prompt = f"Dreamlike artistic visualization of: {(dream.summary or dream.transcript)[:200]}"
        
        s3_url, used_prompt, error_type = await img_service.generate_and_store_image(
            user_id=user_id,
            dream_id=did,
            prompt=prompt
        )
        
        if not s3_url:
            if error_type == "content_policy_violation":
                dream.image_status = "policy_violation"
                await db.commit()
                raise HTTPException(
                    422, 
                    detail={
                        "error": "content_policy_violation",
                        "message": "This dream contains content that was flagged by our copyright and safety system"
                    }
                )
            else:
                dream.image_status = GenerationStatus.FAILED.value
                await db.commit()
                raise HTTPException(500, "Failed to generate image")
        
        # Update dream with image info
        dream.image_url = s3_url
        dream.image_prompt = used_prompt
        dream.image_generated_at = datetime.utcnow()
        dream.image_status = GenerationStatus.COMPLETED.value
        dream.image_metadata = {
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard",
            "style": "vivid"
        }
        
        await db.commit()
        
        return {
            "url": dream.image_url,
            "prompt": dream.image_prompt,
            "generated_at": dream.image_generated_at,
            "message": "Image generated successfully"
        }
        
    except HTTPException:
        # Re-raise HTTPException without wrapping (for 422 content policy violations)
        raise
    except Exception as e:
        logger.error(f"Error generating image for dream {did}: {str(e)}")
        dream.image_status = GenerationStatus.FAILED.value
        await db.commit()
        raise HTTPException(500, f"Image generation failed: {str(e)}")

# ───────────────────────── Debug & Recovery Endpoints ─────────────────────────────── #

@router.get("/{did}/debug", response_model=Dict[str, Any])
async def debug_dream_status(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Get comprehensive debug information about a dream's status."""
    logger.info(f"Debug endpoint called for dream {did}")
    
    # Get dream with detailed segment information
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        # Try to get dream without user constraint to check ownership issues
        from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
        repo = RDSDreamRepository()
        unscoped_dream = await repo.get_dream(None, did, db)
        
        if unscoped_dream:
            raise HTTPException(403, f"Dream exists but belongs to user {unscoped_dream.user_id}, not {user_id}")
        else:
            raise HTTPException(404, "Dream not found")
    
    # Analyze segments
    segment_analysis = []
    for i, seg in enumerate(dream.segments):
        segment_info = {
            "order": seg.order,
            "modality": seg.modality,
            "transcription_status": seg.transcription_status,
            "has_transcript": bool(seg.transcript and seg.transcript.strip()),
            "transcript_length": len(seg.transcript) if seg.transcript else 0,
            "has_filename": bool(seg.filename),
            "filename": seg.filename,
            "has_s3_key": bool(seg.s3_key),
            "s3_key": seg.s3_key,
            "duration": seg.duration,
        }
        
        # Identify issues
        issues = []
        if seg.transcription_status == 'failed':
            issues.append("Transcription failed")
        if seg.modality == 'audio' and not seg.s3_key:
            issues.append("Missing S3 key")
        if seg.modality == 'audio' and not seg.transcript:
            issues.append("Missing transcript")
        
        segment_info["issues"] = issues
        segment_analysis.append(segment_info)
    
    # Overall dream analysis
    dream_issues = []
    if not dream.transcript:
        dream_issues.append("No transcript")
    if dream.state == 'draft':
        dream_issues.append("Still in draft state")
    
    recovery_suggestions = []
    failed_segments = [s for s in dream.segments if s.transcription_status == 'failed']
    completed_segments = [s for s in dream.segments if s.transcription_status == 'completed']
    
    if failed_segments:
        recovery_suggestions.append(f"Retry transcription for {len(failed_segments)} failed segments")
    if completed_segments:
        recovery_suggestions.append(f"Use partial recovery from {len(completed_segments)} successful segments")
    if not dream.segments:
        recovery_suggestions.append("Dream has no segments - likely corrupted sync")
    
    return {
        "dream_id": str(did),
        "user_id": str(user_id),
        "title": dream.title,
        "state": dream.state,
        "has_transcript": bool(dream.transcript and dream.transcript.strip()),
        "transcript_length": len(dream.transcript) if dream.transcript else 0,
        "created_at": dream.created_at.isoformat(),
        "segment_count": len(dream.segments),
        "segments": segment_analysis,
        "dream_issues": dream_issues,
        "recovery_suggestions": recovery_suggestions,
        "debug_timestamp": datetime.utcnow().isoformat()
    }

@router.post("/{did}/force-recovery")
async def force_dream_recovery(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Force attempt comprehensive recovery on a problematic dream."""
    logger.info(f"Force recovery endpoint called for dream {did}")
    
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    # Attempt recovery using the same logic as generate_analysis
    try:
        recovery_result = await svc._attempt_dream_recovery(user_id, did, dream, db)
        
        if recovery_result['success']:
            # Return updated dream status
            updated_dream = await svc.get_dream(user_id, did, db)
            return {
                "success": True,
                "method": recovery_result.get('method', 'unknown'),
                "message": "Dream recovery successful",
                "dream": {
                    "id": str(did),
                    "title": updated_dream.title if updated_dream else "Unknown",
                    "has_transcript": bool(updated_dream.transcript) if updated_dream else False,
                    "transcript_length": len(updated_dream.transcript) if updated_dream and updated_dream.transcript else 0,
                    "state": updated_dream.state if updated_dream else "unknown"
                }
            }
        else:
            return {
                "success": False,
                "error": recovery_result.get('error', 'Unknown error'),
                "message": "Dream recovery failed"
            }
            
    except Exception as e:
        logger.error(f"Force recovery failed for dream {did}: {str(e)}")
        raise HTTPException(500, f"Recovery process failed: {str(e)}")

@router.get("/{did}/segments/status")
async def get_segments_status(
    did: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session),
):
    """Get detailed status of all segments for a dream."""
    logger.info(f"Segments status endpoint called for dream {did}")
    
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    segments_status = []
    for seg in dream.segments:
        status = {
            "id": str(seg.id),
            "order": seg.order,
            "modality": seg.modality,
            "transcription_status": seg.transcription_status,
            "has_transcript": bool(seg.transcript and seg.transcript.strip()),
            "transcript_preview": seg.transcript[:100] + "..." if seg.transcript and len(seg.transcript) > 100 else seg.transcript,
            "filename": seg.filename,
            "s3_key": seg.s3_key,
            "duration": seg.duration,
            "can_retry": seg.transcription_status == 'failed' and bool(seg.s3_key)
        }
        segments_status.append(status)
    
    return {
        "dream_id": str(did),
        "total_segments": len(segments_status),
        "failed_count": len([s for s in segments_status if s["transcription_status"] == "failed"]),
        "completed_count": len([s for s in segments_status if s["transcription_status"] == "completed"]),
        "pending_count": len([s for s in segments_status if s["transcription_status"] == "pending"]),
        "segments": segments_status
    }

# ───────────────────────────── Background Tasks ──────────────────────────────

async def update_profile_after_dream(user_id: UUID, dream_id: UUID):
    """Background task to update profile after dream completion."""
    try:
        from new_backend_ruminate.infrastructure.db.bootstrap import session_scope
        
        logger.info(f"Starting background profile update for user {user_id} after dream {dream_id}")
        
        # Get services
        profile_svc = get_profile_service()
        dream_svc = get_dream_service()
        
        async with session_scope() as session:
            # Get the completed dream
            dream = await dream_svc.get_dream(user_id, dream_id, session)
                
            if dream and dream.summary:  # Only update if dream has been fully processed
                await profile_svc.update_dream_summary_on_completion(user_id, dream, session)
                logger.info(f"Successfully updated profile for user {user_id} after dream {dream_id} completion")
            else:
                logger.warning(f"Dream {dream_id} not found or not fully processed, skipping profile update")
                
    except Exception as e:
        logger.error(f"Background profile update failed for user {user_id}, dream {dream_id}: {str(e)}")
        # Don't raise - background tasks should not fail the main request