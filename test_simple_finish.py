#!/usr/bin/env python3
"""Simple test to check finish endpoint"""

import httpx

API_BASE = "http://localhost:8000"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X2dvb2dsZV9zdWJfMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwidWlkIjoiMTExMTExMTEtMTExMS0xMTExLTExMTEtMTExMTExMTExMTExIiwiZXhwIjoxNzUyMjc1NDg4fQ.8_7ewlIvzxctXbHYgcx5pc3TG3Jw1qOZzvmjMPKzwqs"

# Use the existing test dream
dream_id = "22222222-2222-2222-2222-222222222222"

headers = {"Authorization": f"Bearer {JWT_TOKEN}"}

print(f"Calling finish endpoint for dream {dream_id}...")
response = httpx.post(
    f"{API_BASE}/dreams/{dream_id}/finish",
    headers=headers,
    timeout=30.0
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")