from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import UUID as SAUUID
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pief.logdb.base import (
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
from pief.models.v1.entries import LogbookType


class Base(DeclarativeBase):
    pass


# Junction tables defined first so main tables can reference them via secondary=.


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class DTMixin(CreatedAtMixin, UpdatedAtMixin):
    """Mixin for created_at and updated_at timestamp columns with timezone awareness."""

    pass


class LogbookEntry(Base):
    """Junction table: M:N between entries and logbooks."""

    __tablename__ = "logbook_entries"

    entry_id: Mapped[EntryID] = mapped_column(
        ForeignKey("entries.id"), primary_key=True
    )
    logbook_id: Mapped[LogbookID] = mapped_column(
        ForeignKey("logbooks.id"), primary_key=True
    )


class EntryTag(Base):
    """Junction table: M:N between entries and tags."""

    __tablename__ = "entry_tags"

    entry_id: Mapped[EntryID] = mapped_column(
        ForeignKey("entries.id"), primary_key=True
    )
    tag_id: Mapped[TagID] = mapped_column(ForeignKey("tags.id"), primary_key=True)


class Tag(DTMixin, Base):
    """Tag table — labels for logbook entries."""

    __tablename__ = "tags"

    # ---- Primary key ----
    id: Mapped[TagID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Identity ----
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]
    color: Mapped[str | None]  # hex or named color for UI

    # ---- Relationships ----
    entries: Mapped[list["Entry"]] = relationship(
        back_populates="tags", secondary="entry_tags"
    )


class Instrument(DTMixin, Base):
    """Shell table — populated from Debezium/Kafka CDC pipeline via meta JSONB."""

    __tablename__ = "instruments"

    # ---- Primary key ----
    id: Mapped[InstrumentID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Migration bridge ----
    legacy_id: Mapped[LegacyMongoID | None] = mapped_column(index=True)

    # ---- CDC payload ----
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class Logbook(DTMixin, Base):
    """Logbook table — one per experiment or instrument."""

    __tablename__ = "logbooks"

    # ---- Primary key ----
    id: Mapped[LogbookID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Discriminator ----
    # Stored as VARCHAR; LogbookType StrEnum provides Pydantic-level validation.
    # Using String avoids a native PostgreSQL ENUM type (which requires ALTER TYPE for new values).
    type: Mapped[LogbookType] = mapped_column(String)

    # ---- Identity ----
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    # ---- Relationships ----
    entries: Mapped[list["Entry"]] = relationship(
        back_populates="logbooks", secondary="logbook_entries"
    )


class Experiment(DTMixin, Base):
    """One row per scientific experiment; maps from v1 {exp_name}.info."""

    __tablename__ = "experiments"

    # ---- Primary key ----
    id: Mapped[ExperimentID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Migration bridge (v1 _id = name.replace(" ", "_")) ----
    legacy_id: Mapped[LegacyMongoID | None] = mapped_column(index=True)

    # ---- Identity ----
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    # ---- Scheduling ----
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ---- FKs ----
    instrument_id: Mapped[InstrumentID | None] = mapped_column(
        ForeignKey("instruments.id")
    )
    # soft link; no FK constraint; UUID sourced from external service
    proposal_id: Mapped[ProposalID | None]

    # ---- Hard FK to logbooks (1:1; auto-provisioned at creation) ----
    logbook_id: Mapped[LogbookID | None] = mapped_column(ForeignKey("logbooks.id"))

    # ---- Catch-all for metadata about the experiment ----
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class User(DTMixin, Base):
    """Canonical user identity row."""

    __tablename__ = "users"

    # ---- Primary key ----
    # this is for this database
    id: Mapped[UserUUID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Identity ----
    # this one is the username from our idp
    # we will eventually deal with authn in a more robust way
    # and authz in openfga (planned)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    display_name: Mapped[str | None]


class Attachment(DTMixin, Base):
    """Attachment table: 1:N with entries."""

    __tablename__ = "attachments"

    # ---- Primary key ----
    id: Mapped[AttachmentID] = mapped_column(default=uuid4, primary_key=True)

    # ---- FK to entry ----
    entry_id: Mapped[EntryID] = mapped_column(ForeignKey("entries.id"), index=True)

    # ---- Migration bridge ----
    legacy_id: Mapped[LegacyMongoID | None] = mapped_column(index=True)

    # ---- Metadata ----
    name: Mapped[str | None]
    description: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int]
    uri: Mapped[str]
    preview_uri: Mapped[str | None]

    # ---- Relationship ----
    entry: Mapped["Entry"] = relationship(back_populates="attachments")


class ExternalLink(Base):
    """External link table: 1:N with entries."""

    __tablename__ = "external_links"

    # ---- Primary key ----
    id: Mapped[ExternalLinkID] = mapped_column(default=uuid4, primary_key=True)

    # ---- FK to entry ----
    entry_id: Mapped[EntryID] = mapped_column(ForeignKey("entries.id"), index=True)

    # ---- Discriminator ----
    # this is like slack, jira, github, etc.
    system: Mapped[str]

    # ---- Common ----
    uri: Mapped[str]

    # ---- Flexible metadata ----
    meta: Mapped[dict | None] = mapped_column(JSONB)

    # ---- Relationship ----
    entry: Mapped["Entry"] = relationship(back_populates="external_links")


class Entry(CreatedAtMixin, Base):
    """Logbook entry table"""

    __tablename__ = "entries"

    # ---- Primary key ----
    id: Mapped[EntryID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Migration bridge ----
    # v1 MongoDB ObjectId as hex string; used to prevent duplicate imports.
    legacy_id: Mapped[LegacyMongoID | None] = mapped_column(index=True)

    # ---- Timestamps ----
    # Time the event occurred, as opposed to when it was logged.
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ---- Content ----
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(default="text/markdown")

    # ---- Authorship ----
    author_id: Mapped[UserUUID] = mapped_column(ForeignKey("users.id"))

    # ---- Versioning ----
    version: Mapped[int] = mapped_column(default=1)

    # ---- Retraction ----
    retracted_by: Mapped[UserUUID | None] = mapped_column(ForeignKey("users.id"))
    retracted_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ---- Threading (self-referencing adjacency list) ----
    root_id: Mapped[EntryID | None] = mapped_column(ForeignKey("entries.id"))

    # ---- Soft links (external data-catalog owns Run/Shift lifecycle) ----
    run_id: Mapped[RunID | None]
    shift_id: Mapped[ShiftID | None]

    # ---- Relationships ----
    # M:N to Logbook via LogbookEntry junction
    logbooks: Mapped[list[Logbook]] = relationship(
        back_populates="entries", secondary="logbook_entries"
    )
    tags: Mapped[list["Tag"]] = relationship(
        back_populates="entries", secondary="entry_tags"
    )
    attachments: Mapped[list[Attachment]] = relationship(back_populates="entry")
    external_links: Mapped[list[ExternalLink]] = relationship(back_populates="entry")


class EntryRevision(Base):
    """Snapshot of an entry's mutable fields at a given version."""

    __tablename__ = "entry_revisions"
    __table_args__ = (
        UniqueConstraint("entry_id", "version", name="uq_entry_revision_version"),
    )

    # ---- Primary key ----
    id: Mapped[EntryRevisionID] = mapped_column(default=uuid4, primary_key=True)

    # ---- Migration bridge ----
    legacy_id: Mapped[LegacyMongoID | None] = mapped_column(index=True)

    # ---- FK to entry ----
    entry_id: Mapped[EntryID] = mapped_column(ForeignKey("entries.id"), index=True)

    # ---- Versioning ----
    version: Mapped[int]

    # ---- Authorship ----
    revised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    revised_by: Mapped[UserUUID]

    # ---- Content snapshot ----
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str]
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ---- Snapshot of M:N relationships ----
    tag_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(SAUUID(as_uuid=True)), nullable=True
    )
    attachment_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(SAUUID(as_uuid=True)), nullable=True
    )
