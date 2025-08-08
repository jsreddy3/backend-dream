"""Pydantic schemas for astrology API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class BirthChartRequest(BaseModel):
    """Request schema for birth chart calculation."""
    location: str = Field(..., description="Birth location (can be messy input like 'parizz', 'NYC', etc.)")
    birth_date: str = Field(..., description="Birth date in YYYY-MM-DD format", pattern=r'^\d{4}-\d{2}-\d{2}$')
    birth_time: str = Field(..., description="Birth time in HH:MM format (24-hour)", pattern=r'^\d{2}:\d{2}$')
    house_system: Optional[str] = Field(None, description="House system to use (optional, will auto-select based on location)")


class LocationData(BaseModel):
    """Location data returned from geocoding."""
    latitude: float
    longitude: float
    timezone: str
    formatted_address: str
    country: str
    city: str
    original_input: str
    sanitized_input: str


class ProcessingStep(BaseModel):
    """Information about a processing step."""
    step_name: str
    details: Dict[str, Any]


class PlanetPosition(BaseModel):
    """Planetary position in the chart."""
    name: str
    sign: str
    degree: float
    house: int
    retrograde: bool


class HouseCusp(BaseModel):
    """House cusp information."""
    house_number: int
    sign: str
    degree: float


class Aspect(BaseModel):
    """Planetary aspect."""
    planet1: str
    planet2: str
    aspect: str
    orb: float
    applying: Optional[bool] = None


class BirthChart(BaseModel):
    """Complete birth chart data."""
    birth_datetime_utc: str
    julian_day: float
    ascendant: Dict[str, Any]
    midheaven: Dict[str, Any]
    planets: List[PlanetPosition]
    houses: Dict[int, Dict[str, Any]]
    aspects: List[Aspect]
    sun_sign: str
    moon_sign: str
    rising_sign: str
    chart_svg: Optional[str] = None


class BirthChartResponse(BaseModel):
    """Response schema for birth chart calculation."""
    success: bool
    input: BirthChartRequest
    processing_steps: Dict[str, Any]
    location_data: Optional[LocationData]
    birth_chart: Optional[BirthChart]
    errors: List[str]
    calculation_time: Optional[str] = None


class HouseSystemInfo(BaseModel):
    """Information about a house system."""
    name: str
    description: str


class SupportedSystemsResponse(BaseModel):
    """Response with supported house systems."""
    house_systems: Dict[str, str]