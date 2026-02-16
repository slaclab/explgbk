"""
Models for experiment documents.

Experiments are stored one-per-database in MongoDB. The experiment metadata
lives in the `info` collection as a single document.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class ExperimentParams(MongoBaseModel):
    """
    Arbitrary key/value parameters stored on an experiment.

    NOTE: The keys and values here are highly variable across experiments.
    Common keys include DATA_PATH, PNR (proposal number), dm_locations,
    run_period, xpost_elogs, questionnaire_ws_url, but any key is possible.
    """

    data_path: str | None = Field(None, alias="DATA_PATH")
    pnr: str | None = Field(None, alias="PNR")
    dm_locations: str | None = None
    run_period: str | None = None
    xpost_elogs: str | None = None
    questionnaire_ws_url: str | None = None

    model_config = {"extra": "allow"}


class ExperimentInfo(MongoBaseModel):
    """
    The single metadata document in an experiment's `info` collection.

    Each experiment has its own MongoDB database, and the `info` collection
    contains exactly one document with this shape.
    """

    id: str = Field(alias="_id")
    name: str
    description: str = ""
    instrument: str
    start_time: datetime
    end_time: datetime
    leader_account: str
    contact_info: str
    registration_time: datetime | None = None
    posix_group: str | None = None
    is_locked: bool = False
    latest_setup: PyObjectId | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    # NOTE: initial_sample is only present at creation time and may not
    # persist on the stored document after the sample is set via `current`.
    initial_sample: str | None = None


class ExperimentRegistration(MongoBaseModel):
    """
    Request model for registering a new experiment.

    Used when POST-ing to the experiment registration endpoint.
    """

    instrument: str
    start_time: datetime
    end_time: datetime
    leader_account: str
    contact_info: str
    description: str = ""
    posix_group: str | None = None
    initial_sample: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ExperimentClone(MongoBaseModel):
    """
    Request model for cloning an experiment with new time bounds.
    """

    start_time: datetime
    end_time: datetime


class ExperimentSwitch(MongoBaseModel):
    """
    Document in the `site.experiment_switch` collection tracking which
    experiment is active on a given instrument/station.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    experiment_name: str
    instrument: str
    station: int = 0
    switch_time: datetime
    requestor_uid: str
    is_standby: bool = False
