from typing import List, Optional, Union, Any, Dict
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, computed_field
import json

class SegmentBase(BaseModel):
    order: int
    modality: str  # "audio" or "text"

class SegmentCreate(SegmentBase):
    segment_id: UUID
    # Audio-specific fields
    filename: Optional[str] = None
    duration: Optional[float] = None  # seconds
    s3_key: Optional[str] = None
    # Text-specific fields
    text: Optional[str] = None

class SegmentRead(SegmentBase):
    id: UUID = Field(alias="segment_id")  # Swap field name and alias
    filename: Optional[str] = None
    duration: Optional[float] = None
    s3_key: Optional[str] = None
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

class DreamUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None

class DreamRead(DreamBase):
    id: UUID
    created: datetime
    transcript: Optional[str]
    summary: Optional[str]
    additional_info: Optional[str]
    analysis: Optional[str]
    analysis_generated_at: Optional[datetime]
    analysis_metadata: Optional[dict]
    state: str
    segments: List[SegmentRead] = []
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

class SummaryUpdate(BaseModel):
    summary: str

class GenerateSummaryResponse(BaseModel):
    title: str
    summary: str

# Interpretation Questions Schemas
class InterpretationChoiceRead(BaseModel):
    id: UUID
    choice_text: str
    choice_order: int
    is_custom: bool

    model_config = ConfigDict(from_attributes=True)

class InterpretationQuestionRead(BaseModel):
    id: UUID
    question_text: str
    question_order: int
    choices: List[InterpretationChoiceRead]

    model_config = ConfigDict(from_attributes=True)

class GenerateQuestionsRequest(BaseModel):
    num_questions: int = 3
    num_choices: int = 3

class GenerateQuestionsResponse(BaseModel):
    questions: List[InterpretationQuestionRead]

class RecordAnswerRequest(BaseModel):
    question_id: UUID
    choice_id: Optional[UUID] = None
    custom_answer: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        """Either choice_id or custom_answer must be provided."""
        return bool(self.choice_id or self.custom_answer)

class InterpretationAnswerRead(BaseModel):
    id: UUID
    question_id: UUID
    selected_choice_id: Optional[UUID]
    custom_answer: Optional[str]
    answered_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders = {
            datetime: lambda dt: dt.isoformat(timespec="seconds") + "Z"
        }
    )

class AdditionalInfoUpdate(BaseModel):
    additional_info: str

class GenerateAnalysisRequest(BaseModel):
    force_regenerate: bool = False

class AnalysisResponse(BaseModel):
    analysis: str
    generated_at: datetime
    metadata: Optional[dict] = None
    
    model_config = ConfigDict(
        json_encoders = {
            datetime: lambda dt: dt.isoformat(timespec="seconds") + "Z"
        }
    )