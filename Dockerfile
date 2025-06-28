# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install ffmpeg and minimal deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata first for faster caching
COPY pyproject.toml ./
COPY new_backend_ruminate ./new_backend_ruminate

# Install python deps
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir .

# Expose port FastAPI listens on
EXPOSE 8000

# Default command for the web process; process groups can override
CMD ["uvicorn", "new_backend_ruminate.main:app", "--host", "0.0.0.0", "--port", "8000"]
