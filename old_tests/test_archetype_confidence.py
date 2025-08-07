#!/usr/bin/env python3
"""Test script to verify archetype confidence scoring is in 80-95% range."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from new_backend_ruminate.services.profile.service import ProfileService
from new_backend_ruminate.domain.user.preferences import UserPreferences
from uuid import uuid4

def test_initial_archetype_scoring():
    """Test the initial archetype suggestion during onboarding."""
    print("Testing initial archetype suggestion (onboarding)...")
    
    service = ProfileService(None, None)  # We don't need repos for this test
    
    test_cases = [
        {
            "name": "Minimal preferences",
            "preferences": UserPreferences(
                id=uuid4(),
                user_id=uuid4(),
                primary_goal="self_discovery"
            )
        },
        {
            "name": "Rich preferences",
            "preferences": UserPreferences(
                id=uuid4(),
                user_id=uuid4(),
                primary_goal="emotional_healing",
                common_dream_themes=["family", "water", "emotions"],
                dream_recall_frequency="often",
                dream_vividness="very_vivid"
            )
        },
        {
            "name": "Empty preferences",
            "preferences": UserPreferences(
                id=uuid4(),
                user_id=uuid4()
            )
        }
    ]
    
    for test in test_cases:
        archetype, confidence = service.suggest_initial_archetype(test["preferences"])
        print(f"\n{test['name']}:")
        print(f"  Archetype: {archetype}")
        print(f"  Confidence: {confidence:.2%}")
        assert 0.80 <= confidence <= 0.95, f"Confidence {confidence} not in range 0.80-0.95"
    
    print("\n✅ All initial archetype tests passed!")

def test_ongoing_archetype_scoring():
    """Test the ongoing archetype calculation from dream content."""
    print("\n\nTesting ongoing archetype calculation (from dreams)...")
    
    service = ProfileService(None, None)
    
    test_cases = [
        {
            "name": "No keywords",
            "keywords": {}
        },
        {
            "name": "Few keywords",
            "keywords": {"fly": 2, "journey": 1}
        },
        {
            "name": "Many keywords",
            "keywords": {
                "fly": 10, "journey": 8, "travel": 5, 
                "adventure": 7, "explore": 6, "path": 4
            }
        },
        {
            "name": "Mixed archetype keywords",
            "keywords": {
                "symbol": 3, "fly": 2, "emotion": 4,
                "time": 2, "shadow": 1, "light": 3
            }
        }
    ]
    
    for test in test_cases:
        archetype, confidence = service._calculate_archetype(test["keywords"])
        print(f"\n{test['name']}:")
        print(f"  Keywords: {test['keywords']}")
        print(f"  Archetype: {archetype}")
        print(f"  Confidence: {confidence:.2%}")
        assert 0.80 <= confidence <= 0.95, f"Confidence {confidence} not in range 0.80-0.95"
    
    print("\n✅ All ongoing archetype tests passed!")

if __name__ == "__main__":
    test_initial_archetype_scoring()
    test_ongoing_archetype_scoring()
    print("\n🎉 All tests passed! Confidence scores are now always between 80-95%")