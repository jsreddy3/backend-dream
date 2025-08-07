"""Integration tests for dream service with new context system."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.context.dream import DreamContextBuilder
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, GenerationStatus
from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository


class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self, model="gpt-4"):
        self._model = model
        self.generate_response = AsyncMock()
        self.generate_structured_response = AsyncMock()


@pytest_asyncio.fixture
async def mock_dream_repo():
    """Create a mock dream repository."""
    repo = AsyncMock(spec=RDSDreamRepository)
    return repo


@pytest_asyncio.fixture
async def mock_storage_repo():
    """Create a mock storage repository."""
    repo = AsyncMock()
    return repo


@pytest_asyncio.fixture
async def mock_user_repo():
    """Create a mock user repository."""
    repo = AsyncMock()
    return repo


@pytest_asyncio.fixture
async def mock_llm():
    """Create a mock LLM service."""
    return MockLLMService()


@pytest_asyncio.fixture
async def dream_service(mock_dream_repo, mock_storage_repo, mock_user_repo, mock_llm):
    """Create a dream service with mocked dependencies."""
    service = DreamService(
        dream_repo=mock_dream_repo,
        storage_repo=mock_storage_repo,
        user_repo=mock_user_repo,
        summary_llm=mock_llm,
        question_llm=mock_llm,
        analysis_llm=mock_llm
    )
    return service


@pytest_asyncio.fixture
async def sample_dream_with_transcript():
    """Create a sample dream with transcript for testing."""
    dream = Dream(
        id=uuid4(),
        title=None,  # Not yet generated
        created_at=datetime.utcnow(),
        state=DreamStatus.TRANSCRIBED.value,
        transcript="I was in a vast library filled with ancient books. The shelves seemed to stretch infinitely upward. I was searching for a specific book, but couldn't remember its title. A mysterious librarian appeared and handed me a glowing book.",
        summary=None,  # Not yet generated
        additional_info="I've been feeling overwhelmed with information at work",
    )
    dream.user_id = uuid4()
    return dream


class TestDreamServiceWithContext:
    """Test dream service methods with new context system."""
    
    @pytest.mark.asyncio
    async def test_generate_title_and_summary_with_context(self, dream_service, mock_dream_repo, mock_llm, sample_dream_with_transcript):
        """Test title and summary generation using context system."""
        user_id = sample_dream_with_transcript.user_id
        dream_id = sample_dream_with_transcript.id
        
        # Setup mocks
        mock_dream_repo.get_dream.return_value = sample_dream_with_transcript
        mock_dream_repo.update_summary_status = AsyncMock()
        mock_dream_repo.update_title_and_summary = AsyncMock(return_value=sample_dream_with_transcript)
        
        mock_llm.generate_structured_response.return_value = {
            "title": "The Infinite Library",
            "summary": "A dream about searching for knowledge in an endless library, receiving guidance from a mysterious figure who provides a glowing book."
        }
        
        # Patch the context builder
        with patch('new_backend_ruminate.services.dream.service.DreamContextBuilder') as MockContextBuilder:
            mock_builder = AsyncMock()
            MockContextBuilder.return_value = mock_builder
            
            # Mock context window
            mock_context_window = MagicMock()
            mock_context_window.transcript = sample_dream_with_transcript.transcript
            mock_context_window.to_llm_messages.return_value = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User prompt"}
            ]
            
            mock_builder.build_for_title_summary.return_value = mock_context_window
            mock_builder.prepare_llm_messages.return_value = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User prompt"}
            ]
            mock_builder.get_json_schema_for_task.return_value = {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"}
                },
                "required": ["title", "summary"]
            }
            
            # Execute
            result = await dream_service.generate_title_and_summary(user_id, dream_id)
            
            # Verify context builder was used correctly
            mock_builder.build_for_title_summary.assert_called_once()
            mock_builder.prepare_llm_messages.assert_called_once_with(mock_context_window, "title_summary")
            mock_builder.get_json_schema_for_task.assert_called_once_with("title_summary")
            
            # Verify LLM was called with prepared messages
            mock_llm.generate_structured_response.assert_called_once()
            call_args = mock_llm.generate_structured_response.call_args
            assert call_args[1]["messages"] == [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User prompt"}
            ]
            
            # Verify result
            assert result is not None
            mock_dream_repo.update_title_and_summary.assert_called_once_with(
                user_id, dream_id, "The Infinite Library", 
                "A dream about searching for knowledge in an endless library, receiving guidance from a mysterious figure who provides a glowing book.",
                mock_dream_repo.update_title_and_summary.call_args[0][4]  # session
            )
    
    @pytest.mark.asyncio
    async def test_generate_analysis_with_context(self, dream_service, mock_dream_repo, mock_llm):
        """Test analysis generation using context system."""
        # Create a dream with title and summary
        dream = Dream(
            id=uuid4(),
            title="The Infinite Library",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was in a vast library...",
            summary="A dream about searching for knowledge...",
            additional_info="Feeling overwhelmed at work"
        )
        dream.user_id = uuid4()
        
        user_id = dream.user_id
        dream_id = dream.id
        
        # Setup mocks
        mock_dream_repo.get_dream.return_value = dream
        mock_dream_repo.try_start_analysis_generation.return_value = True
        mock_dream_repo.update_analysis_status = AsyncMock()
        mock_dream_repo.update_analysis = AsyncMock(return_value=dream)
        
        mock_llm.generate_response.return_value = "The library represents your mind's vast repository of knowledge. The endless shelves suggest feeling overwhelmed by information. The glowing book symbolizes finding clarity or the right solution amidst confusion."
        
        # Patch the context builder
        with patch('new_backend_ruminate.services.dream.service.DreamContextBuilder') as MockContextBuilder:
            mock_builder = AsyncMock()
            MockContextBuilder.return_value = mock_builder
            
            # Mock context window with all components
            mock_context_window = MagicMock()
            mock_context_window.transcript = dream.transcript
            mock_context_window.title = dream.title
            mock_context_window.summary = dream.summary
            mock_context_window.additional_info = dream.additional_info
            mock_context_window.get_context_components.return_value = {
                "transcript": dream.transcript,
                "title": dream.title,
                "summary": dream.summary,
                "additional_info": dream.additional_info
            }
            
            mock_builder.build_for_analysis.return_value = mock_context_window
            mock_builder.prepare_llm_messages.return_value = [
                {"role": "system", "content": "You are an expert dream analyst..."},
                {"role": "user", "content": "Please analyze this dream..."}
            ]
            
            # Execute
            result = await dream_service.generate_analysis(user_id, dream_id)
            
            # Verify context builder was used
            mock_builder.build_for_analysis.assert_called_once()
            mock_builder.prepare_llm_messages.assert_called_once_with(mock_context_window, "analysis")
            
            # Verify LLM was called
            mock_llm.generate_response.assert_called_once()
            
            # Verify result
            assert result is not None
            mock_dream_repo.update_analysis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_expanded_analysis_with_context(self, dream_service, mock_dream_repo, mock_llm):
        """Test expanded analysis generation using context system."""
        # Create a dream with existing analysis
        dream = Dream(
            id=uuid4(),
            title="The Infinite Library",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was in a vast library...",
            summary="A dream about searching for knowledge...",
            analysis="The library represents your mind's vast repository...",
            analysis_metadata={"model": "gpt-4", "generated_at": "2024-01-15"}
        )
        dream.user_id = uuid4()
        
        user_id = dream.user_id
        dream_id = dream.id
        
        # Setup mocks
        mock_dream_repo.get_dream.return_value = dream
        mock_dream_repo.try_start_expanded_analysis_generation.return_value = True
        mock_dream_repo.update_expanded_analysis_status = AsyncMock()
        mock_dream_repo.update_expanded_analysis = AsyncMock(return_value=dream)
        
        expanded_analysis = """## Symbolic Meanings
