from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pief.api.models.logbook import LogbookBase
from pief.api.models.tag import TagPublic


class AttachmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    filename: str
    mime_type: str
    size_bytes: int
    uri: str
    preview_uri: str | None


class ExternalLinkPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system: str
    uri: str
    meta: dict | None


class EntryCreate(BaseModel):
    username: str
    title: str = Field(..., min_length=1)
    content: str
    content_type: str = "text/markdown"
    occurred_at: datetime | None = None
    logbook_ids: set[UUID] = Field(..., min_length=1)
    tag_ids: set[UUID] = Field(default_factory=set)
    root_id: UUID | None = None
    run_id: UUID | None = None
    shift_id: UUID | None = None
    email_to: list[str] = Field(default_factory=list)
    jira_project: str | None = None
    slack_channel: str | None = None


class EntryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tag_ids: set[UUID] | None = None
    occurred_at: datetime | None = None


class EntryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    content_type: str
    author_id: UUID
    version: int
    created_at: datetime
    occurred_at: datetime | None
    root_id: UUID | None
    retracted_by: UUID | None
    retracted_time: datetime | None
    run_id: UUID | None
    shift_id: UUID | None
    logbooks: list[LogbookBase]
    tags: list[TagPublic]
    attachments: list[AttachmentPublic]
    external_links: list[ExternalLinkPublic]


class EntriesPublic(BaseModel):
    data: list[EntryPublic]
    count: int


class EntryRevisionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_id: UUID
    version: int
    revised_at: datetime
    revised_by: UUID
    title: str
    content: str
    content_type: str
    tag_ids: list[UUID] | None
    attachment_ids: list[UUID] | None
