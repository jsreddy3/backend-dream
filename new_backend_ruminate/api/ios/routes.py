"""FastAPI routes for iOS push-notification device tokens."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.api.ios.schemas import DeviceCreate, DeviceRead
from new_backend_ruminate.domain.ios.entities.device import Device
from new_backend_ruminate.dependencies import (
    get_current_user_id,
    get_session,
    get_ios_device_repository,
)
from new_backend_ruminate.domain.ios.repo import DeviceRepository

router = APIRouter(prefix="/devices", tags=["ios"])

@router.post("/", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def upsert_device(
    payload: DeviceCreate,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Upsert the APNs device *token* for the authenticated user.

    • If a row with the same *token* already exists, we update its sandbox flag,
      timestamp, and (re-)associate it with the current user.
    • Otherwise we create a new row.
    """
    repo: DeviceRepository = get_ios_device_repository()

    # Lookup by token
    existing = await repo.get_by_token(payload.token, session)
    if existing:
        existing.sandbox = payload.sandbox
        existing.user_id = user_id
        existing.updated_at = datetime.utcnow()
        device = await repo.upsert(existing, session)
    else:
        device = Device(
            token=payload.token,
            sandbox=payload.sandbox,
            user_id=user_id,
            updated_at=datetime.utcnow(),
        )
        device = await repo.upsert(device, session)

    return DeviceRead.model_validate(device)
