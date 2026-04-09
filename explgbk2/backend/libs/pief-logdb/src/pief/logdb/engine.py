"""SQLAlchemy async engine and session factory for pief.logdb.

Uses SQLAlchemy's async engine with psycopg3 (the ``psycopg`` package supports
both sync and async under the same ``postgresql+psycopg://`` URL scheme).
``expire_on_commit=False`` is set on the session factory because async sessions
cannot implicitly re-query expired attributes after a commit — the session may
already be closed by the time ORM objects are accessed in the response.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pief.logdb.config.settings import settings as db_settings

_engine = create_async_engine(str(db_settings.SQLALCHEMY_DATABASE_URI))

_async_session_factory = async_sessionmaker(
    _engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields one ``AsyncSession`` per request."""
    async with _async_session_factory() as session:
        yield session
