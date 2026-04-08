from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel


def _force_utc(v: datetime) -> datetime:
    """Re-attach UTC timezone to naive datetimes returned by MongoDB."""
    if v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# Use this for all datetime fields that come from MongoDB.
# MongoDB strips timezone info on read; this ensures responses always
# serialize with a 'Z' suffix so the frontend can parse them correctly.
UTCDatetime = Annotated[datetime, AfterValidator(_force_utc)]


# Generic message
class Message(BaseModel):
    message: str


# JSON payload containing access token
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(BaseModel):
    sub: str | None = None
