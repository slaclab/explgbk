from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import UUID as SAUUID
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import declared_attr
from sqlmodel import (
    AutoString,
    Column,
    DateTime,
    Field,
    Relationship,
    SQLModel,
    Text,
    func,
)

from .base import (
    AttachmentID,
    EntryID,
    EntryRevisionID,
    ExperimentID,
    ExternalLinkID,
    InstrumentID,
    LegacyMongoID,
    LogbookID,
    ProposalID,
    RunID,
    ShiftID,
    TagID,
    UserUUID,
)
from .entries import LogbookType

# Junction tables defined first so main tables can reference them via link_model.


class UpdatedAtMixin:
    @declared_attr
    def updated_at(self):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=True,
        )


class CreatedAtMixin:
    @declared_attr
    def created_at(self):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=True,
        )


class DTMixin(CreatedAtMixin, UpdatedAtMixin):
    """Mixin for created_at and updated_at timestamp columns with timezone awareness."""

    pass


class LogbookEntry(SQLModel, table=True):
    """Junction table: M:N between entries and logbooks."""

    __tablename__ = "logbook_entries"

    entry_id: EntryID = Field(foreign_key="entries.id", primary_key=True)
    logbook_id: LogbookID = Field(foreign_key="logbooks.id", primary_key=True)


class EntryTag(SQLModel, table=True):
    """Junction table: M:N between entries and tags."""

    __tablename__ = "entry_tags"

    entry_id: EntryID = Field(foreign_key="entries.id", primary_key=True)
    tag_id: TagID = Field(foreign_key="tags.id", primary_key=True)


class Tag(DTMixin, SQLModel, table=True):
    """Tag table — labels for logbook entries."""

    __tablename__ = "tags"

    # ---- Primary key ----
    id: TagID = Field(default_factory=uuid4, primary_key=True)

    # ---- Identity ----
    name: str = Field(..., min_length=1, unique=True)
    description: str | None = Field(default=None)
    color: str | None = Field(default=None)  # hex or named color for UI

    # ---- Relationships ----
    entries: list["Entry"] = Relationship(back_populates="tags", link_model=EntryTag)


class Instrument(DTMixin, SQLModel, table=True):
    """Shell table — populated from Debezium/Kafka CDC pipeline via meta JSONB."""

    __tablename__ = "instruments"

    # ---- Primary key ----
    id: InstrumentID = Field(default_factory=uuid4, primary_key=True)

    # ---- Migration bridge ----
    legacy_id: LegacyMongoID | None = Field(default=None, index=True)

    # ---- CDC payload ----
    meta: dict = Field(default_factory=dict, sa_type=JSONB)


class Logbook(DTMixin, SQLModel, table=True):
    """Logbook table — one per experiment or instrument."""

    __tablename__ = "logbooks"

    # ---- Primary key ----
    id: LogbookID = Field(default_factory=uuid4, primary_key=True)

    # ---- Discriminator ----
    # Stored as VARCHAR; LogbookType StrEnum provides Pydantic-level validation.
    # Using AutoString avoids a native PostgreSQL ENUM type (which requires ALTER TYPE for new values).
    type: LogbookType = Field(..., sa_type=AutoString)

    # ---- Identity ----
    name: str = Field(..., min_length=1, unique=True)
    description: str | None = Field(default=None, sa_type=Text)

    # ---- Relationships ----
    entries: list["Entry"] = Relationship(
        back_populates="logbooks", link_model=LogbookEntry
    )


class Experiment(DTMixin, SQLModel, table=True):
    """One row per scientific experiment; maps from v1 {exp_name}.info."""

    __tablename__ = "experiments"

    # ---- Primary key ----
    id: ExperimentID = Field(default_factory=uuid4, primary_key=True)

    # ---- Migration bridge (v1 _id = name.replace(" ", "_")) ----
    legacy_id: LegacyMongoID | None = Field(default=None, index=True)

    # ---- Identity ----
    name: str = Field(..., min_length=1, unique=True)
    description: str | None = Field(default=None, sa_type=Text)

    # ---- Scheduling ----
    start_time: datetime = Field(..., sa_type=DateTime(timezone=True))
    end_time: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    # ---- FKs ----
    instrument_id: InstrumentID | None = Field(
        default=None, foreign_key="instruments.id"
    )
    # soft link; no FK constraint; UUID sourced from external service
    proposal_id: ProposalID | None = Field(default=None)

    # ---- Hard FK to logbooks (1:1; auto-provisioned at creation) ----
    logbook_id: LogbookID | None = Field(default=None, foreign_key="logbooks.id")

    # ---- Catch-all for metadata about the experiment ----
    meta: dict = Field(default_factory=dict, sa_type=JSONB)


