from app import crud
from app.core import security
from app.models import User, UserCreate
from tests.utils.utils import random_email


async def user_authentication_headers(*, email: str) -> dict[str, str]:
    user = await crud.get_user_by_email(email=email)
    if not user:
        raise ValueError(f"User {email} not found")
    token = security.create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


async def create_random_user() -> User:
    email = random_email()
    user_in = UserCreate(email=email)
    return await crud.create_user(user_create=user_in)


async def authentication_token_from_email(*, email: str) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    user = await crud.get_user_by_email(email=email)
    if not user:
        user_in_create = UserCreate(email=email)
        await crud.create_user(user_create=user_in_create)

    return await user_authentication_headers(email=email)
