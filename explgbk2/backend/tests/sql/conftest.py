"""Shared fixtures for tests/sql/."""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine
from testcontainers.postgres import PostgresContainer

POSTGRES_IMAGE = "postgres:17"
POSTGRES_DRIVER = "psycopg"


@pytest.fixture(scope="module")
def pg() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer(POSTGRES_IMAGE) as container:
        yield container


@pytest.fixture(scope="module")
def engine(pg: PostgresContainer) -> Generator[Engine, None, None]:
    eng = create_engine(pg.get_connection_url(driver=POSTGRES_DRIVER))
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as s:
        with s.begin():
            nested = s.begin_nested()  # SAVEPOINT
            yield s
            nested.rollback()
