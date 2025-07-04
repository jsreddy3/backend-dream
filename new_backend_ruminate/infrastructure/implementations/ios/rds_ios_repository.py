from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.ios.entities.device import Device
from new_backend_ruminate.domain.ios.repo import DeviceRepository
from uuid import UUID
from typing import Optional
from sqlalchemy import select

class RDSDeviceRepository(DeviceRepository):
    """Async SQLAlchemy implementation for Device persistence."""
    def __init__(self) -> None:
        # stateless – real sessions are passed to each method
        pass

    async def get_by_id(self, device_id: UUID, session: AsyncSession) -> Optional[Device]:
        return await session.get(Device, device_id)

    async def get_by_token(self, token: str, session: AsyncSession) -> Optional[Device]:
        result = await session.execute(select(Device).where(Device.token == token))
        return result.scalars().first()

    async def upsert(self, device: Device, session: AsyncSession) -> Device:
        session.add(device)
        await session.commit()
        await session.refresh(device)
        return device

    async def list_by_user(
        self,
        user_id: UUID,
        session: AsyncSession,
    ) -> list[Device]:
        stmt = select(Device).where(Device.user_id == user_id)
        result = await session.scalars(stmt)
        return list(result)
