"""Simple LLM integration tests for user profile context without database."""

import pytest
from llm_test_utils import llm_integration_test, quick_llm_test, quick_structured_llm_test, test_llm_fast
from new_backend_ruminate.context.user.prompts import UserProfilePrompts


class TestUserContextLLMSimple:
    """Test UserProfilePrompts with real LLM calls (no database)."""
    
    @llm_integration_test
    async def test_daily_insight_prompt_with_llm(self, test_llm_fast):
        """Test daily insight prompt generation with real LLM."""
        # Build context components manually (no database)
        context_components = {
            "psychological_profile": {
                "mbti": "ENFP",
                "primary_goal": "creativity", 
                "horoscope": {"sign": "Sagittarius"},
                "big_five": {"openness": 0.95, "neuroticism": 0.3}
            },
            "checkin_text": "Feeling creatively blocked but excited about new ideas",
            "recent_dreams_text": "• 2024-01-10: Flying Through Art Gallery\n  Summary: Soaring through rooms of vibrant paintings\n  Key insight: Represents desire to transcend creative limitations"
        }
        
        # Build prompt using our system
        prompt = UserProfilePrompts.build_daily_insight_prompt(context_components)
        
        # Test with real LLM
        messages = [
            {"role": "system", "content": UserProfilePrompts.DAILY_INSIGHT_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        
        response = await test_llm_fast.generate_response(messages)
        
        # Verify quality
        assert len(response) > 30
        assert "Deep down, you" in response or "deep down, you" in response
        
        # Should reference ENFP or creative themes
        response_lower = response.lower()
        assert any(word in response_lower for word in ["creative", "idea", "express", "enfp", "enthusiasm"])
        
        print(f"\n🧠 Daily Insight Generated:\n{response}")
    
    @llm_integration_test
    async def test_structured_insight_generation(self):
        """Test structured insight generation with JSON schema."""
        prompt = """Based on this user profile, generate a personalized daily insight:

User: INTJ, Primary Goal: self-discovery, Sign: Virgo  
Check-in: "Analyzing patterns in my life, feeling need for more structure"
Recent Dreams: Organizing a vast library, building architectural blueprints

Generate a structured insight in JSON format."""
        
        schema = UserProfilePrompts.get_json_schema_for_task("daily_insight")
        
        result = await quick_structured_llm_test(prompt, schema)
        
        # Verify structured response
        assert "insight" in result
        assert len(result["insight"]) > 20
        
        # Should reference analytical/structural themes for INTJ
        combined_text = result["insight"].lower()
        assert any(word in combined_text for word in ["analyz", "pattern", "structure", "plan", "system"])
        
        print(f"\n📊 Structured Insight:\n{result}")
    
    @llm_integration_test
    async def test_personality_specific_responses(self):
        """Test that different personality types get appropriate responses."""
        personality_tests = [
            {
                "mbti": "ESFP", 
                "checkin": "Had amazing time with friends but now feeling drained",
                "expected_themes": ["social", "energy", "recharge", "balance", "connection"]
            },
            {
                "mbti": "ISTJ",
                "checkin": "Working through my to-do list systematically today", 
                "expected_themes": ["systematic", "organize", "routine", "reliable", "structure"]
            }
        ]
        
        for test_case in personality_tests:
            prompt = f"""You are the user's inner voice. Based on their personality, provide insight.

User Profile: MBTI {test_case['mbti']}, Primary Goal: emotional_healing
Check-in: "{test_case['checkin']}"

Provide a brief insight (60 words max) starting with "Deep down, you..." that reflects their {test_case['mbti']} personality type."""
            
            response = await quick_llm_test(prompt)
            
            # Check for personality-appropriate themes
            response_lower = response.lower()
            theme_found = any(theme in response_lower for theme in test_case["expected_themes"])
            
            print(f"\n🧭 {test_case['mbti']} Response: {response}")
            print(f"Expected themes: {test_case['expected_themes']}")
            print(f"Theme match: {theme_found}")
            
            assert theme_found, f"Response for {test_case['mbti']} didn't match expected themes"
    
    @llm_integration_test 
    async def test_prompt_template_quality(self):
        """Test that our prompt templates produce high-quality responses."""
        # Test the prompt building directly
        context = {
            "psychological_profile": {
                "mbti": "INFJ",
                "primary_goal": "self_discovery",
                "horoscope": {"sign": "Pisces"},
                "big_five": {"openness": 0.9, "intuition": 0.85}
            },
            "checkin_text": "Deep in thought about my life purpose and meaning",
            "recent_dreams_text": "• Ocean depths dream - diving for hidden treasures"
        }
        
        prompt = UserProfilePrompts.build_daily_insight_prompt(context)
        
        # Verify prompt contains key elements
        assert "INFJ" in prompt
        assert "self_discovery" in prompt
        assert "Pisces" in prompt
        assert "life purpose" in prompt
        assert "Ocean depths" in prompt
        
        # Test with LLM
        response = await quick_llm_test(f"""Based on the following psychological profile and context, provide a personalized insight:

{prompt}

Start with "Deep down, you..." and keep it under 100 words.""")
        
        # Quality checks
        assert len(response) > 40
        assert "Deep down, you" in response
        
        # Should reference introspective/intuitive themes for INFJ
        response_lower = response.lower()
        quality_indicators = any(word in response_lower for word in [
            "intuitive", "deep", "meaning", "purpose", "insight", "understand", "inner"
        ])
        
        assert quality_indicators, f"Response lacks INFJ-appropriate depth: {response}"
        
        print(f"\n📝 Template Quality Test:\n{response}")