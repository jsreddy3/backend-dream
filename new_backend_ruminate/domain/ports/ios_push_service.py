from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from abc import ABC, abstractmethod

class NotificationService(ABC):
    @abstractmethod
    async def send_notification(self, user_id: UUID, dream_id: UUID, session: AsyncSession) -> None:
        ...