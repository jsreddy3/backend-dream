#!/usr/bin/env python3
import asyncio
import httpx
import json

async def get_test_token():
    """Get a test JWT token by creating/logging in a test user."""
    
    # First, try to login with Google OAuth mock
    async with httpx.AsyncClient() as client:
        # Create a mock Google OAuth token exchange
        auth_data = {
            "id_token": "mock_google_id_token",
            "user": {
                "sub": "test_user_12345",
                "email": "test@example.com",
                "name": "Test User",
                "picture": "https://example.com/picture.jpg"
            }
        }
        
        try:
            # Try the auth endpoint
            response = await client.post(
                "http://localhost:8000/auth/google/callback",
                json=auth_data
            )
            if response.status_code == 200:
                result = response.json()
                print(f"JWT Token: {result['access_token']}")
                print(f"User ID: {result['user']['id']}")
                return result
        except:
            pass
    
    # If that doesn't work, let's create a direct database entry
    print("Note: You may need to manually create a test user in the database")
    print("Here's a sample JWT token format (you'll need to generate with correct secret):")
    
    # Sample payload
    import time
    payload = {
        "sub": "test_google_sub_123",
        "email": "test@example.com",
        "uid": "YOUR_USER_UUID_HERE",
        "exp": int(time.time()) + 86400  # 24 hours from now
    }
    print(f"\nJWT Payload: {json.dumps(payload, indent=2)}")
    print("\nUse this with your JWT_SECRET to create a token")

if __name__ == "__main__":
    asyncio.run(get_test_token())