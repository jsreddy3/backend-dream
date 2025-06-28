# Running the Backend

All commands should be run from the **backend_dream root directory** (`/Users/jaidenreddy/Documents/projects/backend_dream`).

## Prerequisites

1. **Install python project**
```bash
pip install -e .
```

2. **Install FFmpeg (for video generation):**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   ```

## Starting All Services

### 1. Start PostgreSQL and Redis with Docker
```bash
docker compose up -d
```

This starts both PostgreSQL and Redis in the background.

### 2. Run Database Migrations
```bash
alembic upgrade head
```

### 3. Start the API (Terminal 1)
```bash
uvicorn new_backend_ruminate.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start the Celery Worker (Terminal 2)
```bash
celery -A new_backend_ruminate.worker worker --loglevel=info
```

## Testing Video Generation

Once all services are running, you can test from the new_backend_ruminate directory:

```bash
cd new_backend_ruminate
python test_video_generation.py
cd ..
```

## Monitoring

### Check Services Status
```bash
# Check if Redis is running
docker compose ps

# Test Redis connection
docker exec -it campfire-redis redis-cli ping
# Should return: PONG

# Check database
docker exec -it campfire-db psql -U campfire -d campfire -c "SELECT 1;"
```

### Monitor Celery (Optional)
```bash
# Install Flower
pip install flower

# Run Flower dashboard
celery -A new_backend_ruminate.worker flower --port=5555
```

Then open http://localhost:5555 in your browser.

## Stopping Services

```bash
# Stop Docker services
docker compose down

# Stop API: Ctrl+C in Terminal 1
# Stop Worker: Ctrl+C in Terminal 2
```

## Quick Commands Summary

```bash
# From ruminate root directory:

# 1. Start services
docker compose up -d

# 2. Run migrations  
alembic upgrade head

# 3. Terminal 1 - API
uvicorn new_backend_ruminate.main:app --reload --host 0.0.0.0 --port 8000

# 4. Terminal 2 - Worker
celery -A new_backend_ruminate.worker worker --loglevel=info

# 5. Terminal 3 - Test (optional)
cd new_backend_ruminate && python test_video_generation.py && cd ..
```

## Troubleshooting

### "Module not found" errors
Make sure you're running commands from the ruminate root directory, not from new_backend_ruminate.

### Redis connection errors
Check if Redis is running:
```bash
docker compose ps
```

If not running:
```bash
docker compose up -d redis
```

### Database connection errors
Check if PostgreSQL is running:
```bash
docker compose ps
```

### Video generation fails
1. Check your OPENAI_API_KEY in .env is valid
2. Ensure FFmpeg is installed: `ffmpeg -version`
3. Check worker logs for specific errors