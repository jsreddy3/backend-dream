#!/usr/bin/env python3
"""Test production API endpoints."""

import requests
import json

# Production API base
BASE_URL = "https://backend-dream.fly.dev"

# Test endpoints without auth first
print("Testing production API endpoints...")
print("-" * 50)

# Test root
try:
    resp = requests.get(BASE_URL, timeout=5)
    print(f"GET /: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  Response: {resp.text[:100]}...")
except Exception as e:
    print(f"GET /: Error - {e}")

# Test docs
try:
    resp = requests.get(f"{BASE_URL}/docs", timeout=5)
    print(f"GET /docs: {resp.status_code}")
except Exception as e:
    print(f"GET /docs: Error - {e}")

# Test if profile routes exist
try:
    resp = requests.get(f"{BASE_URL}/users/me/profile", timeout=5)
    print(f"GET /users/me/profile (no auth): {resp.status_code}")
    if resp.status_code == 401:
        print("  ✓ Endpoint exists, requires authentication")
    elif resp.status_code == 404:
        print("  ✗ Endpoint not found - route might not be deployed")
except Exception as e:
    print(f"GET /users/me/profile: Error - {e}")

print("\nTo test with authentication, you need a valid JWT token from the app.")
print("You can get it from the app's UserDefaults or debug logs.")