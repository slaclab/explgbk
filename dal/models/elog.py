"""
Models for elog (electronic logbook) entries.

Elog entries are stored in the `elog` collection of each experiment database.
They support threading (root/parent), attachments, tags, cross-posting,
logical deletion, and versioning.
"""

from datetime import datetime

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class ElogAttachment(MongoBaseModel):
    """
    An attachment on an elog entry.

    Attachments are stored inline on the elog document. The actual binary
    data is stored in an image store (GridFS, SeaweedFS, or tar) and
    referenced by URL.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    name: str
    type: str  # MIME type
    url: str  # imagestore URL (e.g. "mongo://...", "http://...", "tar://...")
    preview_url: str | None = None


class ElogEntry(MongoBaseModel):
    """
    A single elog entry document from the `elog` collection.

    Entries can be top-level or replies (indicated by root/parent fields).
    Edited entries are versioned: the original is cloned as a deleted child,
    and the original document is updated in place.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    relevance_time: datetime
    insert_time: datetime
    author: str
    content: str
    content_type: str = "TEXT"
    title: str | None = None
    run_num: int | str | None = None
    shift: str | None = None
    email_to: list[str] | None = None
    tags: list[str] = Field(default_factory=list)
    attachments: list[ElogAttachment] = Field(default_factory=list)
    # Threading
    root: PyObjectId | None = None
    parent: PyObjectId | None = None
    # Cross-posting
    post_to_elogs: list[str] | None = None
    src_expname: str | None = None
    src_id: PyObjectId | None = None
    # JIRA integration
    jira_ticket: str | None = None
    # Logical deletion / versioning
    deleted_by: str | None = None
    deleted_time: datetime | None = None
    previous_version: PyObjectId | None = None


class ElogEntryCreate(MongoBaseModel):
    """
    Request model for creating a new elog entry.

    NOTE: Attachments are handled separately via multipart file upload,
    not as part of this JSON body.
    """

    content: str
    title: str | None = None
    run_num: int | str | None = None
    shift: str | None = None
    email_to: list[str] | None = None
    tags: list[str] = Field(default_factory=list)
    post_to_elogs: list[str] | None = None
