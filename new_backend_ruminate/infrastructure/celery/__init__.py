from celery import Celery
from new_backend_ruminate.config import settings

# Create the Celery application instance
celery_app = Celery(
    'video_worker',
    broker=settings().redis_url,
    backend=settings().redis_url,
    include=['new_backend_ruminate.infrastructure.celery.tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 min soft limit
    task_acks_late=True,  # Acknowledge tasks after completion
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    worker_max_tasks_per_child=1,  # Restart worker after each task to free memory
    result_expires=86400,  # Results expire after 24 hours
)

# Export the app
__all__ = ['celery_app']