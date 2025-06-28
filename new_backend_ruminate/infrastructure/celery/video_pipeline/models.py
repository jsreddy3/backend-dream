from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class GenerateVideoRequest(BaseModel):
    dream_text: str = Field(..., max_length=1000, description="The dream description to convert to video")

class GenerateVideoResponse(BaseModel):
    job_id: str
    status: JobStatus
    estimated_duration_seconds: int

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    video_url: Optional[str] = None
    cost_estimate: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class Scene(BaseModel):
    scene_id: int
    summary: str
    visual_prompt: str
    voiceover_script: str
    duration_sec: int

class ScenesData(BaseModel):
    dream_summary: str
    scenes: List[Scene]
    total_duration_sec: int