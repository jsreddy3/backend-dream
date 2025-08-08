"""User profile context window data structure."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class UserProfileContextWindow:
    """Container for all user profile context components."""
    
    # Core user data
    user_id: str
    checkin_id: Optional[str] = None
    
    # Check-in data (for insights generation)
    checkin_text: Optional[str] = None
    checkin_date: Optional[datetime] = None
    mood_scores: Optional[Dict[str, float]] = None
    
    # Psychological profile
    mbti_type: Optional[str] = None
    horoscope_data: Optional[Dict[str, Any]] = None
    ocean_scores: Optional[Dict[str, float]] = None
    primary_goal: Optional[str] = None
    personality_traits: Optional[Dict[str, Any]] = None
    
    # Recent dream context
    recent_dreams: Optional[List[Dict[str, Any]]] = None
    
    # User preferences and patterns
    interests: Optional[List[str]] = None
    common_themes: Optional[List[str]] = None
    
    # Generation task info
    task_type: str = "daily_insight"  # "daily_insight", "profile_analysis", "personalized_interpretation"
    
    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_llm_messages(self, system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
        """Convert context window to LLM-ready messages."""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def get_psychological_profile(self) -> Dict[str, Any]:
        """Get formatted psychological profile components."""
        profile = {}
        
        if self.mbti_type:
            profile["mbti"] = self.mbti_type
            
        if self.horoscope_data:
            profile["horoscope"] = {
                "sign": self.horoscope_data.get("sign", "Unknown"),
                "moon": self.horoscope_data.get("moon"),
                "rising": self.horoscope_data.get("rising"),
                "traits": self.horoscope_data.get("traits", [])
            }
            
        if self.ocean_scores:
            profile["big_five"] = {
                "openness": self.ocean_scores.get("openness"),
                "conscientiousness": self.ocean_scores.get("conscientiousness"), 
                "extraversion": self.ocean_scores.get("extraversion"),
                "agreeableness": self.ocean_scores.get("agreeableness"),
                "neuroticism": self.ocean_scores.get("neuroticism")
            }
            
        if self.primary_goal:
            profile["primary_goal"] = self.primary_goal
            
        return profile
    
    def get_recent_dreams_context(self) -> str:
        """Format recent dreams for prompt inclusion."""
        if not self.recent_dreams:
            return ""
            
        dreams_text = []
        for dream in self.recent_dreams:
            dream_text = f"• {dream.get('date', 'Unknown date')}: {dream.get('title', 'Untitled')}"
            if dream.get('summary'):
                dream_text += f"\n  Summary: {dream['summary']}"
            if dream.get('analysis'):
                # Truncate analysis for context brevity
                analysis_preview = dream['analysis'][:200]
                if len(dream['analysis']) > 200:
                    analysis_preview += "..."
                dream_text += f"\n  Key insight: {analysis_preview}"
            dreams_text.append(dream_text)
            
        return "\n".join(dreams_text)
    
    def get_context_components(self) -> Dict[str, Any]:
        """Get all relevant context components for prompt building."""
        components = {}
        
        # Check-in data
        if self.checkin_text:
            components["checkin_text"] = self.checkin_text
            components["checkin_date"] = self.checkin_date.strftime("%Y-%m-%d") if self.checkin_date else None
            
        if self.mood_scores:
            components["mood_scores"] = self.mood_scores
            
        # Psychological profile
        components["psychological_profile"] = self.get_psychological_profile()
        
        # Dreams context
        if self.recent_dreams:
            components["recent_dreams_text"] = self.get_recent_dreams_context()
            
        # User preferences
        if self.interests:
            components["interests"] = self.interests
            
        if self.common_themes:
            components["common_themes"] = self.common_themes
            
        return components
    
    def estimate_tokens(self) -> int:
        """Rough estimate of token count for context management."""
        total_chars = len(self.checkin_text or "")
        
        # Psychological profile
        if self.mbti_type:
            total_chars += len(self.mbti_type)
        if self.primary_goal:
            total_chars += len(self.primary_goal)
            
        # Dreams context
        if self.recent_dreams:
            for dream in self.recent_dreams:
                total_chars += len(str(dream.get('title', '')))
                total_chars += len(str(dream.get('summary', '')))
                total_chars += len(str(dream.get('analysis', '')))
                
        return total_chars // 4  # Rough estimation: 4 chars per token