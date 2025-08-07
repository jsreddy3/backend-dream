#!/usr/bin/env python3
"""Quick test of image generation - creates new dream and generates image"""

import requests
import json
import time
import uuid
from datetime import datetime, timezone
from generate_test_token import generate_token

# Get auth token
token = generate_token()
headers = {"Authorization": f"Bearer {token}"}

# Create a new dream
print("1️⃣ Creating new dream...")
dream_id = str(uuid.uuid4())
dream_data = {
    "id": dream_id,
    "title": f"Test Dream {datetime.now().strftime('%H:%M:%S')}",
    "created_at": datetime.now(timezone.utc).isoformat()
}

response = requests.post("http://localhost:8000/dreams", json=dream_data, headers=headers)
if response.status_code != 201:
    print(f"❌ Failed to create dream: {response.text}")
    exit(1)

print(f"✅ Created dream: {dream_id}")

# Add transcript
print("\n2️⃣ Adding transcript...")
transcript = """I was floating through a nebula of colors, each star pulsing with musical notes. 
As I reached out to touch them, they transformed into butterflies made of light, 
dancing in patterns that spelled out forgotten memories."""

update_data = {"transcript": transcript}
response = requests.patch(f"http://localhost:8000/dreams/{dream_id}", json=update_data, headers=headers)
if response.status_code == 200:
    print(f"✅ Added transcript")
else:
    print(f"❌ Failed to add transcript: {response.text}")
    exit(1)

# Small delay to ensure DB is updated
time.sleep(0.5)

# Generate image
print("\n3️⃣ Generating image...")
print("⏳ This will take 15-20 seconds...")
start_time = time.time()

response = requests.post(f"http://localhost:8000/dreams/{dream_id}/generate-image", headers=headers)
elapsed = time.time() - start_time

if response.status_code == 200:
    data = response.json()
    print(f"\n✅ Image generated in {elapsed:.1f} seconds!")
    print(f"📸 Image URL: {data.get('url', 'N/A')[:80]}...")
    print(f"💭 Prompt used: {data.get('prompt', 'N/A')[:100]}...")
    
    # Verify in database
    print("\n4️⃣ Verifying in database...")
    response = requests.get(f"http://localhost:8000/dreams/{dream_id}", headers=headers)
    dream = response.json()
    print(f"✅ Image status: {dream.get('image_status')}")
    print(f"✅ Image saved at: {dream.get('image_generated_at')}")
else:
    print(f"❌ Failed: {response.text}")

print("\n✨ Test complete!")