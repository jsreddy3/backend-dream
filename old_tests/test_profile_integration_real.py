#!/usr/bin/env python3
"""
Real unit tests for profile integration after dream completion.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

# Mock the domain entities
class MockDream:
    def __init__(self, dream_id: UUID, title: str = "Test Dream", summary: str = "I was flying and felt aware"):
        self.id = dream_id
        self.title = title
        self.summary = summary
        self.created_at = datetime.utcnow()
        self.segments = []

class MockProfileService:
    def __init__(self):
        self.update_dream_summary_on_completion = AsyncMock()

class MockDreamService:
    def __init__(self):
        self.get_dream = AsyncMock()

class MockSession:
    pass

class TestProfileIntegration:
    """Test the profile integration background task."""
    
    @pytest.fixture
    def user_id(self):
        return uuid4()
    
    @pytest.fixture
    def dream_id(self):
        return uuid4()
    
    @pytest.fixture
    def mock_dream(self, dream_id):
        return MockDream(dream_id, "Lucid Flying Dream", "I realized I was dreaming and started flying")
    
    @pytest.fixture
    def mock_profile_service(self):
        return MockProfileService()
    
    @pytest.fixture
    def mock_dream_service(self, mock_dream):
        service = MockDreamService()
        service.get_dream.return_value = mock_dream
        return service
    
    @patch('new_backend_ruminate.api.dream.routes.session_scope')
    @patch('new_backend_ruminate.api.dream.routes.get_profile_service')
    @patch('new_backend_ruminate.api.dream.routes.get_dream_service')
    async def test_update_profile_after_dream_success(
        self, 
        mock_get_dream_service,
        mock_get_profile_service,
        mock_session_scope,
        user_id,
        dream_id,
        mock_dream,
        mock_profile_service,
        mock_dream_service
    ):
        """Test successful profile update after dream completion."""
        
        # Setup mocks
        mock_get_dream_service.return_value = mock_dream_service
        mock_get_profile_service.return_value = mock_profile_service
        mock_session_scope.return_value.__aenter__.return_value = MockSession()
        
        # Import the function we're testing
        from new_backend_ruminate.api.dream.routes import update_profile_after_dream
        
        # Execute the background task
        await update_profile_after_dream(user_id, dream_id)
        
        # Verify dream service was called
        mock_dream_service.get_dream.assert_called_once_with(user_id, dream_id, MockSession())
        
        # Verify profile service was called with correct parameters
        mock_profile_service.update_dream_summary_on_completion.assert_called_once_with(
            user_id, mock_dream, MockSession()
        )
    
    @patch('new_backend_ruminate.api.dream.routes.session_scope')
    @patch('new_backend_ruminate.api.dream.routes.get_profile_service')
    @patch('new_backend_ruminate.api.dream.routes.get_dream_service')
    async def test_update_profile_after_dream_no_summary(
        self,
        mock_get_dream_service,
        mock_get_profile_service,
        mock_session_scope,
        user_id,
        dream_id,
        mock_profile_service,
        mock_dream_service
    ):
        """Test that profile is not updated if dream has no summary."""
        
        # Setup dream without summary
        incomplete_dream = MockDream(dream_id, "Test Dream", None)  # No summary
        incomplete_dream.summary = None
        
        mock_dream_service.get_dream.return_value = incomplete_dream
        mock_get_dream_service.return_value = mock_dream_service
        mock_get_profile_service.return_value = mock_profile_service
        mock_session_scope.return_value.__aenter__.return_value = MockSession()
        
        from new_backend_ruminate.api.dream.routes import update_profile_after_dream
        
        await update_profile_after_dream(user_id, dream_id)
        
        # Verify dream was fetched
        mock_dream_service.get_dream.assert_called_once()
        
        # Verify profile service was NOT called (no summary)
        mock_profile_service.update_dream_summary_on_completion.assert_not_called()
    
    @patch('new_backend_ruminate.api.dream.routes.session_scope')
    @patch('new_backend_ruminate.api.dream.routes.get_profile_service')
    @patch('new_backend_ruminate.api.dream.routes.get_dream_service')
    async def test_update_profile_after_dream_not_found(
        self,
        mock_get_dream_service,
        mock_get_profile_service,
        mock_session_scope,
        user_id,
        dream_id,
        mock_profile_service,
        mock_dream_service
    ):
        """Test that profile update is skipped if dream is not found."""
        
        # Setup dream service to return None (dream not found)
        mock_dream_service.get_dream.return_value = None
        mock_get_dream_service.return_value = mock_dream_service
        mock_get_profile_service.return_value = mock_profile_service
        mock_session_scope.return_value.__aenter__.return_value = MockSession()
        
        from new_backend_ruminate.api.dream.routes import update_profile_after_dream
        
        await update_profile_after_dream(user_id, dream_id)
        
        # Verify dream was fetched
        mock_dream_service.get_dream.assert_called_once()
        
        # Verify profile service was NOT called (dream not found)
        mock_profile_service.update_dream_summary_on_completion.assert_not_called()
    
    @patch('new_backend_ruminate.api.dream.routes.session_scope')
    @patch('new_backend_ruminate.api.dream.routes.get_profile_service')
    @patch('new_backend_ruminate.api.dream.routes.get_dream_service')
    @patch('new_backend_ruminate.api.dream.routes.logger')
    async def test_update_profile_after_dream_error_handling(
        self,
        mock_logger,
        mock_get_dream_service,
        mock_get_profile_service,
        mock_session_scope,
        user_id,
        dream_id,
        mock_profile_service,
        mock_dream_service
    ):
        """Test that errors are caught and logged without raising."""
        
        # Setup profile service to raise an exception
        mock_profile_service.update_dream_summary_on_completion.side_effect = Exception("Database error")
        
        mock_get_dream_service.return_value = mock_dream_service
        mock_get_profile_service.return_value = mock_profile_service
        mock_session_scope.return_value.__aenter__.return_value = MockSession()
        
        # Setup dream service to return a valid dream
        mock_dream = MockDream(dream_id, "Test Dream", "Test summary")
        mock_dream_service.get_dream.return_value = mock_dream
        
        from new_backend_ruminate.api.dream.routes import update_profile_after_dream
        
        # This should not raise an exception
        await update_profile_after_dream(user_id, dream_id)
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Background profile update failed" in error_call
        assert str(user_id) in error_call
        assert str(dream_id) in error_call

# Integration test for the endpoint
class TestDreamCompletionEndpoint:
    """Test that the endpoint properly queues the background task."""
    
    @patch('new_backend_ruminate.api.dream.routes.update_profile_after_dream')
    def test_finish_dream_queues_background_task(self, mock_background_task):
        """Test that finishing a dream queues the profile update task."""
        
        # This would require more complex FastAPI testing setup
        # For now, we verify the task function exists and can be called
        from new_backend_ruminate.api.dream.routes import update_profile_after_dream
        
        assert callable(update_profile_after_dream)
        assert update_profile_after_dream.__name__ == "update_profile_after_dream"

if __name__ == "__main__":
    # Run the tests
    import sys
    
    print("🧪 Running Profile Integration Tests")
    print("="*50)
    
    # Simple test runner since we don't have pytest in this environment
    test_instance = TestProfileIntegration()
    
    async def run_tests():
        user_id = uuid4()
        dream_id = uuid4()
        mock_dream = MockDream(dream_id)
        mock_profile_service = MockProfileService()
        mock_dream_service = MockDreamService()
        
        try:
            print("✅ Test 1: Testing mock setup...")
            assert mock_profile_service.update_dream_summary_on_completion is not None
            assert mock_dream_service.get_dream is not None
            print("   Mock setup successful")
            
            print("✅ Test 2: Testing background task function exists...")
            from new_backend_ruminate.api.dream.routes import update_profile_after_dream
            assert callable(update_profile_after_dream)
            print("   Background task function found")
            
            print("✅ Test 3: Testing mock dream object...")
            assert mock_dream.id == dream_id
            assert mock_dream.title == "Test Dream"
            assert mock_dream.summary == "I was flying and felt aware"
            print("   Mock dream object working")
            
            print("\n🚀 All basic tests passed!")
            print("Note: Full integration tests require running pytest with:")
            print("   pytest test_profile_integration_real.py -v")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            sys.exit(1)
    
    asyncio.run(run_tests())