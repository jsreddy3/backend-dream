#!/usr/bin/env python3
"""
Test script to verify the transcription recovery fix works for the corrupted dream.
This script will attempt to recover dream c18af0e9-cd54-4e61-8106-74487472b90e
"""

import asyncio
import httpx
import json
import os
from uuid import UUID

# Configuration
DREAM_ID = "c18af0e9-cd54-4e61-8106-74487472b90e"
API_BASE_URL = "http://localhost:8000"  # Adjust if different

async def test_recovery():
    """Test the recovery fix on the corrupted dream"""
    
    print(f"🔧 Testing recovery fix for dream {DREAM_ID}")
    print("=" * 60)
    
    # You'll need to provide a valid JWT token for authentication
    # This would typically come from your auth flow
    jwt_token = input("Please enter a valid JWT token (or press Enter to skip auth): ").strip()
    
    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Check dream status before recovery
            print("📊 Checking dream status before recovery...")
            response = await client.get(
                f"{API_BASE_URL}/dreams/{DREAM_ID}/segments/status",
                headers=headers
            )
            
            if response.status_code == 200:
                status = response.json()
                print(f"   Failed segments: {len([s for s in status['segments'] if s['transcription_status'] == 'failed'])}")
                print(f"   Total segments: {len(status['segments'])}")
            else:
                print(f"   Could not get status: {response.status_code}")
            
            # Step 2: Attempt force recovery
            print("\n🚀 Attempting force recovery...")
            response = await client.post(
                f"{API_BASE_URL}/dreams/{DREAM_ID}/force-recovery",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Recovery result: {result}")
                
                if result.get('success'):
                    print("🎉 Recovery successful!")
                    print(f"   Method: {result.get('method')}")
                    print(f"   Message: {result.get('message')}")
                    
                    dream_info = result.get('dream', {})
                    print(f"   Has transcript: {dream_info.get('has_transcript')}")
                    print(f"   Transcript length: {dream_info.get('transcript_length')}")
                    print(f"   State: {dream_info.get('state')}")
                else:
                    print("❌ Recovery failed:")
                    print(f"   Error: {result.get('error')}")
                    print(f"   Message: {result.get('message')}")
            else:
                print(f"❌ Recovery request failed: {response.status_code}")
                print(f"   Response: {response.text}")
            
            # Step 3: Check dream status after recovery
            print("\n📊 Checking dream status after recovery...")
            response = await client.get(
                f"{API_BASE_URL}/dreams/{DREAM_ID}/segments/status",
                headers=headers
            )
            
            if response.status_code == 200:
                status = response.json()
                failed_segments = [s for s in status['segments'] if s['transcription_status'] == 'failed']
                completed_segments = [s for s in status['segments'] if s['transcription_status'] == 'completed']
                
                print(f"   Failed segments: {len(failed_segments)}")
                print(f"   Completed segments: {len(completed_segments)}")
                print(f"   Total segments: {len(status['segments'])}")
                
                if len(failed_segments) == 0:
                    print("🎉 All segments are now working!")
                elif len(failed_segments) < len(status['segments']):
                    print("📈 Some progress made!")
                else:
                    print("❌ No progress - may need manual intervention")
            else:
                print(f"   Could not get status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error during recovery test: {str(e)}")
            
    print("\n" + "=" * 60)
    print("Recovery test complete!")

if __name__ == "__main__":
    asyncio.run(test_recovery())