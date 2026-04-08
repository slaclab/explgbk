"""Tests for Experiment CRUD — uses testcontainers PostgreSQL."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.models.v2.schemas import ExperimentCreate, ExperimentUpdate
from tests.sql.helpers import make_experiment as _make_experiment
from tests.sql.helpers import make_logbook as _make_logbook

# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_create_experiment(session: Session) -> None:
    exp = _make_experiment(session, description="A test experiment")
    assert exp.id is not None
    assert exp.description == "A test experiment"
    assert exp.end_time is None
    assert exp.created_at.tzinfo is not None
    assert exp.updated_at.tzinfo is not None
    assert exp.meta == {}


def test_experiment_name_unique(session: Session) -> None:
    name = f"unique-{uuid.uuid4()}"
    _make_experiment(session, name=name)
    session.flush()
    with pytest.raises(IntegrityError):
        _make_experiment(session, name=name)


def test_experiment_invalid_name_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentCreate(name="", start_time=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def test_get_experiment(session: Session) -> None:
    exp = _make_experiment(session)
    fetched = crud.get_experiment(session=session, experiment_id=exp.id)
    assert fetched is not None
    assert fetched.id == exp.id
    missing = crud.get_experiment(session=session, experiment_id=uuid.uuid4())
    assert missing is None


def test_get_experiment_by_name(session: Session) -> None:
    name = f"named-{uuid.uuid4()}"
    _make_experiment(session, name=name)
    result = crud.get_experiment_by_name(session=session, name=name)
    assert result is not None
    assert result.name == name
    assert crud.get_experiment_by_name(session=session, name="no-such-exp") is None


def test_get_experiment_by_legacy_id(session: Session) -> None:
    legacy = f"oldname_{uuid.uuid4().hex[:8]}"
    _make_experiment(session, legacy_id=legacy)
    result = crud.get_experiment_by_legacy_id(session=session, legacy_id=legacy)
    assert result is not None
    assert result.legacy_id == legacy
    assert crud.get_experiment_by_legacy_id(session=session, legacy_id="nope") is None


# ---------------------------------------------------------------------------
# JSONB meta
# ---------------------------------------------------------------------------


def test_experiment_meta_jsonb(session: Session) -> None:
    """meta JSONB round-trips nested v1 metadata."""
    meta = {
        "leader_account": "jdoe",
        "contact_info": "jdoe@slac.stanford.edu",
        "posix_group": "diadaq",
        "is_locked": False,
        "params": {"DATA_PATH": "/reg/d/psdm/dia/diadaq13", "PNR": "LP13"},
    }
    exp = _make_experiment(session, meta=meta)
    assert exp.meta["leader_account"] == "jdoe"
    assert exp.meta["params"]["DATA_PATH"] == "/reg/d/psdm/dia/diadaq13"
    assert exp.meta["is_locked"] is False


# ---------------------------------------------------------------------------
# FK constraint
# ---------------------------------------------------------------------------


def test_experiment_logbook_fk(session: Session) -> None:
    """logbook_id FK to logbooks.id is enforced."""
    lb = _make_logbook(session)
    exp = _make_experiment(session, logbook_id=lb.id)
    assert exp.logbook_id == lb.id

    # FK violation: non-existent logbook_id must fail
    bad_exp = _make_experiment(session)
    bad_exp.logbook_id = uuid.uuid4()
    session.add(bad_exp)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_experiment(session: Session) -> None:
    """update_experiment mutates description, end_time, and meta."""
    exp = _make_experiment(session, description="Original")
    assert exp.end_time is None

    end = datetime.now(UTC)
    updated = crud.update_experiment(
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
