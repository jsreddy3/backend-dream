#!/usr/bin/env python3
"""Generate JWT token for testing"""

from jose import jwt
from datetime import datetime, timedelta, timezone
from new_backend_ruminate.config import settings
import sys

def generate_token():
    """Generate a JWT token for the test user"""
    test_user_id = '11111111-1111-1111-1111-111111111111'
    
    secret = settings().jwt_secret
    payload = {
        'sub': 'test_google_sub_123',
        'email': 'test@example.com',
        'uid': test_user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=1)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    if len(sys.argv) > 1 and sys.argv[1] == '--token-only':
        print(token)
    else:
        print(f"JWT Token for test user {test_user_id}:")
        print(token)
        print(f"\nTo test image generation:")
        print(f'curl -X POST http://localhost:8000/dreams/22222222-2222-2222-2222-222222222222/generate-image \\')
        print(f'  -H "Authorization: Bearer {token}"')
    
    return token

if __name__ == "__main__":
    generate_token()