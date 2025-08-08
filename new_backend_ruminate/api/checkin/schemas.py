"""Pydantic schemas for check-in API."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class CheckInCreate(BaseModel):
    """Schema for creating a new check-in."""
    checkin_text: str = Field(..., min_length=1, max_length=2000, description="User's check-in text")
    mood_scores: Optional[Dict[str, float]] = Field(None, description="Optional mood scores (0.0-1.0)")
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class CheckInRead(BaseModel):
    """Schema for reading check-in data."""
    id: UUID
    user_id: UUID
    checkin_text: str
    mood_scores: Optional[Dict[str, float]]
    insight_text: Optional[str]
    insight_status: str
    insight_generated_at: Optional[datetime]
    insight_type: str
    insight_version: int
    context_metadata: Optional[Dict[str, Any]]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


class CheckInList(BaseModel):
    """Schema for listing check-ins."""
    checkins: List[CheckInRead]
    total_count: int


class InsightGenerationRequest(BaseModel):
    """Schema for requesting insight generation."""
    force_regenerate: bool = Field(False, description="Force regeneration even if insight already exists")


class InsightResponse(BaseModel):
    """Schema for insight generation response."""
    checkin_id: UUID
    insight_text: Optional[str]
    insight_status: str
    key_themes: Optional[List[str]] = None
    confidence: Optional[float] = None
    generated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


class RecentInsightsResponse(BaseModel):
    """Schema for recent insights overview."""
    insights: List[InsightResponse]
    user_streak: int
    total_insights: int