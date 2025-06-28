from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Protocol
from sqlalchemy.ext.asyncio import AsyncSession

class Retriever(ABC):
    @abstractmethod
    async def fetch(self, ref: Any, *, session: AsyncSession) -> str: ...

class Renderer(Protocol):
    async def __call__(self, *_, session: AsyncSession) -> str: ...
