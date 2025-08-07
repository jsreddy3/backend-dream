#!/usr/bin/env python3
"""Test that image fields were added to database"""

import asyncio
from sqlalchemy import text
from new_backend_ruminate.dependencies import get_session
from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.db.bootstrap import init_engine

async def check_schema():
    await init_engine(settings())
    
    async for session in get_session():
        # Check if new columns exist
        result = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'dreams' 
            AND column_name IN ('image_url', 'image_prompt', 'image_generated_at', 'image_status', 'image_metadata')
            ORDER BY column_name;
        """))
        
        columns = result.fetchall()
        
        print("✅ Image columns in dreams table:")
        for col_name, data_type in columns:
            print(f"  - {col_name}: {data_type}")
        
        if len(columns) == 5:
            print("\n✅ All 5 image columns successfully added!")
            return True
        else:
            print(f"\n❌ Expected 5 columns but found {len(columns)}")
            return False

if __name__ == "__main__":
    success = asyncio.run(check_schema())
    exit(0 if success else 1)