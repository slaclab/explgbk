"""Input/output schemas for v2 models.

Non-table SQLModel classes used for API request validation and CRUD input.
Table definitions live in app.models.v2.db.
"""

from pydantic import AwareDatetime
from sqlmodel import Field, SQLModel

from pief.logdb.base import (
    AttachmentID,
    EntryID,
    InstrumentID,
    LegacyMongoID,
    LogbookID,
    ProposalID,
    RunID,
    ShiftID,
    TagID,
    UserUUID,
)
from pief.models.v1.entries import LogbookType


class LogbookCreate(SQLModel):
    type: LogbookType
    name: str = Field(..., min_length=1)
    description: str | None = None
    legacy_id: LegacyMongoID | None = None


class EntryCreate(SQLModel):
    author_id: UserUUID
    title: str = Field(..., min_length=1)
    content: str
    content_type: str = "text/markdown"
    occurred_at: AwareDatetime | None = None
    legacy_id: LegacyMongoID | None = None
    root_id: EntryID | None = None
    run_id: RunID | None = None
    shift_id: ShiftID | None = None
    logbook_ids: list[LogbookID] = Field(default_factory=list, min_length=1)
    # Zero tags is valid; logbook_ids requires min_length=1 because every entry must belong to at least one logbook
    tag_ids: list[TagID] = Field(default_factory=list)


class EntryUpdate(SQLModel):
    """Fields that can change when editing an entry. Version is bumped automatically."""

    title: str | None = None
    content: str | None = None
    content_type: str | None = None
    occurred_at: AwareDatetime | None = None
    tag_ids: list[TagID] | None = None


class EntryRevisionCreate(SQLModel):
    entry_id: EntryID
    version: int
    # Supplying revised_at is for migration backfill only; production callers should leave it None.
    revised_at: AwareDatetime | None = None
    revised_by: UserUUID
    title: str
    content: str
    content_type: str = "text/markdown"
    occurred_at: AwareDatetime | None = None
    legacy_id: LegacyMongoID | None = None
    tag_ids: list[TagID] = Field(default_factory=list)
    attachment_ids: list[AttachmentID] = Field(default_factory=list)


class ExternalLinkCreate(SQLModel):
    entry_id: EntryID
    system: str = Field(...)
    uri: str
    meta: dict = Field(default_factory=dict)


class AttachmentUpdate(SQLModel):
    """Fields that can be updated on an attachment after async processing."""

    preview_uri: str | None = None
    name: str | None = None
    description: str | None = None


class ExperimentCreate(SQLModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    start_time: AwareDatetime
    end_time: AwareDatetime | None = None
    instrument_id: InstrumentID | None = None
    logbook_id: LogbookID | None = None
    proposal_id: ProposalID | None = None
    meta: dict = Field(default_factory=dict)
    legacy_id: LegacyMongoID | None = None


class ExperimentUpdate(SQLModel):
    """Fields that can change during an experiment's lifecycle."""

    description: str | None = None
    end_time: AwareDatetime | None = None
    logbook_id: LogbookID | None = None
    meta: dict | None = None


class UserCreate(SQLModel):
    username: str = Field(..., min_length=1)
    display_name: str | None = None


class UserUpdate(SQLModel):
    display_name: str | None = None


class TagCreate(SQLModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    color: str | None = None


class TagUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    color: str | None = None


class InstrumentCreate(SQLModel):
    legacy_id: LegacyMongoID | None = None
    meta: dict = Field(default_factory=dict)
