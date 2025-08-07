"""Dream context builder orchestrates all providers."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.dream.repo import DreamRepository
from .providers import (
    DreamTranscriptProvider,
    DreamMetadataProvider,
    DreamAnswersProvider,
    DreamAnalysisProvider
)
from .context_window import DreamContextWindow
from .prompts import DreamPrompts

logger = logging.getLogger(__name__)


class DreamContextBuilder:
    """Orchestrates context building for dream analysis."""
    
    def __init__(self, dream_repo: DreamRepository):
        self._repo = dream_repo
        self._transcript_provider = DreamTranscriptProvider(dream_repo)
        self._metadata_provider = DreamMetadataProvider(dream_repo)
        self._answers_provider = DreamAnswersProvider(dream_repo)
        self._analysis_provider = DreamAnalysisProvider(dream_repo)
        
    async def build_for_title_summary(
        self, 
        user_id: UUID, 
        dream_id: UUID, 
        session: AsyncSession
    ) -> Optional[DreamContextWindow]:
        """Build context for title and summary generation."""
        logger.debug(f"Building context for title/summary generation for dream {dream_id}")
        
        # Get the dream and transcript
        dream = await self._transcript_provider.get_dream(user_id, dream_id, session)
        if not dream:
            logger.error(f"No dream found for {dream_id}")
            return None
        
        # For title/summary, we allow building context even without transcript
        # The service will handle waiting for transcription if needed
        return DreamContextWindow(
            dream_id=str(dream_id),
            user_id=str(user_id),
            transcript=dream.transcript,  # May be None
            created_at=dream.created_at,
            task_type="title_summary"
        )
    
    async def build_for_analysis(
        self,
        user_id: UUID,
        dream_id: UUID,
        session: AsyncSession,
        include_answers: bool = True
    ) -> Optional[DreamContextWindow]:
        """Build context for dream analysis generation."""
        logger.debug(f"Building context for analysis generation for dream {dream_id}")
        
        # Fetch all components concurrently
        dream_task = self._transcript_provider.get_dream(user_id, dream_id, session)
        metadata_task = self._metadata_provider.get_metadata(user_id, dream_id, session)
        
        tasks = [dream_task, metadata_task]
        if include_answers:
            answers_task = self._answers_provider.get_answers(user_id, dream_id, session)
            tasks.append(answers_task)
            
        results = await asyncio.gather(*tasks)
        dream = results[0]
        metadata = results[1]
        answers = results[2] if include_answers else None
        
        if not dream or not dream.transcript:
            logger.error(f"No dream or transcript found for {dream_id}")
            return None
            
        return DreamContextWindow(
            dream_id=str(dream_id),
            user_id=str(user_id),
            transcript=dream.transcript,
            title=metadata.get("title"),
            summary=metadata.get("summary"),
            additional_info=metadata.get("additional_info"),
            created_at=dream.created_at,
            interpretation_answers=answers,
            task_type="analysis"
        )
    
    async def build_for_expanded_analysis(
        self,
        user_id: UUID,
        dream_id: UUID,
        session: AsyncSession
    ) -> Optional[DreamContextWindow]:
        """Build context for expanded analysis generation."""
        logger.debug(f"Building context for expanded analysis generation for dream {dream_id}")
        
        # Fetch all components including existing analysis
        dream_task = self._transcript_provider.get_dream(user_id, dream_id, session)
        metadata_task = self._metadata_provider.get_metadata(user_id, dream_id, session)
        analysis_task = self._analysis_provider.get_analysis(user_id, dream_id, session)
        
        dream, metadata, analysis_data = await asyncio.gather(
            dream_task, metadata_task, analysis_task
        )
        
        if not dream or not dream.transcript:
            logger.error(f"No dream or transcript found for {dream_id}")
            return None
            
        if not analysis_data.get("analysis"):
            logger.error(f"No existing analysis found for {dream_id}")
            return None
            
        return DreamContextWindow(
            dream_id=str(dream_id),
            user_id=str(user_id),
            transcript=dream.transcript,
            title=metadata.get("title"),
            summary=metadata.get("summary"),
            additional_info=metadata.get("additional_info"),
            created_at=dream.created_at,
            existing_analysis=analysis_data.get("analysis"),
            existing_analysis_metadata=analysis_data.get("analysis_metadata"),
            task_type="expanded_analysis"
        )
    
    def prepare_llm_messages(
        self, 
        context_window: DreamContextWindow,
        task_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Prepare LLM messages based on context window and task type."""
        task_type = task_type or context_window.task_type
        
        # Get appropriate prompts
        if task_type == "title_summary":
            system_prompt = DreamPrompts.TITLE_SUMMARY_SYSTEM
            user_prompt = DreamPrompts.TITLE_SUMMARY_USER.format(
                transcript=context_window.transcript
            )
        elif task_type == "analysis":
            system_prompt = DreamPrompts.ANALYSIS_SYSTEM
            components = context_window.get_context_components()
            context = DreamPrompts.build_context(components)
            user_prompt = DreamPrompts.ANALYSIS_USER.format(context=context)
        elif task_type == "expanded_analysis":
            system_prompt = DreamPrompts.EXPANDED_ANALYSIS_SYSTEM
            components = context_window.get_context_components()
            # Remove existing_analysis from general context since it's handled separately
            existing_analysis = components.pop("existing_analysis", "")
            context = DreamPrompts.build_context(components)
            user_prompt = DreamPrompts.EXPANDED_ANALYSIS_USER.format(
                context=context,
                existing_analysis=existing_analysis
            )
        else:
            raise ValueError(f"Unknown task type: {task_type}")
            
        return context_window.to_llm_messages(system_prompt, user_prompt)
    
    def get_json_schema_for_task(self, task_type: str) -> Optional[Dict[str, Any]]:
        """Get the JSON schema for structured responses."""
        if task_type == "title_summary":
            return {
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
        elif task_type == "questions":
            return {
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
                            "description": "Possible interpretations or meanings"
                        }
                    },
                    "required": ["question", "choices"]
                }
            }
        return None