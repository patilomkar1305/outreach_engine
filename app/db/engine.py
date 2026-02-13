"""
app/db/engine.py
────────────────
SQLAlchemy async engine & session factory.
Every module that needs a DB connection imports `get_session`.
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.config import settings

# ---------------------------------------------------------------------------
# Engine  (AsyncAdaptedQueuePool is the default for async engines)
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.postgres.async_url,
    echo=False,
    pool_pre_ping=True,          # validate connections before use
    pool_size=5,
    max_overflow=10,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context-manager that yields a usable session and
    commits on success / rolls back on error.

        async with get_session() as session:
            session.add(...)
            # auto-committed when the block exits cleanly
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
