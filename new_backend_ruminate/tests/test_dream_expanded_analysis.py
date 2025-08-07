"""Comprehensive tests for dream expanded analysis generation."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, GenerationStatus
from new_backend_ruminate.context.dream import DreamContextWindow
from llm_test_utils import LLMTestHelper, llm_integration_test, test_llm


class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self, model="gpt-4o-mini"):
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
async def sample_dream_with_analysis():
    """Create a sample dream with existing analysis."""
    dream = Dream(
        id=uuid4(),
        title="The Infinite Library",
        created_at=datetime.utcnow(),
        state=DreamStatus.TRANSCRIBED.value,
        transcript="I was in a vast library with towering shelves that seemed to stretch infinitely upward. I was searching for a specific book but couldn't remember its title. A mysterious librarian appeared and handed me a glowing book that contained all my forgotten memories.",
        summary="A dream about exploring an infinite library and receiving a book of forgotten memories from a mysterious librarian.",
        additional_info="I've been feeling overwhelmed with information at work lately and struggling to remember important details.",
        analysis="The infinite library represents your mind's vast repository of knowledge. The towering shelves suggest feeling overwhelmed by information. The mysterious librarian symbolizes your inner wisdom guiding you toward self-discovery."
    )
    dream.user_id = uuid4()
    return dream


class TestGenerateExpandedAnalysis:
    """Comprehensive test battery for generate_expanded_analysis function."""
    
    @pytest.mark.asyncio
    async def test_successful_expanded_analysis_generation(self, dream_service, mock_repos, mock_llm, sample_dream_with_analysis):
        """Test successful expanded analysis generation with full context."""
        user_id = sample_dream_with_analysis.user_id
        dream_id = sample_dream_with_analysis.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream_with_analysis
        mock_repos['dream_repo'].update_expanded_analysis = AsyncMock(return_value=sample_dream_with_analysis)
        
        expected_expanded_analysis = """## Symbolic Meanings
The infinite shelves represent the boundless potential of your subconscious mind and accumulated life experiences. The glowing book symbolizes enlightenment or breakthrough insights waiting to be discovered in your memory banks.

## Psychological Patterns
This dream reflects information overload combined with the innate human search for meaningful knowledge. The librarian represents your intuitive wisdom guiding you through complexity.

