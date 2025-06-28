# new_backend_ruminate/context/renderers/default.py

async def plain_renderer(msg, *_ , **__) -> str:
    return msg.content
