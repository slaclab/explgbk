from datetime import UTC, datetime

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.common import UTCDatetime


# Shared properties
class ItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(  # pyrefly: ignore[bad-override]
        default=None, min_length=1, max_length=255
    )


# Database model, database collection inferred from Settings.name
class Item(Document, ItemBase):
    created_at: UTCDatetime | None = Field(default_factory=lambda: datetime.now(UTC))
    owner_id: PydanticObjectId

    class Settings:
        name = "items"


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    owner_id: PydanticObjectId
    created_at: UTCDatetime | None = None


class ItemsPublic(BaseModel):
    data: list[ItemPublic]
    count: int
