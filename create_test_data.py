#!/usr/bin/env python3
"""Create test user and dream with transcript for testing summary generation."""

import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from new_backend_ruminate.domain.user.entities import User
from new_backend_ruminate.domain.dream.entities.dream import Dream
from new_backend_ruminate.domain.dream.entities.segments import Segment  # Import to avoid circular dependency
from new_backend_ruminate.domain.dream.entities.interpretation import InterpretationQuestion, InterpretationChoice, InterpretationAnswer  # Import for relationships
from new_backend_ruminate.config import settings

async def create_test_data():
    # Create engine and session
    engine = create_async_engine(settings().db_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # Create test user
        test_user = User(
            id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
            google_sub='test_google_sub_123',
            email='test@example.com',
            name='Test User',
            created=datetime.utcnow()
        )
        
        # Check if user already exists
        existing = await session.get(User, test_user.id)
        if not existing:
            session.add(test_user)
            await session.commit()
            print(f"Created test user: {test_user.id}")
        else:
            print(f"Test user already exists: {test_user.id}")
        
        # Create test dream with transcript
        test_dream = Dream(
            id=uuid.UUID('22222222-2222-2222-2222-222222222222'),
            user_id=test_user.id,
            title="Test Dream",
            transcript="""I was walking through a dense forest. The trees were incredibly tall, 
            reaching up into a misty canopy. I could hear birds chirping and leaves rustling 
            in the wind. Suddenly, I came across a clearing where there was a small wooden cabin. 
            The cabin had smoke coming from its chimney. I approached the door and knocked, 
            but no one answered. I decided to enter anyway. Inside, I found a table set for two, 
            with fresh bread and soup still steaming. It felt like someone had just left moments ago.""",
            state="completed",
            created=datetime.utcnow()
        )
        
        # Check if dream already exists
        existing_dream = await session.get(Dream, test_dream.id)
        if not existing_dream:
            session.add(test_dream)
            await session.commit()
            print(f"Created test dream: {test_dream.id}")
        else:
            print(f"Test dream already exists: {test_dream.id}")
        
    await engine.dispose()
    
    # Generate JWT token for the test user
    from jose import jwt
    from datetime import timedelta
    
    secret = settings().jwt_secret
    payload = {
        'sub': 'test_google_sub_123',
        'email': 'test@example.com',
        'uid': str(test_user.id),
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    print("\n" + "="*60)
    print("Test data created successfully!")
    print("="*60)
    print(f"\nUser ID: {test_user.id}")
    print(f"Dream ID: {test_dream.id}")
    print(f"\nJWT Token (valid for 7 days):\n{token}")
    print("\n" + "="*60)
    print("\nTo test the summary generation, run:")
    print(f"""
curl -X POST http://localhost:8000/dreams/{test_dream.id}/generate-summary \\
  -H "Authorization: Bearer {token}" | jq
""")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(create_test_data())