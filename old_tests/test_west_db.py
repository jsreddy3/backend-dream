#!/usr/bin/env python3
"""Test the new us-west-1 database connection and performance."""

import asyncio
import time
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_west_db():
    # Your new us-west-1 database
    DATABASE_URL = "postgresql+asyncpg://jsvai:childfrodo10wldd@dreams.cluster-crsosmiwisdr.us-west-1.rds.amazonaws.com:5432/campfire"
    
    print("Testing connection to us-west-1 RDS...")
    print(f"Endpoint: dreams.cluster-crsosmiwisdr.us-west-1.rds.amazonaws.com")
    
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        async with engine.begin() as conn:
            # Test 1: Basic connectivity
            start = time.time()
            await conn.execute(text("SELECT 1"))
            ping_time = (time.time() - start) * 1000
            print(f"\n✓ Connection successful!")
            print(f"  Ping time: {ping_time:.2f}ms")
            
            # Test 2: Check tables exist
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            print(f"\n✓ Found {len(tables)} tables:")
            for table in tables[:5]:  # Show first 5
                print(f"  - {table}")
            if len(tables) > 5:
                print(f"  ... and {len(tables) - 5} more")
            
            # Test 3: Check data
            result = await conn.execute(text("SELECT COUNT(*) FROM dreams"))
            dream_count = result.scalar()
            print(f"\n✓ Dreams table has {dream_count} records")
            
            # Test 4: Performance test
            print("\n📊 Performance comparison:")
            print("  Running 5 test queries...")
            
            times = []
            for i in range(5):
                start = time.time()
                await conn.execute(text("SELECT COUNT(*) FROM dreams"))
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
                print(f"  Query {i+1}: {elapsed:.2f}ms")
            
            avg_time = sum(times) / len(times)
            print(f"\n  Average query time: {avg_time:.2f}ms")
            print(f"  Min: {min(times):.2f}ms, Max: {max(times):.2f}ms")
            
            # Compare to your old latency
            print(f"\n🎉 Improvement: ~{1300/avg_time:.0f}x faster than us-east-1!")
            
        await engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nPossible issues:")
        print("- Check password is correct")
        print("- Ensure security group allows connections from your IP")
        print("- Verify the database was properly restored")

if __name__ == "__main__":
    asyncio.run(test_west_db())