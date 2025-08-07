#!/usr/bin/env python3
"""Complete test for dream image generation feature"""

import requests
import json
import time
from datetime import datetime, timedelta, timezone
from jose import jwt
from new_backend_ruminate.config import settings
import uuid
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from new_backend_ruminate.domain.user.entities import User
from new_backend_ruminate.domain.dream.entities.dream import Dream

async def ensure_test_user():
    """Ensure test user exists in database"""
    engine = create_async_engine(settings().db_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    test_user_id = uuid.UUID('11111111-1111-1111-1111-111111111111')
    
    async with AsyncSessionLocal() as session:
        # Check if user exists
        existing = await session.get(User, test_user_id)
        if not existing:
            test_user = User(
                id=test_user_id,
                google_sub='test_google_sub_123',
                email='test_image_gen@example.com',  # Different email to avoid conflicts
                name='Test Image Gen User'
            )
            session.add(test_user)
            await session.commit()
            print(f"✅ Created test user: {test_user_id}")
        else:
            print(f"✅ Test user already exists: {test_user_id}")
    
    await engine.dispose()
    return test_user_id

def create_jwt_token(user_id):
    """Create JWT token for test user"""
    secret = settings().jwt_secret
    payload = {
        'sub': 'test_google_sub_123',
        'email': 'test_image_gen@example.com',
        'uid': str(user_id),
        'exp': datetime.now(timezone.utc) + timedelta(days=1)
    }
    return jwt.encode(payload, secret, algorithm='HS256')

def create_dream_via_api(token):
    """Create a dream using the API"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create dream
    dream_data = {
        "id": str(uuid.uuid4()),
        "title": "Test Dream for Image Generation",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    response = requests.post(
        "http://localhost:8000/dreams",
        json=dream_data,
        headers=headers
    )
    
    if response.status_code == 201:
        dream = response.json()
        dream_id = dream["id"]
        print(f"✅ Created dream: {dream_id}")
        
        # Update with transcript
        update_data = {
            "transcript": """I found myself in a magical crystal cave filled with glowing gemstones. 
            The crystals pulsed with ethereal light in shades of blue, purple, and gold. 
            As I walked deeper, I discovered an underground lake that reflected the crystal light, 
            creating a kaleidoscope of colors on the water's surface. Floating above the lake 
            were luminescent butterflies made of pure light."""
        }
        
        response = requests.patch(
            f"http://localhost:8000/dreams/{dream_id}",
            json=update_data,
            headers=headers
        )
        
        if response.status_code == 200:
            print(f"✅ Added transcript to dream")
            return dream_id
        else:
            print(f"❌ Failed to add transcript: {response.text}")
            return None
    else:
        print(f"❌ Failed to create dream: {response.text}")
        return None

def test_image_generation(token, dream_id):
    """Test the image generation endpoint"""
    url = f"http://localhost:8000/dreams/{dream_id}/generate-image"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n🎨 Generating image for dream {dream_id}...")
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
            print(f"Image URL: {data.get('url', 'N/A')}")
            print(f"Prompt used: {data.get('prompt', 'N/A')}")
            print(f"Generated at: {data.get('generated_at', 'N/A')}")
            
            # Verify image URL
            if data.get('url'):
                print(f"\n🔍 Verifying image URL...")
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

def check_dream_details(token, dream_id):
    """Check the dream details including image info"""
    url = f"http://localhost:8000/dreams/{dream_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        dream = response.json()
        print(f"\n📋 Dream Details:")
        print(f"Title: {dream.get('title')}")
        print(f"Image URL: {dream.get('image_url', 'None')}")
        print(f"Image Status: {dream.get('image_status', 'None')}")
        print(f"Image Generated At: {dream.get('image_generated_at', 'None')}")

async def main():
    print("=" * 70)
    print("Complete Test: Dream Image Generation Feature")
    print("=" * 70)
    
    # Step 1: Ensure test user exists
    print("\n1️⃣ Setting up test user...")
    user_id = await ensure_test_user()
    
    # Step 2: Create JWT token
    print("\n2️⃣ Creating authentication token...")
    token = create_jwt_token(user_id)
    print(f"✅ Token created: {token[:20]}...")
    
    # Step 3: Create dream with transcript
    print("\n3️⃣ Creating test dream with transcript...")
    dream_id = create_dream_via_api(token)
    if not dream_id:
        print("❌ Failed to create dream")
        return 1
    
    # Step 4: Test image generation
    print("\n4️⃣ Testing image generation...")
    success = test_image_generation(token, dream_id)
    
    # Step 5: Check dream details
    if success:
        check_dream_details(token, dream_id)
    
    print("\n" + "=" * 70)
    if success:
        print("✅ Image generation test PASSED!")
        print("🎉 Phase 1 (API Integration) is complete!")
    else:
        print("❌ Image generation test FAILED!")
    print("=" * 70)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(asyncio.run(main()))