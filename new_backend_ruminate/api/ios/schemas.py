"""Schemas for iOS push-notification device registration."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class DeviceBase(BaseModel):
    token: str = Field(max_length=400)
    sandbox: bool = False

class DeviceCreate(DeviceBase):
    """Payload sent by the iOS client when registering a device token."""
    pass

class DeviceRead(DeviceBase):
    id: UUID
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
