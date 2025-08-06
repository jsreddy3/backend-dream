"""Profile API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID


class ProfileStatistics(BaseModel):
    """User's dream statistics."""
    total_dreams: int
    total_duration_minutes: int
    dream_streak_days: int
    last_dream_date: Optional[date]


class EmotionalMetricRead(BaseModel):
    """Emotional metric data."""
    name: str
    intensity: float = Field(..., ge=0.0, le=1.0)
    color: str


class DreamThemeRead(BaseModel):
    """Dream theme with percentage."""
    name: str
    percentage: int = Field(..., ge=0, le=100)


class ProfileRead(BaseModel):
    """User profile response."""
    name: Optional[str]
    archetype: Optional[str]
    archetype_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    statistics: ProfileStatistics
    emotional_metrics: List[EmotionalMetricRead]
    dream_themes: List[DreamThemeRead]
    recent_symbols: List[str]
    last_calculated_at: Optional[datetime]
    calculation_status: str = Field(..., pattern="^(pending|processing|completed|failed)$")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None
        }


class ProfileCalculateRequest(BaseModel):
    """Request to calculate/recalculate profile."""
    force_recalculate: bool = False


class ProfileCalculateResponse(BaseModel):
    """Response from profile calculation request."""
    status: str
    message: str