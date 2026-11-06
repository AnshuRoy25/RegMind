"""
Connection to Postgres.

- engine:        the connection pool to the database
- SessionLocal:  makes a new session (a "conversation" with the DB) when you need one
- init_db():     creates all tables on startup if they don't exist yet
- get_session(): FastAPI dependency that gives each API request its own session
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import Base

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session