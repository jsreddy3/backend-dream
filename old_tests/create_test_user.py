#!/usr/bin/env python3
"""Create a test user in the database."""

import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from new_backend_ruminate.config import settings
from new_backend_ruminate.domain.user.entities import User

SETTINGS = settings()

async def create_test_user():
    """Create a test user in the database."""
    # Use the test user ID from the JWT token
    user_id = uuid.UUID("f1dcb20e-03ba-4e7b-9d8f-3cda96194593")
    
    # Use the db_url from settings which already has the correct format
    database_url = SETTINGS.db_url
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(
            text("SELECT id FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        existing = result.first()
        
        if existing:
            print(f"✅ User already exists with ID: {user_id}")
        else:
            # Create new user
            await session.execute(
                text("""
                    INSERT INTO users (id, google_sub, email, name, created)
                    VALUES (:id, :google_sub, :email, :name, CURRENT_TIMESTAMP)
                """),
                {
                    "id": user_id,
                    "google_sub": f"test_google_sub_{user_id}",
                    "email": "test@example.com",
                    "name": "Test User"
                }
            )
            await session.commit()
            print(f"✅ Test user created with ID: {user_id}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_test_user())