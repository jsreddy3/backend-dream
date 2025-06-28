# Running the Backend with Video Worker

## Prerequisites

1. **Copy `.env.example` to `.env` and fill in your credentials:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Install Redis (if not already installed):**
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Or run in Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

5. **Install FFmpeg:**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   ```

## Starting the Services

You'll need 3 terminal windows:

### Terminal 1: Start Redis (if not using brew services)
```bash
redis-server
```

### Terminal 2: Start the API
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3: Start the Celery Worker
```bash
celery -A worker worker --loglevel=info
```

## Testing Video Generation

Once all services are running:

```bash
python test_video_generation.py
```

## Monitoring

### Check Celery Tasks (Optional)
```bash
# Install Flower
pip install flower

# Run Flower dashboard
celery -A worker flower --port=5555
```

Then open http://localhost:5555 in your browser.

## Common Issues

### "ModuleNotFoundError: No module named 'new_backend_ruminate'"
```bash
# Install the package in development mode
pip install -e .
```

### "Cannot connect to Redis"
Make sure Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### "OPENAI_API_KEY not set"
Make sure your `.env` file contains valid API keys.

### Database connection errors
For development, you can use SQLite by setting in `.env`:
```
DB_URL=sqlite+aiosqlite:///./dev.sqlite
```

## Quick Start (All in One)

```bash
# Terminal 1
redis-server

# Terminal 2  
uvicorn main:app --reload

# Terminal 3
celery -A worker worker --loglevel=info

# Terminal 4 (test)
python test_video_generation.py
```