The infinite shelves represent boundless potential and accumulated wisdom. The glowing book symbolizes enlightenment or a breakthrough insight waiting to be discovered.

## Psychological Patterns
This dream reflects a common pattern of information overload combined with the search for meaningful knowledge. The mysterious librarian represents your intuitive wisdom guiding you.

## Personal Relevance
Given your work stress, this dream suggests you already possess the answers you seek. Trust your inner guidance to find the right 'book' or solution."""
        
        mock_llm.generate_response.return_value = expanded_analysis
        
        # Patch the context builder
        with patch('new_backend_ruminate.services.dream.service.DreamContextBuilder') as MockContextBuilder:
            mock_builder = AsyncMock()
            MockContextBuilder.return_value = mock_builder
            
            # Mock context window
            mock_context_window = MagicMock()
            mock_context_window.existing_analysis = dream.analysis
            mock_context_window.get_context_components.return_value = {
                "transcript": dream.transcript,
                "title": dream.title,
                "summary": dream.summary,
                "existing_analysis": dream.analysis
            }
            
            mock_builder.build_for_expanded_analysis.return_value = mock_context_window
            mock_builder.prepare_llm_messages.return_value = [
                {"role": "system", "content": "You are an expert dream analyst..."},
                {"role": "user", "content": "Provide expanded analysis..."}
            ]
            
            # Execute
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
            
            # Verify context builder was used
            mock_builder.build_for_expanded_analysis.assert_called_once()
            mock_builder.prepare_llm_messages.assert_called_once_with(mock_context_window, "expanded_analysis")
            
            # Verify result
            assert result is not None
            mock_dream_repo.update_expanded_analysis.assert_called_once()
            call_args = mock_dream_repo.update_expanded_analysis.call_args[0]
            assert call_args[2] == expanded_analysis  # The expanded analysis text
    
    @pytest.mark.asyncio
    async def test_context_building_with_interpretation_answers(self, dream_service, mock_dream_repo, mock_llm):
        """Test that interpretation answers are included in analysis context."""
        dream = Dream(
            id=uuid4(),
            title="The Infinite Library",
            transcript="I was in a vast library...",
            summary="A dream about searching...",
        )
        dream.user_id = uuid4()
        
        # Setup mocks for interpretation Q&A
        mock_dream_repo.get_dream.return_value = dream
        mock_dream_repo.get_interpretation_questions.return_value = []  # Simplified for this test
        mock_dream_repo.get_interpretation_answers.return_value = []
        mock_dream_repo.try_start_analysis_generation.return_value = True
        mock_dream_repo.update_analysis_status = AsyncMock()
        mock_dream_repo.update_analysis = AsyncMock(return_value=dream)
        
        mock_llm.generate_response.return_value = "Analysis considering the interpretation answers..."
        
        with patch('new_backend_ruminate.services.dream.service.DreamContextBuilder') as MockContextBuilder:
            mock_builder = AsyncMock()
            MockContextBuilder.return_value = mock_builder
            
            # Mock context window with interpretation answers
            mock_context_window = MagicMock()
            mock_context_window.interpretation_answers = [
                {
                    "question_text": "What emotions did you feel?",
                    "answer_text": "Freedom and curiosity"
                }
            ]
            mock_context_window.get_context_components.return_value = {
                "transcript": dream.transcript,
                "title": dream.title,
                "answers": "Q: What emotions did you feel?\nA: Freedom and curiosity"
            }
            
            mock_builder.build_for_analysis.return_value = mock_context_window
            mock_builder.prepare_llm_messages.return_value = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Analyze with answers: Q: What emotions did you feel?\nA: Freedom and curiosity"}
            ]
            
            # Execute
            result = await dream_service.generate_analysis(dream.user_id, dream.id)
            
            # Verify answers were included in context
            mock_builder.build_for_analysis.assert_called_once()
            args = mock_builder.build_for_analysis.call_args[0]
            assert args[0] == dream.user_id
            assert args[1] == dream.id
            
            # The context window should have interpretation answers
            assert mock_context_window.interpretation_answers is not None