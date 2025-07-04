#!/usr/bin/env python3
"""Test script for complete dream recording flow with automatic summary generation."""

import asyncio
import httpx
import uuid
import json
from datetime import datetime

API_BASE = "http://localhost:8000"

# Get the JWT token from create_test_data.py output
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X2dvb2dsZV9zdWJfMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwidWlkIjoiMTExMTExMTEtMTExMS0xMTExLTExMTEtMTExMTExMTExMTExIiwiZXhwIjoxNzUyMjc1NDg4fQ.8_7ewlIvzxctXbHYgcx5pc3TG3Jw1qOZzvmjMPKzwqs"

async def test_dream_flow():
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {JWT_TOKEN}"}
        
        # 1. Create a new dream
        dream_id = str(uuid.uuid4())
        print(f"\n1. Creating dream with ID: {dream_id}")
        
        response = await client.post(
            f"{API_BASE}/dreams/",
            headers=headers,
            json={"id": dream_id, "title": "Test Dream Flow"}
        )
        response.raise_for_status()
        dream = response.json()
        print(f"✓ Dream created: {dream['id']}")
        print(f"  State: {dream['state']}")
        
        # 2. Add a text segment (simulating a dream recording)
        segment_id = str(uuid.uuid4())
        dream_text = """I was flying over a beautiful city at sunset. The buildings were made of glass 
        and reflected orange and pink colors. I felt completely free and peaceful. 
        Suddenly I realized I could control where I was going just by thinking about it."""
        
        print(f"\n2. Adding text segment...")
        response = await client.post(
            f"{API_BASE}/dreams/{dream_id}/segments",
            headers=headers,
            json={
                "segment_id": segment_id,
                "modality": "text",
                "order": 1,
                "text": dream_text
            }
        )
        response.raise_for_status()
        segment = response.json()
        print(f"✓ Segment added: {segment.get('segment_id', segment.get('id'))}")
        print(f"  Modality: {segment['modality']}")
        print(f"  Has transcript: {bool(segment.get('transcript'))}")
        
        # 3. Check dream state before finishing
        print(f"\n3. Checking dream state before finishing...")
        response = await client.get(f"{API_BASE}/dreams/{dream_id}", headers=headers)
        response.raise_for_status()
        dream = response.json()
        print(f"  State: {dream['state']}")
        print(f"  Has transcript: {bool(dream.get('transcript'))}")
        print(f"  Summary status: {dream.get('summary_status')}")
        
        # 4. Finish the dream (should trigger summary generation and wait for completion)
        print(f"\n4. Finishing dream (this will wait for transcription consolidation and summary generation)...")
        response = await client.post(
            f"{API_BASE}/dreams/{dream_id}/finish",
            headers=headers
        )
        response.raise_for_status()
        finished_dream = response.json()
        print(f"✓ Dream finished!")
        print(f"  State: {finished_dream['state']}")
        print(f"  Title: {finished_dream['title']}")
        print(f"  Summary Status: {finished_dream.get('summary_status')}")
        print(f"  Has Summary: {bool(finished_dream.get('summary'))}")
        
        # 5. No need to wait anymore since finish endpoint waits for summary
        print(f"\n5. Summary generation completed during finish endpoint")
        
        # 6. Check final dream state
        print(f"\n6. Checking final dream state...")
        response = await client.get(f"{API_BASE}/dreams/{dream_id}", headers=headers)
        response.raise_for_status()
        dream = response.json()
        
        print(f"\n=== FINAL DREAM STATE ===")
        print(f"ID: {dream['id']}")
        print(f"State: {dream['state']}")
        print(f"Title: {dream['title']}")
        print(f"Summary Status: {dream.get('summary_status')}")
        print(f"\nTranscript: {dream.get('transcript')}")
        print(f"\nGenerated Summary: {dream.get('summary')}")
        
        # 7. If summary is still processing, poll for completion
        max_attempts = 10
        attempt = 0
        while dream.get('summary_status') == 'processing' and attempt < max_attempts:
            print(f"\n  Summary still processing, waiting... (attempt {attempt + 1}/{max_attempts})")
            await asyncio.sleep(2)
            response = await client.get(f"{API_BASE}/dreams/{dream_id}", headers=headers)
            response.raise_for_status()
            dream = response.json()
            attempt += 1
        
        if dream.get('summary_status') == 'completed':
            print(f"\n✓ Summary generation completed!")
            print(f"  Final Title: {dream['title']}")
            print(f"  Summary: {dream['summary']}")
        else:
            print(f"\n✗ Summary generation status: {dream.get('summary_status')}")
            
        return dream

if __name__ == "__main__":
    print("=== TESTING COMPLETE DREAM FLOW ===")
    print("This test will:")
    print("1. Create a new dream")
    print("2. Add a text segment (simulating recording)")
    print("3. Finish the dream (triggering summary generation)")
    print("4. Check that summary was generated automatically")
    
    dream = asyncio.run(test_dream_flow())
    
    print("\n=== TEST COMPLETE ===")
    if dream.get('summary'):
        print("✓ Success: Dream was recorded, transcribed, and summarized automatically!")
    else:
        print("✗ Failed: Summary was not generated")