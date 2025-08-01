#!/usr/bin/env python3
"""Check if test user exists in database"""

import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from new_backend_ruminate.config import settings

async def check_user():
    """Check if test user exists"""
    engine = create_async_engine(settings().db_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    test_user_id = uuid.UUID('11111111-1111-1111-1111-111111111111')
    
    async with AsyncSessionLocal() as session:
        # Check users table
        result = await session.execute(
            text("SELECT id, email, google_sub FROM users WHERE id = :user_id"),
            {"user_id": test_user_id}
        )
        user = result.fetchone()
        
        if user:
            print(f"✅ User found in database:")
            print(f"   ID: {user.id}")
            print(f"   Email: {user.email}")
            print(f"   Google Sub: {user.google_sub}")
        else:
            print("❌ User not found in database")
            
        # Check dreams table
        result = await session.execute(
            text("SELECT id, title, transcript IS NOT NULL as has_transcript FROM dreams WHERE id = :dream_id"),
            {"dream_id": uuid.UUID('22222222-2222-2222-2222-222222222222')}
        )
        dream = result.fetchone()
        
        if dream:
            print(f"\n✅ Dream found in database:")
            print(f"   ID: {dream.id}")
            print(f"   Title: {dream.title}")
            print(f"   Has transcript: {dream.has_transcript}")
        else:
            print("\n❌ Dream not found in database")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_user())