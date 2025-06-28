#!/usr/bin/env python
"""
Celery worker entry point for video generation.

To run the worker from ruminate root:
    celery -A new_backend_ruminate.worker worker --loglevel=info

To run with autoreload during development:
    celery -A new_backend_ruminate.worker worker --loglevel=info --autoreload
"""

from new_backend_ruminate.infrastructure.celery import celery_app

# Import tasks to register them
from new_backend_ruminate.infrastructure.celery.tasks import generate_video_task

if __name__ == '__main__':
    celery_app.start()