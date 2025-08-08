"""Port interface for user persistence."""
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import User

class UserRepository(ABC):
    """Hexagonal port: persistence operations for User aggregate."""

    @abstractmethod
    async def upsert_google_user(self, claims: dict, session: AsyncSession) -> User: ...

    @abstractmethod
    async def get_by_id(self, uid: UUID, session: AsyncSession) -> Optional[User]: ...

    @abstractmethod
    async def get_by_sub(self, sub: str, session: AsyncSession) -> Optional[User]: ...

    @abstractmethod
    async def delete_user(self, user_id: UUID, session: AsyncSession) -> None: ...
