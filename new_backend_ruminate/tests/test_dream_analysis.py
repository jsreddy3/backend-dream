"""Comprehensive tests for dream analysis generation."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, GenerationStatus
from new_backend_ruminate.domain.dream.entities.interpretation import (
    InterpretationQuestion,
    InterpretationChoice,
    InterpretationAnswer
)
from new_backend_ruminate.context.dream import DreamContextWindow
from llm_test_utils import LLMTestHelper


class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self, model="gpt-5-mini"):
        self._model = model
        self.generate_response = AsyncMock()
        self.generate_structured_response = AsyncMock()


@pytest_asyncio.fixture
async def mock_repos():
    """Create mock repositories."""
    return {
        'dream_repo': AsyncMock(),
        'storage_repo': AsyncMock(),
        'user_repo': AsyncMock()
    }


@pytest_asyncio.fixture
async def mock_llm():
    """Create a mock LLM service."""
    return MockLLMService()


@pytest_asyncio.fixture
async def dream_service(mock_repos, mock_llm):
    """Create a dream service with mocked dependencies."""
    service = DreamService(
        dream_repo=mock_repos['dream_repo'],
        storage_repo=mock_repos['storage_repo'],
        user_repo=mock_repos['user_repo'],
        summary_llm=mock_llm,
        question_llm=mock_llm,
        analysis_llm=mock_llm
    )
    return service


@pytest_asyncio.fixture
async def sample_dream():
    """Create a comprehensive sample dream."""
    dream = Dream(
        id=uuid4(),
        title="The Infinite Library",
        created_at=datetime.utcnow(),
        state=DreamStatus.TRANSCRIBED.value,
        transcript="I was in a vast library with towering shelves that seemed to stretch infinitely upward. I was searching for a specific book but couldn't remember its title. A mysterious librarian appeared and handed me a glowing book that contained all my forgotten memories.",
        summary="A dream about exploring an infinite library and receiving a book of forgotten memories from a mysterious librarian.",
        additional_info="I've been feeling overwhelmed with information at work lately and struggling to remember important details."
    )
    dream.user_id = uuid4()
    return dream


@pytest_asyncio.fixture
async def sample_questions_and_answers():
    """Create sample interpretation questions and answers."""
    q1 = InterpretationQuestion(
        id=uuid4(),
        dream_id=uuid4(),
        question_text="What emotions did you feel in the library?",
        question_order=1
    )
    q1.choices = [
        InterpretationChoice(id=uuid4(), choice_text="Wonder and curiosity", choice_order=1),
        InterpretationChoice(id=uuid4(), choice_text="Anxiety and confusion", choice_order=2),
        InterpretationChoice(id=uuid4(), choice_text="Peace and tranquility", choice_order=3),
    ]
    
    q2 = InterpretationQuestion(
        id=uuid4(),
        dream_id=uuid4(),
        question_text="What do books represent to you?",
        question_order=2
    )
    q2.choices = [
        InterpretationChoice(id=uuid4(), choice_text="Knowledge and wisdom", choice_order=1),
        InterpretationChoice(id=uuid4(), choice_text="Escape and fantasy", choice_order=2),
        InterpretationChoice(id=uuid4(), choice_text="Memory and nostalgia", choice_order=3),
    ]
    
    # Answers
    a1 = InterpretationAnswer(
        id=uuid4(),
        question_id=q1.id,
        user_id=uuid4(),
        selected_choice_id=q1.choices[0].id,  # "Wonder and curiosity"
        custom_answer=None
    )
    
    a2 = InterpretationAnswer(
        id=uuid4(),
        question_id=q2.id,
        user_id=uuid4(),
        selected_choice_id=None,
        custom_answer="Books represent my desire to understand myself better and recover lost parts of my identity"
    )
    
    return [q1, q2], [a1, a2]


class TestGenerateAnalysis:
    """Comprehensive test battery for generate_analysis function."""
    
    @pytest.mark.asyncio
    async def test_successful_analysis_with_all_context(self, dream_service, mock_repos, mock_llm, sample_dream):
        """Test successful analysis generation with full context including interpretation answers."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=sample_dream)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        expected_analysis = "The infinite library represents your mind's vast repository of knowledge and memories. The towering shelves suggest feeling overwhelmed by information, while the mysterious librarian symbolizes your inner wisdom guiding you toward self-discovery. The glowing book of forgotten memories indicates a desire to reconnect with lost aspects of yourself, particularly given your current work stress and memory concerns."
        
        mock_llm.generate_response.return_value = expected_analysis
        
        # Execute
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id)
        
        # Verify
        assert result is not None
        mock_llm.generate_response.assert_called_once()
        
        # Check that proper context was built
        call_args = mock_llm.generate_response.call_args
        messages = call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "expert dream analyst" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        
        # Verify comprehensive context in user message
        user_content = messages[1]["content"]
        assert "The Infinite Library" in user_content
        assert "vast library" in user_content
        assert "overwhelmed with information" in user_content
        assert "100 words or less" in user_content
        
        # Verify repository calls
        mock_repos['dream_repo'].update_analysis.assert_called_once_with(
            user_id, dream_id, expected_analysis, 
            {'model': 'gpt-5-mini', 'generated_at': mock_repos['dream_repo'].update_analysis.call_args[0][3]['generated_at']},
            mock_session
        )
        mock_repos['dream_repo'].update_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.COMPLETED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_analysis_with_interpretation_answers(self, dream_service, mock_repos, mock_llm, sample_dream, sample_questions_and_answers):
        """Test analysis generation including interpretation answers in context."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        questions, answers = sample_questions_and_answers
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=sample_dream)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = questions
        mock_repos['dream_repo'].get_interpretation_answers.return_value = answers
        
        mock_llm.generate_response.return_value = "Analysis incorporating user's interpretation responses..."
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id)
        
        # Verify
        assert result is not None
        mock_llm.generate_response.assert_called_once()
        
        # Check that interpretation answers were included in context
        call_args = mock_llm.generate_response.call_args
        messages = call_args[0][0]
        user_content = messages[1]["content"]
        
        # Should contain interpretation Q&A
        assert "Wonder and curiosity" in user_content or "interpretation" in user_content.lower()
        assert "Books represent my desire to understand myself" in user_content or "interpretation" in user_content.lower()
    
    @pytest.mark.asyncio
    async def test_no_llm_service_available(self, mock_repos):
        """Test when analysis LLM service is not available."""
        service = DreamService(
            dream_repo=mock_repos['dream_repo'],
            storage_repo=mock_repos['storage_repo'],
            user_repo=mock_repos['user_repo'],
            analysis_llm=None  # No LLM service
        )
        
        result = await service.generate_analysis(uuid4(), uuid4())
        
        assert result is None
        mock_repos['dream_repo'].try_start_analysis_generation.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_dream_not_found(self, dream_service, mock_repos):
        """Test when dream doesn't exist."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = None
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            # Mock context builder to return None for missing dream
            with patch.object(dream_service._context_builder, 'build_for_analysis', return_value=None):
                result = await dream_service.generate_analysis(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_analysis_already_exists_not_forcing(self, dream_service, mock_repos, sample_dream):
        """Test when analysis already exists and not forcing regeneration."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Dream with existing analysis
        sample_dream.analysis = "Existing analysis content"
        
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id, force_regenerate=False)
        
        assert result == sample_dream
        mock_repos['dream_repo'].update_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.COMPLETED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_analysis_already_exists_force_regenerate(self, dream_service, mock_repos, mock_llm, sample_dream):
        """Test forcing regeneration when analysis already exists."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Dream with existing analysis
        sample_dream.analysis = "Old analysis content"
        
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=sample_dream)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        new_analysis = "New regenerated analysis content"
        mock_llm.generate_response.return_value = new_analysis
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id, force_regenerate=True)
        
        assert result is not None
        mock_llm.generate_response.assert_called_once()
        mock_repos['dream_repo'].update_analysis.assert_called_once_with(
            user_id, dream_id, new_analysis, 
            {'model': 'gpt-5-mini', 'generated_at': mock_repos['dream_repo'].update_analysis.call_args[0][3]['generated_at']},
            mock_session
        )
    
    @pytest.mark.asyncio
    async def test_generation_already_in_progress(self, dream_service, mock_repos, sample_dream):
        """Test when analysis generation is already in progress."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = False  # Already in progress
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id)
        
        assert result == sample_dream
        # Should not proceed with generation
        mock_repos['dream_repo'].update_analysis_status.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_dream_recovery_success(self, dream_service, mock_repos, mock_llm):
        """Test successful dream recovery when transcript is missing."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Dream without transcript
        dream_no_transcript = Dream(
            id=dream_id,
            title="Recovered Dream",
            created_at=datetime.utcnow(),
            state=DreamStatus.PENDING.value,
            transcript=None
        )
        dream_no_transcript.user_id = user_id
        
        # Dream with transcript after recovery
        dream_with_transcript = Dream(
            id=dream_id,
            title="Recovered Dream",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="Recovered dream content after processing segments"
        )
        dream_with_transcript.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        # Since our mock recovery function modifies the dream object in-place,
        # we can return the same dream object - it will have the transcript after recovery
        mock_repos['dream_repo'].get_dream.return_value = dream_no_transcript
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=dream_with_transcript)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        mock_llm.generate_response.return_value = "Analysis of recovered dream"
        
        # Create a mock recovery function that actually modifies the dream data
        async def mock_recovery_function(user_id, dream_id, dream_obj, session):
            """Simulate successful recovery by updating the dream object."""
            # Simulate the recovery process updating the dream's transcript
            dream_obj.transcript = "Recovered dream content after processing segments"
            dream_obj.state = DreamStatus.TRANSCRIBED.value
            return {'success': True, 'method': 'partial_recovery'}
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            with patch.object(dream_service, '_attempt_dream_recovery', side_effect=mock_recovery_function):
                result = await dream_service.generate_analysis(user_id, dream_id)
        
        assert result is not None
        mock_llm.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dream_recovery_failure(self, dream_service, mock_repos):
        """Test failed dream recovery when transcript is missing."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Dream without transcript
        dream = Dream(
            id=dream_id,
            title="Failed Recovery Dream",
            created_at=datetime.utcnow(),
            state=DreamStatus.PENDING.value,
            transcript=None
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = dream
        
        # Mock recovery to fail
        recovery_result = {
            'success': False, 
            'error': 'All recovery attempts failed - segments have failed transcription'
        }
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            with patch.object(dream_service, '_attempt_dream_recovery', return_value=recovery_result):
                result = await dream_service.generate_analysis(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_llm_generation_failure(self, dream_service, mock_repos, mock_llm, sample_dream):
        """Test when LLM fails to generate analysis."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        # Make LLM throw an exception
        mock_llm.generate_response.side_effect = Exception("LLM API timeout")
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_various_dream_types_and_contexts(self, dream_service, mock_repos, mock_llm):
        """Test analysis generation with various types of dream content and contexts."""
        test_cases = [
            {
                "description": "Nightmare with anxiety",
                "dream": {
                    "title": "The Chase",
                    "transcript": "I was being chased through dark corridors by an unknown figure. I felt terrified and couldn't find an exit.",
                    "summary": "A nightmare about being pursued through dark spaces.",
                    "additional_info": "I've been under a lot of stress at work lately."
                },
                "expected_keywords": ["anxiety", "stress", "fear", "escape", "pursue"]
            },
            {
                "description": "Lucid dream with control",
                "dream": {
                    "title": "Flying Free",
                    "transcript": "I realized I was dreaming and decided to fly. I soared over beautiful landscapes, feeling completely in control.",
                    "summary": "A lucid dream involving flying and landscape exploration.",
                    "additional_info": "I've been practicing lucid dreaming techniques."
                },
                "expected_keywords": ["control", "freedom", "awareness", "liberation"]
            },
            {
                "description": "Symbolic dream with family",
                "dream": {
                    "title": "Mother's Garden",
                    "transcript": "I was in my deceased mother's garden, but it was overgrown and wild. I started cleaning it up, planting new flowers.",
                    "summary": "A dream about tending to a deceased mother's neglected garden.",
                    "additional_info": "My mother passed away last year. I've been thinking about her a lot."
                },
                "expected_keywords": ["grief", "memory", "renewal", "care", "loss"]
            },
            {
                "description": "Mundane dream reflecting daily life",
                "dream": {
                    "title": "Office Meeting",
                    "transcript": "I was in a work meeting that went on forever. People kept talking but nothing was being decided.",
                    "summary": "A dream about an endless, unproductive work meeting.",
                    "additional_info": "Work has been frustrating lately with too many meetings."
                },
                "expected_keywords": ["frustration", "productivity", "workplace", "communication"]
            }
        ]
        
        for test_case in test_cases:
            user_id = uuid4()
            dream_id = uuid4()
            
            dream_data = test_case["dream"]
            dream = Dream(
                id=dream_id,
                title=dream_data["title"],
                created_at=datetime.utcnow(),
                state=DreamStatus.TRANSCRIBED.value,
                transcript=dream_data["transcript"],
                summary=dream_data["summary"],
                additional_info=dream_data["additional_info"]
            )
            dream.user_id = user_id
            
            # Setup mocks
            mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
            mock_repos['dream_repo'].update_analysis_status = AsyncMock()
            mock_repos['dream_repo'].get_dream.return_value = dream
            mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=dream)
            mock_repos['dream_repo'].get_interpretation_questions.return_value = []
            mock_repos['dream_repo'].get_interpretation_answers.return_value = []
            
            # Generate contextually appropriate analysis
            analysis_text = f"Analysis for {test_case['description']}: This dream reflects themes of {', '.join(test_case['expected_keywords'][:3])}."
            mock_llm.generate_response.return_value = analysis_text
            
            with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__.return_value = mock_session
                
                result = await dream_service.generate_analysis(user_id, dream_id)
            
            assert result is not None, f"Analysis failed for: {test_case['description']}"
            
            # Verify the context included all dream components
            call_args = mock_llm.generate_response.call_args
            messages = call_args[0][0]
            user_content = messages[1]["content"]
            
            assert dream_data["title"] in user_content
            assert dream_data["transcript"] in user_content
            assert dream_data["summary"] in user_content
            assert dream_data["additional_info"] in user_content
            
            # Reset mocks for next iteration
            mock_llm.generate_response.reset_mock()
            for repo_mock in mock_repos.values():
                repo_mock.reset_mock()
    
    @pytest.mark.asyncio
    async def test_context_builder_integration(self, dream_service, mock_repos, mock_llm, sample_dream):
        """Test that the context builder is properly integrated and called."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=sample_dream)
        
        mock_llm.generate_response.return_value = "Contextually rich analysis"
        
        # Create a mock context window
        mock_context_window = DreamContextWindow(
            dream_id=str(dream_id),
            user_id=str(user_id),
            transcript=sample_dream.transcript,
            title=sample_dream.title,
            summary=sample_dream.summary,
            additional_info=sample_dream.additional_info,
            task_type="analysis"
        )
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            with patch.object(dream_service._context_builder, 'build_for_analysis', return_value=mock_context_window) as mock_build:
                with patch.object(dream_service._context_builder, 'prepare_llm_messages', return_value=[
                    {"role": "system", "content": "System prompt"},
                    {"role": "user", "content": "User prompt with context"}
                ]) as mock_prepare:
                    
                    result = await dream_service.generate_analysis(user_id, dream_id)
        
        # Verify context builder methods were called correctly
        assert result is not None
        mock_build.assert_called_once_with(user_id, dream_id, mock_session)
        mock_prepare.assert_called_once_with(mock_context_window, "analysis")
        
        # Verify LLM was called with prepared messages
        mock_llm.generate_response.assert_called_once_with([
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User prompt with context"}
        ])
    
    @pytest.mark.asyncio
    async def test_metadata_generation(self, dream_service, mock_repos, mock_llm, sample_dream):
        """Test that proper metadata is generated and stored."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=sample_dream)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        mock_llm.generate_response.return_value = "Generated analysis"
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id)
        
        # Verify metadata was created correctly
        assert result is not None
        mock_repos['dream_repo'].update_analysis.assert_called_once()
        
        call_args = mock_repos['dream_repo'].update_analysis.call_args[0]
        metadata = call_args[3]  # Fourth argument is metadata
        
        assert metadata['model'] == 'gpt-5-mini'
        assert 'generated_at' in metadata
        assert isinstance(metadata['generated_at'], str)  # ISO format timestamp
    
    @pytest.mark.asyncio
    async def test_error_handling_comprehensive(self, dream_service, mock_repos, mock_llm, sample_dream):
        """Test comprehensive error handling scenarios."""
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        
        # Test database error during analysis save
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream
        mock_repos['dream_repo'].update_analysis = AsyncMock(side_effect=Exception("Database connection failed"))
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        mock_llm.generate_response.return_value = "Analysis that can't be saved"
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_analysis(user_id, dream_id)
        
        assert result is None
        # Should attempt to mark as failed
        assert mock_repos['dream_repo'].update_analysis_status.call_count >= 1
        
        # Check if failure status was set
        failed_calls = [call for call in mock_repos['dream_repo'].update_analysis_status.call_args_list 
                      if call[0][2] == GenerationStatus.FAILED]
        assert len(failed_calls) >= 1