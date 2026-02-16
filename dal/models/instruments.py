"""
Models for instrument documents.

Instruments are stored in the `site.instruments` collection.
"""

from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel
from dal.models.roles import Role


class Instrument(MongoBaseModel):
    """
    An instrument document from the `site.instruments` collection.

    NOTE: The `params` dict contains highly variable instrument-specific
    configuration. Common keys include num_stations, operator_uid, tags,
    elog, elog_mailing_lists, questionnaire_ws_url, legacy_cutoff, but
    any key is possible.
    """

    id: str = Field(alias="_id")
    description: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    roles: list[Role] = Field(default_factory=list)


class InstrumentCreate(MongoBaseModel):
    """
    Request model for creating a new instrument.

    The _id field serves as both the unique identifier and short name
    (e.g. "DIA", "CXI", "MFX").
    """

    id: str = Field(alias="_id")
    description: str
    params: dict[str, Any] = Field(default_factory=dict)
