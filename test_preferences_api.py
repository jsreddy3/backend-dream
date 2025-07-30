#!/usr/bin/env python3
"""Test script for user preferences API endpoints."""

import asyncio
import aiohttp
import json
from datetime import time
import sys

# Test configuration
API_BASE = "http://localhost:8000/api"
TEST_TOKEN = None  # Will be set after getting token

# Test data for preferences
TEST_PREFERENCES = {
    "typical_bedtime": "23:00:00",
    "typical_wake_time": "07:00:00", 
    "sleep_quality": "good",
    "dream_recall_frequency": "often",
    "dream_vividness": "vivid",
    "common_dream_themes": ["flying", "water", "adventure"],
    "primary_goal": "self_discovery",
    "interests": ["lucid_dreaming", "symbolism"],
    "reminder_enabled": True,
    "reminder_time": "07:30:00",
    "reminder_frequency": "daily",
    "reminder_days": [],
    "personality_traits": {"openness": "high"},
    "onboarding_completed": False
}

async def get_test_token():
    """Get a test JWT token."""
    global TEST_TOKEN
    
    # First, try to read from file if it exists
    try:
        with open('test_token.txt', 'r') as f:
            TEST_TOKEN = f.read().strip()
            print("✅ Using existing test token")
            return
    except FileNotFoundError:
        pass
    
    print("❌ No test token found. Please run get_test_token.py first")
    sys.exit(1)

async def test_get_preferences(session):
    """Test GET /users/me/preferences"""
    print("\n🔍 Testing GET /users/me/preferences...")
    
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    async with session.get(f"{API_BASE}/users/me/preferences", headers=headers) as resp:
        print(f"Status: {resp.status}")
        data = await resp.json()
        
        if resp.status == 404:
            print("✅ No preferences found (expected for new user)")
            print(f"Message: {data.get('detail')}")
            return True
        elif resp.status == 200:
            print("✅ Found existing preferences:")
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"❌ Unexpected status: {resp.status}")
            print(f"Response: {data}")
            return False

async def test_create_preferences(session):
    """Test POST /users/me/preferences"""
    print("\n🔍 Testing POST /users/me/preferences...")
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with session.post(
        f"{API_BASE}/users/me/preferences",
        headers=headers,
        json=TEST_PREFERENCES
    ) as resp:
        print(f"Status: {resp.status}")
        data = await resp.json()
        
        if resp.status == 201:
            print("✅ Preferences created successfully!")
            print(f"ID: {data.get('id')}")
            print(f"Initial archetype: {data.get('initial_archetype')}")
            print(f"Onboarding completed: {data.get('onboarding_completed')}")
            return True
        elif resp.status == 400:
            print("❌ Preferences already exist")
            print(f"Message: {data.get('detail')}")
            # This is actually OK if we're running the test multiple times
            return True
        else:
            print(f"❌ Failed to create preferences: {resp.status}")
            print(f"Response: {data}")
            return False

async def test_update_preferences(session):
    """Test PATCH /users/me/preferences"""
    print("\n🔍 Testing PATCH /users/me/preferences...")
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Content-Type": "application/json"
    }
    
    update_data = {
        "sleep_quality": "excellent",
        "dream_recall_frequency": "always",
        "onboarding_completed": True
    }
    
    async with session.patch(
        f"{API_BASE}/users/me/preferences",
        headers=headers,
        json=update_data
    ) as resp:
        print(f"Status: {resp.status}")
        data = await resp.json()
        
        if resp.status == 200:
            print("✅ Preferences updated successfully!")
            print(f"Sleep quality: {data.get('sleep_quality')}")
            print(f"Dream recall: {data.get('dream_recall_frequency')}")
            print(f"Onboarding completed: {data.get('onboarding_completed')}")
            return True
        else:
            print(f"❌ Failed to update preferences: {resp.status}")
            print(f"Response: {data}")
            return False

async def test_suggest_archetype(session):
    """Test POST /users/me/preferences/suggest-archetype"""
    print("\n🔍 Testing POST /users/me/preferences/suggest-archetype...")
    
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    async with session.post(
        f"{API_BASE}/users/me/preferences/suggest-archetype",
        headers=headers
    ) as resp:
        print(f"Status: {resp.status}")
        data = await resp.json()
        
        if resp.status == 200:
            print("✅ Archetype suggestion received!")
            print(f"Suggested archetype: {data.get('suggested_archetype')}")
            print(f"Confidence: {data.get('confidence')}")
            print(f"Details: {json.dumps(data.get('archetype_details'), indent=2)}")
            return True
        else:
            print(f"❌ Failed to get archetype suggestion: {resp.status}")
            print(f"Response: {data}")
            return False

async def main():
    """Run all tests."""
    print("🚀 Starting User Preferences API Tests")
    
    # Get test token
    await get_test_token()
    
    # Create session
    async with aiohttp.ClientSession() as session:
        # Run tests
        results = []
        
        # Test 1: Get preferences (should be 404 initially)
        results.append(await test_get_preferences(session))
        
        # Test 2: Create preferences
        results.append(await test_create_preferences(session))
        
        # Test 3: Get preferences again (should be 200 now)
        results.append(await test_get_preferences(session))
        
        # Test 4: Update preferences
        results.append(await test_update_preferences(session))
        
        # Test 5: Suggest archetype
        results.append(await test_suggest_archetype(session))
        
        # Summary
        print("\n" + "="*50)
        print("📊 Test Summary:")
        passed = sum(results)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        if passed == total:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())