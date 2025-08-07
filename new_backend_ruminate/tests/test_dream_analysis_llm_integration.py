"""Integration tests for dream analysis with real LLM calls."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, patch

from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, GenerationStatus
from llm_test_utils import LLMTestHelper, llm_integration_test, test_llm


@pytest_asyncio.fixture
async def mock_repos():
    """Create mock repositories for LLM integration tests."""
    return {
        'dream_repo': AsyncMock(),
        'storage_repo': AsyncMock(),
        'user_repo': AsyncMock()
    }


@pytest_asyncio.fixture
async def dream_service_with_real_llm(mock_repos, test_llm):
    """Create a dream service with real LLM and mocked repositories."""
    service = DreamService(
        dream_repo=mock_repos['dream_repo'],
        storage_repo=mock_repos['storage_repo'],
        user_repo=mock_repos['user_repo'],
        summary_llm=test_llm,
        question_llm=test_llm,
        analysis_llm=test_llm
    )
    return service


class TestDreamAnalysisLLMIntegration:
    """Integration tests using real LLM calls to verify context system works end-to-end."""
    
    @llm_integration_test
    async def test_real_llm_title_summary_generation(self, dream_service_with_real_llm, mock_repos):
        """Test title/summary generation with real LLM to verify context building."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create a realistic dream
        dream = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was walking through a vast library with endless shelves of glowing books. Each book seemed to contain different memories from my life. A wise librarian appeared and handed me a particular book that felt warm to the touch. When I opened it, I saw scenes from my childhood playing like a movie."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_title_and_summary.return_value = dream
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        # Execute with real LLM
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service_with_real_llm.generate_title_and_summary(user_id, dream_id)
        
        # Verify
        assert result is not None
        
        # Verify the LLM was called and generated reasonable results
        update_call = mock_repos['dream_repo'].update_title_and_summary.call_args
        assert update_call is not None
        
        generated_title = update_call[0][2]  # Third argument is title
        generated_summary = update_call[0][3]  # Fourth argument is summary
        
        # Validate title (should be short and relevant)
        assert len(generated_title) > 0
        assert len(generated_title.split()) <= 10  # Should be reasonably short
        assert any(keyword in generated_title.lower() for keyword in ['library', 'book', 'memory', 'childhood'])
        
        # Validate summary (should be longer and descriptive)
        assert len(generated_summary) > len(generated_title)
        assert any(keyword in generated_summary.lower() for keyword in ['library', 'books', 'memories', 'childhood'])
        
        # Verify completion status was set
        mock_repos['dream_repo'].update_summary_status.assert_called_with(
            user_id, dream_id, GenerationStatus.COMPLETED, mock_session
        )
    
    @llm_integration_test
    async def test_real_llm_analysis_generation(self, dream_service_with_real_llm, mock_repos):
        """Test analysis generation with real LLM to verify rich context building."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create a dream with full context (title, summary, additional info)
        dream = Dream(
            id=dream_id,
            title="The Memory Library",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was walking through a vast library with endless shelves of glowing books. Each book seemed to contain different memories from my life. A wise librarian appeared and handed me a particular book that felt warm to the touch. When I opened it, I saw scenes from my childhood playing like a movie.",
            summary="A dream about exploring a magical library where books contain personal memories, receiving guidance from a wise librarian to reconnect with childhood experiences.",
            additional_info="I've been feeling disconnected from my past lately and struggling with some important decisions. Work has been overwhelming and I haven't had time to reflect."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=dream)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        # Execute with real LLM
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service_with_real_llm.generate_analysis(user_id, dream_id)
        
        # Verify
        assert result is not None
        
        # Verify the analysis was generated and stored
        update_call = mock_repos['dream_repo'].update_analysis.call_args
        assert update_call is not None
        
        generated_analysis = update_call[0][2]  # Third argument is analysis text
        metadata = update_call[0][3]  # Fourth argument is metadata
        
        # Validate analysis content (should reference key dream elements)
        assert len(generated_analysis) > 50  # Should be substantial
        assert len(generated_analysis) <= 120  # But under 100 words as requested in prompt
        
        # Should reference key symbols from the dream
        analysis_lower = generated_analysis.lower()
        assert any(keyword in analysis_lower for keyword in ['librar', 'book', 'memor', 'past'])
        
        # Should address the personal context
        assert any(keyword in analysis_lower for keyword in ['reflect', 'decision', 'connect', 'childhood'])
        
        # Validate metadata
        assert metadata['model'] == 'gpt-4o-mini'
        assert 'generated_at' in metadata
        
        # Verify completion status
        mock_repos['dream_repo'].update_analysis_status.assert_called_with(
            user_id, dream_id, GenerationStatus.COMPLETED, mock_session
        )
    
    @llm_integration_test 
    async def test_real_llm_context_system_comprehensive(self, dream_service_with_real_llm, mock_repos):
        """Test that our context system provides rich, well-structured prompts to the LLM."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create a complex dream scenario
        dream = Dream(
            id=dream_id,
            title="The Underwater City",
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was swimming deep underwater and discovered a beautiful crystal city. The buildings were made of coral and sea glass. I could breathe underwater somehow. I met a dolphin who could speak and told me I was looking for something I had lost long ago. We swam through the city together, exploring ancient temples filled with bioluminescent fish.",
            summary="A dream about discovering an underwater crystal city and meeting a talking dolphin who guides the search for something lost.",
            additional_info="I recently lost my grandmother, who always loved the ocean. I've been having trouble processing the grief and feel like I'm searching for closure."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].try_start_analysis_generation.return_value = True
        mock_repos['dream_repo'].update_analysis_status = AsyncMock()  
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_analysis = AsyncMock(return_value=dream)
        mock_repos['dream_repo'].get_interpretation_questions.return_value = []
        mock_repos['dream_repo'].get_interpretation_answers.return_value = []
        
        # Execute
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service_with_real_llm.generate_analysis(user_id, dream_id)
        
        # Verify result
        assert result is not None
        
        # Get the generated analysis
        update_call = mock_repos['dream_repo'].update_analysis.call_args
        generated_analysis = update_call[0][2]
        
        # Verify the LLM received and processed the rich context appropriately
        # The analysis should show understanding of multiple context layers:
        
        # 1. Dream symbols (underwater, crystal city, dolphin)
        analysis_lower = generated_analysis.lower()
        dream_symbols_present = any(keyword in analysis_lower 
                                  for keyword in ['underwater', 'water', 'city', 'crystal', 'dolphin', 'ocean', 'sea'])
        assert dream_symbols_present, f"Analysis should reference dream symbols. Got: {generated_analysis}"
        
        # 2. Personal context (loss, grief, grandmother)
        personal_context_present = any(keyword in analysis_lower 
                                     for keyword in ['loss', 'grief', 'search', 'lost', 'closure', 'process'])
        assert personal_context_present, f"Analysis should address personal context. Got: {generated_analysis}"
        
        # 3. Appropriate length (concise but insightful)
        word_count = len(generated_analysis.split())
        assert 30 <= word_count <= 120, f"Analysis should be 30-120 words, got {word_count}: {generated_analysis}"
        
        # 4. Coherent interpretation (should make connections)
        # The analysis should not just list symbols but provide interpretation
        assert len(generated_analysis) > 100, "Analysis should be substantial enough to provide interpretation"
    
    @llm_integration_test
    async def test_prompt_engineering_effectiveness(self, test_llm):
        """Test that our prompt engineering produces consistent, high-quality outputs."""
        from new_backend_ruminate.context.dream import DreamContextBuilder, DreamContextWindow
        
        # Create a test context window with challenging dream content
        context_window = DreamContextWindow(
            dream_id="test-dream",
            user_id="test-user", 
            transcript="I was, um, like flying? But also maybe running. There were these things, kind of like animals but not really. Everything kept changing colors and I felt scared but also excited. I think my mom was there, or someone who felt like my mom. We were looking for something important but I can't remember what.",
            title="Confusing Flight Dream",
            summary="A disorienting dream with shape-shifting elements, flight/running, color changes, and searching with a maternal figure.",
            additional_info="I'm going through a major life transition and feeling uncertain about everything.",
            task_type="analysis"
        )
        
        # Use the context builder to create messages
        context_builder = DreamContextBuilder(None)  # No repo needed for message building
        messages = context_builder.prepare_llm_messages(context_window, "analysis")
        
        # Call the real LLM
        analysis = await test_llm.generate_response(messages)
        
        # Verify the LLM handled the challenging, unclear dream content well
        assert len(analysis) > 50, "Should provide substantial analysis even for unclear dreams"
        assert len(analysis) <= 150, "Should stay within reasonable bounds"
        
        # Should address uncertainty/confusion theme
        analysis_lower = analysis.lower()
        uncertainty_addressed = any(keyword in analysis_lower 
                                  for keyword in ['uncertain', 'transition', 'change', 'confusion', 'unclear'])
        assert uncertainty_addressed, f"Should address uncertainty theme. Got: {analysis}"
        
        # Should extract meaning from fragmented content
        meaning_extracted = any(keyword in analysis_lower
                              for keyword in ['search', 'transform', 'identity', 'support', 'guidance'])
        assert meaning_extracted, f"Should extract deeper meaning. Got: {analysis}"