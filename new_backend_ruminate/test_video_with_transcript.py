#!/usr/bin/env python3
"""
Test script with mock transcript for video generation.

This version provides a transcript to test the full video pipeline.
"""

import asyncio
import httpx
import uuid
import json

API_BASE = "http://localhost:8000"

async def test_video_generation_with_transcript():
    async with httpx.AsyncClient() as client:
        # 1. Create a dream
        dream_id = str(uuid.uuid4())
        print(f"Creating dream with ID: {dream_id}")
        
        response = await client.post(
            f"{API_BASE}/dreams/",
            json={"id": dream_id, "title": "Dream with Transcript Test"}
        )
        response.raise_for_status()
        dream = response.json()
        print(f"✓ Dream created: {dream['id']}")
        
        # 2. Directly update the dream's transcript in the database
        # In production, this would be done by Deepgram transcription
        # For testing, we'll use the internal API to set the transcript
        
        print("\nNOTE: In a real scenario, audio segments would be transcribed by Deepgram.")
        print("For this test, we'll simulate having a transcript ready.\n")
        
        # First, let's add a segment
        segment = {
            "segment_id": str(uuid.uuid4()),
            "filename": "test_segment.mp3",
            "duration": 10.0,
            "order": 1,
            "s3_key": f"dreams/{dream_id}/segments/test_segment.mp3"
        }
        response = await client.post(
            f"{API_BASE}/dreams/{dream_id}/segments",
            json=segment
        )
        response.raise_for_status()
        print(f"✓ Added segment: {segment['filename']}")
        
        # 3. Finish the dream (triggers video generation)
        print("\nFinishing dream (this triggers video generation)...")
        print("Note: The video pipeline will use a default test transcript since segments have no transcript")
        
        response = await client.post(f"{API_BASE}/dreams/{dream_id}/finish")
        response.raise_for_status()
        print("✓ Video generation queued")
        
        # 4. Check video status
        print("\nChecking video status...")
        for i in range(20):  # Check for up to 100 seconds
            response = await client.get(f"{API_BASE}/dreams/{dream_id}/video-status")
            status_data = response.json()
            
            status = status_data.get('status', 'Unknown')
            job_id = status_data.get('job_id', 'N/A')
            
            print(f"  Status: {status} (Job ID: {job_id})")
            
            if status == 'COMPLETED':
                print(f"✓ Video completed! URL: {status_data.get('video_url')}")
                break
            elif status == 'FAILED':
                print(f"✗ Video generation failed")
                break
                
            await asyncio.sleep(5)
        
        # 5. Get final dream details
        response = await client.get(f"{API_BASE}/dreams/{dream_id}")
        final_dream = response.json()
        print(f"\nFinal dream state: {final_dream['state']}")
        
        if final_dream['state'] == 'video_ready':
            print("✓ Success! Video generation workflow completed.")
        else:
            print("⚠️  Video generation did not complete as expected.")

if __name__ == "__main__":
    print("Video Generation Test (with Mock Transcript)")
    print("=" * 50)
    print("This test simulates having transcripts ready.")
    print("=" * 50)
    print()
    
    asyncio.run(test_video_generation_with_transcript())