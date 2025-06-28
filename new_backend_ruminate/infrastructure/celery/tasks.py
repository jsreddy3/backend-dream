import logging
from typing import Dict, List, Any
from celery import Task
import httpx
import asyncio
import boto3
from botocore.config import Config
from pathlib import Path
import shutil

from new_backend_ruminate.config import settings
from . import celery_app
from .video_pipeline.orchestrator import VideoPipeline

logger = logging.getLogger(__name__)


class VideoGenerationTask(Task):
    """
    Custom task class for video generation that manages the video pipeline instance.
    """
    def __init__(self):
        self.pipeline = None
    
    def __call__(self, *args, **kwargs):
        """Initialize pipeline on first call (lazy loading)."""
        if self.pipeline is None:
            logger.info("Initializing video pipeline...")
            self.pipeline = VideoPipeline()
        return self.run(*args, **kwargs)


@celery_app.task(
    bind=True,
    base=VideoGenerationTask,
    name='generate_video',
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    retry_backoff=True,
    retry_jitter=True
)
def generate_video_task(
    self, 
    dream_id: str, 
    transcript: str, 
    segments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Celery task that generates a video for a dream.
    
    Args:
        dream_id: UUID of the dream (as string)
        transcript: Full transcript text
        segments: List of segment data
        
    Returns:
        Dictionary with status and video_url
    """
    try:
        logger.info(f"Starting video generation for dream {dream_id}")
        
        # Update task state to show progress
        self.update_state(
            state='STARTED',
            meta={'current': 'Initializing video generation', 'total': 100}
        )
        
        # Generate video using the pipeline
        # The pipeline returns: (video_path, cost, metadata)
        video_path, cost, pipeline_metadata = asyncio.run(
            self.pipeline.generate_video(transcript, dream_id)
        )
        
        # Ensure video_path is a Path object
        if not isinstance(video_path, Path):
            video_path = Path(video_path)
        
        # Upload to S3 and get URL
        video_url = _upload_video_to_s3(video_path, dream_id)
        
        # Combine metadata
        metadata = {
            **pipeline_metadata,
            "cost": cost,
            "local_path": str(video_path)
        }
        
        logger.info(f"Video generation completed for dream {dream_id}")
        
        # Send callback to API
        asyncio.run(_send_completion_callback(dream_id, video_url, metadata))
        
        return {
            "status": "completed",
            "video_url": video_url,
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Video generation failed for dream {dream_id}: {str(e)}")
        
        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying video generation for dream {dream_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)
        
        # If all retries exhausted, send failure callback
        asyncio.run(_send_failure_callback(dream_id, str(e)))
        
        raise


def _upload_video_to_s3(video_path: Path, dream_id: str) -> str:
    """
    Upload video to S3 and return the URL.
    
    Args:
        video_path: Path to the local video file
        dream_id: UUID of the dream
        
    Returns:
        S3 URL of the uploaded video
    """
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings().aws_access_key,
            aws_secret_access_key=settings().aws_secret_key,
            region_name=settings().aws_region,
            config=Config(signature_version='s3v4')
        )
        
        # Define S3 key
        s3_key = f"dreams/{dream_id}/video.mp4"
        bucket_name = settings().s3_bucket
        
        logger.info(f"Uploading video to S3: s3://{bucket_name}/{s3_key}")
        
        # Upload file to S3
        with open(video_path, 'rb') as f:
            s3_client.upload_file(
                str(video_path),
                bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'video/mp4'}
            )
        
        # Construct S3 URL
        s3_url = f"https://{bucket_name}.s3.{settings().aws_region}.amazonaws.com/{s3_key}"
        
        logger.info(f"Successfully uploaded video to S3: {s3_url}")
        
        # Clean up local files
        output_dir = video_path.parent
        if output_dir.exists() and output_dir.name == dream_id:
            logger.info(f"Cleaning up local files in {output_dir}")
            shutil.rmtree(output_dir)
        
        return s3_url
        
    except Exception as e:
        logger.error(f"Failed to upload video to S3 for dream {dream_id}: {str(e)}")
        raise


async def _send_completion_callback(dream_id: str, video_url: str, metadata: Dict[str, Any]):
    """Send completion callback to the API."""
    callback_url = f"{settings().api_base_url}/dreams/{dream_id}/video-complete"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                callback_url,
                json={
                    "video_url": video_url,
                    "metadata": metadata,
                    "status": "completed"
                },
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"Successfully sent completion callback for dream {dream_id}")
    except Exception as e:
        logger.error(f"Failed to send completion callback for dream {dream_id}: {str(e)}")


async def _send_failure_callback(dream_id: str, error: str):
    """Send failure callback to the API."""
    callback_url = f"{settings().api_base_url}/dreams/{dream_id}/video-complete"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                callback_url,
                json={
                    "status": "failed",
                    "error": error
                },
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"Successfully sent failure callback for dream {dream_id}")
    except Exception as e:
        logger.error(f"Failed to send failure callback for dream {dream_id}: {str(e)}")