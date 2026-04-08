from datetime import UTC, datetime
from typing import Annotated

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from pief.api.models.common import UTCDatetime


# Shared properties
class UserBase(BaseModel):
    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    pass


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(  # pyrefly: ignore[bad-override]
        default=None, max_length=255
    )
    is_active: bool | None = None  # pyrefly: ignore[bad-override]
    is_superuser: bool | None = None  # pyrefly: ignore[bad-override]
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdateMe(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


# Database model, database collection inferred from Settings.name
class User(Document, UserBase):
    email: Annotated[EmailStr, Indexed(unique=True)] = Field(max_length=255)
    created_at: UTCDatetime | None = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "users"


# Properties to return via API, id is always required
class UserPublic(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    created_at: UTCDatetime | None = None


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int
