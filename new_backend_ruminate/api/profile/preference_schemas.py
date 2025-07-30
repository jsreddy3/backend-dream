"""Pydantic schemas for user preferences API."""
from __future__ import annotations

from datetime import time
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Enums as string literals for validation
class SleepQuality(str):
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class DreamRecallFrequency(str):
    NEVER = "never"
    RARELY = "rarely"
    SOMETIMES = "sometimes"
    OFTEN = "often"
    ALWAYS = "always"


class DreamVividness(str):
    VAGUE = "vague"
    MODERATE = "moderate"
    VIVID = "vivid"
    VERY_VIVID = "very_vivid"


class PrimaryGoal(str):
    SELF_DISCOVERY = "self_discovery"
    CREATIVITY = "creativity"
    PROBLEM_SOLVING = "problem_solving"
    EMOTIONAL_HEALING = "emotional_healing"
    LUCID_DREAMING = "lucid_dreaming"


class ReminderFrequency(str):
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


# Request/Response schemas
class PreferencesCreate(BaseModel):
    """Schema for creating user preferences during onboarding."""
    # Sleep patterns
    typical_bedtime: Optional[time] = None
    typical_wake_time: Optional[time] = None
    sleep_quality: Optional[str] = Field(None, pattern=f"^({'|'.join(['poor', 'fair', 'good', 'excellent'])})$")
    
    # Dream patterns
    dream_recall_frequency: Optional[str] = Field(None, pattern=f"^({'|'.join(['never', 'rarely', 'sometimes', 'often', 'always'])})$")
    dream_vividness: Optional[str] = Field(None, pattern=f"^({'|'.join(['vague', 'moderate', 'vivid', 'very_vivid'])})$")
    common_dream_themes: List[str] = Field(default_factory=list)
    
    # Goals & interests
    primary_goal: Optional[str] = Field(None, pattern=f"^({'|'.join(['self_discovery', 'creativity', 'problem_solving', 'emotional_healing', 'lucid_dreaming'])})$")
    interests: List[str] = Field(default_factory=list)
    
    # Notifications
    reminder_enabled: bool = True
    reminder_time: Optional[time] = None
    reminder_frequency: str = Field("daily", pattern=f"^({'|'.join(['daily', 'weekly', 'custom'])})$")
    reminder_days: List[str] = Field(default_factory=list)
    
    # Personalization
    initial_archetype: Optional[str] = None
    personality_traits: Dict[str, Any] = Field(default_factory=dict)
    onboarding_completed: bool = False
    
    @validator('reminder_days')
    def validate_reminder_days(cls, v, values):
        """Validate reminder days are valid weekdays."""
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in v:
            if day.lower() not in valid_days:
                raise ValueError(f"Invalid day: {day}. Must be one of {valid_days}")
        return [day.lower() for day in v]
    
    @validator('common_dream_themes', 'interests')
    def validate_list_not_empty_strings(cls, v):
        """Remove empty strings from lists."""
        return [item for item in v if item.strip()]


class PreferencesUpdate(BaseModel):
    """Schema for updating user preferences (all fields optional)."""
    # Sleep patterns
    typical_bedtime: Optional[time] = None
    typical_wake_time: Optional[time] = None
    sleep_quality: Optional[str] = None
    
    # Dream patterns
    dream_recall_frequency: Optional[str] = None
    dream_vividness: Optional[str] = None
    common_dream_themes: Optional[List[str]] = None
    
    # Goals & interests
    primary_goal: Optional[str] = None
    interests: Optional[List[str]] = None
    
    # Notifications
    reminder_enabled: Optional[bool] = None
    reminder_time: Optional[time] = None
    reminder_frequency: Optional[str] = None
    reminder_days: Optional[List[str]] = None
    
    # Personalization
    initial_archetype: Optional[str] = None
    personality_traits: Optional[Dict[str, Any]] = None
    onboarding_completed: Optional[bool] = None
    
    model_config = {"exclude_unset": True}


class PreferencesRead(BaseModel):
    """Schema for reading user preferences."""
    id: UUID
    user_id: UUID
    
    # Sleep patterns
    typical_bedtime: Optional[time]
    typical_wake_time: Optional[time]
    sleep_quality: Optional[str]
    
    # Dream patterns
    dream_recall_frequency: Optional[str]
    dream_vividness: Optional[str]
    common_dream_themes: List[str]
    
    # Goals & interests
    primary_goal: Optional[str]
    interests: List[str]
    
    # Notifications
    reminder_enabled: bool
    reminder_time: Optional[time]
    reminder_frequency: str
    reminder_days: List[str]
    
    # Personalization
    initial_archetype: Optional[str]
    personality_traits: Dict[str, Any]
    onboarding_completed: bool
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}