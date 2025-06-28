from typing import List, Optional, Union, Any, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, computed_field
import json

class AudioSegmentBase(BaseModel):
    filename: str
    duration: float   # seconds
    order: int
    s3_key: str

class AudioSegmentCreate(AudioSegmentBase):
    segment_id: UUID

class AudioSegmentRead(AudioSegmentBase):
    id: UUID = Field(alias="segment_id")  # Swap field name and alias
    transcript: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders = {
            datetime: lambda dt: dt.isoformat(timespec="seconds") + "Z"
        }
    )

class DreamBase(BaseModel):
    title: str

class DreamCreate(DreamBase):
    id: UUID | None = None          # accept optional id from client
    title: str

class DreamUpdate(DreamBase):
    pass

class DreamRead(DreamBase):
    id: UUID
    created: datetime
    transcript: Optional[str]
    state: str
    segments: List[AudioSegmentRead] = []
    video_url: Optional[str] = None
    
    @property  
    def video_s3_key(self) -> Optional[str]:
        """Extract S3 key from video_url for iOS compatibility"""
        if self.video_url:
            # Extract key from URL: https://bucket.s3.region.amazonaws.com/dreams/uuid/video.mp4
            return self.video_url.split('.com/')[-1] if '.com/' in self.video_url else None
        return None
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to include video_s3_key in serialization"""
        data = super().model_dump(**kwargs)
        data['video_s3_key'] = self.video_s3_key
        # Fix datetime format for iOS compatibility
        if 'created' in data and isinstance(data['created'], datetime):
            data['created'] = data['created'].isoformat(timespec="seconds") + "Z"
        # Fix segment field names for iOS compatibility
        if 'segments' in data:
            for segment in data['segments']:
                if 'segment_id' in segment:
                    segment['id'] = segment.pop('segment_id')
        return data

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders = {
            datetime: lambda dt: dt.isoformat(timespec="seconds") + "Z"
        }
    )

class TranscriptRead(BaseModel):
    transcript: str

class UploadUrlResponse(BaseModel):
    upload_url: str
    upload_key: str

class VideoCompleteRequest(BaseModel):
    video_url: Optional[str] = None
    metadata: Optional[dict] = None
    status: str  # "completed" or "failed"
    error: Optional[str] = None

class VideoStatusResponse(BaseModel):
    job_id: Optional[str]
    status: Optional[str]
    video_url: Optional[str]

class VideoURLResponse(BaseModel):
    video_url: str
    expires_in: int = 3600  # URL expires in 1 hour by default