"""Tests for Instrument shell table, FK hardening, and soft-link fields."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.models.v2.schemas import (
    EntryCreate,
    InstrumentCreate,
)
from tests.sql.helpers import make_experiment as _make_experiment
from tests.sql.helpers import make_logbook as _make_logbook

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(session: Session, **kwargs):
    lb = _make_logbook(session)
    defaults = {
        "author_id": uuid.uuid4(),
        "title": "Shell test entry",
        "content": "content",
        "logbook_ids": [lb.id],
    }
    return crud.create_entry(
        session=session,
        entry_in=EntryCreate(**{**defaults, **kwargs}),
    )


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------


def test_create_instrument(session: Session) -> None:
    meta = {"name": "TMO", "facility": "LCLS"}
    inst = crud.create_instrument(
        session=session,
        instrument_in=InstrumentCreate(meta=meta),
    )
    assert inst.id is not None
    assert inst.meta == meta
    assert inst.created_at.tzinfo is not None


def test_get_instrument(session: Session) -> None:
    inst = crud.create_instrument(session=session, instrument_in=InstrumentCreate())
    fetched = crud.get_instrument(session=session, instrument_id=inst.id)
    assert fetched is not None
    assert fetched.id == inst.id
    missing = crud.get_instrument(session=session, instrument_id=uuid.uuid4())
    assert missing is None


# ---------------------------------------------------------------------------
# FK hardening: Experiment.instrument_id → instruments.id
# ---------------------------------------------------------------------------


def test_experiment_instrument_fk(session: Session) -> None:
    """instrument_id FK to instruments.id is enforced."""
    # Valid FK: real instrument
    inst = crud.create_instrument(session=session, instrument_in=InstrumentCreate())
    exp = _make_experiment(session, instrument_id=inst.id)
    assert exp.instrument_id == inst.id

    # FK violation: non-existent instrument_id must fail
    bad_exp = _make_experiment(session)
    bad_exp.instrument_id = uuid.uuid4()
    session.add(bad_exp)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# Soft links: Entry.run_id / Entry.shift_id accept arbitrary UUIDs
# ---------------------------------------------------------------------------


def test_entry_run_id_soft_link(session: Session) -> None:
    """run_id accepts arbitrary UUID — no FK constraint (external data-catalog)."""
    arbitrary_run_id = uuid.uuid4()
    entry = _make_entry(session, run_id=arbitrary_run_id)
    assert entry.run_id == arbitrary_run_id


def test_entry_shift_id_soft_link(session: Session) -> None:
    """shift_id accepts arbitrary UUID — no FK constraint (external data-catalog)."""
    arbitrary_shift_id = uuid.uuid4()
    entry = _make_entry(session, shift_id=arbitrary_shift_id)
    assert entry.shift_id == arbitrary_shift_id


def test_experiment_proposal_id_soft_link(session: Session) -> None:
    """proposal_id accepts arbitrary UUID — no FK constraint (external data-catalog)."""
    arbitrary_proposal_id = uuid.uuid4()
    exp = _make_experiment(session, proposal_id=arbitrary_proposal_id)
    assert exp.proposal_id == arbitrary_proposal_id
