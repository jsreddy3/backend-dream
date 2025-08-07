#!/usr/bin/env python3
"""Simple API test for dream image generation"""

import requests
import json
import time
import uuid
from datetime import datetime, timezone

# Hardcoded test token (from create_test_data.py output)
# You may need to run create_test_data.py once to get a valid token
TEST_TOKEN = None

def get_test_token():
    """Get a test token by calling the auth endpoint with test credentials"""
    # For now, we'll use a hardcoded approach
    # In production, this would use proper OAuth flow
    print("⚠️  Using test authentication...")
    print("Please ensure you have run create_test_data.py at least once")
    print("and the backend server is running on http://localhost:8000")
    return None

def create_dream_and_test_image():
    """Create a dream and test image generation"""
    
    # Step 1: Create a dream (using unauthed endpoint for testing)
    print("\n1️⃣ Creating test dream...")
    
    # For this test, we'll use the existing test dream ID from create_test_data.py
    dream_id = '22222222-2222-2222-2222-222222222222'
    print(f"Using test dream ID: {dream_id}")
    
    # Step 2: Test the test endpoint first
    print("\n2️⃣ Testing DALL-E integration with test endpoint...")
    test_url = "http://localhost:8000/dreams/test-image-generation"
    
    # Create a minimal auth header (the endpoint might not require auth)
    headers = {}
    
    try:
        response = requests.post(test_url, headers=headers, timeout=30)
        print(f"Test endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Test successful!")
            print(f"Test image URL: {data.get('url', 'N/A')}")
        elif response.status_code == 401:
            print("❌ Authentication required. Please check server logs for test user setup.")
            return False
        else:
            print(f"❌ Test failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error calling test endpoint: {str(e)}")
        return False
    
    # Step 3: Test the actual endpoint
    print(f"\n3️⃣ Testing image generation for dream {dream_id}...")
    url = f"http://localhost:8000/dreams/{dream_id}/generate-image"
    
    print(f"Calling POST {url}")
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, timeout=60)
        elapsed = time.time() - start_time
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Image generated successfully!")
            print(f"Image URL: {data.get('url', 'N/A')[:100]}...")
            print(f"Prompt used: {data.get('prompt', 'N/A')}")
            print(f"Generated at: {data.get('generated_at', 'N/A')}")
            
            # Try to verify the image URL
            if data.get('url'):
                print(f"\n🔍 Verifying image is accessible...")
                try:
                    img_response = requests.head(data['url'], timeout=5)
                    if img_response.status_code in [200, 403]:  # 403 might be OK for S3 presigned URLs
                        print("✅ Image URL appears valid")
                    else:
                        print(f"⚠️  Image URL returned status: {img_response.status_code}")
                except Exception as e:
                    print(f"⚠️  Could not verify image URL: {str(e)}")
            
            return True
        elif response.status_code == 401:
            print("❌ Authentication required")
            print("Please ensure:")
            print("1. The test user exists in the database")
            print("2. You have a valid JWT token")
            print("3. The backend server is configured correctly")
            return False
        elif response.status_code == 404:
            print("❌ Dream not found")
            print("Please run create_test_data.py first to create the test dream")
            return False
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def main():
    print("=" * 70)
    print("Simple API Test: Dream Image Generation")
    print("=" * 70)
    
    # Check if server is running
    print("\n🔍 Checking if backend server is running...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            print("✅ Backend server is running")
        else:
            print("⚠️  Backend server returned unexpected status")
    except:
        print("❌ Backend server is not running!")
        print("Please start it with: uvicorn new_backend_ruminate.main:app --reload")
        return 1
    
    # Run the test
    success = create_dream_and_test_image()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ Image generation test PASSED!")
        print("🎉 Phase 1.4 (API Endpoint) is complete!")
    else:
        print("❌ Image generation test FAILED!")
        print("\nTroubleshooting:")
        print("1. Check backend server logs for errors")
        print("2. Ensure OPENAI_API_KEY is set in environment")
        print("3. Ensure AWS credentials are configured")
        print("4. Run create_test_data.py to create test user/dream")
    print("=" * 70)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())