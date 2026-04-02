from fastapi.encoders import jsonable_encoder

from app import crud
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_email


async def test_create_user() -> None:
    email = random_email()
    user_in = UserCreate(email=email)
    user = await crud.create_user(user_create=user_in)
    assert user.email == email


async def test_check_if_user_is_active() -> None:
    email = random_email()
    user_in = UserCreate(email=email)
    user = await crud.create_user(user_create=user_in)
    assert user.is_active is True


async def test_check_if_user_is_active_inactive() -> None:
    email = random_email()
    user_in = UserCreate(email=email, is_active=False)
    user = await crud.create_user(user_create=user_in)
    assert user.is_active is False


async def test_check_if_user_is_superuser() -> None:
    email = random_email()
    user_in = UserCreate(email=email, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    assert user.is_superuser is True


async def test_check_if_user_is_superuser_normal_user() -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)
    assert user.is_superuser is False


async def test_get_user() -> None:
    username = random_email()
    user_in = UserCreate(email=username, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    user_2 = await User.get(user.id)
    assert user_2
    assert user.email == user_2.email
    encoded_user = jsonable_encoder(user)
    encoded_user_2 = jsonable_encoder(user_2)
    assert encoded_user["email"] == encoded_user_2["email"]
    assert encoded_user["is_superuser"] == encoded_user_2["is_superuser"]
    assert encoded_user["_id"] == encoded_user_2["_id"]


async def test_update_user() -> None:
    email = random_email()
    user_in = UserCreate(email=email, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    user_in_update = UserUpdate(full_name="Updated Name", is_superuser=True)
    await crud.update_user(db_user=user, user_in=user_in_update)

    user_2 = await User.get(user.id)
    assert user_2
    assert user.email == user_2.email
    assert user_2.full_name == "Updated Name"
