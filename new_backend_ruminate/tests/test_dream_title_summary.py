"""Comprehensive tests for dream title and summary generation."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from new_backend_ruminate.services.dream.service import DreamService
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus, GenerationStatus
from new_backend_ruminate.context.dream import DreamContextBuilder, DreamContextWindow


class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self, model="gpt-4"):
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


class TestGenerateTitleSummary:
    """Test battery for generate_title_and_summary function."""
    
    @pytest.mark.asyncio
    async def test_successful_generation_with_existing_transcript(self, dream_service, mock_repos, mock_llm):
        """Test successful title/summary generation when transcript already exists."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create a dream with transcript
        dream = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was flying over mountains. The view was breathtaking."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_title_and_summary.return_value = dream
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        mock_llm.generate_structured_response.return_value = {
            "title": "Flying Over Mountains",
            "summary": "A vivid dream about soaring above mountain peaks with breathtaking views."
        }
        
        # Execute
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_title_and_summary(user_id, dream_id)
        
        # Verify
        assert result is not None
        mock_llm.generate_structured_response.assert_called_once()
        
        # Check that proper context was built
        call_args = mock_llm.generate_structured_response.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "flying over mountains" in messages[1]["content"].lower()
        
        # Verify repository calls
        mock_repos['dream_repo'].update_title_and_summary.assert_called_once_with(
            user_id, dream_id, 
            "Flying Over Mountains",
            "A vivid dream about soaring above mountain peaks with breathtaking views.",
            mock_session
        )
        mock_repos['dream_repo'].update_summary_status.assert_called_with(
            user_id, dream_id, GenerationStatus.COMPLETED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_no_llm_service_available(self, mock_repos):
        """Test when summary LLM service is not available."""
        # Create service without LLM
        service = DreamService(
            dream_repo=mock_repos['dream_repo'],
            storage_repo=mock_repos['storage_repo'],
            user_repo=mock_repos['user_repo'],
            summary_llm=None  # No LLM service
        )
        
        result = await service.generate_title_and_summary(uuid4(), uuid4())
        
        assert result is None
        mock_repos['dream_repo'].get_dream.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_dream_not_found(self, dream_service, mock_repos):
        """Test when dream doesn't exist."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Setup mock to return None (dream not found)
        mock_repos['dream_repo'].get_dream.return_value = None
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            # Mock context builder to return None
            with patch.object(dream_service._context_builder, 'build_for_title_summary', return_value=None):
                result = await dream_service.generate_title_and_summary(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_summary_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_wait_for_transcript_success(self, dream_service, mock_repos, mock_llm):
        """Test waiting for transcript when dream has no transcript initially - INTEGRATION TEST."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create dream without transcript initially
        dream_no_transcript = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.PENDING.value,
            transcript=None
        )
        dream_no_transcript.user_id = user_id
        
        # Dream with transcript after waiting (simulating segments finishing transcription)
        dream_with_transcript = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="I was in a library searching for a book."
        )
        dream_with_transcript.user_id = user_id
        
        # Setup repository behavior for the real integration flow:
        # Call 1: Context builder initial check -> no transcript
        # Call 2: Service updates dream with transcript 
        # Call 3: Context builder rebuild -> has transcript
        mock_repos['dream_repo'].get_dream.side_effect = [
            dream_no_transcript,    # Context builder: initial check
            dream_with_transcript,  # Service: get dream to update transcript
            dream_with_transcript   # Context builder: rebuild context
        ]
        mock_repos['dream_repo'].update_title_and_summary.return_value = dream_with_transcript
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        # Mock the wait function to simulate transcription completing
        with patch.object(dream_service, '_wait_for_transcription_and_consolidate', 
                         return_value="I was in a library searching for a book.") as mock_wait:
            
            mock_llm.generate_structured_response.return_value = {
                "title": "Library Book Search",
                "summary": "A dream about searching for a specific book in a library."
            }
            
            # Patch session_scope to use mock session for database operations
            with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__.return_value = mock_session
                
                # Execute the full integration flow - NO context builder mocking
                result = await dream_service.generate_title_and_summary(user_id, dream_id)
            
            # Verify the complete async transcription workflow
            assert result is not None
            
            # Verify transcription wait was called
            mock_wait.assert_called_once_with(user_id, dream_id)
            
            # Verify repository call pattern: context build + service update + context rebuild = 3 calls
            assert mock_repos['dream_repo'].get_dream.call_count == 3
            
            # Verify dream was updated with transcript 
            mock_session.commit.assert_called()
            
            # Verify final LLM generation occurred
            mock_llm.generate_structured_response.assert_called_once()
            
            # Verify final database save
            mock_repos['dream_repo'].update_title_and_summary.assert_called_once_with(
                user_id, dream_id, "Library Book Search", 
                "A dream about searching for a specific book in a library.",
                mock_session
            )
    
    @pytest.mark.asyncio
    async def test_wait_for_transcript_timeout(self, dream_service, mock_repos):
        """Test when waiting for transcript times out."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create dream without transcript
        dream = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.PENDING.value,
            transcript=None
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        # Mock wait function to return None (timeout)
        with patch.object(dream_service, '_wait_for_transcription_and_consolidate', return_value=None):
            with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__.return_value = mock_session
                
                # Mock context builder
                context_no_transcript = DreamContextWindow(
                    dream_id=str(dream_id),
                    user_id=str(user_id),
                    transcript=None,
                    task_type="title_summary"
                )
                
                with patch.object(dream_service._context_builder, 'build_for_title_summary', 
                                return_value=context_no_transcript):
                    result = await dream_service.generate_title_and_summary(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_summary_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_llm_generation_failure(self, dream_service, mock_repos, mock_llm):
        """Test when LLM fails to generate title/summary."""
        user_id = uuid4()
        dream_id = uuid4()
        
        dream = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="A complex dream with many details..."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        # Make LLM throw an exception
        mock_llm.generate_structured_response.side_effect = Exception("LLM API error")
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_title_and_summary(user_id, dream_id)
        
        assert result is None
        mock_repos['dream_repo'].update_summary_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_various_dream_content_types(self, dream_service, mock_repos, mock_llm):
        """Test generation with various types of dream content."""
        test_cases = [
            {
                "transcript": "Flying.",
                "expected_title": "Brief Flight",
                "expected_summary": "A very short dream about flying.",
                "description": "Very short dream"
            },
            {
                "transcript": "I was in my childhood home, but it looked different. The walls were painted purple, and there was a strange door I'd never seen before. When I opened it, I found myself in a vast library filled with books that glowed. Each book contained memories I had forgotten. I picked up one book and suddenly remembered my grandmother's smile. The library keeper, who looked like my old teacher, told me these were all the memories I thought I had lost. I spent what felt like hours reading through these glowing books, rediscovering parts of my past.",
                "expected_title": "The Memory Library",
                "expected_summary": "A dream about discovering a hidden library in a transformed childhood home, where glowing books contain forgotten memories, guided by a figure resembling an old teacher.",
                "description": "Long, detailed dream"
            },
            {
                "transcript": "So like, I was, um, you know, walking... no wait, I think I was running? Yeah, running through this, this forest, and there were these trees, huge trees, and I kept thinking about work, but then suddenly I wasn't in the forest anymore, I was at my desk, but my desk was in the forest? It's hard to explain...",
                "expected_title": "Forest Office Merge",
                "expected_summary": "A dream involving running through a forest that transforms into a work environment, with the desk appearing in the forest setting.",
                "description": "Confused, rambling narration"
            },
            {
                "transcript": "I was at a party. Everyone was wearing masks. I couldn't recognize anyone. I felt anxious and wanted to leave but couldn't find the exit. The masks kept changing - sometimes animals, sometimes abstract patterns. I realized I was also wearing a mask but couldn't take it off. When I finally found a mirror, I saw that my mask was a mirror itself, reflecting everyone else's masks.",
                "expected_title": "The Mask Party",
                "expected_summary": "A dream about attending a party where everyone wears changing masks, feeling trapped and anxious, discovering the dreamer's own mask is a mirror reflecting others.",
                "description": "Symbolic, anxiety-themed dream"
            }
        ]
        
        for test_case in test_cases:
            user_id = uuid4()
            dream_id = uuid4()
            
            dream = Dream(
                id=dream_id,
                title=None,
                created_at=datetime.utcnow(),
                state=DreamStatus.TRANSCRIBED.value,
                transcript=test_case["transcript"]
            )
            dream.user_id = user_id
            
            # Setup mocks
            mock_repos['dream_repo'].get_dream.return_value = dream
            mock_repos['dream_repo'].update_title_and_summary.return_value = dream
            mock_repos['dream_repo'].update_summary_status = AsyncMock()
            
            mock_llm.generate_structured_response.return_value = {
                "title": test_case["expected_title"],
                "summary": test_case["expected_summary"]
            }
            
            with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__.return_value = mock_session
                
                result = await dream_service.generate_title_and_summary(user_id, dream_id)
            
            assert result is not None, f"Failed for: {test_case['description']}"
            
            # Verify the content was processed correctly
            call_args = mock_llm.generate_structured_response.call_args
            messages = call_args[1]["messages"]
            assert test_case["transcript"] in messages[1]["content"], f"Transcript not found in prompt for: {test_case['description']}"
    
    @pytest.mark.asyncio
    async def test_dream_deleted_during_wait(self, dream_service, mock_repos):
        """Test edge case where dream is deleted while waiting for transcript."""
        user_id = uuid4()
        dream_id = uuid4()
        
        # Create dream without transcript
        dream = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.PENDING.value,
            transcript=None
        )
        dream.user_id = user_id
        
        # Setup mocks - context builder returns None initially (simulating dream not found)
        # Mock wait function to return a transcript
        with patch.object(dream_service, '_wait_for_transcription_and_consolidate', 
                         return_value="Some transcript content"):
            with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
                mock_session = AsyncMock()
                mock_session_scope.return_value.__aenter__.return_value = mock_session
                
                # Mock context builder to simulate dream being deleted (returns None)
                with patch.object(dream_service._context_builder, 'build_for_title_summary', 
                                return_value=None):
                    result = await dream_service.generate_title_and_summary(user_id, dream_id)
        
        assert result is None
        # When context builder returns None, update_summary_status is called
        mock_repos['dream_repo'].update_summary_status.assert_called_with(
            user_id, dream_id, GenerationStatus.FAILED, mock_session
        )
    
    @pytest.mark.asyncio
    async def test_context_builder_methods_called(self, dream_service, mock_repos, mock_llm):
        """Test that context builder methods are called correctly."""
        user_id = uuid4()
        dream_id = uuid4()
        
        dream = Dream(
            id=dream_id,
            title=None,
            created_at=datetime.utcnow(),
            state=DreamStatus.TRANSCRIBED.value,
            transcript="Walking through a garden of glass flowers."
        )
        dream.user_id = user_id
        
        # Setup mocks
        mock_repos['dream_repo'].get_dream.return_value = dream
        mock_repos['dream_repo'].update_title_and_summary.return_value = dream
        mock_repos['dream_repo'].update_summary_status = AsyncMock()
        
        # Return a proper dict, not async mock
        mock_llm.generate_structured_response.return_value = {
            "title": "Glass Garden Walk",
            "summary": "A dream about walking through a garden filled with delicate glass flowers."
        }
        
        with patch('new_backend_ruminate.infrastructure.db.bootstrap.session_scope') as mock_session_scope:
            mock_session = AsyncMock()
            mock_session_scope.return_value.__aenter__.return_value = mock_session
            
            result = await dream_service.generate_title_and_summary(user_id, dream_id)
            
            # Verify the function completed successfully
            assert result is not None
            
            # Verify LLM was called with structured response
            mock_llm.generate_structured_response.assert_called_once()
            
            # Verify the messages and schema were used
            call_kwargs = mock_llm.generate_structured_response.call_args[1]
            assert "messages" in call_kwargs
            assert "json_schema" in call_kwargs
            assert len(call_kwargs["messages"]) == 2
            assert call_kwargs["messages"][0]["role"] == "system"
            assert call_kwargs["messages"][1]["role"] == "user"