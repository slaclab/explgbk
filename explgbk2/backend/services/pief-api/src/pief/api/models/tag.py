from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TagPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    color: str | None


class TagsPublic(BaseModel):
    data: list[TagPublic]
    count: int
