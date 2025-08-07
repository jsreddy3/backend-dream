"""Standalone test for prompts - runs without full project imports."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.dream_interpretation import DreamInterpretationPrompts
from prompts.image_generation import DreamImagePrompts
from prompts.daily_insights import DailyInsightsPrompts


def test_interpretation_prompts():
    """Test dream interpretation prompt generation."""
    print("\n=== Testing Dream Interpretation Prompts ===")
    
    # Test data
    transcript = "I was flying over the ocean and saw dolphins jumping."
    user_context = {
        "mbti": "INFP",
        "ocean": {"openness": 8.5, "conscientiousness": 6.0},
        "archetype": "The Mystic Dreamer"
    }
    
    # Test full prompt
    prompt = DreamInterpretationPrompts.get_interpretation_prompt(
        transcript=transcript,
        user_context=user_context
    )
    
    assert "INFP" in prompt
    assert "The Mystic Dreamer" in prompt
    assert "flying over the ocean" in prompt
    print("✓ Full interpretation prompt includes user context")
    
    # Test quick prompt
    quick_prompt = DreamInterpretationPrompts.get_quick_interpretation_prompt(
        transcript=transcript,
        focus="emotional"
    )
    
    assert "emotional content" in quick_prompt
    assert len(quick_prompt) < len(prompt)
    print("✓ Quick interpretation prompt is concise")


def test_image_prompts():
    """Test image generation prompts."""
    print("\n=== Testing Image Generation Prompts ===")
    
    # Test visual element extraction
    transcript = "I saw a bright red dragon flying over a crystal castle"
    elements = DreamImagePrompts.extract_visual_elements(transcript)
    
    assert "dragon" in str(elements).lower()
    assert len(elements) > 0
    print(f"✓ Extracted {len(elements)} visual elements: {elements}")
    
    # Test prompt generation
    prompt = DreamImagePrompts.generate_image_prompt(
        dream_summary="A dragon guards a crystal castle",
        symbols=["dragon", "castle", "crystal"],
        emotional_tone="mysterious",
        style_preset="mystical"
    )
    
    assert "dragon" in prompt
    assert "castle" in prompt
    assert "mystical" in prompt
    assert "enigmatic" in prompt  # from mysterious emotion mapping
    print("✓ Generated image prompt with all elements")
    
    # Test content filtering
    bad_summary = "violent scene with gore"
    safe_prompt = DreamImagePrompts.generate_image_prompt(
        dream_summary=bad_summary,
        style_preset="ethereal"
    )
    
    assert "violent" not in safe_prompt
    assert "Abstract dreamscape" in safe_prompt
    print("✓ Content filter returns safe fallback")


def test_insights_prompts():
    """Test daily insights prompts."""
    print("\n=== Testing Daily Insights Prompts ===")
    
    # Test data
    check_in = "Feeling overwhelmed with work deadlines"
    recent_dreams = [{
        "title": "Endless Maze",
        "interpretation": {"themes": ["confusion", "searching"]}
    }]
    user_profile = {"mbti": "INTJ", "archetype": "The Analyst"}
    
    # Test full insights
    prompt = DailyInsightsPrompts.generate_insights_prompt(
        check_in_text=check_in,
        recent_dreams=recent_dreams,
        user_profile=user_profile
    )
    
    assert "overwhelmed" in prompt
    assert "Endless Maze" in prompt
    assert "INTJ" in prompt
    print("✓ Full insights prompt includes all context")
    
    # Test quick insight
    quick_prompt = DailyInsightsPrompts.generate_quick_insight_prompt(
        check_in_text=check_in,
        dominant_emotion="overwhelmed"
    )
    
    assert len(quick_prompt) < len(prompt)
    assert "50-75 words" in quick_prompt
    print("✓ Quick insight prompt is focused")
    
    # Test synthesis
    synthesis_prompt = DailyInsightsPrompts.generate_dream_synthesis_prompt(
        recent_dreams=recent_dreams * 3,  # Simulate multiple dreams
        time_period="week"
    )
    
    assert "past week" in synthesis_prompt
    assert "3 dreams recorded" in synthesis_prompt
    print("✓ Synthesis prompt handles multiple dreams")


def run_all_tests():
    """Run all prompt tests."""
    print("\n🧪 RUNNING PROMPT TESTS")
    print("=" * 50)
    
    try:
        test_interpretation_prompts()
        test_image_prompts()
        test_insights_prompts()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED!")
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)