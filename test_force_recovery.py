#!/usr/bin/env python3
"""
Test script to trigger force recovery on the corrupted dream and verify the fix works.
This script tests the complete end-to-end recovery process.
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime

# Configuration
DREAM_ID = "c18af0e9-cd54-4e61-8106-74487472b90e"
API_BASE_URL = "http://localhost:8000"  # Adjust if needed

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print('='*60)

def print_status(status, message):
    """Print a status message with appropriate emoji"""
    emoji = "✅" if status == "success" else "❌" if status == "error" else "📊"
    print(f"{emoji} {message}")

async def test_force_recovery():
    """Test the force recovery process on the corrupted dream"""
    
    print_section("TRANSCRIPTION RECOVERY TEST")
    print(f"Target Dream ID: {DREAM_ID}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Time: {datetime.now().isoformat()}")
    
    # Check if we can reach the API
    print_section("STEP 1: API CONNECTIVITY CHECK")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test basic connectivity (no auth needed for this)
            response = await client.get(f"{API_BASE_URL}/")
            if response.status_code in [200, 404]:  # 404 is fine, means server is running
                print_status("success", f"API server is responding (status: {response.status_code})")
            else:
                print_status("error", f"API server returned unexpected status: {response.status_code}")
                return
        except Exception as e:
            print_status("error", f"Cannot reach API server: {str(e)}")
            print("❗ Make sure the backend server is running on localhost:8000")
            return
        
        # Get JWT token
        print_section("STEP 2: AUTHENTICATION")
        
        jwt_token = None
        
        # Try to get token from environment variable first
        if "JWT_TOKEN" in os.environ:
            jwt_token = os.environ["JWT_TOKEN"]
            print_status("success", "JWT token loaded from JWT_TOKEN environment variable")
        else:
            # Prompt user for token
            print("📝 Please provide a valid JWT token for authentication.")
            print("   You can set the JWT_TOKEN environment variable to avoid this prompt.")
            print("   Or press Enter to try without authentication (may fail).")
            jwt_token = input("JWT Token: ").strip()
        
        headers = {}
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"
            print_status("success", "Authentication headers configured")
        else:
            print_status("error", "No JWT token provided - requests may fail")
            
        # Step 3: Check dream status before recovery
        print_section("STEP 3: PRE-RECOVERY STATUS CHECK")
        
        try:
            response = await client.get(
                f"{API_BASE_URL}/dreams/{DREAM_ID}/segments/status",
                headers=headers
            )
            
            if response.status_code == 200:
                status = response.json()
                total_segments = len(status['segments'])
                failed_segments = [s for s in status['segments'] if s['transcription_status'] == 'failed']
                completed_segments = [s for s in status['segments'] if s['transcription_status'] == 'completed']
                pending_segments = [s for s in status['segments'] if s['transcription_status'] == 'pending']
                
                print_status("success", f"Dream status retrieved successfully")
                print(f"   📊 Total segments: {total_segments}")
                print(f"   ❌ Failed segments: {len(failed_segments)}")
                print(f"   ✅ Completed segments: {len(completed_segments)}")
                print(f"   ⏳ Pending segments: {len(pending_segments)}")
                
                if len(failed_segments) == 0:
                    print_status("success", "No failed segments found - dream may already be recovered!")
                    return
                    
            elif response.status_code == 401:
                print_status("error", "Authentication failed - invalid JWT token")
                return
            elif response.status_code == 404:
                print_status("error", "Dream not found - may have been deleted")
                return
            else:
                print_status("error", f"Failed to get dream status: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print_status("error", f"Error checking dream status: {str(e)}")
            return
            
        # Step 4: Trigger force recovery
        print_section("STEP 4: FORCE RECOVERY EXECUTION")
        
        try:
            print("🚀 Triggering force recovery...")
            
            response = await client.post(
                f"{API_BASE_URL}/dreams/{DREAM_ID}/force-recovery",
                headers=headers,
                timeout=60.0  # Recovery might take a while
            )
            
            if response.status_code == 200:
                result = response.json()
                print_status("success", "Force recovery completed!")
                
                print("\n📋 Recovery Results:")
                print(f"   Success: {result.get('success', 'Unknown')}")
                print(f"   Method: {result.get('method', 'Unknown')}")
                print(f"   Message: {result.get('message', 'No message')}")
                
                if result.get('success'):
                    dream_info = result.get('dream', {})
                    print(f"   📄 Has transcript: {dream_info.get('has_transcript', 'Unknown')}")
                    print(f"   📏 Transcript length: {dream_info.get('transcript_length', 'Unknown')} chars")
                    print(f"   🔄 Dream state: {dream_info.get('state', 'Unknown')}")
                    
                    if dream_info.get('has_transcript'):
                        print_status("success", "🎉 Recovery successful - dream now has transcript!")
                    else:
                        print_status("error", "❌ Recovery reported success but no transcript found")
                else:
                    print_status("error", f"Recovery failed: {result.get('error', 'Unknown error')}")
                    
            elif response.status_code == 401:
                print_status("error", "Authentication failed during recovery")
                return
            elif response.status_code == 404:
                print_status("error", "Dream not found during recovery")
                return
            elif response.status_code == 500:
                print_status("error", f"Server error during recovery: {response.text}")
                return
            else:
                print_status("error", f"Recovery request failed: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return
                
        except asyncio.TimeoutError:
            print_status("error", "Recovery request timed out (>60s)")
            print("   This might indicate the recovery is taking longer than expected")
            print("   Check server logs for progress")
            return
        except Exception as e:
            print_status("error", f"Error during recovery: {str(e)}")
            return
            
        # Step 5: Check dream status after recovery
        print_section("STEP 5: POST-RECOVERY STATUS CHECK")
        
        try:
            await asyncio.sleep(2)  # Give the server a moment to update
            
            response = await client.get(
                f"{API_BASE_URL}/dreams/{DREAM_ID}/segments/status",
                headers=headers
            )
            
            if response.status_code == 200:
                status = response.json()
                total_segments = len(status['segments'])
                failed_segments = [s for s in status['segments'] if s['transcription_status'] == 'failed']
                completed_segments = [s for s in status['segments'] if s['transcription_status'] == 'completed']
                pending_segments = [s for s in status['segments'] if s['transcription_status'] == 'pending']
                
                print_status("success", "Post-recovery status retrieved")
                print(f"   📊 Total segments: {total_segments}")
                print(f"   ❌ Failed segments: {len(failed_segments)}")
                print(f"   ✅ Completed segments: {len(completed_segments)}")
                print(f"   ⏳ Pending segments: {len(pending_segments)}")
                
                # Determine success
                if len(failed_segments) == 0 and len(completed_segments) > 0:
                    print_status("success", "🎉 COMPLETE SUCCESS - All segments recovered!")
                elif len(failed_segments) == 0 and len(pending_segments) > 0:
                    print_status("success", "🔄 PARTIAL SUCCESS - Segments now pending (will be processed)")
                elif len(failed_segments) < total_segments:
                    print_status("success", "📈 PARTIAL SUCCESS - Some segments recovered")
                else:
                    print_status("error", "❌ NO PROGRESS - All segments still failed")
                    
            else:
                print_status("error", f"Failed to get post-recovery status: HTTP {response.status_code}")
                
        except Exception as e:
            print_status("error", f"Error checking post-recovery status: {str(e)}")
    
    print_section("TEST COMPLETE")
    print(f"✅ Test completed at {datetime.now().isoformat()}")
    print("\n📋 Next Steps:")
    print("   1. Check the backend logs for detailed recovery process information")
    print("   2. Try viewing the dream in the app to see if errors are resolved")
    print("   3. Verify that analysis/summary generation now works")

if __name__ == "__main__":
    print("🧪 Transcription Recovery Test Script")
    print("This script will test the force recovery endpoint on the corrupted dream.")
    print("Make sure the backend server is running before proceeding.")
    
    input("\nPress Enter to continue...")
    
    try:
        asyncio.run(test_force_recovery())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)