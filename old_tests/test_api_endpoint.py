#!/usr/bin/env python3
"""Test the dream image generation API endpoint"""

import requests
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
import time

def create_test_token():
    """Create a test JWT token"""
    from jose import jwt
    from new_backend_ruminate.config import settings
    
    # Use the test user from create_test_data.py
    test_user_id = '11111111-1111-1111-1111-111111111111'
    
    secret = settings().jwt_secret
    payload = {
        'sub': 'test_google_sub_123',
        'email': 'test@example.com',
        'uid': test_user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=1)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    return token, test_user_id

def test_image_generation():
    """Test the image generation endpoint"""
    # Get test credentials
    token, user_id = create_test_token()
    dream_id = '22222222-2222-2222-2222-222222222222'  # From create_test_data.py
    
    print(f"Test User ID: {user_id}")
    print(f"Test Dream ID: {dream_id}")
    print(f"Token: {token[:20]}...")
    
    # Test the endpoint
    url = f"http://localhost:8000/dreams/{dream_id}/generate-image"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"\nCalling POST {url}")
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, timeout=60)
        elapsed = time.time() - start_time
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success!")
            print(f"Image URL: {data.get('url', 'N/A')}")
            print(f"Prompt: {data.get('prompt', 'N/A')}")
            print(f"Generated at: {data.get('generated_at', 'N/A')}")
            print(f"Message: {data.get('message', 'N/A')}")
            
            # Verify we can access the image URL
            if data.get('url'):
                print(f"\nVerifying image URL is accessible...")
                img_response = requests.head(data['url'])
                if img_response.status_code == 200:
                    print("✅ Image URL is accessible")
                else:
                    print(f"❌ Image URL returned status: {img_response.status_code}")
            
            return True
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
    """Main test function"""
    print("=" * 60)
    print("Testing Dream Image Generation API Endpoint")
    print("=" * 60)
    
    # Run the test (assuming test data already exists)
    success = test_image_generation()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ API endpoint test passed!")
    else:
        print("❌ API endpoint test failed!")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())