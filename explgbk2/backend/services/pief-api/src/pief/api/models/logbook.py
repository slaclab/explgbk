from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LogbookBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: str


class LogbookPublic(LogbookBase):
    description: str | None
    created_at: datetime
    updated_at: datetime


class LogbooksPublic(BaseModel):
    data: list[LogbookPublic]
    count: int
