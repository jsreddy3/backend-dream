#!/usr/bin/env python3
"""
Minimal test script for video generation workflow.

This script:
1. Creates a dream
2. Adds some segments
3. Triggers video generation
4. Checks the status
"""

import asyncio
import httpx
import uuid
import time

API_BASE = "http://localhost:8000"

async def test_video_generation():
    async with httpx.AsyncClient() as client:
        # 1. Create a dream
        dream_id = str(uuid.uuid4())
        print(f"Creating dream with ID: {dream_id}")
        
        response = await client.post(
            f"{API_BASE}/dreams/",
            json={"id": dream_id, "title": "Test Dream for Video"}
        )
        response.raise_for_status()
        dream = response.json()
        print(f"✓ Dream created: {dream['id']}")
        
        # 2. Add a couple of segments (simulate audio uploads)
        segments = [
            {
                "segment_id": str(uuid.uuid4()),
                "filename": "segment1.mp3",
                "duration": 5.0,
                "order": 1,
                "s3_key": f"dreams/{dream_id}/segments/segment1.mp3"
            },
            {
                "segment_id": str(uuid.uuid4()),
                "filename": "segment2.mp3", 
                "duration": 5.0,
                "order": 2,
                "s3_key": f"dreams/{dream_id}/segments/segment2.mp3"
            }
        ]
        
        for segment in segments:
            response = await client.post(
                f"{API_BASE}/dreams/{dream_id}/segments",
                json=segment
            )
            response.raise_for_status()
            print(f"✓ Added segment: {segment['filename']}")
        
        # 3. Wait a moment and check if we need to mock transcripts
        # In production, Deepgram would transcribe automatically
        await asyncio.sleep(2)
        
        # Get the dream to check current state
        response = await client.get(f"{API_BASE}/dreams/{dream_id}")
        dream_data = response.json()
        
        # If no transcript exists, we'll need to update the database directly
        # or ensure the segments have transcripts for video generation
        if not dream_data.get('transcript'):
            print("Note: No transcript found. Video generation might create a placeholder video.")
            print("In production, Deepgram would provide real transcripts.")
        
        # 4. Finish the dream (triggers video generation)
        print("\nFinishing dream (this triggers video generation)...")
        response = await client.post(f"{API_BASE}/dreams/{dream_id}/finish")
        response.raise_for_status()
        print("✓ Video generation queued")
        
        # 5. Check video status
        print("\nChecking video status...")
        for i in range(10):  # Check for up to 50 seconds
            response = await client.get(f"{API_BASE}/dreams/{dream_id}/video-status")
            status_data = response.json()
            
            print(f"  Status: {status_data.get('status', 'Unknown')}")
            
            if status_data.get('status') == 'COMPLETED':
                print(f"✓ Video completed! URL: {status_data.get('video_url')}")
                break
            elif status_data.get('status') == 'FAILED':
                print(f"✗ Video generation failed")
                break
                
            await asyncio.sleep(5)
        
        # 6. Get final dream details
        response = await client.get(f"{API_BASE}/dreams/{dream_id}")
        final_dream = response.json()
        print(f"\nFinal dream state: {final_dream['state']}")

if __name__ == "__main__":
    print("Video Generation Test")
    print("=" * 50)
    print("Make sure:")
    print("1. The API is running (uvicorn)")
    print("2. Redis is running")
    print("3. The Celery worker is running")
    print("4. You have valid API keys in .env")
    print("=" * 50)
    print()
    
    asyncio.run(test_video_generation())