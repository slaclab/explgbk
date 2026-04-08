"""Tests for Logbook and EntryRevision CRUD — uses testcontainers PostgreSQL."""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from pief.logdb import crud
from pief.logdb.tables import LogbookEntry
from pief.logdb.schemas import EntryRevisionCreate, LogbookCreate


# ---------------------------------------------------------------------------
# Logbook tests
# ---------------------------------------------------------------------------


def test_create_logbook(session: Session) -> None:
    lb = crud.create_logbook(
        session=session,
        logbook_in=LogbookCreate(
            type="experiment",
            name="my-experiment-logbook",
            description="A test logbook",
        ),
    )
    assert lb.id is not None
    assert lb.name == "my-experiment-logbook"
    assert lb.type == "experiment"
    assert lb.description == "A test logbook"
    assert lb.created_at.tzinfo is not None
    assert lb.updated_at.tzinfo is not None


def test_logbook_name_unique(session: Session) -> None:
    name = f"unique-{uuid.uuid4()}"
    crud.create_logbook(
        session=session, logbook_in=LogbookCreate(type="experiment", name=name)
    )
    session.flush()
    with pytest.raises(IntegrityError):
        crud.create_logbook(
            session=session, logbook_in=LogbookCreate(type="instrument", name=name)
        )


def test_logbook_invalid_type_rejected() -> None:
    """LogbookType enum must reject invalid logbook types at the Pydantic layer."""
    with pytest.raises(ValidationError):
        LogbookCreate(type="unknown_type", name="x")


def test_create_logbook_entry_link(session: Session, make_entry, make_logbook) -> None:
    """LogbookEntry FK to logbooks.id is enforced."""
    lb = crud.create_logbook(
        session=session,
        logbook_in=LogbookCreate(type="instrument", name=f"inst-{uuid.uuid4()}"),
    )
    entry = make_entry()

    # Manually create a LogbookEntry pointing at our real logbook
    le = LogbookEntry(entry_id=entry.id, logbook_id=lb.id)
    session.add(le)
    session.flush()
    session.refresh(le)

    assert le.entry_id == entry.id
    assert le.logbook_id == lb.id

    # FK violation: non-existent logbook_id must fail
    bad_le = LogbookEntry(entry_id=entry.id, logbook_id=uuid.uuid4())
    session.add(bad_le)
    with pytest.raises(IntegrityError):
        session.flush()


def test_get_logbook(session: Session, make_logbook) -> None:
    """get_logbook returns the logbook by id, None for unknown id."""
    lb = make_logbook()
    fetched = crud.get_logbook(session=session, logbook_id=lb.id)
    assert fetched is not None
    assert fetched.id == lb.id
    missing = crud.get_logbook(session=session, logbook_id=uuid.uuid4())
    assert missing is None


# ---------------------------------------------------------------------------
# EntryRevision tests
# ---------------------------------------------------------------------------


def test_create_entry_revision(session: Session, make_entry) -> None:
    entry = make_entry()

    revision = crud.create_entry_revision(
        session=session,
        revision_in=EntryRevisionCreate(
            entry_id=entry.id,
            version=1,
            revised_by=uuid.uuid4(),
            title="Original title",
            content="Original content",
            content_type="text/markdown",
        ),
    )
    assert revision.id is not None
    assert revision.entry_id == entry.id
    assert revision.version == 1
    assert revision.title == "Original title"
    assert revision.revised_at.tzinfo is not None


def test_get_entry_revisions_ordered(session: Session, make_entry) -> None:
    """get_entry_revisions returns revisions in ascending version order."""
    entry = make_entry()
    author = uuid.uuid4()

    for v in [3, 1, 2]:
        crud.create_entry_revision(
            session=session,
            revision_in=EntryRevisionCreate(
                entry_id=entry.id,
                version=v,
                revised_by=author,
                title=f"Title v{v}",
                content=f"Content v{v}",
                content_type="text/markdown",
            ),
        )

    revisions = crud.get_entry_revisions(session=session, entry_id=entry.id)
    assert len(revisions) == 3
    assert [r.version for r in revisions] == [1, 2, 3]


def test_entry_revision_tag_snapshot(session: Session, make_entry) -> None:
    """tag_ids are stored and retrievable as a JSON array."""
    entry = make_entry()
    tag1 = uuid.uuid4()
    tag2 = uuid.uuid4()

    revision = crud.create_entry_revision(
        session=session,
        revision_in=EntryRevisionCreate(
            entry_id=entry.id,
            version=1,
            revised_by=uuid.uuid4(),
            title="Tagged entry",
            content="Body",
            content_type="text/plain",
            tag_ids=[tag1, tag2],
        ),
    )

    assert len(revision.tag_ids) == 2
    assert set(revision.tag_ids) == {tag1, tag2}
