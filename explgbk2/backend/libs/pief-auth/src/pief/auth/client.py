"""OpenFGA async client and settings for pief.auth."""

from collections.abc import AsyncGenerator
from typing import Literal

import openfga_sdk
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../../.env",
        env_ignore_empty=True,
        extra="ignore",
    )

    OPENFGA_API_SCHEME: Literal["http", "https"] = "http"
    OPENFGA_API_HOST: str = "localhost:8080"
    OPENFGA_STORE_ID: str
    OPENFGA_MODEL_ID: str


settings = AuthSettings()  # type: ignore


async def get_fga_client() -> AsyncGenerator[openfga_sdk.OpenFgaClient, None]:
    """FastAPI dependency that yields one OpenFgaClient per request."""
    configuration = openfga_sdk.ClientConfiguration(
        api_scheme=settings.OPENFGA_API_SCHEME,
        api_host=settings.OPENFGA_API_HOST,
        store_id=settings.OPENFGA_STORE_ID,
        authorization_model_id=settings.OPENFGA_MODEL_ID,
    )
    async with openfga_sdk.OpenFgaClient(configuration) as client:
        yield client
