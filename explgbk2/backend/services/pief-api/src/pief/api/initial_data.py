import asyncio
import logging

from alembic import command
from sqlalchemy import create_engine

from pief.api.core.config import settings
from pief.logdb import crud
from pief.logdb.config.alembic import alembic_config
from pief.logdb.config.settings import settings as db_settings
from pief.logdb.engine import get_session
from pief.logdb.schemas import UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _create_initial_data() -> None:
    async for session in get_session():
        user = await crud.get_user_by_username(
            session=session, username=settings.FIRST_SUPERUSER
        )
        if not user:
            logger.info("Creating default user: %s", settings.FIRST_SUPERUSER)
            await crud.create_user(
                session=session,
                user_in=UserCreate(username=settings.FIRST_SUPERUSER),
            )
            await session.commit()
        break


def main() -> None:
    logger.info("Running database migrations")
    engine = create_engine(str(db_settings.SQLALCHEMY_DATABASE_URI))
    try:
        command.upgrade(alembic_config(engine), "head")
    finally:
        engine.dispose()
    logger.info("Migrations complete")

    logger.info("Creating initial data")
    asyncio.run(_create_initial_data())
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
