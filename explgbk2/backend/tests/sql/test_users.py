"""Tests for User CRUD — uses testcontainers PostgreSQL."""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.models.v2.schemas import UserCreate, UserUpdate


def _make_user(session: Session, **kwargs):
    defaults = {
        "username": f"user-{uuid.uuid4()}",
    }
    return crud.create_user(
        session=session,
        user_in=UserCreate(**{**defaults, **kwargs}),
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_create_user(session: Session) -> None:
    user = _make_user(session, display_name="Alice")
    assert user.id is not None
    assert user.display_name == "Alice"
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None


def test_user_username_unique(session: Session) -> None:
    username = f"unique-{uuid.uuid4()}"
    _make_user(session, username=username)
    session.flush()
    with pytest.raises(IntegrityError):
        _make_user(session, username=username)


def test_user_invalid_username_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(username="")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def test_get_user(session: Session) -> None:
    user = _make_user(session)
    fetched = crud.get_user(session=session, user_id=user.id)
    assert fetched is not None
    assert fetched.id == user.id
    missing = crud.get_user(session=session, user_id=uuid.uuid4())
    assert missing is None


def test_get_user_by_username(session: Session) -> None:
    username = f"named-{uuid.uuid4()}"
    _make_user(session, username=username)
    result = crud.get_user_by_username(session=session, username=username)
    assert result is not None
    assert result.username == username
    assert crud.get_user_by_username(session=session, username="no-such-user") is None


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_user(session: Session) -> None:
    user = _make_user(session, display_name="Original")
    updated = crud.update_user(
        session=session,
        user=user,
        user_update=UserUpdate(display_name="Updated"),
    )
    assert updated.display_name == "Updated"


