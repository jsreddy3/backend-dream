"""Astrology API routes for birth chart calculation."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

from new_backend_ruminate.dependencies import get_astrology_service
from new_backend_ruminate.services.astrology.astrology_service import AstrologyService
from .schemas import (
    BirthChartRequest, 
    BirthChartResponse, 
    SupportedSystemsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/astrology", tags=["astrology"])


@router.post("/birth-chart", response_model=BirthChartResponse)
async def calculate_birth_chart_advanced(
    request: BirthChartRequest,
    astrology_service: AstrologyService = Depends(get_astrology_service)
) -> Dict[str, Any]:
    """
    Calculate a complete birth chart from user input.
    
    This endpoint handles the full pipeline:
    1. Location sanitization (fixes typos like "parizz" -> "Paris, France")
    2. Geocoding to get coordinates and timezone
    3. House system selection based on location
    4. Birth data validation
    5. Birth chart calculation with planetary positions, houses, and aspects
    
    Example requests:
    - Messy location: "parizz" -> gets fixed to "Paris, France"
    - Abbreviations: "NYC" -> becomes "New York City, NY, USA"
    - Missing info: "Las Vegas" -> becomes "Las Vegas, Nevada, USA"
    """
    try:
        logger.info(f"Birth chart request: {request.birth_date} {request.birth_time} in '{request.location}'")
        
        # Call the main astrology service
        result = await astrology_service.calculate_birth_chart_advanced(
            raw_location=request.location,
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            house_system=request.house_system
        )
        
        # Convert to response format
        response = BirthChartResponse(
            success=result["success"],
            input=request,
            processing_steps=result["processing_steps"],
            location_data=result["location_data"],
            birth_chart=result["birth_chart"],
            errors=result["errors"],
            calculation_time=result.get("calculation_time")
        )
        
        if not result["success"]:
            logger.warning(f"Birth chart calculation failed: {result['errors']}")
            # Return 200 with success=False rather than HTTP error
            # This allows frontend to show detailed error information
        
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error in birth chart endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error during birth chart calculation: {str(e)}"
        )


@router.get("/house-systems", response_model=SupportedSystemsResponse)
async def get_supported_house_systems(
    astrology_service: AstrologyService = Depends(get_astrology_service)
) -> Dict[str, Any]:
    """
    Get list of supported house systems with descriptions.
    
    House systems determine how the 12 astrological houses are calculated:
    - placidus: Most popular Western system (default for most locations)
    - whole_sign: Ancient Vedic system (default for India)
    - regiomontanus: Medieval system (default for Germany/Austria)
    - etc.
    """
    try:
        systems = astrology_service.get_supported_house_systems()
        return SupportedSystemsResponse(house_systems=systems)
        
    except Exception as e:
        logger.error(f"Error getting house systems: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving house systems")


@router.post("/test-pipeline")
async def test_birth_chart_pipeline(
    astrology_service: AstrologyService = Depends(get_astrology_service)
) -> Dict[str, Any]:
    """
    Test endpoint to verify the birth chart pipeline works end-to-end.
    Uses sample data: January 7, 2003, 12:30 AM, Las Vegas, Nevada
    """
    try:
        logger.info("Testing birth chart pipeline with sample data")
        
        result = await astrology_service.calculate_birth_chart_advanced(
            raw_location="Las Vegas, Nevada",
            birth_date="2003-01-07",
            birth_time="00:30"
        )
        
        return {
            "test_status": "completed",
            "pipeline_success": result["success"],
            "steps_completed": list(result["processing_steps"].keys()),
            "location_processed": result["location_data"] is not None,
            "chart_calculated": result["birth_chart"] is not None,
            "errors": result["errors"],
            "sample_data": {
                "sun_sign": result["birth_chart"]["sun_sign"] if result["birth_chart"] else None,
                "moon_sign": result["birth_chart"]["moon_sign"] if result["birth_chart"] else None,
                "rising_sign": result["birth_chart"]["rising_sign"] if result["birth_chart"] else None,
            }
        }
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {str(e)}", exc_info=True)
        return {
            "test_status": "failed",
            "error": str(e),
            "pipeline_success": False
        }