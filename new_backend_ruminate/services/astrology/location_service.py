"""Location service for geocoding birth places."""

import logging
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)


class LocationService:
    """Service for converting location names to coordinates."""
    
    def __init__(self, llm_service=None):
        # We'll use a free geocoding service - you could also use Google Maps API
        self.geocoding_url = "https://nominatim.openstreetmap.org/search"
        # Cache for common locations
        self._location_cache = {}
        # LLM service for location sanitization
        self._llm = llm_service
        
    async def sanitize_location_input(self, raw_location: str) -> Optional[str]:
        """Use LLM to sanitize and standardize location input."""
        if not self._llm:
            logger.debug("No LLM service available for location sanitization")
            return raw_location.strip()
            
        try:
            messages = [
                {
                    "role": "system", 
                    "content": "You are a location standardization assistant. Convert user input into a clean, standardized location format suitable for geocoding APIs. Fix typos, expand abbreviations, and provide the most specific location possible. Return your response as JSON."
                },
                {
                    "role": "user",
                    "content": f"Standardize this location: '{raw_location}'\n\nReturn the cleanest, most complete location name that would work best for a geocoding service (e.g., 'Paris, France' instead of 'Parizz' or 'NYC' -> 'New York City, NY, USA'). Please respond in JSON format with the standardized location and confidence level."
                }
            ]
            
            json_schema = {
                "type": "object",
                "properties": {
                    "standardized_location": {
                        "type": "string",
                        "description": "The clean, standardized location name"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Confidence in the standardization"
                    }
                },
                "required": ["standardized_location", "confidence"]
            }
            
            result = await self._llm.generate_structured_response(
                messages=messages,
                response_format={"type": "json_object"},
                json_schema=json_schema
            )
            
            standardized = result.get("standardized_location", raw_location.strip())
            confidence = result.get("confidence", "unknown")
            
            logger.info(f"Location sanitized: '{raw_location}' -> '{standardized}' (confidence: {confidence})")
            return standardized
            
        except Exception as e:
            logger.warning(f"Failed to sanitize location '{raw_location}': {str(e)}")
            return raw_location.strip()

    async def geocode_location(self, location_name: str) -> Optional[Dict[str, any]]:
        """Convert location name to coordinates and timezone."""
        
        # First, sanitize the input using LLM if available
        sanitized_location = await self.sanitize_location_input(location_name)
        if not sanitized_location:
            return None
        
        # Check cache first (use sanitized location for cache key)
        cache_key = sanitized_location.lower().strip()
        if cache_key in self._location_cache:
            logger.info(f"Using cached coordinates for {sanitized_location}")
            return self._location_cache[cache_key]
        
        try:
            # Use Nominatim (OpenStreetMap) geocoding service
            params = {
                'q': sanitized_location,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'DreamAnalysisApp/1.0'  # Required by Nominatim
            }
            
            response = requests.get(
                self.geocoding_url, 
                params=params, 
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Geocoding failed for {sanitized_location}: HTTP {response.status_code}")
                return None
            
            data = response.json()
            if not data:
                logger.warning(f"No results found for location: {sanitized_location}")
                return None
            
            result = data[0]
            latitude = float(result['lat'])
            longitude = float(result['lon'])
            
            # Try to determine timezone from coordinates
            timezone = await self._get_timezone_from_coords(latitude, longitude)
            
            location_data = {
                'latitude': latitude,
                'longitude': longitude,
                'timezone': timezone,
                'formatted_address': result.get('display_name', sanitized_location),
                'country': result.get('address', {}).get('country', ''),
                'city': self._extract_city(result.get('address', {})),
                'original_input': location_name,  # Keep track of original input
                'sanitized_input': sanitized_location
            }
            
            # Cache the result
            self._location_cache[cache_key] = location_data
            
            logger.info(f"Geocoded {sanitized_location} -> {latitude}, {longitude}, {timezone}")
            return location_data
            
        except requests.RequestException as e:
            logger.error(f"Network error geocoding {sanitized_location}: {str(e)}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"Data parsing error for {sanitized_location}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error geocoding {sanitized_location}: {str(e)}")
            return None
    
    async def _get_timezone_from_coords(self, latitude: float, longitude: float) -> str:
        """Get timezone from coordinates using a free API."""
        try:
            # Check for known exceptions first
            # Las Vegas and most of Nevada use Pacific Time despite being geographically in Mountain Time zone
            if 35 <= latitude <= 37 and -116 <= longitude <= -114:  # Las Vegas area
                return "America/Los_Angeles"
            
            # Phoenix area - uses Mountain Standard Time year-round (no DST)
            if 32 <= latitude <= 34 and -113 <= longitude <= -111:  # Phoenix area
                return "America/Phoenix"
            
            # Use TimeZoneDB API (free tier available) or similar service
            # For now, we'll use a simple timezone mapping based on longitude
            # In production, you'd use a proper timezone API
            
            # Simple timezone estimation (not 100% accurate but better than nothing)
            # This is a rough approximation - use a real timezone API for production
            timezone_offset = round(longitude / 15)  # Use round instead of int for better accuracy
            
            # Map to common timezones
            timezone_map = {
                -12: "Pacific/Wake",
                -11: "Pacific/Midway", 
                -10: "Pacific/Honolulu",
                -9: "America/Anchorage",
                -8: "America/Los_Angeles",
                -7: "America/Denver", 
                -6: "America/Chicago",
                -5: "America/New_York",
                -4: "America/Halifax",
                -3: "America/Sao_Paulo",
                -2: "Atlantic/South_Georgia",
                -1: "Atlantic/Azores",
                0: "Europe/London",
                1: "Europe/Paris",
                2: "Europe/Berlin",
                3: "Europe/Moscow",
                4: "Asia/Dubai",
                5: "Asia/Karachi", 
                6: "Asia/Dhaka",
                7: "Asia/Bangkok",
                8: "Asia/Shanghai",
                9: "Asia/Tokyo",
                10: "Australia/Sydney",
                11: "Pacific/Noumea",
                12: "Pacific/Auckland"
            }
            
            return timezone_map.get(timezone_offset, "UTC")
            
        except Exception as e:
            logger.warning(f"Could not determine timezone for {latitude}, {longitude}: {str(e)}")
            return "UTC"
    
    def _extract_city(self, address_components: Dict) -> str:
        """Extract city name from address components."""
        # Try different city field names
        city_fields = ['city', 'town', 'village', 'municipality', 'county']
        
        for field in city_fields:
            if field in address_components:
                return address_components[field]
        
        return ""
    
    def get_default_house_system(self, country: str = "") -> str:
        """Get default house system based on location/tradition."""
        # Different astrological traditions prefer different house systems
        country_lower = country.lower()
        
        if any(keyword in country_lower for keyword in ['india', 'hindu', 'vedic']):
            return "whole_sign"  # Vedic tradition
        elif any(keyword in country_lower for keyword in ['germany', 'austria']):
            return "regiomontanus"  # European tradition
        else:
            return "placidus"  # Most common Western system
    
    def validate_location(self, location_name: str) -> bool:
        """Basic validation of location string."""
        if not location_name or len(location_name.strip()) < 2:
            return False
        
        # Check for obviously invalid inputs
        invalid_patterns = ['test', '123', 'null', 'undefined']
        location_lower = location_name.lower().strip()
        
        return not any(pattern in location_lower for pattern in invalid_patterns)
    
    def get_cached_locations(self) -> Dict[str, Dict]:
        """Return cached locations for debugging."""
        return self._location_cache.copy()
    
    def clear_cache(self) -> None:
        """Clear location cache."""
        self._location_cache.clear()
        logger.info("Location cache cleared")


# Pre-populate cache with common locations for better performance
COMMON_LOCATIONS = {
    "new york, ny": {
        "latitude": 40.7128,
        "longitude": -74.0060, 
        "timezone": "America/New_York",
        "formatted_address": "New York, NY, USA",
        "country": "United States",
        "city": "New York"
    },
    "london, uk": {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "timezone": "Europe/London", 
        "formatted_address": "London, UK",
        "country": "United Kingdom",
        "city": "London"
    },
    "los angeles, ca": {
        "latitude": 34.0522,
        "longitude": -118.2437,
        "timezone": "America/Los_Angeles",
        "formatted_address": "Los Angeles, CA, USA", 
        "country": "United States",
        "city": "Los Angeles"
    }
}


