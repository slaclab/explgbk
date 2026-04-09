"""Tests for Logbook and EntryRevision CRUD — uses testcontainers PostgreSQL."""

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pief.logdb import crud
from pief.logdb.tables import Entry, Logbook, LogbookEntry
from pief.logdb.schemas import EntryRevisionCreate, LogbookCreate


# ---------------------------------------------------------------------------
# Logbook tests
# ---------------------------------------------------------------------------


async def test_create_logbook(session: AsyncSession) -> None:
    lb = await crud.create_logbook(
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


async def test_logbook_name_unique(session: AsyncSession) -> None:
    name = f"unique-{uuid.uuid4()}"
    await crud.create_logbook(
        session=session, logbook_in=LogbookCreate(type="experiment", name=name)
    )
    await session.flush()
    with pytest.raises(IntegrityError):
        await crud.create_logbook(
            session=session, logbook_in=LogbookCreate(type="instrument", name=name)
        )


def test_logbook_invalid_type_rejected() -> None:
    """LogbookType enum must reject invalid logbook types at the Pydantic layer."""
    with pytest.raises(ValidationError):
        LogbookCreate(type="unknown_type", name="x")


async def test_create_logbook_entry_link(
    session: AsyncSession,
    make_entry: Callable[..., Coroutine[Any, Any, Entry]],
    make_logbook: Callable[..., Coroutine[Any, Any, Logbook]],
) -> None:
    """LogbookEntry FK to logbooks.id is enforced."""
    lb = await crud.create_logbook(
        session=session,
        logbook_in=LogbookCreate(type="instrument", name=f"inst-{uuid.uuid4()}"),
    )
    entry = await make_entry()

    # Manually create a LogbookEntry pointing at our real logbook
    le = LogbookEntry(entry_id=entry.id, logbook_id=lb.id)
    session.add(le)
    await session.flush()
    await session.refresh(le)

    assert le.entry_id == entry.id
    assert le.logbook_id == lb.id

    # FK violation: non-existent logbook_id must fail
    bad_le = LogbookEntry(entry_id=entry.id, logbook_id=uuid.uuid4())
    session.add(bad_le)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_get_logbook(
    session: AsyncSession, make_logbook: Callable[..., Coroutine[Any, Any, Logbook]]
) -> None:
    """get_logbook returns the logbook by id, None for unknown id."""
    lb = await make_logbook()
    fetched = await crud.get_logbook(session=session, logbook_id=lb.id)
    assert fetched is not None
    assert fetched.id == lb.id
    missing = await crud.get_logbook(session=session, logbook_id=uuid.uuid4())
    assert missing is None


# ---------------------------------------------------------------------------
# EntryRevision tests
# ---------------------------------------------------------------------------


async def test_create_entry_revision(
    session: AsyncSession, make_entry: Callable[..., Coroutine[Any, Any, Entry]]
) -> None:
    entry = await make_entry()

    revision = await crud.create_entry_revision(
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


async def test_get_entry_revisions_ordered(
    session: AsyncSession, make_entry: Callable[..., Coroutine[Any, Any, Entry]]
) -> None:
    """get_entry_revisions returns revisions in ascending version order."""
    entry = await make_entry()
    author = uuid.uuid4()

    for v in [3, 1, 2]:
        await crud.create_entry_revision(
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

    revisions = await crud.get_entry_revisions(session=session, entry_id=entry.id)
    assert len(revisions) == 3
    assert [r.version for r in revisions] == [1, 2, 3]


async def test_entry_revision_tag_snapshot(
    session: AsyncSession, make_entry: Callable[..., Coroutine[Any, Any, Entry]]
) -> None:
    """tag_ids are stored and retrievable as a JSON array."""
    entry = await make_entry()
    tag1 = uuid.uuid4()
    tag2 = uuid.uuid4()

    revision = await crud.create_entry_revision(
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

    assert revision.tag_ids is not None
    assert len(revision.tag_ids) == 2
    assert set(revision.tag_ids) == {tag1, tag2}
