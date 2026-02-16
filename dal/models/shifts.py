"""
Models for shift documents.

Shifts are stored in the `shifts` collection of each experiment database.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class Shift(MongoBaseModel):
    """
    A shift document from the `shifts` collection.

    Shifts have unique names and non-overlapping time ranges within
    an experiment. The `logical_end_time` is computed on read (it's
    the start of the next shift, or now if this is the latest shift).
    """

    id: PyObjectId | None = Field(None, alias="_id")
    name: str
    begin_time: datetime
    end_time: datetime | None = None
    leader: str
    description: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    # Computed on read, not stored
    logical_end_time: datetime | None = None


class ShiftCreate(MongoBaseModel):
    """
    Request model for creating a new shift.
    """

    name: str
    leader: str
    begin_time: datetime
    description: str = ""
    end_time: datetime | None = None
    params: dict[str, Any] = Field(default_factory=dict)
