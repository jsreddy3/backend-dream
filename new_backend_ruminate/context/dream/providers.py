"""Context providers for dream analysis."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.dream.repo import DreamRepository
from new_backend_ruminate.domain.dream.entities.dream import Dream


class DreamTranscriptProvider:
    """Provides dream transcript and basic metadata."""
    
    def __init__(self, dream_repo: DreamRepository):
        self._repo = dream_repo
        
    async def get_transcript(self, user_id: UUID, dream_id: UUID, session: AsyncSession) -> Optional[str]:
        """Get the dream transcript."""
        return await self._repo.get_transcript(user_id, dream_id, session)
        
    async def get_dream(self, user_id: UUID, dream_id: UUID, session: AsyncSession) -> Optional[Dream]:
        """Get the full dream entity."""
        return await self._repo.get_dream(user_id, dream_id, session)


class DreamMetadataProvider:
    """Provides dream metadata like title, summary, additional info."""
    
    def __init__(self, dream_repo: DreamRepository):
        self._repo = dream_repo
        
    async def get_metadata(self, user_id: UUID, dream_id: UUID, session: AsyncSession) -> Dict[str, Any]:
        """Get dream metadata."""
        dream = await self._repo.get_dream(user_id, dream_id, session)
        if not dream:
            return {}
            
        return {
            "title": dream.title,
            "summary": dream.summary,
            "additional_info": dream.additional_info,
            "created_at": dream.created_at,
            "state": dream.state
        }


class DreamAnswersProvider:
    """Provides interpretation answers for the dream."""
    
    def __init__(self, dream_repo: DreamRepository):
        self._repo = dream_repo
        
    async def get_answers(self, user_id: UUID, dream_id: UUID, session: AsyncSession) -> List[Dict[str, Any]]:
        """Get interpretation answers with their questions."""
        questions = await self._repo.get_interpretation_questions(user_id, dream_id, session)
        answers = await self._repo.get_interpretation_answers(user_id, dream_id, session)
        
        # Create a mapping of question_id to answer
        answer_map = {answer.question_id: answer for answer in answers}
        
        # Format the Q&A pairs
        formatted_answers = []
        for question in questions:
            if question.id in answer_map:
                answer = answer_map[question.id]
                formatted_answers.append({
                    "question_text": question.question_text,
                    "answer_text": answer.custom_answer if answer.custom_answer else self._get_selected_choice_text(question, answer.selected_choice_id),
                    "question_order": question.question_order
                })
                
        return sorted(formatted_answers, key=lambda x: x.get("question_order", 0))
    
    def _get_selected_choice_text(self, question, choice_id) -> str:
        """Get the text of the selected choice."""
        for choice in question.choices:
            if choice.id == choice_id:
                return choice.choice_text
        return ""


class DreamAnalysisProvider:
    """Provides existing analysis data."""
    
    def __init__(self, dream_repo: DreamRepository):
        self._repo = dream_repo
        
    async def get_analysis(self, user_id: UUID, dream_id: UUID, session: AsyncSession) -> Dict[str, Any]:
        """Get existing analysis and metadata."""
        dream = await self._repo.get_dream(user_id, dream_id, session)
        if not dream:
            return {}
            
        return {
            "analysis": dream.analysis,
            "analysis_metadata": dream.analysis_metadata,
            "expanded_analysis": dream.expanded_analysis,
            "expanded_analysis_metadata": dream.expanded_analysis_metadata
        }