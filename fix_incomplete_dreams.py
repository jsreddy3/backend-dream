#!/usr/bin/env python3
"""
Script to identify and fix incomplete dreams that have segments but no transcript.
This commonly happens when dreams were recorded offline and synced later.
"""

import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

# Add the backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'new_backend_ruminate'))

from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.db.bootstrap import init_engine, session_scope
from new_backend_ruminate.dependencies import get_dream_service
from new_backend_ruminate.domain.dream.entities.dream import Dream

async def find_incomplete_dreams():
    """Find dreams that have segments but no transcript."""
    config = settings()
    await init_engine(config)
    
    incomplete_dreams = []
    
    async with session_scope() as session:
        # Query for dreams that have segments but no transcript
        from sqlalchemy import text
        result = await session.execute(text("""
            SELECT DISTINCT d.id, d.user_id, d.title, d.created_at, 
                   COUNT(s.id) as segment_count
            FROM dreams d 
            JOIN segments s ON d.id = s.dream_id 
            WHERE d.transcript IS NULL OR d.transcript = ''
            GROUP BY d.id, d.user_id, d.title, d.created_at
            ORDER BY d.created_at DESC
        """))
        
        for row in result:
            incomplete_dreams.append({
                'id': row.id,
                'user_id': row.user_id,
                'title': row.title,
                'created_at': row.created_at,
                'segment_count': row.segment_count
            })
    
    return incomplete_dreams

async def fix_incomplete_dream(dream_id: UUID, user_id: UUID):
    """Attempt to fix a specific incomplete dream."""
    print(f"  Fixing dream {dream_id}...")
    
    try:
        # Get dream service (simplified version)
        from new_backend_ruminate.services.dream.service import DreamService
        from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
        from new_backend_ruminate.infrastructure.implementations.object_storage.s3_storage_repository import S3StorageRepository
        from new_backend_ruminate.infrastructure.implementations.user.rds_user_repository import RDSUserRepository
        from new_backend_ruminate.infrastructure.transcription.deepgram import DeepgramTranscriptionService
        from new_backend_ruminate.infrastructure.llm.openai_llm import OpenAILLM
        
        config = settings()
        
        dream_repo = RDSDreamRepository()
        storage_repo = S3StorageRepository(
            bucket=config.s3_bucket,
            aws_access_key=config.aws_access_key,
            aws_secret_key=config.aws_secret_key,
            region=config.aws_region
        )
        user_repo = RDSUserRepository()
        transcription_svc = DeepgramTranscriptionService(api_key=config.deepgram_api_key)
        summary_llm = OpenAILLM(api_key=config.openai_api_key, model=config.dream_summary_model)
        
        service = DreamService(
            dream_repo=dream_repo,
            storage_repo=storage_repo,
            user_repo=user_repo,
            transcription_svc=transcription_svc,
            summary_llm=summary_llm
        )
        
        # Attempt to finish the dream
        await service.finish_dream(user_id, dream_id)
        print(f"  ✅ Successfully fixed dream {dream_id}")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to fix dream {dream_id}: {str(e)}")
        return False

async def main():
    """Main function to find and fix incomplete dreams."""
    print("🔍 Searching for incomplete dreams...")
    
    incomplete_dreams = await find_incomplete_dreams()
    
    if not incomplete_dreams:
        print("✅ No incomplete dreams found!")
        return
    
    print(f"📋 Found {len(incomplete_dreams)} incomplete dreams:")
    for dream in incomplete_dreams:
        print(f"  - {dream['title']} (ID: {dream['id']}) - {dream['segment_count']} segments - {dream['created_at']}")
    
    # Ask user if they want to fix them
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        print("\n🔧 Attempting to fix incomplete dreams...")
        
        fixed_count = 0
        for dream in incomplete_dreams:
            success = await fix_incomplete_dream(dream['id'], dream['user_id'])
            if success:
                fixed_count += 1
        
        print(f"\n✅ Fixed {fixed_count} out of {len(incomplete_dreams)} dreams")
        
        if fixed_count < len(incomplete_dreams):
            print("💡 Some dreams may need manual investigation. Check the logs for details.")
    
    else:
        print("\n💡 To attempt automatic fixes, run:")
        print("python fix_incomplete_dreams.py --fix")

if __name__ == "__main__":
    asyncio.run(main())