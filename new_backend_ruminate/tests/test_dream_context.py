"""Tests for dream context building system."""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from new_backend_ruminate.context.dream import (
    DreamContextBuilder,
    DreamContextWindow,
    DreamPrompts,
    DreamTranscriptProvider,
    DreamMetadataProvider,
    DreamAnswersProvider,
    DreamAnalysisProvider
)
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus
from new_backend_ruminate.domain.dream.entities.segments import Segment
from new_backend_ruminate.domain.dream.entities.interpretation import (
    InterpretationQuestion,
    InterpretationChoice,
    InterpretationAnswer
)

# Import all entities to ensure SQLAlchemy relationships are properly resolved
from new_backend_ruminate.domain.user.entities import User


@pytest_asyncio.fixture
async def mock_dream_repo():
    """Create a mock dream repository."""
    repo = AsyncMock()
    return repo


@pytest_asyncio.fixture
async def dream_context_builder(mock_dream_repo):
    """Create a dream context builder with mocked dependencies."""
    return DreamContextBuilder(mock_dream_repo)


def create_sample_dream():
    """Create a sample dream for testing."""
    dream = Dream(
        id=uuid4(),
        title="Flying Over Mountains",
        created_at=datetime.utcnow(),
        state=DreamStatus.TRANSCRIBED.value,
        transcript="I was flying over beautiful mountains with snow-capped peaks...",
        summary="A vivid dream about flying over mountainous landscapes",
        additional_info="I've been stressed about work lately",
        analysis="This dream may represent a desire for freedom and escape",
        analysis_metadata={"model": "gpt-4", "generated_at": "2024-01-15T10:00:00"}
    )
    dream.user_id = uuid4()
    return dream


@pytest_asyncio.fixture
async def sample_questions():
    """Create sample interpretation questions."""
    q1 = InterpretationQuestion(
        id=uuid4(),
        dream_id=uuid4(),
        question_text="What emotions did you feel while flying?",
        question_order=1
    )
    q1.choices = [
        InterpretationChoice(id=uuid4(), choice_text="Freedom and joy", choice_order=1),
        InterpretationChoice(id=uuid4(), choice_text="Fear and anxiety", choice_order=2),
        InterpretationChoice(id=uuid4(), choice_text="Peace and calm", choice_order=3),
    ]
    
    q2 = InterpretationQuestion(
        id=uuid4(),
        dream_id=uuid4(),
        question_text="What do mountains represent to you?",
        question_order=2
    )
    q2.choices = [
        InterpretationChoice(id=uuid4(), choice_text="Challenges to overcome", choice_order=1),
        InterpretationChoice(id=uuid4(), choice_text="Stability and strength", choice_order=2),
        InterpretationChoice(id=uuid4(), choice_text="Isolation and distance", choice_order=3),
    ]
    
    return [q1, q2]


@pytest_asyncio.fixture
async def sample_answers(sample_questions):
    """Create sample answers to interpretation questions."""
    q1, q2 = sample_questions
    
    a1 = InterpretationAnswer(
        id=uuid4(),
        question_id=q1.id,
        user_id=uuid4(),
        selected_choice_id=q1.choices[0].id,  # "Freedom and joy"
        custom_answer=None
    )
    
    a2 = InterpretationAnswer(
        id=uuid4(),
        question_id=q2.id,
        user_id=uuid4(),
        selected_choice_id=None,
        custom_answer="Mountains remind me of my childhood home"
    )
    
    return [a1, a2]


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


