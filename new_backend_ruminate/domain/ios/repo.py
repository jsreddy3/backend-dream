from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.ios.entities.device import Device


class DeviceRepository(ABC):
    @abstractmethod
    async def get_by_id(self, device_id: UUID, session: AsyncSession) -> Optional[Device]: ...

    @abstractmethod
    async def get_by_token(self, token: str, session: AsyncSession) -> Optional[Device]: ...

    @abstractmethod
    async def upsert(self, device: Device, session: AsyncSession) -> Device: ...

    @abstractmethod
    async def list_by_user(self, user_id: UUID, session: AsyncSession) -> list[Device]: ...