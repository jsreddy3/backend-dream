#!/usr/bin/env python3
"""Test S3 upload pipeline for dream images"""

import asyncio
import uuid
from new_backend_ruminate.services.image_generation.service import ImageGenerationService

async def test_s3_upload():
    print("Testing S3 upload pipeline...")
    
    service = ImageGenerationService()
    
    # Test with fake user and dream IDs
    test_user_id = uuid.uuid4()
    test_dream_id = uuid.uuid4()
    test_prompt = "A magical dreamscape with floating crystals and aurora lights"
    
    print(f"User ID: {test_user_id}")
    print(f"Dream ID: {test_dream_id}")
    print(f"Prompt: {test_prompt}")
    
    # Generate and store image
    s3_url, used_prompt = await service.generate_and_store_image(
        user_id=test_user_id,
        dream_id=test_dream_id,
        prompt=test_prompt
    )
    
    if s3_url:
        print(f"\n✅ Success!")
        print(f"S3 URL: {s3_url}")
        print(f"Prompt used: {used_prompt}")
        return True
    else:
        print("\n❌ Failed to generate and store image")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_s3_upload())
    exit(0 if success else 1)