"""Standalone tests for user profile context system without database dependencies."""

import pytest
from uuid import uuid4
from datetime import datetime

from new_backend_ruminate.context.user.context_window import UserProfileContextWindow
from new_backend_ruminate.context.user.prompts import UserProfilePrompts


class TestUserProfileContextWindow:
    """Test UserProfileContextWindow functionality."""
    
    def test_context_window_creation(self):
        """Test creating a user profile context window with all fields."""
        window = UserProfileContextWindow(
            user_id="user-123",
            checkin_id="checkin-456",
            checkin_text="Feeling anxious about work today",
            checkin_date=datetime.utcnow(),
            mood_scores={"anxiety": 0.7, "stress": 0.8, "hope": 0.3},
            mbti_type="INFP",
            horoscope_data={"sign": "Leo", "moon": "Cancer", "rising": "Virgo"},
            ocean_scores={"openness": 0.9, "conscientiousness": 0.5},
            primary_goal="emotional_healing",
            task_type="daily_insight"
        )
        
        assert window.user_id == "user-123"
        assert window.checkin_id == "checkin-456"
        assert window.checkin_text == "Feeling anxious about work today"
        assert window.mbti_type == "INFP"
        assert window.task_type == "daily_insight"
        assert window.mood_scores["anxiety"] == 0.7
    
    def test_to_llm_messages(self):
        """Test converting context window to LLM messages."""
        window = UserProfileContextWindow(
            user_id="user-123",
            checkin_text="Test check-in"
        )
        
        messages = window.to_llm_messages("System prompt", "User prompt")
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System prompt"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"
    
    def test_get_psychological_profile(self):
        """Test psychological profile formatting."""
        window = UserProfileContextWindow(
            user_id="user-123",
            mbti_type="ENFJ",
            horoscope_data={"sign": "Scorpio", "moon": "Pisces"},
            ocean_scores={"openness": 0.8, "extraversion": 0.9},
            primary_goal="creativity"
        )
        
        profile = window.get_psychological_profile()
        
        assert profile["mbti"] == "ENFJ"
        assert profile["horoscope"]["sign"] == "Scorpio" 
        assert profile["horoscope"]["moon"] == "Pisces"
        assert profile["big_five"]["openness"] == 0.8
        assert profile["big_five"]["extraversion"] == 0.9
        assert profile["primary_goal"] == "creativity"
    
    def test_get_recent_dreams_context(self):
        """Test formatting recent dreams for prompt inclusion."""
        dreams = [
            {
                "date": "2024-01-15",
                "title": "Flying Over Ocean",
                "summary": "Soaring above waves",
                "analysis": "This dream represents freedom and emotional flow that connects deeply with your subconscious mind. The ocean symbolizes the vast depths of your inner world, while flying indicates a powerful desire to transcend current limitations and soar beyond conventional boundaries. This symbolic journey suggests you are ready to embrace new perspectives and explore uncharted territories in your personal growth and creative expression."
            },
            {
                "date": "2024-01-14", 
                "title": "Lost in Forest",
                "summary": "Wandering through dark trees",
                "analysis": "Forest represents the unknown aspects of your psyche"
            }
        ]
        
        window = UserProfileContextWindow(
            user_id="user-123",
            recent_dreams=dreams
        )
        
        dreams_text = window.get_recent_dreams_context()
        
        assert "2024-01-15: Flying Over Ocean" in dreams_text
        assert "Soaring above waves" in dreams_text
        assert "freedom and emotional flow" in dreams_text
        assert "2024-01-14: Lost in Forest" in dreams_text
        # Check analysis truncation for long dreams
        assert "..." in dreams_text  # First dream analysis should be truncated
    
    def test_get_context_components(self):
        """Test getting all context components."""
        window = UserProfileContextWindow(
            user_id="user-123",
            checkin_text="Feeling great today",
            checkin_date=datetime(2024, 1, 15, 10, 30),
            mood_scores={"joy": 0.8, "energy": 0.7},
            mbti_type="INTJ",
            horoscope_data={"sign": "Gemini"},
            interests=["meditation", "art"],
            common_themes=["flying", "water"]
        )
        
        components = window.get_context_components()
        
        assert components["checkin_text"] == "Feeling great today"
        assert components["checkin_date"] == "2024-01-15"
        assert components["mood_scores"] == {"joy": 0.8, "energy": 0.7}
        assert components["psychological_profile"]["mbti"] == "INTJ"
        assert components["interests"] == ["meditation", "art"]
        assert components["common_themes"] == ["flying", "water"]
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        window = UserProfileContextWindow(
            user_id="user-123",
            checkin_text="This is a sample check-in text",  # ~8 words
            mbti_type="INFP",  # 4 chars
            primary_goal="self-discovery",  # ~14 chars
            recent_dreams=[
                {"title": "Dream Title", "summary": "Brief summary", "analysis": "Analysis text"}
            ]
        )
        
        tokens = window.estimate_tokens()
        assert isinstance(tokens, int)
        assert tokens > 0  # Should have some tokens based on content


