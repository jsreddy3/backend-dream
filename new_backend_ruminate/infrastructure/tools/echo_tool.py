# new_backend_ruminate/infrastructure/tools/echo_tool.py

from __future__ import annotations
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.ports.tool import Tool, register_tool


class EchoTool(Tool):
    name         = "echo"
    description  = "Echo back the supplied text exactly."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo"}
        },
        "required": ["text"],
    }

    async def run(self, *, session: AsyncSession, **kwargs) -> str:   # noqa: D401
        return kwargs["text"]


# register at import time
register_tool(EchoTool())