class TestDreamContextBuilder:
    """Test DreamContextBuilder functionality."""
    
    @pytest.mark.asyncio
    async def test_build_for_title_summary(self, dream_context_builder, mock_dream_repo):
        """Test building context for title and summary generation."""
        # Create sample dream (now that SQLAlchemy is configured)
        sample_dream = create_sample_dream()
        
        # Setup mock
        mock_dream_repo.get_dream.return_value = sample_dream
        dream_context_builder._transcript_provider.get_dream = mock_dream_repo.get_dream
        
        # Build context
        user_id = uuid4()
        dream_id = uuid4()
        session = MagicMock()
        
        context = await dream_context_builder.build_for_title_summary(user_id, dream_id, session)
        
        # Verify
        assert context is not None
        assert context.dream_id == str(dream_id)
        assert context.user_id == str(user_id)
        assert context.transcript == sample_dream.transcript
        assert context.task_type == "title_summary"
        mock_dream_repo.get_dream.assert_called_once_with(user_id, dream_id, session)
    
    @pytest.mark.asyncio
    async def test_build_for_title_summary_no_transcript(self, dream_context_builder, mock_dream_repo):
        """Test handling missing transcript."""
        # Setup mock with dream but no transcript
        dream_without_transcript = Dream(id=uuid4(), title="Test")
        dream_without_transcript.transcript = None
        mock_dream_repo.get_dream.return_value = dream_without_transcript
        dream_context_builder._transcript_provider.get_dream = mock_dream_repo.get_dream
        
        # Build context
        context = await dream_context_builder.build_for_title_summary(uuid4(), uuid4(), MagicMock())
        
        # Should return None
        assert context is None
    
    @pytest.mark.asyncio
    async def test_build_for_analysis(self, dream_context_builder, mock_dream_repo, sample_questions, sample_answers):
        """Test building context for analysis generation."""
        # Create sample dream (now that SQLAlchemy is configured)
        sample_dream = create_sample_dream()
        
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        session = MagicMock()
        
        # Setup mocks
        mock_dream_repo.get_dream.return_value = sample_dream
        mock_dream_repo.get_interpretation_questions.return_value = sample_questions
        mock_dream_repo.get_interpretation_answers.return_value = sample_answers
        
        # Update providers
        dream_context_builder._transcript_provider._repo = mock_dream_repo
        dream_context_builder._metadata_provider._repo = mock_dream_repo
        dream_context_builder._answers_provider._repo = mock_dream_repo
        
        # Build context
        context = await dream_context_builder.build_for_analysis(user_id, dream_id, session)
        
        # Verify
        assert context is not None
        assert context.transcript == sample_dream.transcript
        assert context.title == sample_dream.title
        assert context.summary == sample_dream.summary
        assert context.additional_info == sample_dream.additional_info
        assert context.interpretation_answers is not None
        assert len(context.interpretation_answers) == 2
        assert context.task_type == "analysis"
    
    @pytest.mark.asyncio
    async def test_build_for_expanded_analysis(self, dream_context_builder, mock_dream_repo):
        """Test building context for expanded analysis."""
        # Create sample dream (now that SQLAlchemy is configured)
        sample_dream = create_sample_dream()
        
        user_id = sample_dream.user_id
        dream_id = sample_dream.id
        session = MagicMock()
        
        # Setup mock
        mock_dream_repo.get_dream.return_value = sample_dream
        dream_context_builder._transcript_provider._repo = mock_dream_repo
        dream_context_builder._metadata_provider._repo = mock_dream_repo
        dream_context_builder._analysis_provider._repo = mock_dream_repo
        
        # Build context
        context = await dream_context_builder.build_for_expanded_analysis(user_id, dream_id, session)
        
        # Verify
        assert context is not None
        assert context.existing_analysis == sample_dream.analysis
        assert context.existing_analysis_metadata == sample_dream.analysis_metadata
        assert context.task_type == "expanded_analysis"
    
    def test_prepare_llm_messages_title_summary(self, dream_context_builder):
        """Test preparing LLM messages for title/summary task."""
        context = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="I was flying over mountains",
            task_type="title_summary"
        )
        
        messages = dream_context_builder.prepare_llm_messages(context)
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "intelligent, empathetic conversationalist" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "I was flying over mountains" in messages[1]["content"]
        assert "Return a JSON object with 'title' and 'summary' fields" in messages[1]["content"]
    
    def test_prepare_llm_messages_analysis(self, dream_context_builder):
        """Test preparing LLM messages for analysis task."""
        context = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="Dream content",
            title="Dream Title",
            summary="Dream summary",
            task_type="analysis"
        )
        
        messages = dream_context_builder.prepare_llm_messages(context)
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "expert dream analyst" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "Dream Title" in messages[1]["content"]
        assert "Dream content" in messages[1]["content"]
        assert "100 words or less" in messages[1]["content"]
    
    def test_prepare_llm_messages_expanded_analysis(self, dream_context_builder):
        """Test preparing LLM messages for expanded analysis task."""
        context = DreamContextWindow(
            dream_id="dream-123",
            user_id="user-456",
            transcript="Dream content",
            title="Dream Title",
            existing_analysis="Initial analysis text",
            task_type="expanded_analysis"
        )
        
        messages = dream_context_builder.prepare_llm_messages(context)
        
        assert len(messages) == 2
        assert "YOUR INITIAL ANALYSIS:" in messages[1]["content"]
        assert "Initial analysis text" in messages[1]["content"]
        assert "Symbolic Meanings" in messages[1]["content"]
        assert "Psychological Patterns" in messages[1]["content"]
        assert "Personal Relevance" in messages[1]["content"]
    
    def test_get_json_schema_for_task(self, dream_context_builder):
        """Test getting JSON schemas for different tasks."""
        # Title/summary schema
        schema = dream_context_builder.get_json_schema_for_task("title_summary")
        assert schema is not None
        assert "title" in schema["properties"]
        assert "summary" in schema["properties"]
        assert schema["required"] == ["title", "summary"]
        
        # Questions schema
        schema = dream_context_builder.get_json_schema_for_task("questions")
        assert schema is not None
        assert schema["type"] == "array"
        assert "question" in schema["items"]["properties"]
        assert "choices" in schema["items"]["properties"]
        
        # No schema for other tasks
        assert dream_context_builder.get_json_schema_for_task("analysis") is None
        assert dream_context_builder.get_json_schema_for_task("expanded_analysis") is None


