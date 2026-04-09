"""Tests for Instrument shell table, FK hardening, and soft-link fields."""

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pief.logdb import crud
from pief.logdb.schemas import (
    InstrumentCreate,
)
from pief.logdb.tables import Entry, Experiment


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------


async def test_create_instrument(session: AsyncSession) -> None:
    meta = {"name": "TMO", "facility": "LCLS"}
    inst = await crud.create_instrument(
        session=session,
        instrument_in=InstrumentCreate(meta=meta),
    )
    assert inst.id is not None
    assert inst.meta == meta
    assert inst.created_at.tzinfo is not None


async def test_get_instrument(session: AsyncSession) -> None:
    inst = await crud.create_instrument(
        session=session, instrument_in=InstrumentCreate()
    )
    fetched = await crud.get_instrument(session=session, instrument_id=inst.id)
    assert fetched is not None
    assert fetched.id == inst.id
    missing = await crud.get_instrument(session=session, instrument_id=uuid.uuid4())
    assert missing is None


# ---------------------------------------------------------------------------
# FK hardening: Experiment.instrument_id -> instruments.id
# ---------------------------------------------------------------------------


async def test_experiment_instrument_fk(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    """instrument_id FK to instruments.id is enforced."""
    # Valid FK: real instrument
    inst = await crud.create_instrument(
        session=session, instrument_in=InstrumentCreate()
    )
    exp = await make_experiment(instrument_id=inst.id)
    assert exp.instrument_id == inst.id

    # FK violation: non-existent instrument_id must fail
    bad_exp = await make_experiment()
    bad_exp.instrument_id = uuid.uuid4()
    session.add(bad_exp)
    with pytest.raises(IntegrityError):
        await session.flush()


# ---------------------------------------------------------------------------
# Soft links: Entry.run_id / Entry.shift_id accept arbitrary UUIDs
# ---------------------------------------------------------------------------


async def test_entry_run_id_soft_link(
    session: AsyncSession, make_entry: Callable[..., Coroutine[Any, Any, Entry]]
) -> None:
    """run_id accepts arbitrary UUID — no FK constraint (external data-catalog)."""
    arbitrary_run_id = uuid.uuid4()
    entry = await make_entry(run_id=arbitrary_run_id)
    assert entry.run_id == arbitrary_run_id


async def test_entry_shift_id_soft_link(
    session: AsyncSession, make_entry: Callable[..., Coroutine[Any, Any, Entry]]
) -> None:
    """shift_id accepts arbitrary UUID — no FK constraint (external data-catalog)."""
    arbitrary_shift_id = uuid.uuid4()
    entry = await make_entry(shift_id=arbitrary_shift_id)
    assert entry.shift_id == arbitrary_shift_id


async def test_experiment_proposal_id_soft_link(
    session: AsyncSession,
    make_experiment: Callable[..., Coroutine[Any, Any, Experiment]],
) -> None:
    """proposal_id accepts arbitrary UUID — no FK constraint (external data-catalog)."""
    arbitrary_proposal_id = uuid.uuid4()
    exp = await make_experiment(proposal_id=arbitrary_proposal_id)
    assert exp.proposal_id == arbitrary_proposal_id
