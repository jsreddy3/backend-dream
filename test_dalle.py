#!/usr/bin/env python3
"""Test DALL-E 3 integration directly"""

import asyncio
import os
from new_backend_ruminate.services.image_generation.service import ImageGenerationService

async def test_dalle():
    print("Testing DALL-E 3 integration...")
    
    service = ImageGenerationService()
    
    # Test with hardcoded prompt
    image_url = await service.test_generation()
    
    if image_url:
        print(f"✅ Success! Image URL: {image_url}")
        return True
    else:
        print("❌ Failed to generate image")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_dalle())
    exit(0 if success else 1)