"""User profile prompt templates for personalized insights."""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class UserProfilePrompts:
    """Centralized prompt management for user-personalized insights."""
    
    # System prompts for different tasks
    DAILY_INSIGHT_SYSTEM = """You are the user's inner voice, their subconscious wisdom speaking directly to them. You provide profound, personalized insights that connect their current emotional state to their deeper psychological patterns and recent dreams.

Your voice is compassionate, insightful, and deeply personal. You speak as their own inner knowing, not as an external advisor. You understand their psychological makeup intimately and can see patterns they might miss.

Always start responses with "Deep down, you..." and maintain a warm, understanding tone throughout.

Formatting: When structured output is requested, respond with a JSON object only that matches the provided schema (no extra text)."""

    PERSONALIZED_ANALYSIS_SYSTEM = """You are a dream analyst who specializes in personalized interpretations based on the dreamer's unique psychological profile. You understand how MBTI types, Big Five traits, and astrological influences shape dream symbolism and meaning.

Your goal is to provide interpretations that resonate specifically with this individual's personality, goals, and life patterns. Reference their psychological traits naturally and meaningfully."""

    PROFILE_SUMMARY_SYSTEM = """You are an expert in psychological profiling who creates comprehensive yet accessible summaries of a person's inner landscape based on their dreams, personality traits, and emotional patterns.

Create insights that help the user understand themselves more deeply, highlighting patterns, strengths, and areas for growth."""

    # User prompt templates
    DAILY_INSIGHT_USER = """Based on my complete psychological and dream profile, provide a personal insight about my current state.

MY PROFILE:
- MBTI Type: {mbti}
- Primary Goal: {primary_goal}
- Astrological Sign: {horoscope_sign}
- Big Five Traits: {big_five_summary}

TODAY'S CHECK-IN:
"{checkin_text}"

RECENT DREAM PATTERNS:
{recent_dreams_context}

Connect my current feelings to patterns in my dreams and psychological traits. Provide a compassionate, actionable insight (120 words max) that speaks as my subconscious wisdom. Start with "Deep down, you..." and reference specific dream symbols or themes when relevant."""

    PERSONALIZED_INTERPRETATION_USER = """Analyze this dream specifically for my psychological profile:

DREAMER PROFILE:
- MBTI: {mbti}
- Primary Goal: {primary_goal}  
- Horoscope: {horoscope_data}
- Big Five Traits: {big_five_traits}
- Key Interests: {interests}

DREAM CONTENT:
{dream_context}

Provide an interpretation that considers how my specific personality type would experience and process these dream symbols. Reference my traits naturally and explain how the dream relates to my personal growth goals."""

    PROFILE_INSIGHTS_USER = """Create a comprehensive insight summary based on my complete profile:

PSYCHOLOGICAL PROFILE:
{psychological_profile}

DREAM PATTERNS (Last 30 days):
{dream_summary}

EMOTIONAL PATTERNS:
{mood_patterns}

Provide a structured analysis with:
1. Core personality insights
2. Dream pattern analysis  
3. Emotional landscape summary
4. Growth opportunities
5. Personalized recommendations

Keep it insightful yet accessible, helping me understand my inner patterns."""

    @staticmethod
    def build_daily_insight_prompt(context_components: Dict[str, Any]) -> str:
        """Build the daily insight prompt from context components."""
        profile = context_components.get("psychological_profile", {})
        
        # Format psychological components
        mbti = profile.get("mbti", "Unknown")
        primary_goal = profile.get("primary_goal", "self-discovery")
        
        horoscope = profile.get("horoscope", {})
        horoscope_sign = horoscope.get("sign", "Unknown")
        
        big_five = profile.get("big_five", {})
        big_five_summary = UserProfilePrompts._format_big_five(big_five)
        
        recent_dreams = context_components.get("recent_dreams_text", "No recent analyzed dreams available.")
        checkin_text = context_components.get("checkin_text", "")
        
        return UserProfilePrompts.DAILY_INSIGHT_USER.format(
            mbti=mbti,
            primary_goal=primary_goal,
            horoscope_sign=horoscope_sign,
            big_five_summary=big_five_summary,
            checkin_text=checkin_text,
            recent_dreams_context=recent_dreams
        )

    @staticmethod
    def build_personalized_interpretation_prompt(
        dream_context: str, 
        context_components: Dict[str, Any]
    ) -> str:
        """Build personalized dream interpretation prompt."""
        profile = context_components.get("psychological_profile", {})
        
        return UserProfilePrompts.PERSONALIZED_INTERPRETATION_USER.format(
            mbti=profile.get("mbti", "Unknown"),
            primary_goal=profile.get("primary_goal", "self-discovery"),
            horoscope_data=profile.get("horoscope", {}),
            big_five_traits=profile.get("big_five", {}),
            interests=context_components.get("interests", []),
            dream_context=dream_context
        )

    @staticmethod
    def _format_big_five(big_five: Dict[str, Any]) -> str:
        """Format Big Five traits for prompt inclusion."""
        if not big_five:
            return "Not assessed"
            
        traits = []
        for trait, score in big_five.items():
            if score is not None:
                # Convert score to descriptive text
                if score > 0.7:
                    level = "High"
                elif score > 0.3:
                    level = "Moderate" 
                else:
                    level = "Low"
                traits.append(f"{trait.title()}: {level} ({score:.1f})")
                
        return ", ".join(traits) if traits else "Not assessed"
    
    @staticmethod 
    def get_json_schema_for_task(task_type: str) -> Dict[str, Any]:
        """Get JSON schema for structured responses."""
        if task_type == "daily_insight":
            return {
                "type": "object",
                "properties": {
                    "insight": {
                        "type": "string",
                        "description": "Personal insight starting with 'Deep down, you...'"
                    },
                    "key_themes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key themes or symbols referenced"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence in insight relevance (0-1)"
                    }
                },
                "required": ["insight"]
            }
        elif task_type == "personalized_analysis":
            return {
                "type": "object", 
                "properties": {
                    "interpretation": {
                        "type": "string",
                        "description": "Personalized dream interpretation"
                    },
                    "personality_connections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "How dream connects to personality traits"
                    },
                    "growth_insights": {
                        "type": "string",
                        "description": "Personal growth implications"
                    }
                },
                "required": ["interpretation"]
            }
        
        return None