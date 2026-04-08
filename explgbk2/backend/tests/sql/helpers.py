"""Shared helper functions for tests/sql/."""

import uuid
from datetime import UTC, datetime

from sqlmodel import Session

from app import crud
from app.models.v2.schemas import EntryCreate, ExperimentCreate, LogbookCreate


def make_logbook(session: Session):
    return crud.create_logbook(
        session=session,
        logbook_in=LogbookCreate(type="experiment", name=f"lb-{uuid.uuid4()}"),
    )


def make_entry(session: Session, **kwargs):
    lb = make_logbook(session)
    defaults = {
        "author_id": uuid.uuid4(),
        "title": "Test entry",
        "content": "Some content",
        "logbook_ids": [lb.id],
    }
    return crud.create_entry(
        session=session, entry_in=EntryCreate(**{**defaults, **kwargs})
    )


def make_experiment(session: Session, **kwargs):
    defaults = {
        "name": f"exp-{uuid.uuid4()}",
        "start_time": datetime.now(UTC),
    }
    return crud.create_experiment(
        session=session,
        experiment_in=ExperimentCreate(**{**defaults, **kwargs}),
    )
