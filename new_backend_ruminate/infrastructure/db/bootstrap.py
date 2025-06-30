# new_backend_ruminate/infrastructure/db/bootstrap.py
"""
Single-source-of-truth for the SQLAlchemy async engine, session factory
and request-scoped unit-of-work helper.  No other module is permitted to
instantiate an engine or a sessionmaker; import these artefacts instead.

This file is imported by:
  • FastAPI application factory (lifespan) – for init_engine()
  • Alembic env.py                                – for `engine`
  • Repository implementations                    – for SessionFactory
  • Service / router dependency providers         – for session_scope()
  """

from __future__ import annotations

import asyncpg, asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.engine.url import URL
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
from new_backend_ruminate.config import _Settings as Settings

# Public, eagerly assigned in init_engine; start as None so that accidental
# early access raises deterministically rather than silently forging a new pool.
engine: Optional[AsyncEngine] = None
SessionFactory: Optional[async_sessionmaker[AsyncSession]] = None

# --------------------------------------------------------------------------- #
# Engine initialisation                                                       #
# --------------------------------------------------------------------------- #

async def init_engine(settings: "Settings") -> None:
    """
    Initialise the global AsyncEngine and async_sessionmaker exactly once.

    This coroutine MUST be called from the application lifespan handler
    *before* any request can touch the database.  A second invocation is an
    illegal state and raises RuntimeError.

    Phases
    ------
    1. Derive the SQLAlchemy URL from the strongly-typed Settings object,
       supporting at least:
         • PostgreSQL via asyncpg    – 'postgresql+asyncpg://…'
         • SQLite via aiosqlite      – 'sqlite+aiosqlite:///…'
       but allowing transparent extension to other async dialects.

    2. Decide on pool class:
         – Single-process dev uses QueuePool (default) with small size.
         – Serverless / short-lived lambda uses NullPool.
       Settings flags choose appropriately.

    3. Call create_async_engine with echo=False, future=True, poolclass=<…>,
       pool_size, max_overflow tuned from settings, and name the engine
       variable at module scope so all imports see the same instance.

    4. Create SessionFactory = async_sessionmaker(bind=engine,
       expire_on_commit=False, autoflush=False, autocommit=False).

    5. Run an optional one-shot connectivity check:
         async with engine.begin() as conn:
             await conn.execute(text("SELECT 1"))
       to fail fast on bad credentials.

    6. Expose telemetry hooks (e.g. SQL COMMENT ON) or event listeners for
       OpenTelemetry here if needed; keep out of business modules.

    7. Make idempotence explicit: if init_engine is invoked a second time
       raise RuntimeError so test suites or mis-wired DI graphs cannot
       silently create two pools.
    """
    global engine, SessionFactory

    if engine is not None or SessionFactory is not None:
        raise RuntimeError("init_engine() called twice; global engine already set")

    # -- Phase 1: URL synthesis ------------------------------------------------
    dialect = settings.db_dialect  # 'postgresql' | 'sqlite' | …
    if dialect == "postgresql":
        url = URL.create(
            drivername="postgresql+asyncpg",
            username=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
        )
        pool_cls = QueuePool
    elif dialect == "sqlite":
        url = settings.db_url
        # SQLite in async mode is already serialised; no pool needed.
        pool_cls = NullPool
    else:
        raise ValueError(f"Unsupported dialect {dialect!r}")

    # -- Phase 2–3: Engine construction ---------------------------------------
    kw = dict(
        echo = settings.sql_echo,
        future = True,
        # Proactively validate connections at checkout to avoid stale or half-open
        # sockets ("connection was closed in the middle of operation").  This
        # runs a lightweight `SELECT 1` before each use and transparently
        # reconnects if necessary.
        pool_pre_ping = True,
        # Close and reopen connections that have been idle for more than
        # `pool_recycle` seconds to mitigate NAT/firewall timeouts seen on
        # some networks.
        pool_recycle = 1800,
    )

    if pool_cls is QueuePool:
        kw.update(
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
        )
    
    engine = create_async_engine(
        url,
        **kw,
    )

    # -- Phase 4: Session factory ---------------------------------------------
    SessionFactory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # -- Phase 5: Ping ---------------------------------------------------------
    for attempt in range(5):                     # <= new
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            break                                # success
        except asyncpg.PostgresError:            # db not ready yet
            await asyncio.sleep(0.75 * (attempt + 0.5))
    else:
        raise RuntimeError("database never became ready")

    # Phase 6: (optional) telemetry wiring omitted for brevity
    # Phase 7 handled at top of function


# --------------------------------------------------------------------------- #
# Unit-of-work helper                                                         #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Asynchronous context manager that yields an AsyncSession bound to the
    global SessionFactory and encapsulates commit/rollback semantics.

    Usage in services:
        async with session_scope() as session:
            repo.save(entity, session)

    Usage in FastAPI:
        @router.post("/")
        async def endpoint(session: AsyncSession = Depends(session_scope)):
            …

    Behaviour contract
    ------------------
    • Ensures SessionFactory has been initialised; raises otherwise.
    • On normal exit commits, then closes.
    • On exception rollbacks, re-raises, then closes.
    • Always closes to return the connection to the pool.
    """
    if SessionFactory is None:
        raise RuntimeError("SessionFactory is not initialised; call init_engine()")

    session: AsyncSession = SessionFactory()
    try:
        yield session
        await session.commit()
    except BaseException:  # includes CancelledError
        await session.rollback()
        raise
    finally:
        await session.close()


# --------------------------------------------------------------------------- #
# Convenience FastAPI dependency                                              #
# --------------------------------------------------------------------------- #

async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Thin wrapper exposing session_scope as a FastAPI dependency.  Kept in the
    same module to avoid import cycles, but routers should import only this
    function, never SessionFactory directly.
    """
    async with session_scope() as session:
        yield session