## Personal Relevance
Given your work stress and memory concerns, this dream suggests you already possess the answers you seek. Trust your inner guidance to find the right solutions."""
        
        mock_llm.generate_response.return_value = expected_expanded_analysis
        
        # Execute
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
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
        assert sample_dream_with_analysis.analysis in user_content  # Existing analysis included
        assert "Symbolic Meanings" in user_content
        assert "Psychological Patterns" in user_content
        assert "Personal Relevance" in user_content
        
        # Verify repository calls
        mock_repos['dream_repo'].update_expanded_analysis.assert_called_once_with(
            user_id, dream_id, expected_expanded_analysis,
            {'model': 'gpt-4o-mini', 'generated_at': mock_repos['dream_repo'].update_expanded_analysis.call_args[0][3]['generated_at'], 'type': 'expanded'},
            mock_session
        )
        mock_repos['dream_repo'].update_expanded_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.COMPLETED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_no_llm_service_available(self, mock_repos):
        """Test when analysis LLM service is not available."""
        service = DreamService(
            dream_repo=mock_repos['dream_repo'],
            storage_repo=mock_repos['storage_repo'],
            user_repo=mock_repos['user_repo'],
            analysis_llm=None  # No LLM service
        )
        
        result = await service.generate_expanded_analysis(uuid4(), uuid4())
        
        assert result is None
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_dream_not_found(self, dream_service, mock_repos):
        """Test when dream doesn't exist."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = None
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_expanded_analysis_already_exists(self, dream_service, mock_repos, sample_dream_with_analysis):
        """Test when expanded analysis already exists."""
        user_id = sample_dream_with_analysis.user_id
        dream_id = sample_dream_with_analysis.id
        
        # Dream with existing expanded analysis
        sample_dream_with_analysis.expanded_analysis = "Existing expanded analysis content"
        
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream_with_analysis
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        assert result == sample_dream_with_analysis
        # Should not call LLM or update
        mock_repos['dream_repo'].update_expanded_analysis.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_transcript_available(self, dream_service, mock_repos):
        """Test when dream has no transcript."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Dream without transcript
        dream = Dream(
            id=dream_id,
            title="Test Dream",
            created_at=datetime.utcnow(),
            state=DreamStatus.PENDING.value,
            transcript=None,
            analysis="Some analysis"
        )
        dream.user_id = user_id
        
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = dream
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_no_initial_analysis_available(self, dream_service, mock_repos):
        """Test when dream has no initial analysis."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Dream without analysis
        dream = Dream(
            id=dream_id,
            title="Test Dream",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="Some dream content",
            analysis=None
        )
        dream.user_id = user_id
        
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = dream
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_context_builder_integration(self, dream_service, mock_repos, mock_llm, sample_dream_with_analysis):
        """Test that the context builder is properly integrated and called."""
        user_id = sample_dream_with_analysis.user_id
        dream_id = sample_dream_with_analysis.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream_with_analysis
        mock_repos['dream_repo'].update_expanded_analysis = AsyncMock(return_value=sample_dream_with_analysis)
        
        mock_llm.generate_response.return_value = "Contextually rich expanded analysis"
        
        # Create a mock context window
        mock_context_window = DreamContextWindow(
            dream_id=str(dream_id),
            user_id=str(user_id),
            transcript=sample_dream_with_analysis.transcript,
            title=sample_dream_with_analysis.title,
            summary=sample_dream_with_analysis.summary,
            additional_info=sample_dream_with_analysis.additional_info,
            existing_analysis=sample_dream_with_analysis.analysis,
            task_type="expanded_analysis"
        )
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            with patch.object(dream_service._context_builder, 'build_for_expanded_analysis', return_value=mock_context_window) as mock_build:
                with patch.object(dream_service._context_builder, 'prepare_llm_messages', return_value=[
                    {"role": "system", "content": "System prompt for expanded analysis"},
                    {"role": "user", "content": "User prompt with existing analysis context"}
                ]) as mock_prepare:
                    
                    result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        # Verify context builder methods were called correctly
        assert result is not None
        mock_build.assert_called_once_with(user_id, dream_id, mock_session)
        mock_prepare.assert_called_once_with(mock_context_window, "expanded_analysis")
        
        # Verify LLM was called with prepared messages
        mock_llm.generate_response.assert_called_once_with([
            {"role": "system", "content": "System prompt for expanded analysis"},
            {"role": "user", "content": "User prompt with existing analysis context"}
        ])


# ============================================================================
# REAL LLM INTEGRATION TESTS
# ============================================================================

@pytest_asyncio.fixture
async def dream_service_with_real_llm(mock_repos, test_llm):
    """Create a dream service with real LLM and mocked repositories."""
    service = DreamService(
        dream_repo=mock_repos['dream_repo'],
        storage_repo=mock_repos['storage_repo'],
        user_repo=mock_repos['user_repo'],
        analysis_llm=test_llm
    )
    return service


