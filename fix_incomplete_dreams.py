#!/usr/bin/env python3
"""
Comprehensive diagnostic and recovery tool for offline dreams with failed segments.
Addresses the core issues discovered from logs:
- Failed segments (transcription_status = 'failed')
- User ownership problems ('Dream not found for user')
- Missing or corrupted S3 files
"""

import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

# Add the backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'new_backend_ruminate'))

from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.db.bootstrap import init_engine, session_scope
from new_backend_ruminate.domain.dream.entities.dream import Dream
from new_backend_ruminate.domain.dream.entities.segments import Segment

class DreamDiagnostics:
    """Comprehensive diagnostics for problematic offline dreams."""
    
    def __init__(self):
        self.config = settings()
        self.issues = []
        self.stats = {
            'total_dreams': 0,
            'failed_segments': 0,
            'missing_transcripts': 0,
            'user_mismatches': 0,
            'recoverable': 0,
            'unrecoverable': 0
        }
    
    async def run_full_diagnosis(self) -> Dict[str, Any]:
        """Run comprehensive diagnosis of all problematic dreams."""
        print("🔍 Starting comprehensive dream diagnostics...")
        
        await init_engine(self.config)
        
        # Step 1: Find all problematic dreams
        problematic_dreams = await self._find_problematic_dreams()
        self.stats['total_dreams'] = len(problematic_dreams)
        
        if not problematic_dreams:
            print("✅ No problematic dreams found!")
            return self.stats
        
        print(f"📋 Found {len(problematic_dreams)} problematic dreams")
        
        # Step 2: Analyze each dream in detail
        detailed_analysis = []
        for dream_info in problematic_dreams:
            analysis = await self._analyze_dream_detailed(dream_info)
            detailed_analysis.append(analysis)
            self._update_stats(analysis)
        
        # Step 3: Generate report
        await self._generate_report(detailed_analysis)
        
        return {
            'stats': self.stats,
            'dreams': detailed_analysis,
            'issues': self.issues
        }
    
    async def _find_problematic_dreams(self) -> List[Dict[str, Any]]:
        """Find dreams with various issues."""
        async with session_scope() as session:
            # Query for dreams with segments but issues
            from sqlalchemy import text
            result = await session.execute(text("""
                SELECT 
                    d.id, 
                    d.user_id, 
                    d.title, 
                    d.state,
                    d.transcript,
                    d.created_at,
                    COUNT(s.id) as segment_count,
                    COUNT(CASE WHEN s.transcription_status = 'failed' THEN 1 END) as failed_segments,
                    COUNT(CASE WHEN s.transcription_status = 'completed' THEN 1 END) as completed_segments,
                    COUNT(CASE WHEN s.transcription_status = 'pending' THEN 1 END) as pending_segments,
                    STRING_AGG(s.transcription_status, ',') as segment_statuses,
                    STRING_AGG(s.s3_key, ',') as s3_keys
                FROM dreams d 
                LEFT JOIN segments s ON d.id = s.dream_id 
                WHERE (
                    -- Dreams with failed segments
                    s.transcription_status = 'failed' OR
                    -- Dreams with no transcript but have segments
                    (d.transcript IS NULL OR d.transcript = '') AND s.id IS NOT NULL OR
                    -- Dreams with title "Untitled Dream" (likely from offline)
                    d.title = 'Untitled Dream'
                )
                GROUP BY d.id, d.user_id, d.title, d.state, d.transcript, d.created_at
                ORDER BY d.created_at DESC
            """))
            
            dreams = []
            for row in result:
                dreams.append({
                    'id': row.id,
                    'user_id': row.user_id,
                    'title': row.title,
                    'state': row.state,
                    'has_transcript': bool(row.transcript and row.transcript.strip()),
                    'created_at': row.created_at,
                    'segment_count': row.segment_count or 0,
                    'failed_segments': row.failed_segments or 0,
                    'completed_segments': row.completed_segments or 0,
                    'pending_segments': row.pending_segments or 0,
                    'segment_statuses': row.segment_statuses,
                    's3_keys': row.s3_keys
                })
            
            return dreams
    
    async def _analyze_dream_detailed(self, dream_info: Dict[str, Any]) -> Dict[str, Any]:
        """Perform detailed analysis of a specific dream."""
        dream_id = dream_info['id']
        user_id = dream_info['user_id']
        
        analysis = {
            'dream_id': str(dream_id),
            'user_id': str(user_id),
            'title': dream_info['title'],
            'issues': [],
            'recovery_options': [],
            'severity': 'unknown'
        }
        
        # Check user ownership consistency
        user_ownership_ok = await self._check_user_ownership(dream_id, user_id)
        if not user_ownership_ok:
            analysis['issues'].append("User ownership inconsistency - dream not accessible by user")
            analysis['severity'] = 'critical'
        
        # Analyze segments in detail
        segment_analysis = await self._analyze_segments(dream_id, user_id)
        analysis.update(segment_analysis)
        
        # Check S3 file existence
        s3_analysis = await self._check_s3_files(dream_info.get('s3_keys', ''))
        analysis.update(s3_analysis)
        
        # Determine recovery options
        recovery_options = self._determine_recovery_options(analysis)
        analysis['recovery_options'] = recovery_options
        
        # Set severity if not already critical
        if analysis['severity'] == 'unknown':
            if analysis['issues']:
                analysis['severity'] = 'high' if 'failed' in str(analysis['issues']) else 'medium'
            else:
                analysis['severity'] = 'low'
        
        return analysis
    
    async def _check_user_ownership(self, dream_id: UUID, user_id: UUID) -> bool:
        """Check if user can actually access the dream."""
        try:
            from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
            repo = RDSDreamRepository()
            
            async with session_scope() as session:
                dream = await repo.get_dream(user_id, dream_id, session)
                return dream is not None
        except Exception as e:
            self.issues.append(f"Error checking user ownership for {dream_id}: {str(e)}")
            return False
    
    async def _analyze_segments(self, dream_id: UUID, user_id: Optional[UUID]) -> Dict[str, Any]:
        """Analyze segments for a dream."""
        try:
            from new_backend_ruminate.infrastructure.implementations.dream.rds_dream_repository import RDSDreamRepository
            repo = RDSDreamRepository()
            
            async with session_scope() as session:
                # Get dream without user constraint to see all segments
                dream = await repo.get_dream(None, dream_id, session)
                if not dream or not dream.segments:
                    return {
                        'segment_issues': ['No segments found'],
                        'segments_detail': []
                    }
                
                segment_details = []
                issues = []
                
                for i, seg in enumerate(dream.segments):
                    detail = {
                        'order': seg.order,
                        'modality': seg.modality,
                        'status': seg.transcription_status,
                        'has_transcript': bool(seg.transcript and seg.transcript.strip()),
                        'has_filename': bool(seg.filename),
                        's3_key': seg.s3_key,
                        'duration': seg.duration
                    }
                    
                    # Identify specific issues
                    if seg.transcription_status == 'failed':
                        issues.append(f"Segment {i} transcription failed")
                        detail['issue'] = 'transcription_failed'
                    elif seg.modality == 'audio' and not seg.s3_key:
                        issues.append(f"Segment {i} missing S3 key")
                        detail['issue'] = 'missing_s3_key'
                    elif seg.modality == 'audio' and not seg.transcript:
                        issues.append(f"Segment {i} missing transcript")
                        detail['issue'] = 'missing_transcript'
                    
                    segment_details.append(detail)
                
                return {
                    'segment_issues': issues,
                    'segments_detail': segment_details
                }
                
        except Exception as e:
            return {
                'segment_issues': [f"Error analyzing segments: {str(e)}"],
                'segments_detail': []
            }
    
    async def _check_s3_files(self, s3_keys_str: str) -> Dict[str, Any]:
        """Check if S3 files actually exist."""
        if not s3_keys_str:
            return {'s3_issues': ['No S3 keys to check'], 's3_status': {}}
        
        s3_keys = [key.strip() for key in s3_keys_str.split(',') if key.strip()]
        if not s3_keys:
            return {'s3_issues': ['No valid S3 keys'], 's3_status': {}}
        
        try:
            from new_backend_ruminate.infrastructure.implementations.object_storage.s3_storage_repository import S3StorageRepository
            
            storage = S3StorageRepository(
                bucket=self.config.s3_bucket,
                aws_access_key=self.config.aws_access_key,
                aws_secret_key=self.config.aws_secret_key,
                region=self.config.aws_region
            )
            
            s3_status = {}
            issues = []
            
            for s3_key in s3_keys:
                try:
                    # Check if file exists (this is a simplified check)
                    # In a real implementation, you'd use storage.check_file_exists() or similar
                    s3_status[s3_key] = 'unknown'  # We'd need to implement file existence check
                    issues.append(f"S3 file existence check not implemented for {s3_key}")
                except Exception as e:
                    s3_status[s3_key] = 'error'
                    issues.append(f"Error checking S3 key {s3_key}: {str(e)}")
            
            return {
                's3_issues': issues,
                's3_status': s3_status
            }
            
        except Exception as e:
            return {
                's3_issues': [f"Error setting up S3 client: {str(e)}"],
                's3_status': {}
            }
    
    def _determine_recovery_options(self, analysis: Dict[str, Any]) -> List[str]:
        """Determine what recovery options are available."""
        options = []
        
        # If user ownership is broken, need to fix that first
        if any('ownership' in issue for issue in analysis.get('issues', [])):
            options.append('repair_user_ownership')
        
        # If segments failed transcription, can try to retry
        if any('transcription failed' in issue for issue in analysis.get('segment_issues', [])):
            options.append('retry_transcription')
        
        # If segments are missing S3 keys, need manual intervention
        if any('missing S3 key' in issue for issue in analysis.get('segment_issues', [])):
            options.append('manual_segment_recovery')
        
        # If some segments are OK, can try partial recovery
        segments_detail = analysis.get('segments_detail', [])
        if segments_detail and any(s.get('has_transcript') for s in segments_detail):
            options.append('partial_transcript_recovery')
        
        # If no recovery options, mark as unrecoverable
        if not options:
            options.append('unrecoverable')
        
        return options
    
    def _update_stats(self, analysis: Dict[str, Any]):
        """Update overall statistics."""
        if any('failed' in issue for issue in analysis.get('segment_issues', [])):
            self.stats['failed_segments'] += 1
        
        if any('ownership' in issue for issue in analysis.get('issues', [])):
            self.stats['user_mismatches'] += 1
        
        if 'unrecoverable' in analysis.get('recovery_options', []):
            self.stats['unrecoverable'] += 1
        else:
            self.stats['recoverable'] += 1
    
    async def _generate_report(self, detailed_analysis: List[Dict[str, Any]]):
        """Generate comprehensive report."""
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE DREAM DIAGNOSTICS REPORT")
        print("="*80)
        
        print(f"\n📈 STATISTICS:")
        print(f"  Total problematic dreams: {self.stats['total_dreams']}")
        print(f"  Dreams with failed segments: {self.stats['failed_segments']}")
        print(f"  Dreams with user ownership issues: {self.stats['user_mismatches']}")
        print(f"  Potentially recoverable: {self.stats['recoverable']}")
        print(f"  Likely unrecoverable: {self.stats['unrecoverable']}")
        
        print(f"\n🔍 DETAILED ANALYSIS:")
        for i, analysis in enumerate(detailed_analysis, 1):
            print(f"\n  Dream {i}: {analysis['title']} ({analysis['dream_id'][:8]}...)")
            print(f"    Severity: {analysis['severity'].upper()}")
            
            if analysis['issues']:
                print(f"    Issues:")
                for issue in analysis['issues']:
                    print(f"      - {issue}")
            
            if analysis.get('segment_issues'):
                print(f"    Segment Issues:")
                for issue in analysis['segment_issues']:
                    print(f"      - {issue}")
            
            if analysis.get('recovery_options'):
                print(f"    Recovery Options:")
                for option in analysis['recovery_options']:
                    print(f"      - {option}")
        
        if self.issues:
            print(f"\n⚠️  SYSTEM ISSUES ENCOUNTERED:")
            for issue in self.issues:
                print(f"    - {issue}")
        
        # Save detailed report to file
        report_file = f"dream_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'stats': self.stats,
                'dreams': detailed_analysis,
                'issues': self.issues,
                'generated_at': datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\n💾 Detailed report saved to: {report_file}")

async def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Dream Diagnostics Tool")
        print("Usage:")
        print("  python fix_incomplete_dreams.py           - Run diagnostics only")
        print("  python fix_incomplete_dreams.py --help    - Show this help")
        print("")
        print("This tool analyzes dreams with failed segments and user ownership issues")
        print("that commonly occur when dreams are recorded offline and synced later.")
        return
    
    diagnostics = DreamDiagnostics()
    results = await diagnostics.run_full_diagnosis()
    
    print(f"\n✅ Diagnostics complete! Check the generated JSON report for full details.")
    
    if results['stats']['recoverable'] > 0:
        print(f"💡 Next steps: Implement recovery logic for {results['stats']['recoverable']} recoverable dreams")
    
    if results['stats']['unrecoverable'] > 0:
        print(f"⚠️  Warning: {results['stats']['unrecoverable']} dreams may need manual intervention")

if __name__ == "__main__":
    asyncio.run(main())