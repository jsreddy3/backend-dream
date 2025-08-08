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


class DailyMessageRead(BaseModel):
    """Daily personalized message for the user."""
    message: str
    inspiration: str


class ArchetypeRead(BaseModel):
    """Complete archetype information."""
    id: str
    name: str
    symbol: str
    description: str
    researcher: str
    theory: str
    daily_message: Optional[DailyMessageRead] = None


class ProfileRead(BaseModel):
    """User profile response."""
    name: Optional[str]
    archetype: Optional[str]  # Deprecated - use archetype_details instead
    archetype_details: Optional[ArchetypeRead] = None
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


class BirthChartRequest(BaseModel):
    """Request for birth chart calculation - user-friendly inputs only."""
    birth_date: date = Field(..., description="Birth date (YYYY-MM-DD)")
    birth_time: str = Field(..., description="Birth time in 24h format (HH:MM)")
    birth_place: str = Field(..., description="Birth place (e.g. 'New York, NY' or 'London, UK')")
    
    class Config:
        schema_extra = {
            "example": {
                "birth_date": "1995-05-04", 
                "birth_time": "18:30",
                "birth_place": "New York, NY"
            }
        }


class BirthChartRequestAdvanced(BaseModel):
    """Advanced birth chart request with manual coordinates (for debugging/advanced users)."""
    birth_date: date = Field(..., description="Birth date (YYYY-MM-DD)")
    birth_time: str = Field(..., description="Birth time in 24h format (HH:MM)")
    birth_place: str = Field(..., description="Birth place description")
    timezone: str = Field(..., description="IANA timezone (e.g. America/New_York)")
    latitude: float = Field(..., ge=-90, le=90, description="Birth place latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Birth place longitude")
    house_system: str = Field("placidus", description="House system (placidus, whole_sign, etc)")
    
    class Config:
        schema_extra = {
            "example": {
                "birth_date": "1995-05-04",
                "birth_time": "18:30", 
                "birth_place": "New York, NY",
                "timezone": "America/New_York",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "house_system": "placidus"
            }
        }


class PlanetPosition(BaseModel):
    """Position of a celestial body."""
    name: str
    sign: str
    degree: float
    house: int
    retrograde: bool = False


class AspectInfo(BaseModel):
    """Aspect between two planets."""
    planet1: str
    planet2: str
    aspect: str  # conjunction, opposition, trine, square, sextile
    orb: float
    applying: bool


class BirthChartResponse(BaseModel):
    """Birth chart calculation response."""
    # Chart metadata
    birth_datetime_utc: datetime
    julian_day: float
    
    # Key points
    ascendant: Dict[str, Any]  # sign, degree
    midheaven: Dict[str, Any]  # sign, degree
    
    # Planetary positions
    planets: List[PlanetPosition]
    
    # House cusps
    houses: Dict[int, Dict[str, Any]]  # house number -> {sign, degree}
    
    # Major aspects
    aspects: List[AspectInfo]
    
    # Summary for profile
    sun_sign: str
    moon_sign: str
    rising_sign: str
    
    # Optional chart image
    chart_svg: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }