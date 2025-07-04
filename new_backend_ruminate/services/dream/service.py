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
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, VideoStatus
from new_backend_ruminate.domain.dream.entities.segments import Segment
from new_backend_ruminate.domain.dream.entities.interpretation import InterpretationQuestion, InterpretationChoice, InterpretationAnswer
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
        question_llm: Optional[LLMService] = None,
        analysis_llm: Optional[LLMService] = None,
    ) -> None:
        self._repo = dream_repo
        self._storage = storage_repo
        self._user_repo = user_repo
        self._transcribe = transcription_svc
        self._hub = event_hub
        self._summary_llm = summary_llm
        self._question_llm = question_llm
        self._analysis_llm = analysis_llm

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

    async def update_additional_info(self, user_id: UUID, did: UUID, additional_info: str, session: AsyncSession) -> Optional[Dream]:
        return await self._repo.update_additional_info(user_id, did, additional_info, session)

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

    async def generate_interpretation_questions(
        self, 
        user_id: UUID, 
        did: UUID, 
        session: AsyncSession,
        num_questions: int = 3,
        num_choices: int = 3
    ) -> List[InterpretationQuestion]:
        """Generate interpretation questions with multiple choice answers."""
        if not self._question_llm:
            logger.warning("Question LLM service not available, cannot generate questions")
            return []
        
        # Get the dream, transcript, and summary
        dream = await self._repo.get_dream(user_id, did, session)
        if not dream:
            logger.error(f"Dream {did} not found for user {user_id}")
            return []
        
        if not dream.transcript:
            logger.error(f"No transcript available for dream {did}")
            return []
        
        # Check if questions already exist
        existing_questions = await self._repo.get_interpretation_questions(user_id, did, session)
        if existing_questions:
            logger.info(f"Questions already exist for dream {did}, returning existing questions")
            return existing_questions
        
        logger.info(f"Generating {num_questions} interpretation questions for dream {did}")
        
        # Prepare the prompt
        messages = [
            {"role": "system", "content": """You are a dream interpretation assistant that helps users gain deeper insights into their dreams. 
Your task is to generate thoughtful questions about specific elements of the dream that are necessary to understand the dream."""},
            {"role": "user", "content": f"""Based on this dream, generate {num_questions} insightful questions to help the dreamer explore its meaning.

Dream transcript:
{dream.transcript}

For each question, also provide {num_choices} possible answer options that you think the dreamer is likely to choose.

Return a JSON array with this structure:
[
  {{
    "question": "The question text",
    "choices": ["First choice", "Second choice", "Third choice"]
  }},
  ...
]"""}
        ]
        
        # Define the JSON schema
        json_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "A thoughtful question about a specific element in the dream"
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": num_choices,
                        "maxItems": num_choices,
                        "description": "Possible interpretations or meanings"
                    }
                },
                "required": ["question", "choices"]
            },
            "minItems": num_questions,
            "maxItems": num_questions
        }
        
        try:
            # Generate questions using the question LLM
            result = await self._question_llm.generate_structured_response(
                messages=messages,
                response_format={"type": "json_object"},
                json_schema={"type": "object", "properties": {"questions": json_schema}, "required": ["questions"]}
            )
            
            # Extract questions array (handle both direct array and wrapped object)
            questions_data = result.get("questions", result) if isinstance(result, dict) else result
            if not isinstance(questions_data, list):
                logger.error(f"Invalid response format from LLM: {result}")
                return []
            
            # Create question entities
            questions = []
            for idx, q_data in enumerate(questions_data):
                question = InterpretationQuestion(
                    dream_id=did,
                    question_text=q_data["question"],
                    question_order=idx + 1
                )
                
                # Add choices
                question.choices = []
                for choice_idx, choice_text in enumerate(q_data["choices"]):
                    choice = InterpretationChoice(
                        choice_text=choice_text,
                        choice_order=choice_idx + 1,
                        is_custom=False
                    )
                    question.choices.append(choice)
                
                # Add custom answer option
                custom_choice = InterpretationChoice(
                    choice_text="Other (please specify)",
                    choice_order=len(q_data["choices"]) + 1,
                    is_custom=True
                )
                question.choices.append(custom_choice)
                
                questions.append(question)
            
            # Save questions to database
            saved_questions = await self._repo.create_interpretation_questions(user_id, did, questions, session)
            logger.info(f"Generated and saved {len(saved_questions)} interpretation questions for dream {did}")
            
            return saved_questions
            
        except Exception as e:
            logger.error(f"Failed to generate interpretation questions for dream {did}: {str(e)}")
            return []

    async def record_interpretation_answer(
        self,
        user_id: UUID,
        question_id: UUID,
        choice_id: Optional[UUID],
        custom_answer: Optional[str],
        session: AsyncSession
    ) -> Optional[InterpretationAnswer]:
        """Record a user's answer to an interpretation question."""
        # Create answer entity
        answer = InterpretationAnswer(
            question_id=question_id,
            user_id=user_id,
            selected_choice_id=choice_id,
            custom_answer=custom_answer
        )
        
        try:
            saved_answer = await self._repo.record_interpretation_answer(user_id, answer, session)
            logger.info(f"Recorded answer for question {question_id} by user {user_id}")
            return saved_answer
        except Exception as e:
            logger.error(f"Failed to record answer: {str(e)}")
            return None

    async def get_interpretation_questions(self, user_id: UUID, did: UUID, session: AsyncSession) -> List[InterpretationQuestion]:
        """Get all interpretation questions for a dream."""
        return await self._repo.get_interpretation_questions(user_id, did, session)

    async def get_interpretation_answers(self, user_id: UUID, did: UUID, session: AsyncSession) -> List[InterpretationAnswer]:
        """Get all interpretation answers for a dream by the user."""
        return await self._repo.get_interpretation_answers(user_id, did, session)

    async def generate_analysis(
        self, 
        user_id: UUID, 
        did: UUID, 
        session: AsyncSession,
        force_regenerate: bool = False
    ) -> Optional[Dream]:
        """Generate comprehensive dream analysis using all available information."""
        if not self._analysis_llm:
            logger.warning("Analysis LLM service not available, cannot generate analysis")
            return None
        
        # Get the dream and all related data
        dream = await self._repo.get_dream(user_id, did, session)
        if not dream:
            logger.error(f"Dream {did} not found for user {user_id}")
            return None
        
        # Check if analysis already exists and not forcing regeneration
        if dream.analysis and not force_regenerate:
            logger.info(f"Analysis already exists for dream {did}, returning existing analysis")
            return dream
        
        # Validate prerequisites
        if not dream.transcript:
            logger.error(f"No transcript available for dream {did}, cannot generate analysis")
            return None
        
        logger.info(f"Generating analysis for dream {did}")
        
        # Get questions and answers
        questions = await self._repo.get_interpretation_questions(user_id, did, session)
        answers = await self._repo.get_interpretation_answers(user_id, did, session)
        
        # Create a mapping of question_id to answer for easy lookup
        answer_map = {answer.question_id: answer for answer in answers}
        
        # Build the comprehensive context
        context_parts = []
        
        # 1. Basic dream information
        context_parts.append(f"Dream Title: {dream.title or 'Untitled'}")
        context_parts.append(f"\nOriginal Dream Transcript:\n{dream.transcript}")
        
        if dream.summary:
            context_parts.append(f"\nSummary:\n{dream.summary}")
        
        # 2. Interpretation questions and answers
        if questions:
            context_parts.append("\nInterpretation Questions and Responses:")
            for question in questions:
                context_parts.append(f"\nQ: {question.question_text}")
                
                if question.id in answer_map:
                    answer = answer_map[question.id]
                    if answer.custom_answer:
                        context_parts.append(f"A: {answer.custom_answer}")
                    elif answer.selected_choice_id:
                        # Find the selected choice
                        selected_choice = next(
                            (c for c in question.choices if c.id == answer.selected_choice_id),
                            None
                        )
                        if selected_choice:
                            context_parts.append(f"A: {selected_choice.choice_text}")
                else:
                    context_parts.append("A: (No response provided)")
        
        # 3. Additional information
        if dream.additional_info:
            context_parts.append(f"\nAdditional Context:\n{dream.additional_info}")
        
        # Prepare the analysis prompt
        messages = [
            {"role": "system", "content": """You are an expert dream analyst who helps people understand the deeper meanings and insights within their dreams. 
Your approach combines psychological understanding, symbolic interpretation, and personal context to provide meaningful insights.

IMPORTANT GUIDELINES:
- Base your analysis on the actual dream content and the dreamer's responses
- Consider both universal symbols and personal associations
- Be thoughtful and non-prescriptive - offer possibilities rather than definitive answers
- Connect dream elements to the dreamer's provided context when available
- Maintain a warm, professional, and insightful tone
- Avoid making assumptions about the dreamer's life beyond what they've shared
- Focus on themes, emotions, symbols, and potential personal significance"""},
            {"role": "user", "content": f"""Please provide a comprehensive analysis of this dream based on all the information provided:

{chr(10).join(context_parts)}

Create a thoughtful interpretation that:
1. Identifies key themes and symbols in the dream
2. Explores potential meanings based on the dreamer's responses
3. Considers emotional undertones and their significance
4. Connects elements to any personal context shared
5. Offers insights for self-reflection without being prescriptive

Please write the analysis in a warm, accessible style that invites further reflection."""}
        ]
        
        try:
            # Generate analysis using the analysis LLM
            analysis_text = await self._analysis_llm.generate_response(messages)
            
            # Prepare metadata
            metadata = {
                "model": getattr(self._analysis_llm, '_model', 'unknown'),
                "generated_at": datetime.utcnow().isoformat(),
                "has_answers": len(answers) > 0,
                "num_questions": len(questions),
                "num_answers": len(answers)
            }
            
            # Save analysis to database
            updated_dream = await self._repo.update_analysis(
                user_id, did, 
                analysis_text, 
                metadata, 
                session
            )
            
            logger.info(f"Generated and saved analysis for dream {did}")
            return updated_dream
            
        except Exception as e:
            logger.error(f"Failed to generate analysis for dream {did}: {str(e)}")
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
                