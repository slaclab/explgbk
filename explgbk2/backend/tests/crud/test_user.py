from fastapi.encoders import jsonable_encoder
from pwdlib.hashers.bcrypt import BcryptHasher

from app import crud
from app.core.security import verify_password
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_email, random_lower_string


async def test_create_user() -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await crud.create_user(user_create=user_in)
    assert user.email == email
    assert hasattr(user, "hashed_password")


async def test_authenticate_user() -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await crud.create_user(user_create=user_in)
    authenticated_user = await crud.authenticate(email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


async def test_not_authenticate_user() -> None:
    email = random_email()
    password = random_lower_string()
    user = await crud.authenticate(email=email, password=password)
    assert user is None


async def test_check_if_user_is_active() -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await crud.create_user(user_create=user_in)
    assert user.is_active is True


async def test_check_if_user_is_active_inactive() -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_active=False)
    user = await crud.create_user(user_create=user_in)
    assert user.is_active is False


async def test_check_if_user_is_superuser() -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    assert user.is_superuser is True


async def test_check_if_user_is_superuser_normal_user() -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = await crud.create_user(user_create=user_in)
    assert user.is_superuser is False


async def test_get_user() -> None:
    password = random_lower_string()
    username = random_email()
    user_in = UserCreate(email=username, password=password, is_superuser=True)
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
    password = random_lower_string()
    email = random_email()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    await crud.update_user(db_user=user, user_in=user_in_update)

    user_2 = await User.get(user.id)
    assert user_2
    assert user.email == user_2.email
    verified, _ = verify_password(new_password, user_2.hashed_password)
    assert verified


async def test_authenticate_user_with_bcrypt_upgrades_to_argon2() -> None:
    """Test that a user with bcrypt password hash gets upgraded to argon2 on login."""
    email = random_email()
    password = random_lower_string()

    bcrypt_hasher = BcryptHasher()
    bcrypt_hash = bcrypt_hasher.hash(password)
    assert bcrypt_hash.startswith("$2")

    user = User(email=email, hashed_password=bcrypt_hash)
    await user.insert()

    assert user.hashed_password.startswith("$2")

    authenticated_user = await crud.authenticate(email=email, password=password)
    assert authenticated_user
    assert authenticated_user.email == email

    refreshed = await User.get(authenticated_user.id)
    assert refreshed
    assert refreshed.hashed_password.startswith("$argon2")

    verified, updated_hash = verify_password(password, refreshed.hashed_password)
    assert verified
    assert updated_hash is None
