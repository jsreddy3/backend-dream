# tests/conftest.py
import os
import tempfile
import pytest_asyncio
from sqlalchemy import text

from new_backend_ruminate.infrastructure.db import bootstrap
from new_backend_ruminate.infrastructure.db.meta import Base
from new_backend_ruminate.config import settings as _settings
import logging

for name in (
    "aiosqlite",
    "asyncio",              # selector_events etc.
    "sqlalchemy.pool",      # connection checkout/return
    "sqlalchemy.engine.Engine",  # SQL text if you ever set echo=True
):
    logging.getLogger(name).setLevel(logging.WARNING)

# leave your application namespace free to speak at INFO
logging.getLogger("new_backend_ruminate").setLevel(logging.INFO)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def sqlite_file_db():
    """
    One per-session SQLite file that survives multiple connections, so every
    AsyncSession sees the same schema and data.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db")
    os.environ["DB_URL"] = f"sqlite+aiosqlite:///{tmp.name}"

    # purge cached settings so the new env var is respected
    _settings.cache_clear()
    cfg = _settings()

    await bootstrap.init_engine(cfg)

    async with bootstrap.engine.begin() as conn:          # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)

    yield

    await bootstrap.engine.dispose()
    tmp.close()


@pytest_asyncio.fixture
async def db_session():
    """
    Function-scoped AsyncSession; rolls back automatically on exit.
    """
    async with bootstrap.session_scope() as session:
        yield session
