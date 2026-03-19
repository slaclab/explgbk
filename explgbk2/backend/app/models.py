from datetime import datetime, timezone
from typing import Annotated

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


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
    created_at: datetime | None = Field(default_factory=get_datetime_utc)

    class Settings:
        name = "users"


# Properties to return via API, id is always required
class UserPublic(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    created_at: datetime | None = None


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int


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
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: PydanticObjectId

    class Settings:
        name = "items"


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    owner_id: PydanticObjectId
    created_at: datetime | None = None


class ItemsPublic(BaseModel):
    data: list[ItemPublic]
    count: int


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