class TestExpandedAnalysisLLMIntegration:
    """Integration tests with real LLM for expanded analysis generation."""
    
    @llm_integration_test
    async def test_real_expanded_analysis_generation(self, dream_service_with_real_llm, mock_repos):
        """Test expanded analysis generation with real LLM."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create dream with existing analysis
        dream = Dream(
            id=dream_id,
            title="The Memory Palace",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I found myself in an enormous palace with countless rooms. Each room contained different memories from my life - childhood bedroom, first school, grandmother's kitchen. I was searching for something important but couldn't remember what. In the center was a spiral staircase going up forever. As I climbed, memories became more vivid. At the top, I found a locked door.",
            summary="A dream about exploring a memory palace with rooms containing life memories, searching for something important, and finding a locked door at the top.",
            additional_info="I've been going through old photos and thinking about my grandmother who passed away. Work stress is making me feel disconnected from important things.",
            analysis="The memory palace represents your mind organizing past experiences. The locked door suggests something important you feel you've forgotten or lost access to. The infinite staircase symbolizes the depths of memory and consciousness."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_expanded_analysis = AsyncMock(return_value=dream)
        
        # Execute with real LLM
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service_with_real_llm.generate_expanded_analysis(user_id, dream_id)
        
        # Verify result  
        assert result is not None
        
        # Get the generated expanded analysis
        update_call = mock_repos['dream_repo'].update_expanded_analysis.call_args
        generated_expanded_analysis = update_call[0][2]  # Third argument is expanded analysis text
        metadata = update_call[0][3]  # Fourth argument is metadata
        
        # Verify expanded analysis content
        assert len(generated_expanded_analysis) > 150  # Should be substantial (150-200 words)
        assert len(generated_expanded_analysis) < 300  # But not too long
        
        # Verify structured sections are present
        expanded_text_lower = generated_expanded_analysis.lower()
        
        # Should have section headers
        section_indicators = ['symbolic', 'psychological', 'personal', 'meaning', 'pattern', 'relevance']
        sections_found = sum(1 for indicator in section_indicators if indicator in expanded_text_lower)
        assert sections_found >= 2, f"Should have structured sections. Found: {sections_found} indicators in: {generated_expanded_analysis}"
        
        # Should reference dream elements
        dream_elements = ['memory', 'palace', 'room', 'stair', 'door', 'grandmother']
        dream_refs = sum(1 for element in dream_elements if element in expanded_text_lower)
        assert dream_refs >= 2, f"Should reference dream elements. Found: {dream_refs} in: {generated_expanded_analysis}"
        
        # Should address personal context
        personal_elements = ['work', 'stress', 'photo', 'disconnect', 'loss', 'grief']
        personal_refs = sum(1 for element in personal_elements if element in expanded_text_lower)
        assert personal_refs >= 1, f"Should address personal context. Found: {personal_refs} in: {generated_expanded_analysis}"
        
        # Verify metadata
        assert metadata['model'] == 'gpt-4o-mini'
        assert metadata['type'] == 'expanded'
        assert 'generated_at' in metadata
    
    @llm_integration_test
    async def test_expanded_analysis_builds_on_existing(self, dream_service_with_real_llm, mock_repos):
        """Test that expanded analysis builds meaningfully on the existing analysis."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create simple dream with basic analysis
        dream = Dream(
            id=dream_id,
            title="Flying Above the City",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was soaring high above my city, looking down at tiny buildings and cars. I felt completely free and in control. The wind felt amazing. I could go anywhere - over the ocean, through clouds, across mountains. I wasn't afraid of falling.",
            summary="A flying dream with feelings of freedom and control over a cityscape.",
            additional_info="Just got a promotion at work and feel more in control of my career path.",
            analysis="Flying dreams represent feelings of liberation and personal empowerment. Your control in the dream mirrors your career advancement and increased confidence."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_expanded_analysis = AsyncMock(return_value=dream)
        
        # Execute
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service_with_real_llm.generate_expanded_analysis(user_id, dream_id)
        
        # Verify it builds meaningfully on existing analysis
        assert result is not None
        
        update_call = mock_repos['dream_repo'].update_expanded_analysis.call_args
        expanded_analysis = update_call[0][2]
        
        # Should be significantly longer than original analysis
        original_length = len(dream.analysis)
        expanded_length = len(expanded_analysis)
        assert expanded_length > original_length * 1.5, f"Expanded analysis ({expanded_length} chars) should be much longer than original ({original_length} chars)"
        
        # Should contain concepts from original analysis
        original_concepts = ['flying', 'freedom', 'liberation', 'empowerment', 'control', 'career']
        expanded_text_lower = expanded_analysis.lower()
        original_concepts_present = sum(1 for concept in original_concepts if concept in expanded_text_lower)
        
        # Should maintain core themes while adding new insights
        assert original_concepts_present >= 3, f"Should reference original concepts. Found {original_concepts_present}/6: {expanded_analysis}"
        
        # Should add new dimensions of analysis
        new_dimensions = ['symbolic', 'psychological', 'personal', 'deeper', 'meaning', 'significance']
        new_insights = sum(1 for dimension in new_dimensions if dimension in expanded_text_lower)
        assert new_insights >= 2, f"Should provide new analytical dimensions. Found {new_insights}: {expanded_analysis}"