class TestProviders:
    """Test individual providers."""
    
    @pytest.mark.asyncio
    async def test_transcript_provider(self, mock_dream_repo, sample_dream):
        """Test DreamTranscriptProvider."""
        provider = DreamTranscriptProvider(mock_dream_repo)
        mock_dream_repo.get_transcript.return_value = "Test transcript"
        mock_dream_repo.get_dream.return_value = sample_dream
        
        session = MagicMock()
        user_id = uuid4()
        dream_id = uuid4()
        
        # Test get_transcript
        transcript = await provider.get_transcript(user_id, dream_id, session)
        assert transcript == "Test transcript"
        mock_dream_repo.get_transcript.assert_called_once_with(user_id, dream_id, session)
        
        # Test get_dream
        dream = await provider.get_dream(user_id, dream_id, session)
        assert dream == sample_dream
        mock_dream_repo.get_dream.assert_called_once_with(user_id, dream_id, session)
    
    @pytest.mark.asyncio
    async def test_answers_provider(self, mock_dream_repo, sample_questions, sample_answers):
        """Test DreamAnswersProvider formatting."""
        provider = DreamAnswersProvider(mock_dream_repo)
        mock_dream_repo.get_interpretation_questions.return_value = sample_questions
        mock_dream_repo.get_interpretation_answers.return_value = sample_answers
        
        session = MagicMock()
        user_id = uuid4()
        dream_id = uuid4()
        
        formatted = await provider.get_answers(user_id, dream_id, session)
        
        assert len(formatted) == 2
        assert formatted[0]["question_text"] == "What emotions did you feel while flying?"
        assert formatted[0]["answer_text"] == "Freedom and joy"
        assert formatted[1]["question_text"] == "What do mountains represent to you?"
        assert formatted[1]["answer_text"] == "Mountains remind me of my childhood home"