class User(DTMixin, SQLModel, table=True):
    """Canonical user identity row."""

    __tablename__ = "users"

    # ---- Primary key ----
    # this is for this database
    id: UserUUID = Field(default_factory=uuid4, primary_key=True)

    # ---- Identity ----
    # this one is the username from our idp
    # we will eventually deal with authn in a more robust way
    # and authz in openfga (planned)
    username: str = Field(..., min_length=1, unique=True, index=True)
    display_name: str | None = Field(default=None)


class Attachment(DTMixin, SQLModel, table=True):
    """Attachment table: 1:N with entries."""

    __tablename__ = "attachments"

    # ---- Primary key ----
    id: AttachmentID = Field(default_factory=uuid4, primary_key=True)

    # ---- FK to entry ----
    entry_id: EntryID = Field(foreign_key="entries.id", index=True)

    # ---- Migration bridge ----
    legacy_id: LegacyMongoID | None = Field(default=None, index=True)

    # ---- Metadata ----
    name: str | None = Field(default=None)
    description: str | None = Field(default=None, sa_type=Text)
    filename: str = Field(...)
    mime_type: str = Field(...)
    size_bytes: int = Field(...)
    uri: str = Field(...)
    preview_uri: str | None = Field(default=None)

    # ---- Relationship ----
    entry: "Entry" = Relationship(back_populates="attachments")


class ExternalLink(SQLModel, table=True):
    """External link table: 1:N with entries."""

    __tablename__ = "external_links"

    # ---- Primary key ----
    id: ExternalLinkID = Field(default_factory=uuid4, primary_key=True)

    # ---- FK to entry ----
    entry_id: EntryID = Field(foreign_key="entries.id", index=True)

    # ---- Discriminator ----
    # this is like slack, jira, github, etc.
    system: str = Field(...)

    # ---- Common ----
    uri: str = Field(...)

    # ---- Flexible metadata ----
    meta: dict | None = Field(default=None, sa_type=JSONB)

    # ---- Relationship ----
    entry: "Entry" = Relationship(back_populates="external_links")


class Entry(SQLModel, table=True):
    """Logbook entry table"""

    __tablename__ = "entries"

    # ---- Primary key ----
    id: EntryID = Field(default_factory=uuid4, primary_key=True)

    # ---- Migration bridge ----
    # v1 MongoDB ObjectId as hex string; used to prevent duplicate imports.
    legacy_id: LegacyMongoID | None = Field(default=None, index=True)

    # ---- Timestamps ----
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )
    # Time the event occurred, as opposed to when it was logged.
    occurred_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    # ---- Content ----
    title: str = Field(..., min_length=1)
    content: str = Field(..., sa_type=Text)
    content_type: str = Field(default="text/markdown")

    # ---- Authorship ----
    author_id: UserUUID = Field(...)

    # ---- Versioning ----
    version: int = Field(default=1)

    # ---- Retraction ----
    retracted_by: UserUUID | None = Field(default=None)
    retracted_time: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    # ---- Threading (self-referencing adjacency list) ----
    root_id: EntryID | None = Field(
        default=None,
        foreign_key="entries.id",
        nullable=True,
    )

    # ---- Soft links (external data-catalog owns Run/Shift lifecycle) ----
    run_id: RunID | None = Field(default=None)
    shift_id: ShiftID | None = Field(default=None)

    # ---- Relationships ----
    # M:N to Logbook via LogbookEntry junction
    logbooks: list[Logbook] = Relationship(
        back_populates="entries", link_model=LogbookEntry
    )
    tags: list["Tag"] = Relationship(back_populates="entries", link_model=EntryTag)
    attachments: list[Attachment] = Relationship(back_populates="entry")
    external_links: list[ExternalLink] = Relationship(back_populates="entry")


class EntryRevision(SQLModel, table=True):
    """Snapshot of an entry's mutable fields at a given version."""

    __tablename__ = "entry_revisions"
    __table_args__ = (
        UniqueConstraint("entry_id", "version", name="uq_entry_revision_version"),
    )

    # ---- Primary key ----
    id: EntryRevisionID = Field(default_factory=uuid4, primary_key=True)

    # ---- Migration bridge ----
    legacy_id: LegacyMongoID | None = Field(default=None, index=True)

    # ---- FK to entry ----
    entry_id: EntryID = Field(foreign_key="entries.id", index=True)

    # ---- Versioning ----
    version: int = Field(...)

    # ---- Authorship ----
    revised_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )
    revised_by: UserUUID = Field(...)

    # ---- Content snapshot ----
    title: str = Field(...)
    content: str = Field(..., sa_type=Text)
    content_type: str = Field(...)
    occurred_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )

    # ---- Snapshot of M:N relationships ----
    tag_ids: list[TagID] = Field(
        default_factory=list, sa_type=ARRAY(SAUUID(as_uuid=True))
    )
    attachment_ids: list[AttachmentID] = Field(
        default_factory=list, sa_type=ARRAY(SAUUID(as_uuid=True))
    )
