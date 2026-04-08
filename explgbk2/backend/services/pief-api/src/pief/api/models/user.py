from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Properties to return via API — id is always required
class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str | None
    created_at: datetime | None
    updated_at: datetime | None


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int


# Fields the current user is allowed to update on their own profile
class UserUpdateMe(BaseModel):
    display_name: str | None = None
