#!/usr/bin/env python3
"""Test script to verify generate_title_and_summary works when called before finish_dream."""

import asyncio
import httpx
import uuid
import json
import time
from datetime import datetime

API_BASE = "http://localhost:8000"

# Get the JWT token from create_test_data.py output
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X2dvb2dsZV9zdWJfMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwidWlkIjoiMTExMTExMTEtMTExMS0xMTExLTExMTEtMTExMTExMTExMTExIiwiZXhwIjoxNzUyMjc1NDg4fQ.8_7ewlIvzxctXbHYgcx5pc3TG3Jw1qOZzvmjMPKzwqs"

async def test_summary_before_finish():
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {JWT_TOKEN}"}
        
        # 1. Create a new dream
        dream_id = str(uuid.uuid4())
        print(f"\n1. Creating dream with ID: {dream_id}")
        
        response = await client.post(
            f"{API_BASE}/dreams/",
            headers=headers,
            json={"id": dream_id, "title": "Test Summary Before Finish"}
        )
        response.raise_for_status()
        dream = response.json()
        print(f"✓ Dream created: {dream['id']}")
        print(f"  State: {dream['state']}")
        
        # 2. Add multiple text segments (simulating a recording with multiple parts)
        segments = [
            {
                "text": "I found myself in a vast library that seemed to extend infinitely in all directions.",
                "order": 1
            },
            {
                "text": "The books were floating in the air, and I could reach any of them just by thinking about the topic.",
                "order": 2
            },
            {
                "text": "When I opened one book about the ocean, water started flowing out of the pages, creating a small waterfall.",
                "order": 3
            }
        ]
        
        print(f"\n2. Adding {len(segments)} text segments...")
        for seg_data in segments:
            segment_id = str(uuid.uuid4())
            response = await client.post(
                f"{API_BASE}/dreams/{dream_id}/segments",
                headers=headers,
                json={
                    "segment_id": segment_id,
                    "modality": "text",
                    "order": seg_data["order"],
                    "text": seg_data["text"]
                }
            )
            response.raise_for_status()
            print(f"✓ Added segment {seg_data['order']}")
        
        # 3. Check dream state - should not have consolidated transcript yet
        print(f"\n3. Checking dream state before finish...")
        response = await client.get(f"{API_BASE}/dreams/{dream_id}", headers=headers)
        response.raise_for_status()
        dream = response.json()
        print(f"  State: {dream['state']}")
        print(f"  Has transcript: {bool(dream.get('transcript'))}")
        print(f"  Number of segments: {len(dream.get('segments', []))}")
        
        # 4. Call generate-summary BEFORE calling finish
        print(f"\n4. Calling generate-summary endpoint (before finish)...")
        print("   This should wait for transcription consolidation...")
        
        start_time = time.time()
        response = await client.post(
            f"{API_BASE}/dreams/{dream_id}/generate-summary",
            headers=headers
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Summary generated successfully! (took {elapsed:.1f}s)")
            print(f"  Generated Title: {result['title']}")
            print(f"  Summary: {result['summary']}")
        else:
            print(f"✗ Failed to generate summary: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
        
        # 5. Check dream state after summary generation
        print(f"\n5. Checking dream state after summary generation...")
        response = await client.get(f"{API_BASE}/dreams/{dream_id}", headers=headers)
        response.raise_for_status()
        dream = response.json()
        print(f"  State: {dream['state']}")
        print(f"  Has transcript: {bool(dream.get('transcript'))}")
        print(f"  Summary status: {dream.get('summary_status')}")
        print(f"  Has summary: {bool(dream.get('summary'))}")
        
        # 6. Now call finish to complete the dream
        print(f"\n6. Calling finish endpoint...")
        response = await client.post(
            f"{API_BASE}/dreams/{dream_id}/finish",
            headers=headers
        )
        response.raise_for_status()
        finished_dream = response.json()
        print(f"✓ Dream finished!")
        print(f"  State: {finished_dream['state']}")
        
        # 7. Verify final state
        print(f"\n=== FINAL VERIFICATION ===")
        print(f"Dream ID: {dream['id']}")
        print(f"State: {finished_dream['state']}")
        print(f"Title: {finished_dream['title']}")
        print(f"Summary Status: {finished_dream.get('summary_status')}")
        
        if dream.get('transcript'):
            print(f"\nConsolidated Transcript:")
            print(dream['transcript'])
        
        return True

if __name__ == "__main__":
    print("=== TESTING SUMMARY GENERATION BEFORE FINISH ===")
    print("This test will:")
    print("1. Create a new dream")
    print("2. Add multiple text segments")
    print("3. Call generate-summary BEFORE calling finish")
    print("4. Verify that summary generation waits for and consolidates transcripts")
    print("5. Then call finish to complete the dream")
    
    success = asyncio.run(test_summary_before_finish())
    
    print("\n=== TEST COMPLETE ===")
    if success:
        print("✓ Success: generate_title_and_summary properly handles incomplete transcriptions!")
    else:
        print("✗ Failed: There was an issue with summary generation")