"""High-level astrology service that orchestrates location and birth chart services."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .location_service import LocationService
from .birth_chart_service import BirthChartService

logger = logging.getLogger(__name__)


class AstrologyService:
    """Main astrology service that orchestrates the full birth chart pipeline."""
    
    def __init__(self, location_service: LocationService, birth_chart_service: BirthChartService):
        self.location_service = location_service
        self.birth_chart_service = birth_chart_service
    
    async def calculate_birth_chart_advanced(
        self,
        raw_location: str,
        birth_date: str,  # YYYY-MM-DD
        birth_time: str,  # HH:MM
        house_system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete birth chart calculation pipeline from raw user input.
        
        Args:
            raw_location: User's messy location input (e.g., "parizz", "NYC", "Las Vegas, Nevada")
            birth_date: Birth date in YYYY-MM-DD format
            birth_time: Birth time in HH:MM format (24-hour)
            house_system: Optional house system override
        
        Returns:
            Complete birth chart data with metadata about the processing steps
        """
        logger.info(f"Starting birth chart calculation for {birth_date} {birth_time} in '{raw_location}'")
        
        result = {
            "input": {
                "raw_location": raw_location,
                "birth_date": birth_date,
                "birth_time": birth_time,
                "requested_house_system": house_system
            },
            "processing_steps": {},
            "location_data": None,
            "birth_chart": None,
            "errors": [],
            "success": False
        }
        
        try:
            # STEP 1: Location sanitization and geocoding
            logger.debug("Step 1: Processing location")
            location_data = await self.location_service.geocode_location(raw_location)
            
            if not location_data:
                error_msg = f"Could not geocode location: '{raw_location}'"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                return result
            
            result["location_data"] = location_data
            result["processing_steps"]["location_processing"] = {
                "original_input": raw_location,
                "sanitized_input": location_data.get("sanitized_input", raw_location),
                "coordinates": f"{location_data['latitude']}, {location_data['longitude']}",
                "timezone": location_data["timezone"],
                "formatted_address": location_data["formatted_address"]
            }
            
            # STEP 2: House system selection
            if not house_system:
                house_system = self.location_service.get_default_house_system(
                    location_data.get("country", "")
                )
            
            result["processing_steps"]["house_system"] = {
                "selected": house_system,
                "reason": f"Default for {location_data.get('country', 'unknown location')}"
            }
            
            # STEP 3: Birth data validation
            logger.debug("Step 3: Validating birth data")
            validation_errors = self.birth_chart_service.validate_birth_data(
                birth_date=birth_date,
                birth_time=birth_time,
                timezone=location_data["timezone"],
                latitude=location_data["latitude"],
                longitude=location_data["longitude"]
            )
            
            if validation_errors:
                result["errors"].extend([f"{field}: {error}" for field, error in validation_errors.items()])
                return result
            
            result["processing_steps"]["validation"] = "✅ All birth data valid"
            
            # STEP 4: Birth chart calculation
            logger.debug("Step 4: Calculating birth chart")
            birth_chart = self.birth_chart_service.calculate_birth_chart(
                birth_date=birth_date,
                birth_time=birth_time,
                timezone=location_data["timezone"],
                latitude=location_data["latitude"],
                longitude=location_data["longitude"],
                birth_place=location_data["formatted_address"],
                house_system=house_system
            )
            
            result["birth_chart"] = birth_chart
            result["processing_steps"]["chart_calculation"] = {
                "status": "✅ Chart calculated successfully",
                "house_system_used": house_system,
                "calculation_time": datetime.utcnow().isoformat()
            }
            
            result["success"] = True
            logger.info(f"Successfully calculated birth chart for {birth_date} {birth_time} in {location_data['formatted_address']}")
            
            return result
            
        except ImportError as e:
            error_msg = f"Astrology library not available: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            result["processing_steps"]["error"] = "⚠️ Kerykeion library not installed"
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error in birth chart calculation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)
            return result
    
    def get_supported_house_systems(self) -> Dict[str, str]:
        """Get supported house systems with descriptions."""
        systems = self.birth_chart_service.get_supported_house_systems()
        return {
            system: self._get_house_system_description(system) 
            for system in systems
        }
    
    def _get_house_system_description(self, system: str) -> str:
        """Get description for a house system."""
        descriptions = {
            "placidus": "Most popular Western system, unequal house sizes",
            "whole_sign": "Ancient system used in Vedic astrology, equal 30° houses",
            "porphyry": "Equal division of quadrants, popular in Europe", 
            "regiomontanus": "Medieval system, popular in Germany",
            "campanus": "Based on prime vertical, used for location-specific readings",
            "equal": "Equal 30° houses from Ascendant, simple and clear"
        }
        return descriptions.get(system, f"{system.title()} house system")