from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import MongoDsn
from testcontainers.mongodb import MongoDbContainer

from app.core.config import settings
from app.core.db import init_db, reset_db
from app.main import app
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session")
async def db() -> AsyncGenerator[None, None]:
    with MongoDbContainer("mongo:7.0") as mongo:
        settings.MONGODB_URI = MongoDsn(mongo.get_connection_url())
        await init_db()
        yield
        await reset_db()


@pytest.fixture(scope="module")
async def client(db: None) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture(scope="module")
async def superuser_token_headers() -> dict[str, str]:
    return await get_superuser_token_headers()


@pytest.fixture(scope="module")
async def normal_user_token_headers() -> dict[str, str]:
    return await authentication_token_from_email(email=settings.EMAIL_TEST_USER)
