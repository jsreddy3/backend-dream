# new_backend_ruminate/main.py

from fastapi import FastAPI
from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.db.bootstrap import init_engine
from new_backend_ruminate.dependencies import get_event_hub  # optional: expose on app.state
from new_backend_ruminate.api.conversation.routes import router as conversation_router
from new_backend_ruminate.api.dream.routes import router as dream_router

import logging
from fastapi.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# ───────────────────── global error logging ────────────────────── #
@app.middleware("http")
async def _error_logging_middleware(request: Request, call_next):
    try:
        print("Middleware")
        return await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception processing %s %s", request.method, request.url)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

# ─────────────────────────── routes ────────────────────────────── #
app.include_router(conversation_router)          # wires /conversations/…
app.include_router(dream_router)                 # wires /dreams/…

@app.on_event("startup")
async def _startup() -> None:
    await init_engine(settings())
    app.state.event_hub = get_event_hub()          # handy for websocket upgrades
