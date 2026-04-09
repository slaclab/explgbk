"""Tests for entry CRUD — uses testcontainers PostgreSQL."""

import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from pief.logdb import crud
from pief.logdb.tables import (
    Attachment,
    Entry,
    EntryTag,
    ExternalLink,
    Logbook,
    LogbookEntry,
    User,
)
from pief.logdb.schemas import AttachmentUpdate, EntryCreate, EntryUpdate, TagCreate

MakeEntryType = Callable[..., Coroutine[Any, Any, Entry]]


async def test_create_entry(session: AsyncSession, make_entry: MakeEntryType) -> None:
    entry = await make_entry()
    assert entry.id is not None
    assert entry.version == 1
    assert entry.content_type == "text/markdown"
    assert entry.created_at.tzinfo is not None


async def test_get_entry(session: AsyncSession, make_entry: MakeEntryType) -> None:
    entry = await make_entry()
    fetched = await crud.get_entry(session=session, entry_id=entry.id)
    assert fetched is not None
    assert fetched.id == entry.id


async def test_timezone_aware_timestamps(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """created_at and occurred_at must round-trip with timezone info."""
    now = datetime.now(UTC)
    entry = await make_entry(occurred_at=now)
    assert entry.occurred_at is not None
    assert entry.occurred_at.tzinfo is not None
    assert entry.created_at.tzinfo is not None


async def test_naive_datetime_rejected(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """EntryCreate must reject naive (tz-unaware) datetimes for occurred_at."""
    with pytest.raises(ValidationError):
        await make_entry(occurred_at=datetime.now())


async def test_thread_replies(session: AsyncSession, make_entry: MakeEntryType) -> None:
    """root_id creates a parent-child relationship in the same table."""
    parent = await make_entry(title="Parent")
    child = await make_entry(title="Reply", root_id=parent.id)
    replies = await crud.get_thread_replies(session=session, root_id=parent.id)
    assert len(replies) == 1
    assert replies[0].id == child.id


async def test_get_entry_by_legacy_id(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """legacy_id is indexed and can be used for dedup lookups."""
    oid = "507f1f77bcf86cd799439011"
    await make_entry(legacy_id=oid)
    result = await crud.get_entry_by_legacy_id(session=session, legacy_id=oid)
    assert result is not None
    assert result.legacy_id == oid


async def test_retract_entry(
    session: AsyncSession,
    make_entry: MakeEntryType,
    make_user: Callable[..., Coroutine[Any, Any, User]],
) -> None:
    """retract_entry sets retracted_by and retracted_time."""
    entry = await make_entry()
    retracting_user = await make_user()
    retracted = await crud.retract_entry(
        session=session, entry=entry, retracted_by=retracting_user.id
    )
    assert retracted.retracted_by == retracting_user.id
    assert retracted.retracted_time is not None
    assert retracted.retracted_time.tzinfo is not None


async def test_update_entry_bumps_version(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """update_entry bumps version and persists content changes."""
    entry = await make_entry()
    assert entry.version == 1
    updated = await crud.update_entry(
        session=session,
        entry=entry,
        entry_update=EntryUpdate(title="Revised title"),
    )
    assert updated.version == 2
    assert updated.title == "Revised title"


# ---------------------------------------------------------------------------
# Junction table tests
# ---------------------------------------------------------------------------


async def test_create_entry_with_logbook_ids(
    session: AsyncSession,
    make_entry: MakeEntryType,
    make_logbook: Callable[..., Coroutine[Any, Any, Logbook]],
) -> None:
    """Creating an entry with logbook_ids produces LogbookEntry junction rows."""
    lb1 = (await make_logbook()).id
    lb2 = (await make_logbook()).id
    entry = await make_entry(logbook_ids=[lb1, lb2])

    rows = (
        (
            await session.execute(
                select(LogbookEntry).where(col(LogbookEntry.entry_id) == entry.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    stored_ids = {r.logbook_id for r in rows}
    assert stored_ids == {lb1, lb2}


async def test_create_entry_with_tag_ids(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """Creating an entry with tag_ids produces EntryTag junction rows."""
    t1 = (
        await crud.create_tag(
            session=session, tag_in=TagCreate(name=f"tag-{uuid.uuid4()}")
        )
    ).id
    t2 = (
        await crud.create_tag(
            session=session, tag_in=TagCreate(name=f"tag-{uuid.uuid4()}")
        )
    ).id
    t3 = (
        await crud.create_tag(
            session=session, tag_in=TagCreate(name=f"tag-{uuid.uuid4()}")
        )
    ).id
    entry = await make_entry(tag_ids=[t1, t2, t3])

    rows = (
        (
            await session.execute(
                select(EntryTag).where(col(EntryTag.entry_id) == entry.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 3
    stored_ids = {r.tag_id for r in rows}
    assert stored_ids == {t1, t2, t3}


def test_empty_logbook_ids_rejected() -> None:
    """EntryCreate must reject an empty logbook_ids list (min_length=1)."""
    with pytest.raises(ValidationError):
        EntryCreate(
            author_id=uuid.uuid4(),
            title="Test entry",
            content="Some content",
            logbook_ids=[],
        )


# ---------------------------------------------------------------------------
# Attachment tests
# ---------------------------------------------------------------------------


async def test_create_attachment(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """Attachment rows can be created with a FK to an entry."""
    entry = await make_entry()

    attachment = Attachment(
        entry_id=entry.id,
        filename="screenshot.png",
        mime_type="image/png",
        size_bytes=12345,
        uri="https://storage.example.com/screenshot.png",
    )
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    assert attachment.id is not None
    assert attachment.entry_id == entry.id
    assert attachment.created_at.tzinfo is not None

    fetched = await session.get(Attachment, attachment.id)
    assert fetched is not None
    assert fetched.filename == "screenshot.png"
    assert fetched.mime_type == "image/png"
    assert fetched.size_bytes == 12345


async def test_create_attachment_with_optional_fields(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """Attachment optional fields (name, description, legacy_id, preview_uri) persist."""
    entry = await make_entry()

    attachment = Attachment(
        entry_id=entry.id,
        legacy_id="507f1f77bcf86cd799439011",
        name="Screenshot",
        description="A helpful image",
        filename="screenshot.png",
        mime_type="image/png",
        size_bytes=4096,
        uri="https://storage.example.com/screenshot.png",
        preview_uri="https://storage.example.com/screenshot_thumb.png",
    )
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    assert attachment.name == "Screenshot"
    assert attachment.description == "A helpful image"
    assert attachment.legacy_id == "507f1f77bcf86cd799439011"
    assert attachment.preview_uri is not None


# ---------------------------------------------------------------------------
# ExternalLink tests
# ---------------------------------------------------------------------------


async def test_create_jira_link(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    entry = await make_entry()
    link = ExternalLink(
        entry_id=entry.id,
        system="jira",
        uri="https://jira.example.com/browse/DATA-1234",
        meta={"ticket_id": "DATA-1234"},
    )
    session.add(link)
    await session.flush()
    assert link.id is not None
    assert link.system == "jira"
    assert link.meta, "meta field must be present here"
    assert link.meta["ticket_id"] == "DATA-1234"


async def test_create_slack_link(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    entry = await make_entry()
    link = ExternalLink(
        entry_id=entry.id,
        system="slack",
        uri="https://slack.com/archives/C123/p456",
        meta={"channel_id": "C123", "message_ts": "p456"},
    )
    session.add(link)
    await session.flush()
    assert link.id is not None
    assert link.system == "slack"
    assert link.meta, "meta field must be present here"
    assert link.meta["channel_id"] == "C123"


async def test_multiple_external_links_per_entry(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """An entry can have multiple external links of different systems."""
    entry = await make_entry()

    jira_link = ExternalLink(
        entry_id=entry.id,
        system="jira",
        uri="https://jira.example.com/browse/DATA-42",
        meta={"ticket_id": "DATA-42"},
    )
    slack_link = ExternalLink(
        entry_id=entry.id,
        system="slack",
        uri="https://slack.example.com/archives/C99/p9999",
        meta={"channel_id": "C1", "message_ts": "ts1"},
    )
    session.add(jira_link)
    session.add(slack_link)
    await session.flush()

    links = (
        (
            await session.execute(
                select(ExternalLink).where(col(ExternalLink.entry_id) == entry.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 2
    systems = {lnk.system for lnk in links}
    assert systems == {"jira", "slack"}


async def test_external_link_meta_roundtrip(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """meta JSONB column round-trips arbitrary key-value data."""
    entry = await make_entry()
    link = ExternalLink(
        entry_id=entry.id,
        system="github",
        uri="https://github.com/org/repo/issues/42",
        meta={"issue_number": "42", "repo": "org/repo"},
    )
    session.add(link)
    await session.flush()
    await session.refresh(link)
    assert link.meta == {"issue_number": "42", "repo": "org/repo"}


# ---------------------------------------------------------------------------
# Attachment update tests
# ---------------------------------------------------------------------------


async def test_attachment_timestamps(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """DTMixin gives Attachment both created_at and updated_at on creation."""
    entry = await make_entry()
    attachment = Attachment(
        entry_id=entry.id,
        filename="shot.png",
        mime_type="image/png",
        size_bytes=1024,
        uri="https://storage.example.com/shot.png",
    )
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)
    assert attachment.created_at is not None
    assert attachment.created_at.tzinfo is not None
    assert attachment.updated_at is not None
    assert attachment.updated_at.tzinfo is not None


async def test_update_attachment(
    session: AsyncSession, make_entry: MakeEntryType
) -> None:
    """update_attachment persists preview_uri and updated_at advances."""
    entry = await make_entry()
    attachment = Attachment(
        entry_id=entry.id,
        filename="shot.png",
        mime_type="image/png",
        size_bytes=1024,
        uri="https://storage.example.com/shot.png",
    )
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)

    updated = await crud.update_attachment(
        session=session,
        attachment=attachment,
        attachment_update=AttachmentUpdate(
            preview_uri="https://storage.example.com/shot_thumb.png"
        ),
    )
    assert updated.preview_uri == "https://storage.example.com/shot_thumb.png"
    assert updated.updated_at is not None
    assert updated.updated_at.tzinfo is not None
