# tests/agent/test_tool_registry.py
import pytest, asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.ports.tool import Tool, register_tool, tool_registry

class Echo(Tool):
    name, description, parameters = "echo_stub", "", {
        "type": "object",
        "properties": {"txt": {"type": "string"}},
        "required": ["txt"],
    }
    async def run(self, *, session, **kw):
        return kw["txt"]

register_tool(Echo())


@pytest.mark.asyncio
async def test_tool_runs(db_session):
    t = tool_registry["echo_stub"]
    assert await t.run(session=db_session, txt="ping") == "ping"
