from abc import abstractmethod
from typing import Protocol, Dict, List, Any
from uuid import UUID


class VideoQueuePort(Protocol):
    @abstractmethod
    async def enqueue_video_generation(
        self, 
        dream_id: UUID, 
        transcript: str, 
        segments: List[Dict[str, Any]]
    ) -> str:
        """
        Queue a video generation job.
        
        Args:
            dream_id: UUID of the dream
            transcript: Full transcript text
            segments: List of segment data with order, transcript, and audio_url
            
        Returns:
            job_id: Unique identifier for the queued job
        """
        ...
        
    @abstractmethod
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a video generation job.
        
        Args:
            job_id: The job identifier returned by enqueue_video_generation
            
        Returns:
            Dictionary containing:
                - job_id: The job identifier
                - status: Current status (PENDING, STARTED, SUCCESS, FAILURE, RETRY)
                - info: Additional information about the job
                - result: Job result if completed
        """
        ...
        
    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a video generation job if possible.
        
        Args:
            job_id: The job identifier to cancel
            
        Returns:
            True if cancelled, False if job cannot be cancelled
        """
        ...