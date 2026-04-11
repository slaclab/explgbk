from typing import Any

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.common import UTCDatetime


class ExperimentRole(BaseModel):
    """Parsed from {exp_name}.roles collection."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    app: str
    name: str
    players: list[str] = Field(default_factory=list)


class ExperimentInfo(BaseModel):
    """Parsed from {exp_name}.info collection."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: str = Field(alias="_id")
    name: str
    description: str | None = None
    instrument: str | None = None
    contact_info: str | None = None
    leader_account: str | None = None
    posix_group: str | None = None
    data_collection_software: str | None = None
    params: dict | None = None
    start_time: UTCDatetime | None = None
    end_time: UTCDatetime | None = None
    registration_time: UTCDatetime | None = None


class Run(BaseModel):
    """Parsed from {exp_name}.runs collection."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: PydanticObjectId = Field(alias="_id")
    num: int
    type: str = ""
    begin_time: UTCDatetime
    end_time: UTCDatetime | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    editable_params: dict[str, Any] = Field(default_factory=dict)


class Shift(BaseModel):
    """Parsed from {exp_name}.shifts collection."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: PydanticObjectId = Field(alias="_id")
    name: str
    begin_time: UTCDatetime
    end_time: UTCDatetime | None = None
    leader: str | None = None
    description: str | None = None
    params: dict = Field(default_factory=dict)


class ElogEntry(BaseModel):
    """Parsed from {exp_name}.elog collection."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: PydanticObjectId = Field(alias="_id")
    relevance_time: UTCDatetime
    insert_time: UTCDatetime
    author: str
    content: str
    content_type: str = "TEXT"
