"""
Models for file catalog documents.

Files are stored in the `file_catalog` collection of each experiment database.
They track data files produced by runs and their availability at different
storage locations (e.g. SLAC, NERSC).
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class FileLocation(MongoBaseModel):
    """
    Availability info for a file at a specific storage location.
    """

    asof: datetime


class FileCatalogEntry(MongoBaseModel):
    """
    A file catalog entry from the `file_catalog` collection.

    NOTE: `run_num` can be int or str (CryoEM grids).
    The combination of (path, run_num) is unique within an experiment.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    path: str
    run_num: int | str
    size: int | None = None
    checksum: str | None = None
    create_timestamp: datetime | None = None
    modify_timestamp: datetime | None = None
    locations: dict[str, FileLocation] = Field(default_factory=dict)


class FileRegistration(MongoBaseModel):
    """
    Request model for registering a file (single or batch).

    At minimum, `path` is required. If `run_num` is not provided, the
    current run number is attached automatically by the service layer.

    NOTE: The `locations` field here uses dict[str, Any] rather than
    dict[str, FileLocation] because the service layer may pass partial
    location data that gets merged into the existing document.
    """

    path: str
    run_num: int | str | None = None
    size: int | None = None
    checksum: str | None = None
    create_timestamp: datetime | None = None
    modify_timestamp: datetime | None = None
    locations: dict[str, Any] | None = None
