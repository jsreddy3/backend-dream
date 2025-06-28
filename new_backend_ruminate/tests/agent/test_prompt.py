# tests/agent/test_prompt.py
import json, textwrap, pytest
from new_backend_ruminate.context.prompts import agent_system_prompt
from new_backend_ruminate.domain.ports.tool import Tool

class Foo(Tool):
    name, description, parameters = "foo", "does foo", {"type":"object"}
    async def run(self, *, session, **kw): return ""

@pytest.mark.asyncio
async def test_agent_system_prompt_includes_all_tools():
    txt = agent_system_prompt([Foo()])
    assert "foo" in txt and "does foo" in txt
    assert json.dumps(Foo.parameters) in txt
