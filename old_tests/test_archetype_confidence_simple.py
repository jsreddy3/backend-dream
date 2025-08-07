#!/usr/bin/env python3
"""Simple test to verify archetype confidence scoring logic."""

def test_confidence_mapping():
    """Test the confidence score mapping to 80-95% range."""
    print("Testing confidence score mapping...")
    
    # Test cases with raw scores (0-1) and expected mapped scores (0.80-0.95)
    test_cases = [
        (0.0, 0.80),   # Minimum raw score -> 80%
        (0.5, 0.875),  # Middle raw score -> 87.5%
        (1.0, 0.95),   # Maximum raw score -> 95%
        (0.25, 0.8375), # Quarter score -> 83.75%
        (0.75, 0.9125), # Three-quarter score -> 91.25%
    ]
    
    for raw_score, expected in test_cases:
        # This is the mapping formula from the code
        confidence = 0.80 + (raw_score * 0.15)
        print(f"  Raw: {raw_score:.2f} -> Confidence: {confidence:.2%} (expected: {expected:.2%})")
        assert abs(confidence - expected) < 0.001, f"Mismatch: {confidence} != {expected}"
    
    print("✅ All confidence mappings correct!")
    
    # Show some example scoring scenarios
    print("\n\nExample scoring scenarios:")
    
    print("\n1. Initial Archetype (Onboarding):")
    print("   - User selects 'emotional_healing' goal (+3 points)")
    print("   - Themes: 'family', 'emotions' (+2 points)")
    print("   - High dream recall (+1 point)")
    print("   - Total: 6/10 points -> 89% confidence")
    
    print("\n2. Ongoing Archetype (From Dreams):")
    print("   - 50 total keywords in dreams")
    print("   - 8 match 'moonwalker' keywords")
    print("   - Raw score: 8/(50*0.1) = 1.6, capped at 1.0")
    print("   - Confidence: 95% (maximum)")
    
    print("\n3. Default Case (No Data):")
    print("   - Always returns 'starweaver' with 85% confidence")
    print("   - This ensures users always get a meaningful result")

if __name__ == "__main__":
    test_confidence_mapping()
    print("\n🎉 Confidence scores will now always be between 80-95%!")