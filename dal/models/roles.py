"""
Models for role documents.

Roles are stored in both per-experiment `roles` collections and the
global `site.roles` collection. They control access via app/name/players.
"""

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class Role(MongoBaseModel):
    """
    A role document controlling access to an application feature.

    Players are a mix of "uid:<username>" entries and POSIX group names.
    Site-level roles additionally have a `privileges` list.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    app: str
    name: str
    players: list[str] = Field(default_factory=list)
    # Only present on site-level roles
    privileges: list[str] | None = None
