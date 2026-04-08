"""Tests for entry CRUD — uses testcontainers PostgreSQL."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlmodel import Session, select

from pief.logdb import crud
from pief.logdb.tables import (
    Attachment,
    EntryTag,
    ExternalLink,
    LogbookEntry,
)
from pief.logdb.schemas import AttachmentUpdate, EntryCreate, EntryUpdate, TagCreate


def test_create_entry(session: Session, make_entry) -> None:
    entry = make_entry()
    assert entry.id is not None
    assert entry.version == 1
    assert entry.content_type == "text/markdown"
    assert entry.created_at.tzinfo is not None


def test_get_entry(session: Session, make_entry) -> None:
    entry = make_entry()
    fetched = crud.get_entry(session=session, entry_id=entry.id)
    assert fetched is not None
    assert fetched.id == entry.id


def test_timezone_aware_timestamps(session: Session, make_entry) -> None:
    """created_at and occurred_at must round-trip with timezone info."""
    now = datetime.now(UTC)
    entry = make_entry(occurred_at=now)
    assert entry.occurred_at is not None
    assert entry.occurred_at.tzinfo is not None
    assert entry.created_at.tzinfo is not None


def test_naive_datetime_rejected(session: Session, make_entry) -> None:
    """EntryCreate must reject naive (tz-unaware) datetimes for occurred_at."""
    with pytest.raises(ValidationError):
        make_entry(occurred_at=datetime.now())


def test_thread_replies(session: Session, make_entry) -> None:
    """root_id creates a parent-child relationship in the same table."""
    parent = make_entry(title="Parent")
    child = make_entry(title="Reply", root_id=parent.id)
    replies = crud.get_thread_replies(session=session, root_id=parent.id)
    assert len(replies) == 1
    assert replies[0].id == child.id


def test_get_entry_by_legacy_id(session: Session, make_entry) -> None:
    """legacy_id is indexed and can be used for dedup lookups."""
    oid = "507f1f77bcf86cd799439011"
    make_entry(legacy_id=oid)
    result = crud.get_entry_by_legacy_id(session=session, legacy_id=oid)
    assert result is not None
    assert result.legacy_id == oid


def test_retract_entry(session: Session, make_entry) -> None:
    """retract_entry sets retracted_by and retracted_time."""
    entry = make_entry()
    retracting_user = uuid.uuid4()
    retracted = crud.retract_entry(
        session=session, entry=entry, retracted_by=retracting_user
    )
    assert retracted.retracted_by == retracting_user
    assert retracted.retracted_time is not None
    assert retracted.retracted_time.tzinfo is not None


def test_update_entry_bumps_version(session: Session, make_entry) -> None:
    """update_entry bumps version and persists content changes."""
    entry = make_entry()
    assert entry.version == 1
    updated = crud.update_entry(
        session=session,
        entry=entry,
        entry_update=EntryUpdate(title="Revised title"),
    )
    assert updated.version == 2
    assert updated.title == "Revised title"


# ---------------------------------------------------------------------------
# Junction table tests
# ---------------------------------------------------------------------------


def test_create_entry_with_logbook_ids(
    session: Session, make_entry, make_logbook
) -> None:
    """Creating an entry with logbook_ids produces LogbookEntry junction rows."""
    lb1 = make_logbook().id
    lb2 = make_logbook().id
    entry = make_entry(logbook_ids=[lb1, lb2])

    rows = session.exec(
        select(LogbookEntry).where(LogbookEntry.entry_id == entry.id)
    ).all()
    assert len(rows) == 2
    stored_ids = {r.logbook_id for r in rows}
    assert stored_ids == {lb1, lb2}


def test_create_entry_with_tag_ids(session: Session, make_entry) -> None:
    """Creating an entry with tag_ids produces EntryTag junction rows."""
    t1 = crud.create_tag(
        session=session, tag_in=TagCreate(name=f"tag-{uuid.uuid4()}")
    ).id
    t2 = crud.create_tag(
        session=session, tag_in=TagCreate(name=f"tag-{uuid.uuid4()}")
    ).id
    t3 = crud.create_tag(
        session=session, tag_in=TagCreate(name=f"tag-{uuid.uuid4()}")
    ).id
    entry = make_entry(tag_ids=[t1, t2, t3])

    rows = session.exec(select(EntryTag).where(EntryTag.entry_id == entry.id)).all()
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


def test_create_attachment(session: Session, make_entry) -> None:
    """Attachment rows can be created with a FK to an entry."""
    entry = make_entry()

    attachment = Attachment(
        entry_id=entry.id,
        filename="screenshot.png",
        mime_type="image/png",
        size_bytes=12345,
        uri="https://storage.example.com/screenshot.png",
    )
    session.add(attachment)
    session.flush()
    session.refresh(attachment)

    assert attachment.id is not None
    assert attachment.entry_id == entry.id
    assert attachment.created_at.tzinfo is not None

    fetched = session.get(Attachment, attachment.id)
    assert fetched is not None
    assert fetched.filename == "screenshot.png"
    assert fetched.mime_type == "image/png"
    assert fetched.size_bytes == 12345


def test_create_attachment_with_optional_fields(session: Session, make_entry) -> None:
    """Attachment optional fields (name, description, legacy_id, preview_uri) persist."""
    entry = make_entry()

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
    session.flush()
    session.refresh(attachment)

    assert attachment.name == "Screenshot"
    assert attachment.description == "A helpful image"
    assert attachment.legacy_id == "507f1f77bcf86cd799439011"
    assert attachment.preview_uri is not None


# ---------------------------------------------------------------------------
# ExternalLink tests
# ---------------------------------------------------------------------------


def test_create_jira_link(session: Session, make_entry) -> None:
    entry = make_entry()
    link = ExternalLink(
        entry_id=entry.id,
        system="jira",
        uri="https://jira.example.com/browse/DATA-1234",
        meta={"ticket_id": "DATA-1234"},
    )
    session.add(link)
    session.flush()
    assert link.id is not None
    assert link.system == "jira"
    assert link.meta, "meta field must be present here"
    assert link.meta["ticket_id"] == "DATA-1234"


def test_create_slack_link(session: Session, make_entry) -> None:
    entry = make_entry()
    link = ExternalLink(
        entry_id=entry.id,
        system="slack",
        uri="https://slack.com/archives/C123/p456",
        meta={"channel_id": "C123", "message_ts": "p456"},
    )
    session.add(link)
    session.flush()
    assert link.id is not None
    assert link.system == "slack"
    assert link.meta, "meta field must be present here"
    assert link.meta["channel_id"] == "C123"


def test_multiple_external_links_per_entry(session: Session, make_entry) -> None:
    """An entry can have multiple external links of different systems."""
    entry = make_entry()

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
    session.flush()

    links = session.exec(
        select(ExternalLink).where(ExternalLink.entry_id == entry.id)
    ).all()
    assert len(links) == 2
    systems = {lnk.system for lnk in links}
    assert systems == {"jira", "slack"}


def test_external_link_meta_roundtrip(session: Session, make_entry) -> None:
    """meta JSONB column round-trips arbitrary key-value data."""
    entry = make_entry()
    link = ExternalLink(
        entry_id=entry.id,
        system="github",
        uri="https://github.com/org/repo/issues/42",
        meta={"issue_number": "42", "repo": "org/repo"},
    )
    session.add(link)
    session.flush()
    session.refresh(link)
    assert link.meta == {"issue_number": "42", "repo": "org/repo"}


# ---------------------------------------------------------------------------
# Attachment update tests
# ---------------------------------------------------------------------------


def test_attachment_timestamps(session: Session, make_entry) -> None:
    """DTMixin gives Attachment both created_at and updated_at on creation."""
    entry = make_entry()
    attachment = Attachment(
        entry_id=entry.id,
        filename="shot.png",
        mime_type="image/png",
        size_bytes=1024,
        uri="https://storage.example.com/shot.png",
    )
    session.add(attachment)
    session.flush()
    session.refresh(attachment)
    assert attachment.created_at is not None
    assert attachment.created_at.tzinfo is not None
    assert attachment.updated_at is not None
    assert attachment.updated_at.tzinfo is not None


def test_update_attachment(session: Session, make_entry) -> None:
    """update_attachment persists preview_uri and updated_at advances."""
    entry = make_entry()
    attachment = Attachment(
        entry_id=entry.id,
        filename="shot.png",
        mime_type="image/png",
        size_bytes=1024,
        uri="https://storage.example.com/shot.png",
    )
    session.add(attachment)
    session.flush()
    session.refresh(attachment)

    updated = crud.update_attachment(
        session=session,
        attachment=attachment,
        attachment_update=AttachmentUpdate(
            preview_uri="https://storage.example.com/shot_thumb.png"
        ),
    )
    assert updated.preview_uri == "https://storage.example.com/shot_thumb.png"
    assert updated.updated_at is not None
    assert updated.updated_at.tzinfo is not None
