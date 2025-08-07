# tests/conftest.py
import os
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from new_backend_ruminate.infrastructure.db import bootstrap
from new_backend_ruminate.infrastructure.db.meta import Base
from new_backend_ruminate.config import settings as _settings
import logging

for name in (
    "asyncio",              # selector_events etc.
    "sqlalchemy.pool",      # connection checkout/return
    "sqlalchemy.engine.Engine",  # SQL text if you ever set echo=True
):
    logging.getLogger(name).setLevel(logging.WARNING)

# leave your application namespace free to speak at INFO
logging.getLogger("new_backend_ruminate").setLevel(logging.INFO)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def postgres_test_db():
    """
    Session-scoped Postgres test database.
    Creates a separate test database to avoid affecting development data.
    """
    # Connect to main database to create test database
    admin_engine = create_async_engine(
        "postgresql+asyncpg://campfire:campfire@localhost:5433/campfire",
        isolation_level="AUTOCOMMIT"
    )
    
    async with admin_engine.begin() as conn:
        # Drop and recreate test database
        await conn.execute(text("DROP DATABASE IF EXISTS campfire_test"))
        await conn.execute(text("CREATE DATABASE campfire_test"))
    
    await admin_engine.dispose()
    
    # Configure test database
    os.environ["DB_URL"] = "postgresql+asyncpg://campfire:campfire@localhost:5433/campfire_test"
    _settings.cache_clear()
    cfg = _settings()
    
    await bootstrap.init_engine(cfg)
    
    # Create all tables
    async with bootstrap.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Cleanup
    await bootstrap.engine.dispose()
    
    # Drop test database
    async with admin_engine.begin() as conn:
        await conn.execute(text("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'campfire_test'
            AND pid <> pg_backend_pid()
        """))
        await conn.execute(text("DROP DATABASE IF EXISTS campfire_test"))
    
    await admin_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    """
    Function-scoped AsyncSession; rolls back automatically on exit.
    """
    async with bootstrap.session_scope() as session:
        yield session
