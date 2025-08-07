#!/usr/bin/env python3
"""Final quick test - delete existing image and regenerate"""

import requests
from generate_test_token import generate_token
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from new_backend_ruminate.config import settings
import uuid
import time

async def clear_existing_image():
    """Clear image from test dream to test regeneration"""
    engine = create_async_engine(settings().db_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    dream_id = uuid.UUID('22222222-2222-2222-2222-222222222222')
    
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                UPDATE dreams 
                SET image_url = NULL, 
                    image_prompt = NULL, 
                    image_generated_at = NULL, 
                    image_status = NULL,
                    image_metadata = NULL
                WHERE id = :dream_id
            """),
            {"dream_id": dream_id}
        )
        await session.commit()
        print("✅ Cleared existing image from test dream")
    
    await engine.dispose()

def test_image_generation():
    """Test image generation on cleaned dream"""
    token = generate_token()
    headers = {"Authorization": f"Bearer {token}"}
    dream_id = '22222222-2222-2222-2222-222222222222'
    
    print("\n🎨 Testing image generation...")
    print("⏳ This will take 15-20 seconds...")
    
    start_time = time.time()
    response = requests.post(
        f"http://localhost:8000/dreams/{dream_id}/generate-image",
        headers=headers
    )
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ SUCCESS! Image generated in {elapsed:.1f} seconds")
        print(f"📸 URL: {data.get('url', '')[:80]}...")
        print(f"💭 Prompt: {data.get('prompt', '')[:100]}...")
        return True
    else:
        print(f"\n❌ Failed: {response.text}")
        return False

# Run the test
print("=" * 60)
print("Final Quick Test - Image Generation")
print("=" * 60)

# Clear existing image
asyncio.run(clear_existing_image())

# Test generation
success = test_image_generation()

if success:
    print("\n✨ Image generation is working perfectly!")
    print("📱 Ready to implement iOS UI (Phase 3)")
else:
    print("\n⚠️  Check server logs for errors")

print("=" * 60)