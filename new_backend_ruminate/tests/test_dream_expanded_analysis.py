"""Comprehensive tests for dream expanded analysis generation."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, GenerationStatus
from new_backend_ruminate.context.dream import DreamContextWindow
from llm_test_utils import LLMTestHelper, requires_llm, llm_integration_test


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
    async def test_generation_already_in_progress(self, dream_service, mock_repos, sample_dream_with_analysis):
        """Test when expanded analysis generation is already in progress."""
        user_id = sample_dream_with_analysis.user_id
        dream_id = sample_dream_with_analysis.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = False  # Already in progress
        mock_repos['dream_repo'].get_dream.return_value = sample_dream_with_analysis
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        assert result == sample_dream_with_analysis
        # Should not proceed with generation
        mock_repos['dream_repo'].update_expanded_analysis_status.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_llm_generation_failure(self, dream_service, mock_repos, mock_llm, sample_dream_with_analysis):
        """Test when LLM fails to generate expanded analysis."""
        user_id = sample_dream_with_analysis.user_id
        dream_id = sample_dream_with_analysis.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream_with_analysis
        
        # Make LLM throw an exception
        mock_llm.generate_response.side_effect = Exception("LLM API timeout")
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_expanded_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
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
    
    @pytest.mark.asyncio
    async def test_metadata_generation(self, dream_service, mock_repos, mock_llm, sample_dream_with_analysis):
        """Test that proper metadata is generated and stored."""
        user_id = sample_dream_with_analysis.user_id
        dream_id = sample_dream_with_analysis.id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_expanded_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_expanded_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = sample_dream_with_analysis
        mock_repos['dream_repo'].update_expanded_analysis = AsyncMock(return_value=sample_dream_with_analysis)
        
        mock_llm.generate_response.return_value = "Generated expanded analysis"
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_expanded_analysis(user_id, dream_id)
        
        # Verify metadata was created correctly
        assert result is not None
        mock_repos['dream_repo'].update_expanded_analysis.assert_called_once()
        
        call_args = mock_repos['dream_repo'].update_expanded_analysis.call_args[0]
        metadata = call_args[3]  # Fourth argument is metadata
        
        assert metadata['model'] == 'gpt-4o-mini'
        assert metadata['type'] == 'expanded'
        assert 'generated_at' in metadata
        assert isinstance(metadata['generated_at'], str)  # ISO format timestamp


# ============================================================================
# REAL LLM INTEGRATION TESTS
# ============================================================================

@pytest_asyncio.fixture
async def dream_service_with_real_llm_expanded(mock_repos, test_llm):
    """Create a dream service with real LLM and mocked repositories for expanded analysis."""
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
    async def test_real_expanded_analysis_generation_comprehensive(self, dream_service_with_real_llm_expanded, mock_repos):
        """Test expanded analysis generation with real LLM - comprehensive dream."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create comprehensive dream with existing analysis
        dream = Dream(
            id=dream_id,
            title="The Memory Palace",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I found myself in an enormous palace with countless rooms. Each room contained different memories from my life - childhood bedroom, first school, grandmother's kitchen. I was searching for something important but couldn't remember what. In the center of the palace was a spiral staircase that seemed to go up forever. As I climbed, the memories became more vivid and emotional. At the top, I found a door that was locked. I knew the key was somewhere in one of the memory rooms, but I woke up before finding it.",
            summary="A dream about exploring a vast memory palace with rooms containing life memories, searching for something important, and encountering a locked door at the top of an infinite staircase.",
            additional_info="I've been going through old photo albums lately and thinking about my grandmother who passed away. Work has been stressful and I feel like I'm losing touch with important things in my life.",
            analysis="The memory palace represents your mind's way of organizing and accessing past experiences. The locked door suggests there's something important you feel you've forgotten or lost access to. The infinite staircase symbolizes the endless depths of memory and consciousness."
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
            
            result = await dream_service_with_real_llm_expanded.generate_expanded_analysis(user_id, dream_id)
        
        # Verify result  
        assert result is not None
        
        # Get the generated expanded analysis
        update_call = mock_repos['dream_repo'].update_expanded_analysis.call_args
        generated_expanded_analysis = update_call[0][2]  # Third argument is expanded analysis text
        metadata = update_call[0][3]  # Fourth argument is metadata
        
        # Verify expanded analysis content
        assert len(generated_expanded_analysis) > 100  # Should be substantial
        
        # Verify sections are present in the structured response
        expanded_text_lower = generated_expanded_analysis.lower()
        assert "symbolic" in expanded_text_lower or "meaning" in expanded_text_lower
        assert "psychological" in expanded_text_lower or "pattern" in expanded_text_lower
        assert "personal" in expanded_text_lower or "relevance" in expanded_text_lower
        
        # Verify it references the original dream elements
        assert "memory" in expanded_text_lower or "palace" in expanded_text_lower
        
        # Verify metadata
        assert metadata['model'] == 'gpt-4o-mini'
        assert metadata['type'] == 'expanded'
        assert 'generated_at' in metadata
    
    @llm_integration_test
    async def test_real_expanded_analysis_nightmare_theme(self, dream_service_with_real_llm_expanded, mock_repos):
        """Test expanded analysis with real LLM - nightmare theme."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create nightmare dream
        dream = Dream(
            id=dream_id,
            title="The Endless Chase",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was running through dark, twisting corridors that never seemed to end. Something was chasing me but I couldn't see what it was - I could only hear its footsteps getting closer. Every door I tried was locked, every window was too high. My legs felt heavy and slow, like I was running through mud. I kept looking back but saw only darkness. The fear was overwhelming. I finally found a door that opened, but it led to another corridor just like the first.",
            summary="A nightmare about being chased through endless dark corridors, unable to escape, with growing fear and helplessness.",
            additional_info="I've been avoiding a difficult conversation with my boss about my performance review. I keep putting it off.",
            analysis="This chase dream reflects anxiety about avoiding something important in your waking life. The locked doors symbolize feeling trapped without options, while the pursuer represents the consequences you're trying to escape."
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
            
            result = await dream_service_with_real_llm_expanded.generate_expanded_analysis(user_id, dream_id)
        
        # Verify nightmare-specific analysis
        assert result is not None
        
        # Get the generated expanded analysis
        update_call = mock_repos['dream_repo'].update_expanded_analysis.call_args
        generated_expanded_analysis = update_call[0][2]
        
        expanded_text_lower = generated_expanded_analysis.lower()
        
        # Should address anxiety, avoidance, or fear themes
        anxiety_terms = ['anxiety', 'fear', 'avoid', 'escape', 'stress', 'overwhelm', 'chase', 'trap']
        assert any(term in expanded_text_lower for term in anxiety_terms)
        
        # Should be substantial
        assert len(generated_expanded_analysis) > 100
    
    @llm_integration_test
    async def test_real_expanded_analysis_builds_on_existing(self, dream_service_with_real_llm_expanded, mock_repos):
        """Test that expanded analysis actually builds on and references the existing analysis."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create dream with specific analysis to build upon
        dream = Dream(
            id=dream_id,
            title="Flying Above the City",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was soaring high above my city, looking down at all the tiny buildings and cars. I felt completely free and in control. The wind felt amazing against my face. I could go anywhere I wanted - over the ocean, through clouds, across mountains. I wasn't afraid of falling at all.",
            summary="A lucid flying dream with feelings of freedom and control over a cityscape.",
            additional_info="I just got a promotion at work and feel like I have more control over my career path now.",
            analysis="Flying dreams often represent feelings of liberation and personal empowerment. Your sense of control in the dream mirrors your recent career advancement and increased confidence."
        )
        dream.user_id = user_id
        
        # Create and generate
        created_dream = await dream_repo.create_dream(user_id, dream, db_session)
        await db_session.commit()
        
        result = await service.generate_expanded_analysis(user_id, created_dream.id)
        
        # Verify it builds on existing analysis
        assert result is not None
        assert result.expanded_analysis is not None
        
        expanded_text = result.expanded_analysis.lower()
        initial_text = dream.analysis.lower()
        
        # Should contain new insights beyond the initial analysis
        assert len(result.expanded_analysis) > len(dream.analysis) * 1.5  # Significantly longer
        
        # Should reference concepts from original (freedom, control, empowerment, flying)
        original_concepts = ['freedom', 'control', 'empower', 'flying', 'liberation']
        expanded_concepts_found = sum(1 for concept in original_concepts if concept in expanded_text)
        initial_concepts_found = sum(1 for concept in original_concepts if concept in initial_text)
        
        # Expanded analysis should maintain or add to the conceptual richness
        assert expanded_concepts_found >= initial_concepts_found