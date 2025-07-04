from abc import ABC, abstractmethod
from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from new_backend_ruminate.domain.dream.entities.dream import Dream
from new_backend_ruminate.domain.dream.entities.segments import Segment
from new_backend_ruminate.domain.dream.entities.interpretation import InterpretationQuestion, InterpretationChoice, InterpretationAnswer

class DreamRepository(ABC):
    # dreams
    @abstractmethod
    async def create_dream(self, user_id: UUID, dream: Dream, session: AsyncSession) -> Dream: ...
    @abstractmethod
    async def get_dream(self, user_id: Optional[UUID], did: UUID, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def list_dreams_by_user(self, user_id: UUID, session: AsyncSession) -> List[Dream]: ...
    @abstractmethod
    async def update_title(self, user_id: UUID, did: UUID, title: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def update_summary(self, user_id: UUID, did: UUID, summary: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def update_title_and_summary(self, user_id: UUID, did: UUID, title: str, summary: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def update_additional_info(self, user_id: UUID, did: UUID, additional_info: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def update_analysis(self, user_id: UUID, did: UUID, analysis: str, metadata: dict, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def set_state(self, user_id: UUID, did: UUID, state: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def update_summary_status(self, user_id: UUID, did: UUID, status: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def try_start_summary_generation(self, user_id: UUID, did: UUID, session: AsyncSession) -> bool: ...
    @abstractmethod
    async def update_questions_status(self, user_id: UUID, did: UUID, status: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def try_start_questions_generation(self, user_id: UUID, did: UUID, session: AsyncSession) -> bool: ...
    @abstractmethod
    async def update_analysis_status(self, user_id: UUID, did: UUID, status: str, session: AsyncSession) -> Optional[Dream]: ...
    @abstractmethod
    async def try_start_analysis_generation(self, user_id: UUID, did: UUID, session: AsyncSession) -> bool: ...
    @abstractmethod
    async def delete_dream(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[Dream]: ...

    # segments
    @abstractmethod
    async def create_segment(self, user_id: UUID, segment: Segment, session: AsyncSession) -> Segment: ...
    @abstractmethod
    async def get_segment(self, user_id: UUID, did: UUID, sid: UUID, session: AsyncSession) -> Optional[Segment]: ...
    @abstractmethod
    async def delete_segment(self, user_id: UUID, did: UUID, sid: UUID, session: AsyncSession) -> Optional[Segment]: ...
    @abstractmethod
    async def update_segment_transcript(self, user_id: UUID, did: UUID, sid: UUID, transcript: str, session: AsyncSession) -> Optional[Segment]: ...
    @abstractmethod
    async def update_segment_transcription_status(self, user_id: UUID, did: UUID, sid: UUID, status: str, session: AsyncSession) -> Optional[Segment]: ...
    
    # getters
    @abstractmethod
    async def get_video_url(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]: ...
    @abstractmethod
    async def get_transcript(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]: ...
    @abstractmethod
    async def get_audio_url(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]: ...
    @abstractmethod
    async def get_status(self, user_id: UUID, did: UUID, session: AsyncSession) -> Optional[str]: ...
    
    # interpretation questions
    @abstractmethod
    async def create_interpretation_questions(self, user_id: UUID, did: UUID, questions: List[InterpretationQuestion], session: AsyncSession) -> List[InterpretationQuestion]: ...
    @abstractmethod
    async def get_interpretation_questions(self, user_id: UUID, did: UUID, session: AsyncSession) -> List[InterpretationQuestion]: ...
    @abstractmethod
    async def record_interpretation_answer(self, user_id: UUID, answer: InterpretationAnswer, session: AsyncSession) -> InterpretationAnswer: ...
    @abstractmethod
    async def get_interpretation_answers(self, user_id: UUID, did: UUID, session: AsyncSession) -> List[InterpretationAnswer]: ...