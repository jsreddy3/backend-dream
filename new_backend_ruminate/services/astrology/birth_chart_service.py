"""Birth chart calculation service using Kerykeion library."""

import logging
from datetime import datetime, time
from typing import Dict, List, Any, Optional
import pytz

try:
    from kerykeion import AstrologicalSubject
    KERYKEION_AVAILABLE = True
except ImportError:
    KERYKEION_AVAILABLE = False

logger = logging.getLogger(__name__)


class BirthChartService:
    """Service for calculating birth charts with proper timezone handling."""
    
    def __init__(self):
        if not KERYKEION_AVAILABLE:
            logger.warning("Kerykeion not available - birth chart calculations will fail")
    
    def calculate_birth_chart(
        self,
        birth_date: str,  # YYYY-MM-DD
        birth_time: str,  # HH:MM
        timezone: str,    # IANA timezone
        latitude: float,
        longitude: float,
        birth_place: str,
        house_system: str = "placidus"
    ) -> Dict[str, Any]:
        """Calculate complete birth chart with error handling."""
        
        if not KERYKEION_AVAILABLE:
            raise ImportError("Kerykeion library not installed. Run: pip install kerykeion")
        
        try:
            # Parse date and time
            year, month, day = map(int, birth_date.split('-'))
            hour, minute = map(int, birth_time.split(':'))
            
            # Validate timezone
            try:
                pytz.timezone(timezone)
            except pytz.UnknownTimeZoneError:
                raise ValueError(f"Unknown timezone: {timezone}")
            
            # Create AstrologicalSubject (this is the main Kerykeion class)
            subject = AstrologicalSubject(
                name="Birth Chart",
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                lat=latitude,
                lng=longitude,
                tz_str=timezone,
                city=birth_place,
                nation="",  # Will be inferred from coordinates
                houses_system_identifier=self._map_house_system(house_system)
            )
            
            # Extract and format data
            return self._format_chart_data(subject, birth_place)
            
        except Exception as e:
            logger.error(f"Birth chart calculation failed: {str(e)}")
            raise ValueError(f"Chart calculation failed: {str(e)}")
    
    def _format_chart_data(self, subject: Any, birth_place: str) -> Dict[str, Any]:
        """Format Kerykeion AstrologicalSubject or dict into our API response format."""
        
        # Check if subject is a dict (for testing) or AstrologicalSubject
        if isinstance(subject, dict):
            # Handle dict format for testing
            planets = []
            if "planets" in subject:
                for name, data in subject["planets"].items():
                    planets.append({
                        "name": name,
                        "sign": data.get("sign", ""),
                        "degree": data.get("longitude", 0.0),
                        "house": data.get("house", 0),
                        "retrograde": data.get("retrograde", False)
                    })
            
            houses = {}
            if "houses" in subject:
                for house_num, data in subject["houses"].items():
                    houses[int(house_num)] = {
                        "sign": data.get("sign", ""),
                        "degree": data.get("longitude", 0.0)
                    }
            
            ascendant = subject.get("ascendant", {})
            midheaven = subject.get("midheaven", {})
            
            # Extract datetime info if present
            birth_datetime = subject.get("birth_datetime_utc", "1990-01-01 00:00")
            julian_day = subject.get("julian_day", 0.0)
            
            # Get sun/moon/rising from planets or summary fields
            sun_sign = subject.get("sun_sign", "")
            moon_sign = subject.get("moon_sign", "")
            rising_sign = subject.get("rising_sign", ascendant.get("sign", ""))
            
            # If not in summary, extract from planets
            if not sun_sign and "planets" in subject and "Sun" in subject["planets"]:
                sun_sign = subject["planets"]["Sun"].get("sign", "")
            if not moon_sign and "planets" in subject and "Moon" in subject["planets"]:
                moon_sign = subject["planets"]["Moon"].get("sign", "")
            
            # Convert aspects from dict to list format if needed
            aspects = subject.get("aspects", [])
            if isinstance(aspects, dict):
                aspects = list(aspects.values())
                
            return {
                "birth_datetime_utc": birth_datetime,
                "julian_day": julian_day,
                "ascendant": {
                    "sign": ascendant.get("sign", rising_sign),
                    "degree": ascendant.get("longitude", 0.0)
                },
                "midheaven": {
                    "sign": midheaven.get("sign", ""),
                    "degree": midheaven.get("longitude", 0.0)
                },
                "planets": planets,
                "houses": houses,
                "aspects": aspects,
                "sun_sign": sun_sign,
                "moon_sign": moon_sign,
                "rising_sign": rising_sign,
                "chart_svg": subject.get("chart_svg")
            }
        
        # Original code for AstrologicalSubject
        planets = []
        planet_names = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
        
        for planet_name in planet_names:
            if hasattr(subject, planet_name):
                planet = getattr(subject, planet_name)
                planets.append({
                    "name": planet_name.title(),
                    "sign": getattr(planet, 'sign', ''),
                    "degree": getattr(planet, 'position', 0.0),
                    "house": self._extract_house_number(getattr(planet, 'house', '')),
                    "retrograde": getattr(planet, 'retrograde', False)
                })
        
        # Extract house cusps
        houses = {}
        for i in range(1, 13):
            house_attr = f"first_house" if i == 1 else f"house_{i}"
            if hasattr(subject, house_attr):
                house_data = getattr(subject, house_attr)
                houses[i] = {
                    "sign": getattr(house_data, 'sign', ''),
                    "degree": getattr(house_data, 'position', 0.0)
                }
        
        # Get sun and moon signs for summary
        sun_sign = getattr(subject.sun, 'sign', '') if hasattr(subject, 'sun') else ''
        moon_sign = getattr(subject.moon, 'sign', '') if hasattr(subject, 'moon') else ''
        rising_sign = getattr(subject.first_house, 'sign', '') if hasattr(subject, 'first_house') else ''
        
        return {
            "birth_datetime_utc": f"{subject.year}-{subject.month:02d}-{subject.day:02d} {subject.hour:02d}:{subject.minute:02d}",
            "julian_day": getattr(subject, 'julian_day', 0.0),
            "ascendant": {
                "sign": rising_sign,
                "degree": getattr(subject.first_house, 'position', 0.0) if hasattr(subject, 'first_house') else 0.0
            },
            "midheaven": {
                "sign": getattr(subject.tenth_house, 'sign', '') if hasattr(subject, 'tenth_house') else '',
                "degree": getattr(subject.tenth_house, 'position', 0.0) if hasattr(subject, 'tenth_house') else 0.0
            },
            "planets": planets,
            "houses": houses,
            "aspects": [],  # We'll implement aspects later
            "sun_sign": sun_sign,
            "moon_sign": moon_sign,
            "rising_sign": rising_sign,
            "chart_svg": None  # Could generate SVG here if needed
        }
    
    def _extract_aspects(self, aspects_data: Dict) -> List[Dict[str, Any]]:
        """Extract major aspects from chart data."""
        aspects = []
        
        # Kerykeion aspect format varies, so we'll handle it defensively
        if not aspects_data:
            return aspects
            
        for aspect_key, aspect_info in aspects_data.items():
            if isinstance(aspect_info, dict):
                aspects.append({
                    "planet1": aspect_info.get("planet1", ""),
                    "planet2": aspect_info.get("planet2", ""),
                    "aspect": aspect_info.get("aspect", ""),
                    "orb": aspect_info.get("orb", 0.0),
                    "applying": aspect_info.get("applying", False)
                })
        
        return aspects[:20]  # Limit to 20 major aspects
    
    def _map_house_system(self, system: str) -> str:
        """Map house system names to Kerykeion single-letter codes."""
        mapping = {
            "placidus": "P",
            "whole_sign": "W", 
            "porphyry": "O",
            "regiomontanus": "R",
            "campanus": "C",
            "equal": "A"
        }
        return mapping.get(system.lower(), "P")  # Default to Placidus
    
    def _extract_house_number(self, house_str: str) -> int:
        """Extract house number from strings like 'First_House', 'Second_House', etc."""
        if not house_str:
            return 1
        
        house_map = {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4,
            'fifth': 5, 'sixth': 6, 'seventh': 7, 'eighth': 8,
            'ninth': 9, 'tenth': 10, 'eleventh': 11, 'twelfth': 12
        }
        
        # Convert to lowercase and remove underscores
        house_lower = house_str.lower().replace('_', ' ').replace(' house', '')
        
        return house_map.get(house_lower, 1)
    
    def validate_birth_data(
        self,
        birth_date: str,
        birth_time: str,
        timezone: str,
        latitude: float,
        longitude: float
    ) -> Dict[str, str]:
        """Validate birth data and return any errors."""
        errors = {}
        
        # Validate date format
        try:
            datetime.strptime(birth_date, "%Y-%m-%d")
        except ValueError:
            errors["birth_date"] = "Invalid date format. Use YYYY-MM-DD"
        
        # Validate time format
        try:
            time.fromisoformat(birth_time)
        except ValueError:
            errors["birth_time"] = "Invalid time format. Use HH:MM"
        
        # Validate timezone
        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            errors["timezone"] = f"Unknown timezone: {timezone}"
        
        # Validate coordinates
        if not (-90 <= latitude <= 90):
            errors["latitude"] = "Latitude must be between -90 and 90"
        
        if not (-180 <= longitude <= 180):
            errors["longitude"] = "Longitude must be between -180 and 180"
        
        return errors
    
    def get_supported_house_systems(self) -> List[str]:
        """Return list of supported house systems."""
        return [
            "placidus",
            "whole_sign", 
            "porphyry",
            "regiomontanus",
            "campanus",
            "equal"
        ]