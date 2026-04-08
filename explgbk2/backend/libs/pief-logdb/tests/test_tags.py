"""Tests for Tag CRUD and EntryTag FK enforcement — uses testcontainers PostgreSQL."""

import uuid
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from pief.logdb import crud
from pief.logdb.tables import EntryTag, Tag
from pief.logdb.schemas import TagCreate, TagUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_tag(session: Session, **kwargs: Any) -> Tag:
    defaults = {"name": f"tag-{uuid.uuid4()}"}
    return crud.create_tag(session=session, tag_in=TagCreate(**{**defaults, **kwargs}))


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_create_tag(session: Session) -> None:
    tag = make_tag(session, description="A test tag", color="#ff0000")
    assert tag.id is not None
    assert tag.description == "A test tag"
    assert tag.color == "#ff0000"
    assert tag.created_at.tzinfo is not None
    assert tag.updated_at.tzinfo is not None


def test_tag_name_unique(session: Session) -> None:
    name = f"unique-{uuid.uuid4()}"
    make_tag(session, name=name)
    session.flush()
    with pytest.raises(IntegrityError):
        make_tag(session, name=name)


def test_tag_invalid_name_rejected() -> None:
    with pytest.raises(ValidationError):
        TagCreate(name="")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def test_get_tag(session: Session) -> None:
    tag = make_tag(session)
    fetched = crud.get_tag(session=session, tag_id=tag.id)
    assert fetched is not None
    assert fetched.id == tag.id
    missing = crud.get_tag(session=session, tag_id=uuid.uuid4())
    assert missing is None


def test_get_tag_by_name(session: Session) -> None:
    name = f"named-{uuid.uuid4()}"
    make_tag(session, name=name)
    result = crud.get_tag_by_name(session=session, name=name)
    assert result is not None
    assert result.name == name
    assert crud.get_tag_by_name(session=session, name="no-such-tag") is None


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_tag(session: Session) -> None:
    tag = make_tag(session, description="Original", color=None)
    new_name = f"renamed-{uuid.uuid4()}"
    updated = crud.update_tag(
        session=session,
        tag=tag,
        tag_update=TagUpdate(name=new_name, description="Updated", color="#00ff00"),
    )
    assert updated.name == new_name
    assert updated.description == "Updated"
    assert updated.color == "#00ff00"


def test_update_tag_duplicate_name_raises(session: Session) -> None:
    tag_a = make_tag(session)
    tag_b = make_tag(session)
    session.flush()
    with pytest.raises(IntegrityError):
        crud.update_tag(
            session=session,
            tag=tag_b,
            tag_update=TagUpdate(name=tag_a.name),
        )


# ---------------------------------------------------------------------------
# FK enforcement on EntryTag
# ---------------------------------------------------------------------------


def test_entry_tag_fk_enforced(session: Session) -> None:
    """EntryTag with a bad entry_id raises IntegrityError."""
    tag = make_tag(session)
    bad_entry_tag = EntryTag(entry_id=uuid.uuid4(), tag_id=tag.id)
    session.add(bad_entry_tag)
    with pytest.raises(IntegrityError):
        session.flush()


def test_tag_fk_on_entry_tag_enforced(session: Session, make_entry) -> None:
    """EntryTag with a non-existent tag_id raises IntegrityError."""
    entry = make_entry()
    bad_entry_tag = EntryTag(entry_id=entry.id, tag_id=uuid.uuid4())
    session.add(bad_entry_tag)
    with pytest.raises(IntegrityError):
        session.flush()
