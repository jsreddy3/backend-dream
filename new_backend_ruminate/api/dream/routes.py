# new_backend_ruminate/api/dream/routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi.responses import StreamingResponse
from typing import List
import logging

from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub
from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.object_storage.repo import ObjectStorageRepository
from new_backend_ruminate.dependencies import (
    get_session,
    get_event_hub,
    get_dream_service,
    get_storage_service,
    get_current_user_id,
)
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
    # Manually serialize to include video_s3_key
    return [DreamRead.model_validate(dream).model_dump() for dream in dreams]

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
    return DreamRead.model_validate(dream).model_dump()

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
    print(f"Generated upload URL {url} with key {key}")
    return UploadUrlResponse(upload_url=url, upload_key=key)

# ─────────────────────── finish & video complete ────────────────────── #

@router.post("/{did}/finish", response_model=DreamRead)
async def finish_dream(
    did: UUID, 
    user_id: UUID = Depends(get_current_user_id), 
    svc: DreamService = Depends(get_dream_service),
    db: AsyncSession = Depends(get_session)
):
    logger.info(f"Finish dream endpoint called for dream {did}")
    await svc.finish_dream(user_id, did)
    logger.info(f"Dream {did} finished, transcription and summary generation completed")
    
    # Return the updated dream with generated title and summary
    dream = await svc.get_dream(user_id, did, db)
    if not dream:
        raise HTTPException(404, "Dream not found")
    
    return DreamRead.model_validate(dream).model_dump()

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
    if not dream:
        raise HTTPException(400, "Failed to generate summary. Check if transcript is available.")
    
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
    
    if not dream or not dream.analysis:
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