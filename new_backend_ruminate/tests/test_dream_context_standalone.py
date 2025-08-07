"""Standalone tests for dream context system without database dependencies."""

import pytest
from uuid import uuid4
from datetime import datetime

from new_backend_ruminate.context.dream.context_window import DreamContextWindow
from new_backend_ruminate.context.dream.prompts import DreamPrompts


class TestDreamContextWindow:
    """Test DreamContextWindow functionality."""
    
    def test_context_window_creation(self):
        """Test creating a context window with all fields."""
        window = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="I had a dream about flying",
            title="Flying Dream",
            summary="A dream about soaring through clouds",
            additional_info="Feeling stressed lately",
            created_at=datetime.utcnow(),
            task_type="analysis"
        )
        
        assert window.dream_id == "dream-123"
        assert window.user_id == "user-456"
        assert window.transcript == "I had a dream about flying"
        assert window.title == "Flying Dream"
        assert window.task_type == "analysis"
    
    def test_to_llm_messages(self):
        """Test converting context window to LLM messages."""
        window = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="Test transcript"
        )
        
        messages = window.to_llm_messages(
            system_prompt="You are a dream analyst",
            user_prompt="Analyze this dream"
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a dream analyst"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Analyze this dream"
    
    def test_get_context_components(self):
        """Test extracting context components."""
        window = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="Dream transcript",
            title="Dream Title",
            summary="Dream summary",
            additional_info="Extra info",
            interpretation_answers=[
                {
                    "question_text": "How did you feel?",
                    "answer_text": "Happy and free"
                }
            ]
        )
        
        components = window.get_context_components()
        
        assert components["transcript"] == "Dream transcript"
        assert components["title"] == "Dream Title"
        assert components["summary"] == "Dream summary"
        assert components["additional_info"] == "Extra info"
        assert "Q: How did you feel?" in components["answers"]
        assert "A: Happy and free" in components["answers"]
    
    def test_get_context_components_with_untitled_dream(self):
        """Test that untitled dreams get 'Untitled' as title."""
        window = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="Dream transcript",
            title=None
        )
        
        components = window.get_context_components()
        assert components["title"] == "Untitled"
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        window = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="This is a test transcript with some content",  # 44 chars
            title="Test Dream",  # 10 chars
            summary="A brief summary"  # 15 chars
        )
        
        # Total: 44 + 10 + 15 = 69 chars
        # Estimated tokens: 69 / 4 = 17
        assert window.estimate_tokens() == 17
    
    def test_context_window_for_expanded_analysis(self):
        """Test context window setup for expanded analysis."""
        window = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="Dream content",
            title="Dream Title",
            existing_analysis="Initial analysis",
            task_type="expanded_analysis"
        )
        
        components = window.get_context_components()
        
        # For expanded analysis, existing_analysis should be included
        assert components["existing_analysis"] == "Initial analysis"


class TestDreamPrompts:
    """Test DreamPrompts functionality."""
    
    def test_build_context_all_components(self):
        """Test building context with all components."""
        components = {
            "title": "Flying Dream",
            "transcript": "I was flying over mountains",
            "summary": "A dream about flying",
            "additional_info": "Stressed about work",
            "answers": "Q: How did you feel?\nA: Free and happy"
        }
        
        context = DreamPrompts.build_context(components)
        
        assert "Dream Title: Flying Dream" in context
        assert "Original Dream Transcript:\nI was flying over mountains" in context
        assert "Summary:\nA dream about flying" in context
        assert "Additional Context:\nStressed about work" in context
        assert "Interpretation Answers:\nQ: How did you feel?" in context
    
    def test_build_context_partial_components(self):
        """Test building context with only some components."""
        components = {
            "title": "Dream",
            "transcript": "Dream content"
        }
        
        context = DreamPrompts.build_context(components)
        
        assert "Dream Title: Dream" in context
        assert "Original Dream Transcript:\nDream content" in context
        assert "Summary:" not in context
        assert "Additional Context:" not in context
    
    def test_prompt_templates(self):
        """Test that prompt templates are properly formatted."""
        # Test title/summary prompt
        prompt = DreamPrompts.TITLE_SUMMARY_USER.format(transcript="Test dream")
        assert "Test dream" in prompt
        assert "JSON object" in prompt
        
        # Test analysis prompt
        prompt = DreamPrompts.ANALYSIS_USER.format(context="Dream context here")
        assert "Dream context here" in prompt
        assert "100 words or less" in prompt
        
        # Test expanded analysis prompt
        prompt = DreamPrompts.EXPANDED_ANALYSIS_USER.format(
            context="Dream context",
            existing_analysis="Initial analysis"
        )
        assert "Dream context" in prompt
        assert "Initial analysis" in prompt
        assert "Symbolic Meanings" in prompt
        assert "Psychological Patterns" in prompt
        
        # Test questions prompt
        prompt = DreamPrompts.QUESTIONS_USER.format(
            transcript="Dream transcript",
            num_questions=3,
            num_choices=3
        )
        assert "Dream transcript" in prompt
        assert "3" in prompt
    
    def test_system_prompts_exist(self):
        """Test that all system prompts are defined."""
        assert len(DreamPrompts.TITLE_SUMMARY_SYSTEM) > 0
        assert len(DreamPrompts.ANALYSIS_SYSTEM) > 0
        assert len(DreamPrompts.EXPANDED_ANALYSIS_SYSTEM) > 0
        assert len(DreamPrompts.QUESTIONS_SYSTEM) > 0