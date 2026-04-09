"""Shared fixtures for tests/sql/."""

import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from pief.logdb import crud
from pief.logdb.schemas import EntryCreate, ExperimentCreate, LogbookCreate, UserCreate
from pief.logdb.tables import Entry, Experiment, Logbook, User
import pief.logdb.tables as _tables  # noqa: F401 — registers all ORM table metadata
from pief.logdb.tables import Base

POSTGRES_IMAGE = "postgres:17"
POSTGRES_DRIVER = "psycopg"


@pytest.fixture(scope="module")
def pg() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer(POSTGRES_IMAGE) as container:
        yield container


@pytest_asyncio.fixture(scope="module")
async def engine(pg: PostgresContainer) -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(pg.get_connection_url(driver=POSTGRES_DRIVER))
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture()
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as s:
        async with s.begin():
            nested = await s.begin_nested()  # SAVEPOINT
            yield s
            await nested.rollback()


@pytest.fixture()
def make_logbook(session: AsyncSession) -> Callable[..., Coroutine[Any, Any, Logbook]]:
    async def _factory(**kwargs: Any) -> Logbook:
        defaults: dict[str, Any] = {"type": "experiment", "name": f"lb-{uuid.uuid4()}"}
        return await crud.create_logbook(
            session=session,
            logbook_in=LogbookCreate(**{**defaults, **kwargs}),
        )

    return _factory


@pytest.fixture()
def make_user(session: AsyncSession) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _factory(**kwargs: Any) -> User:
        defaults: dict[str, Any] = {"username": f"user-{uuid.uuid4()}"}
        return await crud.create_user(
            session=session,
            user_in=UserCreate(**{**defaults, **kwargs}),
        )

    return _factory


@pytest.fixture()
def make_entry(
    session: AsyncSession,
    make_logbook: Callable[..., Coroutine[Any, Any, Logbook]],
    make_user: Callable[..., Coroutine[Any, Any, User]],
) -> Callable[..., Coroutine[Any, Any, Entry]]:
    async def _factory(**kwargs: Any) -> Entry:
        if "logbook_ids" not in kwargs:
            lb = await make_logbook()
            kwargs["logbook_ids"] = [lb.id]
        if "author_id" not in kwargs:
            user = await make_user()
            kwargs["author_id"] = user.id
        defaults: dict[str, Any] = {
            "title": "Test entry",
            "content": "Some content",
        }
        return await crud.create_entry(
            session=session,
            entry_in=EntryCreate(**{**defaults, **kwargs}),
        )

    return _factory


@pytest.fixture()
def make_experiment(
    session: AsyncSession,
) -> Callable[..., Coroutine[Any, Any, Experiment]]:
    async def _factory(**kwargs: Any) -> Experiment:
        defaults: dict[str, Any] = {
            "name": f"exp-{uuid.uuid4()}",
            "start_time": datetime.now(UTC),
        }
        return await crud.create_experiment(
            session=session,
            experiment_in=ExperimentCreate(**{**defaults, **kwargs}),
        )

    return _factory
