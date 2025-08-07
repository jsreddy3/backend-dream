#!/usr/bin/env python3
"""
Test script to validate the dream recovery system locally before deployment.
This will test the various recovery scenarios with mock data.
"""

import asyncio
import sys
import os
from uuid import uuid4
from datetime import datetime

# Add the backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'new_backend_ruminate'))

from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.db.bootstrap import init_engine, session_scope
from new_backend_ruminate.domain.dream.entities.dream import Dream, DreamStatus
from new_backend_ruminate.domain.dream.entities.segments import Segment

async def setup_test_environment():
    """Set up test environment and create test data."""
    print("🔧 Setting up test environment...")
    
    config = settings()
    await init_engine(config)
    
    test_user_id = uuid4()
    print(f"Using test user ID: {test_user_id}")
    
    return test_user_id

async def create_test_dream_with_failed_segments(user_id):
    """Create a test dream with failed segments to test recovery."""
    print("📝 Creating test dream with failed segments...")
    
    dream_id = uuid4()
    dream = Dream(
        id=dream_id,
        user_id=user_id,
        title="Test Failed Dream",
        state=DreamStatus.PENDING.value,
        created_at=datetime.utcnow(),
        transcript=None
    )
    
    # Create test segments with different failure modes
    segments = [
        Segment(
            id=uuid4(),
            user_id=user_id,
            dream_id=dream_id,
            modality='audio',
            filename='test1.m4a',
            duration=30.0,
            order=0,
            s3_key='test/path/test1.m4a',
            transcription_status='failed',
            transcript=None
        ),
        Segment(
            id=uuid4(),
            user_id=user_id,
            dream_id=dream_id,
            modality='audio',
            filename='test2.m4a',
            duration=25.0,
            order=1,
            s3_key='test/path/test2.m4a',
            transcription_status='failed',
            transcript=None
        ),
        Segment(
            id=uuid4(),
            user_id=user_id,
            dream_id=dream_id,
            modality='text',
            filename=None,
            duration=None,
            order=2,
            s3_key=None,
            transcription_status='completed',
            transcript='This is a text segment that worked'
        )
    ]
    
    async with session_scope() as session:
        session.add(dream)
        for seg in segments:
            session.add(seg)
        await session.commit()
        print(f"✅ Created test dream {dream_id} with {len(segments)} segments")
        return dream_id

async def create_test_dream_with_orphaned_user(original_user_id):
    """Create a test dream with user ownership issues."""
    print("👤 Creating test dream with user ownership issues...")
    
    dream_id = uuid4()
    # Create dream with no user_id (orphaned)
    dream = Dream(
        id=dream_id,
        user_id=None,  # Orphaned!
        title="Orphaned Test Dream",
        state=DreamStatus.PENDING.value,
        created_at=datetime.utcnow(),
        transcript=None
    )
    
    segment = Segment(
        id=uuid4(),
        user_id=None,  # Also orphaned
        dream_id=dream_id,
        modality='text',
        filename=None,
        duration=None,
        order=0,
        s3_key=None,
        transcription_status='completed',
        transcript='This dream has user ownership issues'
    )
    
    async with session_scope() as session:
        session.add(dream)
        session.add(segment)
        await session.commit()
        print(f"✅ Created orphaned dream {dream_id}")
        return dream_id

