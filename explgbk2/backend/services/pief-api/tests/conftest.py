"""Session-wide fixtures for pief-api integration tests.

Uses testcontainers PostgreSQL + Alembic for a fully migrated, isolated database.
Overrides the pief.logdb.engine.get_session dependency so the FastAPI TestClient
uses the test database instead of the real one.
"""

from collections.abc import AsyncGenerator, Generator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from testcontainers.postgres import PostgresContainer

import pief.logdb.tables as _tables  # noqa: F401 — registers all ORM table metadata
from pief.api.core.config import settings
from pief.api.main import app
from pief.logdb.config.alembic import alembic_config
from pief.logdb.engine import get_session
from pief.logdb.tables import User

POSTGRES_IMAGE = "postgres:17"
POSTGRES_DRIVER = "psycopg"


@pytest.fixture(scope="session")
def pg() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer(POSTGRES_IMAGE) as container:
        yield container


@pytest.fixture(scope="session")
def postgres_engine(pg: PostgresContainer) -> Generator[Engine, None, None]:
    """Sync engine for test data setup and Alembic migrations."""
    engine = create_engine(pg.get_connection_url(driver=POSTGRES_DRIVER))
    command.upgrade(alembic_config(engine), "head")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def client(
    pg: PostgresContainer, postgres_engine: Engine
) -> Generator[TestClient, None, None]:
    """TestClient wired to the test database via async dependency override."""
    # Build the async engine from the raw container URL (avoids masked password).
    async_conn_url = pg.get_connection_url(driver=POSTGRES_DRIVER)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        engine = create_async_engine(async_conn_url)
        async with AsyncSession(engine) as session:
            yield session
        await engine.dispose()

    app.dependency_overrides[get_session] = override_get_session

    # Seed the default user using sync ORM.
    with Session(postgres_engine) as session:
        existing = (
            session.execute(
                select(User).where(User.username == settings.FIRST_SUPERUSER)
            )
            .scalars()
            .one_or_none()
        )
        if not existing:
            session.add(User(username=settings.FIRST_SUPERUSER))
            session.commit()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
