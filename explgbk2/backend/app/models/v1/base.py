"""
Shared base types for v1 MongoDB document models.

These types handle both:
  - Direct MongoDB reads (BSON ObjectId, naive datetime from pymongo)
  - Debezium CDC extended JSON ({"$oid": "..."}, {"$date": ms})
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict

# ---------------------------------------------------------------------------
# PyObjectId — accepts BSON ObjectId, {"$oid": "..."}, or plain str/bytes
# ---------------------------------------------------------------------------


def _coerce_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict) and "$oid" in v:
        return str(v["$oid"])
    return str(v)


PyObjectId = Annotated[str, BeforeValidator(_coerce_object_id)]


# ---------------------------------------------------------------------------
# MongoInt — accepts plain int or MongoDB Extended JSON {"$numberLong": "..."} /
#            {"$numberInt": ...}
# ---------------------------------------------------------------------------


def _coerce_int(v: Any) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, dict):
        if "$numberLong" in v:
            return int(v["$numberLong"])
        if "$numberInt" in v:
            return int(v["$numberInt"])
    return int(v)  # last-resort cast; will raise on bad input


MongoInt = Annotated[int, BeforeValidator(_coerce_int)]


# ---------------------------------------------------------------------------
# UTCDatetime — accepts Python datetime (possibly naive) or extended JSON
# ---------------------------------------------------------------------------


def _coerce_datetime(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, dict):
        raw = v.get("$date")
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw / 1000, tz=UTC)
        if isinstance(raw, dict) and "$numberLong" in raw:
            return datetime.fromtimestamp(int(raw["$numberLong"]) / 1000, tz=UTC)
    raise ValueError(f"Cannot parse datetime from {v!r}")


def _force_utc(v: datetime) -> datetime:
    """Re-attach UTC timezone to naive datetimes returned by pymongo."""
    if v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


UTCDatetime = Annotated[
    datetime, BeforeValidator(_coerce_datetime), AfterValidator(_force_utc)
]


# ---------------------------------------------------------------------------
# Base model config: accept both Python field names and MongoDB alias names
# ---------------------------------------------------------------------------


class MongoModel(BaseModel):
    """
    Base class for all MongoDB document models.
    Supports both field name access and MongoDB field aliases (e.g. _id).
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
