"""Tests for Tag CRUD and EntryTag FK enforcement — uses testcontainers PostgreSQL."""

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pief.logdb import crud
from pief.logdb.tables import Entry, EntryTag, Tag
from pief.logdb.schemas import TagCreate, TagUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_tag(session: AsyncSession, **kwargs: Any) -> Tag:
    defaults = {"name": f"tag-{uuid.uuid4()}"}
    return await crud.create_tag(
        session=session, tag_in=TagCreate(**{**defaults, **kwargs})
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


async def test_create_tag(session: AsyncSession) -> None:
    tag = await make_tag(session, description="A test tag", color="#ff0000")
    assert tag.id is not None
    assert tag.description == "A test tag"
    assert tag.color == "#ff0000"
    assert tag.created_at.tzinfo is not None
    assert tag.updated_at.tzinfo is not None


async def test_tag_name_unique(session: AsyncSession) -> None:
    name = f"unique-{uuid.uuid4()}"
    await make_tag(session, name=name)
    await session.flush()
    with pytest.raises(IntegrityError):
        await make_tag(session, name=name)


def test_tag_invalid_name_rejected() -> None:
    with pytest.raises(ValidationError):
        TagCreate(name="")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def test_get_tag(session: AsyncSession) -> None:
    tag = await make_tag(session)
    fetched = await crud.get_tag(session=session, tag_id=tag.id)
    assert fetched is not None
    assert fetched.id == tag.id
    missing = await crud.get_tag(session=session, tag_id=uuid.uuid4())
    assert missing is None


async def test_get_tag_by_name(session: AsyncSession) -> None:
    name = f"named-{uuid.uuid4()}"
    await make_tag(session, name=name)
    result = await crud.get_tag_by_name(session=session, name=name)
    assert result is not None
    assert result.name == name
    assert await crud.get_tag_by_name(session=session, name="no-such-tag") is None


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_tag(session: AsyncSession) -> None:
    tag = await make_tag(session, description="Original", color=None)
    new_name = f"renamed-{uuid.uuid4()}"
    updated = await crud.update_tag(
        session=session,
        tag=tag,
        tag_update=TagUpdate(name=new_name, description="Updated", color="#00ff00"),
    )
    assert updated.name == new_name
    assert updated.description == "Updated"
    assert updated.color == "#00ff00"


async def test_update_tag_duplicate_name_raises(session: AsyncSession) -> None:
    tag_a = await make_tag(session)
    tag_b = await make_tag(session)
    await session.flush()
    with pytest.raises(IntegrityError):
        await crud.update_tag(
            session=session,
            tag=tag_b,
            tag_update=TagUpdate(name=tag_a.name),
        )


# ---------------------------------------------------------------------------
# FK enforcement on EntryTag
# ---------------------------------------------------------------------------


async def test_entry_tag_fk_enforced(session: AsyncSession) -> None:
    """EntryTag with a bad entry_id raises IntegrityError."""
    tag = await make_tag(session)
    bad_entry_tag = EntryTag(entry_id=uuid.uuid4(), tag_id=tag.id)
    session.add(bad_entry_tag)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_tag_fk_on_entry_tag_enforced(
    session: AsyncSession, make_entry: Callable[..., Coroutine[Any, Any, Entry]]
) -> None:
    """EntryTag with a non-existent tag_id raises IntegrityError."""
    entry = await make_entry()
    bad_entry_tag = EntryTag(entry_id=entry.id, tag_id=uuid.uuid4())
    session.add(bad_entry_tag)
    with pytest.raises(IntegrityError):
        await session.flush()
