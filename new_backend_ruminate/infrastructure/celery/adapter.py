from typing import Dict, List, Any
from uuid import UUID
from celery.result import AsyncResult

from new_backend_ruminate.domain.ports.video_queue import VideoQueuePort


class CeleryVideoQueueAdapter(VideoQueuePort):
    """
    Adapter that implements the VideoQueuePort using Celery as the task queue.
    """
    
    async def enqueue_video_generation(
        self, 
        dream_id: UUID, 
        transcript: str, 
        segments: List[Dict[str, Any]]
    ) -> str:
        """
        Queue a video generation job using Celery.
        
        Returns the Celery task ID which can be used to track the job.
        """
        # Import here to avoid circular imports
        from .tasks import generate_video_task
        
        # Send task to Celery queue
        result = generate_video_task.delay(
            dream_id=str(dream_id),
            transcript=transcript,
            segments=segments
        )
        
        return result.id
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a Celery task.
        
        Returns a dictionary with status information.
        """
        # Import here to avoid circular imports
        from .tasks import generate_video_task
        
        result = AsyncResult(job_id, app=generate_video_task.app)
        
        # Map Celery states to a consistent format
        status_map = {
            'PENDING': 'QUEUED',
            'STARTED': 'PROCESSING',
            'SUCCESS': 'COMPLETED',
            'FAILURE': 'FAILED',
            'RETRY': 'PROCESSING',
            'REVOKED': 'CANCELLED'
        }
        
        status_info = {
            'job_id': job_id,
            'status': status_map.get(result.state, result.state),
            'info': None,
            'result': None
        }
        
        # Add additional info based on state
        if result.state == 'PENDING':
            status_info['info'] = 'Task is waiting in queue'
        elif result.state == 'STARTED':
            status_info['info'] = result.info if result.info else 'Task is being processed'
        elif result.state == 'SUCCESS':
            status_info['result'] = result.result
            status_info['info'] = 'Task completed successfully'
        elif result.state == 'FAILURE':
            status_info['info'] = str(result.info) if result.info else 'Task failed'
        elif result.state == 'RETRY':
            status_info['info'] = f'Task is being retried'
        
        return status_info
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a Celery task if it hasn't started yet.
        
        Returns True if the task was successfully cancelled.
        """
        # Import here to avoid circular imports
        from .tasks import generate_video_task
        
        result = AsyncResult(job_id, app=generate_video_task.app)
        
        # Can only cancel if task hasn't started
        if result.state in ['PENDING', 'RETRY']:
            result.revoke(terminate=False)
            return True
        
        return False