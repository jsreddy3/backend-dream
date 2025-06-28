# Video Generation Worker Setup

This document describes the video generation worker implementation for the new backend.

## Architecture Overview

The video generation functionality has been implemented as a separate Celery worker that processes video generation jobs asynchronously. This provides:

- **Scalability**: Workers can be scaled independently of the API
- **Fault tolerance**: Failed jobs can be retried automatically
- **Resource isolation**: Long-running video tasks don't block the API
- **Monitoring**: Job status can be tracked via Celery

## Components Added

### 1. Dependencies
- `celery[redis]` - Task queue framework
- `redis` - Message broker and result backend
- `kombu` - Messaging library

### 2. Domain Layer
- `domain/ports/video_queue.py` - Port interface for video queue operations
- Updated `domain/dream/entities/dream.py` with video tracking fields

### 3. Infrastructure Layer
- `infrastructure/celery/__init__.py` - Celery app configuration
- `infrastructure/celery/adapter.py` - Celery adapter implementing VideoQueuePort
- `infrastructure/celery/tasks.py` - Video generation task definition
- `infrastructure/celery/video_pipeline/` - Copied video pipeline from campfire

### 4. Service Layer
- Updated `services/video.py` to queue jobs instead of running inline
- Added video completion handling methods to `DreamService`

### 5. API Layer
- Added `/dreams/{did}/video-status` endpoint to check job status
- Updated `/dreams/{did}/video-complete` to handle worker callbacks
- Added request/response schemas for video operations

### 6. Database Changes
- Added video tracking fields to dreams table:
  - `video_job_id` - Celery task ID
  - `video_status` - Current status (queued/processing/completed/failed)
  - `video_url` - S3 URL of generated video
  - `video_metadata` - JSON metadata from pipeline
  - `video_started_at` - When generation started
  - `video_completed_at` - When generation completed

## Setup Instructions

### 1. Run Database Migrations
```bash
alembic upgrade head
```

### 2. Configure Environment Variables
Add to your `.env` file:
```
REDIS_URL=redis://localhost:6379/0
API_BASE_URL=http://localhost:8000
```

For Fly.io deployment:
```
REDIS_URL=redis://your-redis.upstash.io
API_BASE_URL=https://your-app.fly.dev
```

### 3. Start Redis (Local Development)
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally
brew install redis
redis-server
```

### 4. Start the Worker
```bash
# Basic worker
celery -A worker worker --loglevel=info

# With autoreload for development
celery -A worker worker --loglevel=info --autoreload

# With specific concurrency
celery -A worker worker --loglevel=info --concurrency=2
```

### 5. Monitor Workers (Optional)
```bash
# Install Flower
pip install flower

# Start Flower dashboard
celery -A worker flower --port=5555
```

## Fly.io Deployment

### 1. Create Redis Instance
```bash
fly redis create --name your-app-redis
```

### 2. Create Worker Configuration
Create `fly.worker.toml`:
```toml
app = "your-app-worker"
primary_region = "sjc"

[processes]
worker = "celery -A worker worker --loglevel=info"

[env]
REDIS_URL = "redis://default:your-password@your-redis.upstash.io"
API_BASE_URL = "https://your-app.fly.dev"
# Copy other env vars from main app
```

### 3. Deploy Worker
```bash
fly deploy -c fly.worker.toml
```

## Usage

### 1. Video Generation Flow
1. User calls `POST /dreams/{did}/finish`
2. API queues video generation job via Celery
3. Worker picks up job and runs video pipeline
4. Worker sends callback to `POST /dreams/{did}/video-complete`
5. API updates dream status and stores video URL

### 2. Check Video Status
```bash
GET /dreams/{did}/video-status

Response:
{
  "job_id": "celery-task-id",
  "status": "processing",
  "video_url": null
}
```

### 3. Video Complete Callback
The worker automatically calls this endpoint when done:
```bash
POST /dreams/{did}/video-complete
{
  "status": "completed",
  "video_url": "https://bucket.s3.amazonaws.com/videos/dream-id.mp4",
  "metadata": {
    "duration": 30,
    "scenes": 2,
    "cost": 0.15
  }
}
```

## System Requirements

### FFmpeg Installation
The video pipeline requires FFmpeg to be installed on your system:

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## TODO / Future Improvements

1. ~~**S3 Upload**: Currently returns mock S3 URLs. Need to implement actual S3 upload in `tasks.py`~~ ✅ COMPLETED
2. **Progress Updates**: Add real-time progress updates via SSE
3. **Priority Queues**: Implement different priority levels for premium users
4. **Video Preview**: Generate low-res previews quickly
5. **Cleanup**: Add periodic task to clean up old local video files
6. **Monitoring**: Add Prometheus metrics for queue depth, processing time
7. **Error Recovery**: Implement more sophisticated retry strategies

## Troubleshooting

### Worker Not Processing Jobs
1. Check Redis connection: `redis-cli ping`
2. Check worker logs for errors
3. Verify env vars are set correctly

### Video Generation Fails
1. Check worker logs for specific errors
2. Verify OpenAI API key is valid
3. Check disk space for video output
4. Ensure FFmpeg is installed

### Database Errors
1. Run migrations: `alembic upgrade head`
2. Check database connection
3. Verify schema matches entity definitions