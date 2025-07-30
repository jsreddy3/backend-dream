#!/usr/bin/env python3
"""Create a test JWT token for API testing."""

import os
from datetime import datetime, timedelta
from jose import jwt
import uuid

# Load settings
from new_backend_ruminate.config import settings

SETTINGS = settings()
JWT_ALG = "HS256"
JWT_EXPIRES = timedelta(hours=24)

def create_test_token():
    """Create a test JWT token."""
    # Generate a test user ID
    test_user_id = str(uuid.uuid4())
    
    # Create token payload
    now = datetime.utcnow()
    payload = {
        "uid": test_user_id,
        "email": "test@example.com",
        "iat": now,
        "exp": now + JWT_EXPIRES,
    }
    
    # Create token
    token = jwt.encode(payload, SETTINGS.jwt_secret, algorithm=JWT_ALG)
    
    # Save to file
    with open('test_token.txt', 'w') as f:
        f.write(token)
    
    print(f"✅ Test token created!")
    print(f"User ID: {test_user_id}")
    print(f"Email: test@example.com")
    print(f"Token saved to: test_token.txt")
    print(f"\nToken: {token}")
    
    return token, test_user_id

if __name__ == "__main__":
    token, user_id = create_test_token()