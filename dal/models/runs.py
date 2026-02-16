"""
Models for run documents.

Runs are stored in the `runs` collection of each experiment database.
Run numbers can be int (most cases) or str (CryoEM grid numbers).
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class EditableParam(MongoBaseModel):
    """
    A single user-editable parameter on a run.

    These are parameters that users can set/modify after a run is created,
    as opposed to DAQ-provided params which are immutable.
    """

    value: Any
    modified_by: str
    modified_time: datetime


class Run(MongoBaseModel):
    """
    A run document from the `runs` collection.

    NOTE: `num` is int for most experiments but can be str for CryoEM
    grid-based experiments. The `params` dict keys may contain unicode
    escape characters (U+FF0E for '.', U+FF04 for '$') due to MongoDB
    key restrictions on EPICS PV names.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    num: int | str
    type: str
    begin_time: datetime
    end_time: datetime | None = None
    sample: PyObjectId | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    editable_params: dict[str, EditableParam] = Field(default_factory=dict)
    # Computed fields (added on read, not stored in DB)
    duration: float | None = None
    begin_time_epoch: int | None = None
    end_time_epoch: int | None = None


class RunStartRequest(MongoBaseModel):
    """
    Request model for starting a new run via the DAL.
    """

    experiment_name: str
    run_type: str
    user_specified_run_number: int | None = None
    user_specified_start_time: datetime | None = None
    user_specified_sample: str | None = None
    params: dict[str, Any] | None = None
