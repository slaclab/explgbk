from bson import ObjectId
from httpx import AsyncClient

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_email


async def test_get_users_superuser_me(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    r = await client.get(
        f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers
    )
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER


async def test_get_users_normal_user_me(
    client: AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = await client.get(
        f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers
    )
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == settings.EMAIL_TEST_USER


async def test_get_existing_user_as_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)
    user_id = user.id
    r = await client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = await crud.get_user_by_email(email=username)
    assert existing_user
    assert existing_user.email == api_user["email"]


async def test_get_non_existing_user_as_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    r = await client.get(
        f"{settings.API_V1_STR}/users/{ObjectId()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert r.json() == {"detail": "User not found"}


async def test_get_existing_user_current_user(client: AsyncClient) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)
    user_id = user.id

    headers = await user_authentication_headers(email=username)

    r = await client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=headers,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = await crud.get_user_by_email(email=username)
    assert existing_user
    assert existing_user.email == api_user["email"]


async def test_get_existing_user_permissions_error(
    client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user = await create_random_user()

    r = await client.get(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json() == {"detail": "The user doesn't have enough privileges"}


async def test_get_non_existing_user_permissions_error(
    client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user_id = ObjectId()

    r = await client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json() == {"detail": "The user doesn't have enough privileges"}


async def test_retrieve_users(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    await crud.create_user(user_create=user_in)

    username2 = random_email()
    user_in2 = UserCreate(email=username2)
    await crud.create_user(user_create=user_in2)

    r = await client.get(
        f"{settings.API_V1_STR}/users/", headers=superuser_token_headers
    )
    all_users = r.json()

    assert len(all_users["data"]) > 1
    assert "count" in all_users
    for item in all_users["data"]:
        assert "email" in item


async def test_update_user_me(
    client: AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    full_name = "Updated Name"
    email = random_email()
    data = {"full_name": full_name, "email": email}
    r = await client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["email"] == email
    assert updated_user["full_name"] == full_name

    user_db = await User.find_one(User.email == email)
    assert user_db
    assert user_db.email == email
    assert user_db.full_name == full_name


async def test_update_user_me_email_exists(
    client: AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)

    data = {"email": user.email}
    r = await client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User with this email already exists"


async def test_update_user(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)

    data = {"full_name": "Updated_full_name"}
    r = await client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()

    assert updated_user["full_name"] == "Updated_full_name"

    user_db = await User.find_one(User.email == username)
    assert user_db
    assert user_db.full_name == "Updated_full_name"


async def test_update_user_not_exists(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"full_name": "Updated_full_name"}
    r = await client.patch(
        f"{settings.API_V1_STR}/users/{ObjectId()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "The user with this id does not exist in the system"


async def test_update_user_email_exists(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)

    username2 = random_email()
    user_in2 = UserCreate(email=username2)
    user2 = await crud.create_user(user_create=user_in2)

    data = {"email": user2.email}
    r = await client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User with this email already exists"


async def test_delete_user_me(client: AsyncClient) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)
    user_id = user.id

    headers = await user_authentication_headers(email=username)

    r = await client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
    )
    assert r.status_code == 200
    deleted_user = r.json()
    assert deleted_user["message"] == "User deleted successfully"
    result = await User.get(user_id)
    assert result is None


async def test_delete_user_me_as_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    r = await client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    assert r.status_code == 403
    response = r.json()
    assert response["detail"] == "Super users are not allowed to delete themselves"


async def test_delete_user_super_user(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)
    user_id = user.id
    r = await client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    deleted_user = r.json()
    assert deleted_user["message"] == "User deleted successfully"
    result = await User.get(user_id)
    assert result is None


async def test_delete_user_not_found(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    r = await client.delete(
        f"{settings.API_V1_STR}/users/{ObjectId()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "User not found"


async def test_delete_user_current_super_user_error(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    super_user = await crud.get_user_by_email(email=settings.FIRST_SUPERUSER)
    assert super_user
    user_id = super_user.id

    r = await client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Super users are not allowed to delete themselves"


async def test_delete_user_without_privileges(
    client: AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    username = random_email()
    user_in = UserCreate(email=username)
    user = await crud.create_user(user_create=user_in)

    r = await client.delete(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "The user doesn't have enough privileges"
