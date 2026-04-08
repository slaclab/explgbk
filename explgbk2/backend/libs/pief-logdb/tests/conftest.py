"""Shared fixtures for tests/sql/."""

import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine
from testcontainers.postgres import PostgresContainer

from pief.logdb import crud
from pief.logdb.schemas import EntryCreate, ExperimentCreate, LogbookCreate
from pief.logdb.tables import Entry, Experiment, Logbook

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


@pytest.fixture()
def make_logbook(session: Session) -> Callable[..., Logbook]:
    def _factory(**kwargs: Any) -> Logbook:
        defaults: dict[str, Any] = {"type": "experiment", "name": f"lb-{uuid.uuid4()}"}
        return crud.create_logbook(
            session=session,
            logbook_in=LogbookCreate(**{**defaults, **kwargs}),
        )

    return _factory


@pytest.fixture()
def make_entry(
    session: Session, make_logbook: Callable[..., Logbook]
) -> Callable[..., Entry]:
    def _factory(**kwargs: Any) -> Entry:
        if "logbook_ids" not in kwargs:
            lb = make_logbook()
            kwargs["logbook_ids"] = [lb.id]
        defaults: dict[str, Any] = {
            "author_id": uuid.uuid4(),
            "title": "Test entry",
            "content": "Some content",
        }
        return crud.create_entry(
            session=session,
            entry_in=EntryCreate(**{**defaults, **kwargs}),
        )

    return _factory


@pytest.fixture()
def make_experiment(session: Session) -> Callable[..., Experiment]:
    def _factory(**kwargs: Any) -> Experiment:
        defaults: dict[str, Any] = {
            "name": f"exp-{uuid.uuid4()}",
            "start_time": datetime.now(UTC),
        }
        return crud.create_experiment(
            session=session,
            experiment_in=ExperimentCreate(**{**defaults, **kwargs}),
        )

    return _factory
