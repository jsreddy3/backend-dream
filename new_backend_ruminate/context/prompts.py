import json
from new_backend_ruminate.domain.ports.tool import Tool

default_system_prompts = {
    "chat": "You are a helpful assistant.",
}

def agent_system_prompt(tools: list[Tool]) -> str:
    tool_lines = "\n".join(
        f"- {t.name}: {t.description}  params={json.dumps(t.parameters)}"
        for t in tools
    )
    return (
        "You are an autonomous research agent.  You may call these tools:\n"
        f"{tool_lines}\n\n"
        "Return a JSON object with keys thought, response_type, and either "
        "`action`+`arguments` or `answer`.\n"
    )