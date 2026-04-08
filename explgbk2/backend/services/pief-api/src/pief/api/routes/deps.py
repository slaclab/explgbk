from typing import Annotated

import jwt
from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from pymongo import AsyncMongoClient

from pief.api.core import security
from pief.api.core.config import settings
from pief.api.core.db import get_mongo_client
from pief.api.models.common import TokenPayload
from pief.api.models.user import User

MongoClientDep = Annotated[AsyncMongoClient, Depends(get_mongo_client)]

# auto_error=False so unauthenticated requests fall through to the fallback below
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)

TokenDep = Annotated[str | None, Depends(reusable_oauth2)]


async def get_current_user(token: TokenDep) -> User:
    # No token — return the first superuser as a temporary default until
    # Dex IDP integration is complete.
    if token is None:
        user = await User.find_one(User.is_superuser == True)  # noqa: E712
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Token present — accept without signature verification (blindly trust;
    # signature validation will be added when Dex IDP is integrated).
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=[security.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    try:
        user_id = PydanticObjectId(token_data.sub)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
