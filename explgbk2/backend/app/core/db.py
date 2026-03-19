from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.models import Item, User, UserCreate


async def init_db() -> None:
    from app import crud

    client = AsyncMongoClient(str(settings.MONGODB_URI))
    await init_beanie(
        database=client[settings.MONGODB_DB], document_models=[User, Item]
    )

    user = await crud.get_user_by_email(email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        await crud.create_user(user_create=user_in)


async def reset_db() -> None:
    await Item.delete_all()
    await User.delete_all()
