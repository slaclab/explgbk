from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from pief.api.core import security
from pief.api.core.config import settings
from pief.api.models.common import TokenPayload
from pief.logdb import crud
from pief.logdb.engine import get_session
from pief.logdb.tables import User

SessionDep = Annotated[Session, Depends(get_session)]

# auto_error=False so unauthenticated requests fall through to the fallback below
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)

TokenDep = Annotated[str | None, Depends(reusable_oauth2)]


def get_current_user(token: TokenDep, session: SessionDep) -> User:
    # No token — return the first superuser as a temporary default until
    # Dex IDP integration is complete.
    if token is None:
        user = crud.get_user_by_username(
            session=session, username=settings.FIRST_SUPERUSER
        )
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

    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    user = crud.get_user_by_username(session=session, username=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
