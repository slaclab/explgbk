from beanie import PydanticObjectId
from httpx import AsyncClient

from app.core.config import settings
from app.models import User


async def test_create_user(client: AsyncClient) -> None:
    r = await client.post(
        f"{settings.API_V1_STR}/private/users/",
        json={
            "email": "pollo@listo.com",
            "password": "password123",
            "full_name": "Pollo Listo",
        },
    )

    assert r.status_code == 200

    data = r.json()

    user = await User.get(PydanticObjectId(data["id"]))

    assert user
    assert user.email == "pollo@listo.com"
    assert user.full_name == "Pollo Listo"
