# new_backend/domain/ports/tool.py

from abc import ABC, abstractmethod
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

class Tool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]          # JSON-schema fragment for args

    @abstractmethod
    async def run(self, *, session: AsyncSession, **kwargs) -> str: ...

tool_registry: Dict[str, Tool] = {}
def register_tool(t: Tool) -> None: tool_registry[t.name] = t