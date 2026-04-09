"""Tests for Experiment CRUD — uses testcontainers PostgreSQL."""

import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pief.logdb import crud
from pief.logdb.schemas import ExperimentCreate, ExperimentUpdate
from pief.logdb.tables import Experiment, Logbook


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


async def test_create_experiment(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    exp = await make_experiment(description="A test experiment")
    assert exp.id is not None
    assert exp.description == "A test experiment"
    assert exp.end_time is None
    assert exp.created_at.tzinfo is not None
    assert exp.updated_at.tzinfo is not None
    assert exp.meta == {}


async def test_experiment_name_unique(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    name = f"unique-{uuid.uuid4()}"
    await make_experiment(name=name)
    await session.flush()
    with pytest.raises(IntegrityError):
        await make_experiment(name=name)


def test_experiment_invalid_name_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentCreate(name="", start_time=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def test_get_experiment(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    exp = await make_experiment()
    fetched = await crud.get_experiment(session=session, experiment_id=exp.id)
    assert fetched is not None
    assert fetched.id == exp.id
    missing = await crud.get_experiment(session=session, experiment_id=uuid.uuid4())
    assert missing is None


async def test_get_experiment_by_name(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    name = f"named-{uuid.uuid4()}"
    await make_experiment(name=name)
    result = await crud.get_experiment_by_name(session=session, name=name)
    assert result is not None
    assert result.name == name
    assert (
        await crud.get_experiment_by_name(session=session, name="no-such-exp") is None
    )


async def test_get_experiment_by_legacy_id(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    legacy = f"oldname_{uuid.uuid4().hex[:8]}"
    await make_experiment(legacy_id=legacy)
    result = await crud.get_experiment_by_legacy_id(session=session, legacy_id=legacy)
    assert result is not None
    assert result.legacy_id == legacy
    assert (
        await crud.get_experiment_by_legacy_id(session=session, legacy_id="nope")
        is None
    )


# ---------------------------------------------------------------------------
# JSONB meta
# ---------------------------------------------------------------------------


async def test_experiment_meta_jsonb(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    """meta JSONB round-trips nested v1 metadata."""
    meta = {
        "leader_account": "jdoe",
        "contact_info": "jdoe@slac.stanford.edu",
        "posix_group": "diadaq",
        "is_locked": False,
        "params": {"DATA_PATH": "/reg/d/psdm/dia/diadaq13", "PNR": "LP13"},
    }
    exp = await make_experiment(meta=meta)
    assert exp.meta["leader_account"] == "jdoe"
    assert exp.meta["params"]["DATA_PATH"] == "/reg/d/psdm/dia/diadaq13"
    assert exp.meta["is_locked"] is False


# ---------------------------------------------------------------------------
# FK constraint
# ---------------------------------------------------------------------------


async def test_experiment_logbook_fk(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
    make_logbook: Callable[..., Coroutine[Any, Any, Logbook]],
) -> None:
    """logbook_id FK to logbooks.id is enforced."""
    lb = await make_logbook()
    exp = await make_experiment(logbook_id=lb.id)
    assert exp.logbook_id == lb.id

    # FK violation: non-existent logbook_id must fail
    bad_exp = await make_experiment()
    bad_exp.logbook_id = uuid.uuid4()
    session.add(bad_exp)
    with pytest.raises(IntegrityError):
        await session.flush()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_experiment(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    """update_experiment mutates description, end_time, and meta."""
    exp = await make_experiment(description="Original")
    assert exp.end_time is None

    end = datetime.now(UTC)
    updated = await crud.update_experiment(
        session=session,
        experiment=exp,
        experiment_update=ExperimentUpdate(
            description="Updated",
            end_time=end,
            meta={"is_locked": True},
        ),
    )
    assert updated.description == "Updated"
    assert updated.end_time is not None
    assert updated.end_time.tzinfo is not None
    assert updated.meta["is_locked"] is True
