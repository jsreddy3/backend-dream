#!/usr/bin/env python3
"""
Script to create/calculate user profile for testing.
This will ensure the profile exists and includes the user's name.
"""

import asyncio
import os
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DB_URL", "postgresql+asyncpg://jsvai:childfrodo10wldd@dreams.cluster-crsosmiwisdr.us-west-1.rds.amazonaws.com:5432/campfire")

async def create_profiles():
    """Create profiles for all users who don't have one."""
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # First, get all users
            result = await session.execute(text("""
                SELECT id, email, name 
                FROM users
                ORDER BY created DESC
            """))
            users = result.fetchall()
            
            print(f"Found {len(users)} users")
            
            for user_id, email, name in users:
                print(f"\nProcessing user: {email} (name: {name})")
                
                # Check if profile exists
                profile_result = await session.execute(text("""
                    SELECT id FROM user_profiles
                    WHERE user_id = :user_id
                """), {"user_id": user_id})
                
                existing_profile = profile_result.fetchone()
                
                if existing_profile:
                    print(f"  ✓ Profile already exists")
                else:
                    print(f"  → Creating profile...")
                    
                    # Create a basic profile
                    await session.execute(text("""
                        INSERT INTO user_profiles (
                            user_id,
                            archetype,
                            archetype_confidence,
                            emotional_landscape,
                            top_themes,
                            recent_symbols,
                            last_calculated_at,
                            calculation_version
                        ) VALUES (
                            :user_id,
                            'analytical',
                            0.75,
                            '[{"name": "Curiosity", "intensity": 0.8, "color": "#FF9100"}]'::jsonb,
                            '[{"name": "Discovery", "percentage": 40}]'::jsonb,
                            '["🌟", "🌊", "🦋"]'::jsonb,
                            :now,
                            1
                        )
                    """), {
                        "user_id": user_id,
                        "now": datetime.utcnow()
                    })
                    
                    await session.commit()
                    print(f"  ✓ Profile created successfully")
                
                # Also ensure dream_summaries exists
                summary_result = await session.execute(text("""
                    SELECT user_id FROM dream_summaries
                    WHERE user_id = :user_id
                """), {"user_id": user_id})
                
                existing_summary = summary_result.fetchone()
                
                if not existing_summary:
                    print(f"  → Creating dream summary...")
                    
                    # Count dreams for this user
                    dream_count_result = await session.execute(text("""
                        SELECT COUNT(*) FROM dreams
                        WHERE user_id = :user_id
                    """), {"user_id": user_id})
                    dream_count = dream_count_result.scalar()
                    
                    await session.execute(text("""
                        INSERT INTO dream_summaries (
                            user_id,
                            dream_count,
                            total_duration_seconds,
                            dream_streak_days,
                            last_dream_date
                        ) VALUES (
                            :user_id,
                            :dream_count,
                            0,
                            0,
                            :now
                        )
                    """), {
                        "user_id": user_id,
                        "dream_count": dream_count,
                        "now": datetime.utcnow()
                    })
                    
                    await session.commit()
                    print(f"  ✓ Dream summary created (dream count: {dream_count})")
                
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()
    
    await engine.dispose()
    print("\n✅ Profile creation complete!")

if __name__ == "__main__":
    asyncio.run(create_profiles())