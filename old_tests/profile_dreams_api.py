#!/usr/bin/env python3
"""Profile the Dreams API endpoint to identify performance bottlenecks."""

import asyncio
import time
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

async def profile_dreams_query(user_id: str):
    """Profile the database query performance for listing dreams."""
    
    # Create async engine
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/dbname")
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Test 1: Count dreams for user
        start = time.time()
        result = await session.execute(
            text("SELECT COUNT(*) FROM dreams WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        count = result.scalar()
        logger.info(f"Dream count for user: {count} (took {time.time() - start:.3f}s)")
        
        # Test 2: Basic dream query without segments
        start = time.time()
        result = await session.execute(
            text("""
                SELECT id, title, created_at, state, summary, video_url
                FROM dreams 
                WHERE user_id = :user_id 
                ORDER BY created_at DESC
                LIMIT 20
            """),
            {"user_id": user_id}
        )
        dreams = result.fetchall()
        logger.info(f"Basic dreams query returned {len(dreams)} rows (took {time.time() - start:.3f}s)")
        
        # Test 3: Count segments per dream
        if dreams:
            dream_ids = [str(d.id) for d in dreams[:5]]  # Check first 5 dreams
            start = time.time()
            result = await session.execute(
                text("""
                    SELECT dream_id, COUNT(*) as segment_count
                    FROM segments
                    WHERE dream_id = ANY(:dream_ids)
                    GROUP BY dream_id
                """),
                {"dream_ids": dream_ids}
            )
            segment_counts = result.fetchall()
            logger.info(f"Segment counts: {dict(segment_counts)} (took {time.time() - start:.3f}s)")
        
        # Test 4: Full query with JOIN (similar to what SQLAlchemy generates)
        start = time.time()
        result = await session.execute(
            text("""
                SELECT 
                    d.id, d.title, d.created_at, d.state, d.summary, d.video_url,
                    s.id as segment_id, s.order, s.modality, s.filename, s.duration, s.transcript
                FROM dreams d
                LEFT JOIN segments s ON d.id = s.dream_id
                WHERE d.user_id = :user_id
                ORDER BY d.created_at DESC, s.order
            """),
            {"user_id": user_id}
        )
        full_results = result.fetchall()
        logger.info(f"Full query with segments returned {len(full_results)} rows (took {time.time() - start:.3f}s)")
        
        # Test 5: Check for missing indexes
        start = time.time()
        result = await session.execute(
            text("""
                SELECT 
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename IN ('dreams', 'segments')
                ORDER BY tablename, indexname
            """)
        )
        indexes = result.fetchall()
        logger.info("\nExisting indexes:")
        for idx in indexes:
            logger.info(f"  {idx.tablename}.{idx.indexname}: {idx.indexdef}")
            
        # Test 6: Analyze query plan
        logger.info("\nQuery execution plan for dreams listing:")
        result = await session.execute(
            text("""
                EXPLAIN ANALYZE
                SELECT 
                    d.id, d.title, d.created_at, d.state,
                    s.id as segment_id
                FROM dreams d
                LEFT JOIN segments s ON d.id = s.dream_id
                WHERE d.user_id = :user_id
                ORDER BY d.created_at DESC
            """),
            {"user_id": user_id}
        )
        for row in result:
            logger.info(f"  {row[0]}")
    
    await engine.dispose()

async def main():
    # You'll need to provide a valid user_id from your database
    user_id = input("Enter a user_id to profile (UUID): ").strip()
    if not user_id:
        logger.error("No user_id provided")
        return
        
    await profile_dreams_query(user_id)

if __name__ == "__main__":
    asyncio.run(main())