#!/usr/bin/env python3
"""Create test user and dream directly in database"""

import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from new_backend_ruminate.config import settings

async def create_test_data():
    """Create test user and dream using raw SQL"""
    engine = create_async_engine(settings().db_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    test_user_id = uuid.UUID('11111111-1111-1111-1111-111111111111')
    test_dream_id = uuid.UUID('22222222-2222-2222-2222-222222222222')
    
    async with AsyncSessionLocal() as session:
        # Create test user
        try:
            await session.execute(
                text("""
                    INSERT INTO users (id, google_sub, email, name, created)
                    VALUES (:id, :google_sub, :email, :name, :created)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": test_user_id,
                    "google_sub": "test_google_sub_123",
                    "email": f"test_{uuid.uuid4().hex[:8]}@example.com",  # Unique email
                    "name": "Test User",
                    "created": datetime.now(timezone.utc).replace(tzinfo=None)
                }
            )
            await session.commit()
            print(f"✅ Created/ensured test user: {test_user_id}")
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            await session.rollback()
        
        # Create test dream
        try:
            await session.execute(
                text("""
                    INSERT INTO dreams (id, user_id, title, transcript, state, created_at)
                    VALUES (:id, :user_id, :title, :transcript, :state, :created_at)
                    ON CONFLICT (id) DO UPDATE SET transcript = EXCLUDED.transcript
                """),
                {
                    "id": test_dream_id,
                    "user_id": test_user_id,
                    "title": "Test Dream for Image Generation",
                    "transcript": """I found myself in a magical crystal cave filled with glowing gemstones. 
                    The crystals pulsed with ethereal light in shades of blue, purple, and gold. 
                    As I walked deeper, I discovered an underground lake that reflected the crystal light, 
                    creating a kaleidoscope of colors on the water's surface. Floating above the lake 
                    were luminescent butterflies made of pure light.""",
                    "state": "completed",
                    "created_at": datetime.now(timezone.utc).replace(tzinfo=None)
                }
            )
            await session.commit()
            print(f"✅ Created/updated test dream: {test_dream_id}")
        except Exception as e:
            print(f"❌ Error creating dream: {e}")
            await session.rollback()
    
    await engine.dispose()
    
    # Generate JWT token
    from jose import jwt
    from datetime import timedelta
    
    secret = settings().jwt_secret
    payload = {
        'sub': 'test_google_sub_123',
        'email': 'test@example.com',
        'uid': str(test_user_id),
        'exp': datetime.now(timezone.utc) + timedelta(days=1)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    print("\n" + "="*60)
    print("Test data created successfully!")
    print("="*60)
    print(f"\nUser ID: {test_user_id}")
    print(f"Dream ID: {test_dream_id}")
    print(f"\nJWT Token:\n{token}")
    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(create_test_data())