import random
import string

from app import crud
from app.core import security
from app.core.config import settings


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


async def get_superuser_token_headers() -> dict[str, str]:
    user = await crud.get_user_by_email(email=settings.FIRST_SUPERUSER)
    token = security.create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}
