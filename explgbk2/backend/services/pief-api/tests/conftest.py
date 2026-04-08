"""Session-wide fixtures for pief-api integration tests.

Uses testcontainers PostgreSQL + Alembic for a fully migrated, isolated database.
Overrides the pief.logdb.engine.get_session dependency so the FastAPI TestClient
uses the test database instead of the real one.
"""

from collections.abc import Generator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlmodel import Session
from testcontainers.postgres import PostgresContainer

import pief.logdb.tables as _tables  # noqa: F401 — registers all SQLModel metadata
from pief.api.core.config import settings
from pief.api.main import app
from pief.logdb import crud
from pief.logdb.config.alembic import alembic_config
from pief.logdb.engine import get_session
from pief.logdb.schemas import UserCreate

POSTGRES_IMAGE = "postgres:17"
POSTGRES_DRIVER = "psycopg"


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    """Spin up a PostgreSQL container, apply all migrations, yield the engine."""
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        engine = create_engine(pg.get_connection_url(driver=POSTGRES_DRIVER))
        command.upgrade(alembic_config(engine), "head")
        yield engine
        engine.dispose()


@pytest.fixture(scope="session")
def client(postgres_engine: Engine) -> Generator[TestClient, None, None]:
    """TestClient wired to the test database via dependency override."""

    def override_get_session() -> Generator[Session, None, None]:
        with Session(postgres_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    # Seed the default user that deps.py expects to find.
    with Session(postgres_engine) as session:
        if not crud.get_user_by_username(
            session=session, username=settings.FIRST_SUPERUSER
        ):
            crud.create_user(
                session=session,
                user_in=UserCreate(username=settings.FIRST_SUPERUSER),
            )
            session.commit()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