class TestUserProfilePrompts:
    """Test UserProfilePrompts functionality."""
    
    def test_build_daily_insight_prompt(self):
        """Test building daily insight prompt."""
        context_components = {
            "psychological_profile": {
                "mbti": "INFP",
                "primary_goal": "emotional_healing",
                "horoscope": {"sign": "Leo"},
                "big_five": {"openness": 0.9, "neuroticism": 0.4}
            },
            "checkin_text": "Feeling overwhelmed with work",
            "recent_dreams_text": "• 2024-01-15: Flying Dream\n  Summary: Soaring through clouds"
        }
        
        prompt = UserProfilePrompts.build_daily_insight_prompt(context_components)
        
        assert "INFP" in prompt
        assert "emotional_healing" in prompt
        assert "Leo" in prompt
        assert "Feeling overwhelmed with work" in prompt
        assert "Flying Dream" in prompt
        assert "Deep down, you..." in prompt
    
    def test_build_personalized_interpretation_prompt(self):
        """Test building personalized dream interpretation prompt."""
        dream_context = "Title: Ocean Dream\nSummary: Swimming with dolphins"
        context_components = {
            "psychological_profile": {
                "mbti": "ENFJ",
                "primary_goal": "creativity",
                "horoscope": {"sign": "Pisces"},
                "big_five": {"openness": 0.8}
            },
            "interests": ["marine_life", "spiritual_growth"]
        }
        
        prompt = UserProfilePrompts.build_personalized_interpretation_prompt(
            dream_context, context_components
        )
        
        assert "ENFJ" in prompt
        assert "creativity" in prompt
        assert "Pisces" in prompt
        assert "Ocean Dream" in prompt
        assert "Swimming with dolphins" in prompt
        assert "marine_life" in prompt
    
    def test_format_big_five(self):
        """Test Big Five trait formatting."""
        big_five = {
            "openness": 0.9,
            "conscientiousness": 0.3,
            "extraversion": 0.7,
            "agreeableness": None,  # Should be skipped
            "neuroticism": 0.1
        }
        
        formatted = UserProfilePrompts._format_big_five(big_five)
        
        assert "Openness: High (0.9)" in formatted
        assert "Conscientiousness: Low (0.3)" in formatted
        assert "Extraversion: Moderate (0.7)" in formatted
        assert "Neuroticism: Low (0.1)" in formatted
        assert "Agreeableness" not in formatted  # None should be skipped
    
    def test_get_json_schema_for_daily_insight(self):
        """Test JSON schema for daily insight task."""
        schema = UserProfilePrompts.get_json_schema_for_task("daily_insight")
        
        assert schema is not None
        assert schema["type"] == "object"
        assert "insight" in schema["properties"]
        assert "key_themes" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert schema["required"] == ["insight"]
    
    def test_get_json_schema_for_personalized_analysis(self):
        """Test JSON schema for personalized analysis task."""
        schema = UserProfilePrompts.get_json_schema_for_task("personalized_analysis")
        
        assert schema is not None
        assert schema["type"] == "object"
        assert "interpretation" in schema["properties"]
        assert "personality_connections" in schema["properties"]
        assert "growth_insights" in schema["properties"]
        assert schema["required"] == ["interpretation"]
    
    def test_get_json_schema_unknown_task(self):
        """Test JSON schema for unknown task type."""
        schema = UserProfilePrompts.get_json_schema_for_task("unknown_task")
        assert schema is None