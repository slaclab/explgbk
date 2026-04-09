"""Tests for User CRUD — uses testcontainers PostgreSQL."""

import uuid
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pief.logdb import crud
from pief.logdb.schemas import UserCreate, UserUpdate
from pief.logdb.tables import User


async def make_user(session: AsyncSession, **kwargs: Any) -> User:
    defaults = {
        "username": f"user-{uuid.uuid4()}",
    }
    return await crud.create_user(
        session=session,
        user_in=UserCreate(**{**defaults, **kwargs}),
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


async def test_create_user(session: AsyncSession) -> None:
    user = await make_user(session, display_name="Alice")
    assert user.id is not None
    assert user.display_name == "Alice"
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None


async def test_user_username_unique(session: AsyncSession) -> None:
    username = f"unique-{uuid.uuid4()}"
    await make_user(session, username=username)
    await session.flush()
    with pytest.raises(IntegrityError):
        await make_user(session, username=username)


def test_user_invalid_username_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(username="")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def test_get_user(session: AsyncSession) -> None:
    user = await make_user(session)
    fetched = await crud.get_user(session=session, user_id=user.id)
    assert fetched is not None
    assert fetched.id == user.id
    missing = await crud.get_user(session=session, user_id=uuid.uuid4())
    assert missing is None


async def test_get_user_by_username(session: AsyncSession) -> None:
    username = f"named-{uuid.uuid4()}"
    await make_user(session, username=username)
    result = await crud.get_user_by_username(session=session, username=username)
    assert result is not None
    assert result.username == username
    assert (
        await crud.get_user_by_username(session=session, username="no-such-user")
        is None
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_user(session: AsyncSession) -> None:
    user = await make_user(session, display_name="Original")
    updated = await crud.update_user(
        session=session,
        user=user,
        user_update=UserUpdate(display_name="Updated"),
    )
    assert updated.display_name == "Updated"
