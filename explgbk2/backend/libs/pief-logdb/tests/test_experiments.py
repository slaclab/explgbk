"""Tests for Experiment CRUD — uses testcontainers PostgreSQL."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from pief.logdb import crud
from pief.logdb.schemas import ExperimentCreate, ExperimentUpdate


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_create_experiment(session: Session, make_experiment) -> None:
    exp = make_experiment(description="A test experiment")
    assert exp.id is not None
    assert exp.description == "A test experiment"
    assert exp.end_time is None
    assert exp.created_at.tzinfo is not None
    assert exp.updated_at.tzinfo is not None
    assert exp.meta == {}


def test_experiment_name_unique(session: Session, make_experiment) -> None:
    name = f"unique-{uuid.uuid4()}"
    make_experiment(name=name)
    session.flush()
    with pytest.raises(IntegrityError):
        make_experiment(name=name)


def test_experiment_invalid_name_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentCreate(name="", start_time=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def test_get_experiment(session: Session, make_experiment) -> None:
    exp = make_experiment()
    fetched = crud.get_experiment(session=session, experiment_id=exp.id)
    assert fetched is not None
    assert fetched.id == exp.id
    missing = crud.get_experiment(session=session, experiment_id=uuid.uuid4())
    assert missing is None


def test_get_experiment_by_name(session: Session, make_experiment) -> None:
    name = f"named-{uuid.uuid4()}"
    make_experiment(name=name)
    result = crud.get_experiment_by_name(session=session, name=name)
    assert result is not None
    assert result.name == name
    assert crud.get_experiment_by_name(session=session, name="no-such-exp") is None


def test_get_experiment_by_legacy_id(session: Session, make_experiment) -> None:
    legacy = f"oldname_{uuid.uuid4().hex[:8]}"
    make_experiment(legacy_id=legacy)
    result = crud.get_experiment_by_legacy_id(session=session, legacy_id=legacy)
    assert result is not None
    assert result.legacy_id == legacy
    assert crud.get_experiment_by_legacy_id(session=session, legacy_id="nope") is None


# ---------------------------------------------------------------------------
# JSONB meta
# ---------------------------------------------------------------------------


def test_experiment_meta_jsonb(session: Session, make_experiment) -> None:
    """meta JSONB round-trips nested v1 metadata."""
    meta = {
        "leader_account": "jdoe",
        "contact_info": "jdoe@slac.stanford.edu",
        "posix_group": "diadaq",
        "is_locked": False,
        "params": {"DATA_PATH": "/reg/d/psdm/dia/diadaq13", "PNR": "LP13"},
    }
    exp = make_experiment(meta=meta)
    assert exp.meta["leader_account"] == "jdoe"
    assert exp.meta["params"]["DATA_PATH"] == "/reg/d/psdm/dia/diadaq13"
    assert exp.meta["is_locked"] is False


# ---------------------------------------------------------------------------
# FK constraint
# ---------------------------------------------------------------------------


def test_experiment_logbook_fk(session: Session, make_experiment, make_logbook) -> None:
    """logbook_id FK to logbooks.id is enforced."""
    lb = make_logbook()
    exp = make_experiment(logbook_id=lb.id)
    assert exp.logbook_id == lb.id

    # FK violation: non-existent logbook_id must fail
    bad_exp = make_experiment()
    bad_exp.logbook_id = uuid.uuid4()
    session.add(bad_exp)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_experiment(session: Session, make_experiment) -> None:
    """update_experiment mutates description, end_time, and meta."""
    exp = make_experiment(description="Original")
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
