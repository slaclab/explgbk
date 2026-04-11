from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.core.config import LGBK_CACHE_DB, settings
from app.models.cache import Experiment
from app.models.user import User, UserCreate

_mongo_client: AsyncMongoClient | None = None


def get_mongo_client() -> AsyncMongoClient:
    assert _mongo_client is not None, "MongoDB client not initialized"
    return _mongo_client


async def init_db() -> None:
    global _mongo_client
    from app import crud

    _mongo_client = AsyncMongoClient(str(settings.MONGODB_URI))
    # App models in the main app DB
    await init_beanie(
        database=_mongo_client[settings.MONGODB_DB], document_models=[User]
    )
    # Experiment cache in explgbk_cache DB
    await init_beanie(
        database=_mongo_client[LGBK_CACHE_DB], document_models=[Experiment]
    )

    user = await crud.get_user_by_email(email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            is_superuser=True,
        )
        await crud.create_user(user_create=user_in)


async def reset_db() -> None:
    await User.delete_all()
    await Experiment.delete_all()
