"""Input/output schemas for v2 models.

Pydantic schemas used for API request validation and CRUD input.
Table definitions live in pief.logdb.tables.
"""

from pydantic import AwareDatetime, BaseModel, Field

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


class LogbookCreate(BaseModel):
    type: LogbookType
    name: str = Field(..., min_length=1)
    description: str | None = None


class EntryCreate(BaseModel):
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


class EntryUpdate(BaseModel):
    """Fields that can change when editing an entry. Version is bumped automatically."""

    title: str | None = None
    content: str | None = None
    content_type: str | None = None
    occurred_at: AwareDatetime | None = None
    tag_ids: list[TagID] | None = None


class EntryRevisionCreate(BaseModel):
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


class ExternalLinkCreate(BaseModel):
    entry_id: EntryID
    system: str = Field(...)
    uri: str
    meta: dict = Field(default_factory=dict)


class AttachmentUpdate(BaseModel):
    """Fields that can be updated on an attachment after async processing."""

    preview_uri: str | None = None
    name: str | None = None
    description: str | None = None


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    start_time: AwareDatetime
    end_time: AwareDatetime | None = None
    instrument_id: InstrumentID | None = None
    logbook_id: LogbookID | None = None
    proposal_id: ProposalID | None = None
    meta: dict = Field(default_factory=dict)
    legacy_id: LegacyMongoID | None = None


class ExperimentUpdate(BaseModel):
    """Fields that can change during an experiment's lifecycle."""

    description: str | None = None
    end_time: AwareDatetime | None = None
    logbook_id: LogbookID | None = None
    meta: dict | None = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1)
    display_name: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    color: str | None = None


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    color: str | None = None


class InstrumentCreate(BaseModel):
    legacy_id: LegacyMongoID | None = None
    meta: dict = Field(default_factory=dict)