async def test_recovery_system(user_id):
    """Test the recovery system with various scenarios."""
    print("\n🧪 Testing recovery system...")
    
    from new_backend_ruminate.services.dream.service import DreamService
    from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
    from new_backend_ruminate.infrastructure.implementations.object_storage.s3_storage_repository import S3StorageRepository
    from new_backend_ruminate.infrastructure.implementations.user.rds_user_repository import RDSUserRepository
    
    config = settings()
    
    # Create service (without transcription service for testing)
    dream_repo = RDSDreamRepository()
    storage_repo = S3StorageRepository(
        bucket=config.s3_bucket,
        aws_access_key=config.aws_access_key,
        aws_secret_key=config.aws_secret_key,
        region=config.aws_region
    )
    user_repo = RDSUserRepository()
    
    service = DreamService(
        dream_repo=dream_repo,
        storage_repo=storage_repo,
        user_repo=user_repo,
        transcription_svc=None,  # No transcription for testing
        summary_llm=None
    )
    
    # Test 1: Dream with failed segments (partial recovery)
    print("\n📋 Test 1: Dream with failed segments...")
    failed_dream_id = await create_test_dream_with_failed_segments(user_id)
    
    async with session_scope() as session:
        dream = await dream_repo.get_dream(user_id, failed_dream_id, session)
        if dream:
            result = await service._attempt_dream_recovery(user_id, failed_dream_id, dream, session)
            print(f"  Recovery result: {result}")
            
            if result['success']:
                print(f"  ✅ Partial recovery successful via {result.get('method')}")
                # Check if transcript was created
                updated_dream = await dream_repo.get_dream(user_id, failed_dream_id, session)
                if updated_dream and updated_dream.transcript:
                    print(f"  📝 Transcript created: {len(updated_dream.transcript)} chars")
                    print(f"  📄 Preview: {updated_dream.transcript[:100]}...")
            else:
                print(f"  ❌ Recovery failed: {result.get('error')}")
        else:
            print("  ❌ Could not find test dream")
    
    # Test 2: Dream with user ownership issues
    print("\n📋 Test 2: Dream with user ownership issues...")
    orphaned_dream_id = await create_test_dream_with_orphaned_user(user_id)
    
    async with session_scope() as session:
        # First try to access as the user (should fail)
        dream = await dream_repo.get_dream(user_id, orphaned_dream_id, session)
        if not dream:
            print("  ✅ Correctly unable to access orphaned dream initially")
            
            # Now get unscoped and test ownership repair
            unscoped_dream = await dream_repo.get_dream(None, orphaned_dream_id, session)
            if unscoped_dream:
                result = await service._attempt_dream_recovery(user_id, orphaned_dream_id, unscoped_dream, session)
                print(f"  Recovery result: {result}")
                
                if result['success']:
                    print(f"  ✅ User ownership repair successful")
                    # Verify dream is now accessible
                    recovered_dream = await dream_repo.get_dream(user_id, orphaned_dream_id, session)
                    if recovered_dream:
                        print(f"  📝 Dream now accessible by user: {recovered_dream.title}")
                    else:
                        print(f"  ❌ Dream still not accessible after ownership repair")
                else:
                    print(f"  ❌ Ownership repair failed: {result.get('error')}")
            else:
                print("  ❌ Could not find orphaned dream")
        else:
            print("  ⚠️  Dream was already accessible (unexpected)")

async def cleanup_test_data(user_id):
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    async with session_scope() as session:
        from sqlalchemy import text
        
        # Delete test dreams and segments
        await session.execute(text("DELETE FROM segments WHERE user_id = :user_id OR user_id IS NULL"), {"user_id": user_id})
        await session.execute(text("DELETE FROM dreams WHERE user_id = :user_id OR user_id IS NULL"), {"user_id": user_id})
        await session.commit()
        print("✅ Test data cleaned up")

async def main():
    """Main test function."""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Dream Recovery System Test")
        print("Usage:")
        print("  python test_recovery_system.py           - Run recovery tests")
        print("  python test_recovery_system.py --help    - Show this help")
        print("")
        print("This script tests the dream recovery system with mock data")
        return
    
    print("🚀 Dream Recovery System Test Suite")
    print("="*50)
    
    try:
        user_id = await setup_test_environment()
        await test_recovery_system(user_id)
        
        print("\n🎉 All tests completed!")
        print("💡 If tests passed, the recovery system should work on your problematic dreams")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'user_id' in locals():
            await cleanup_test_data(user_id)

if __name__ == "__main__":
    asyncio.run(main())