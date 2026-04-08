import logging

from alembic import command
from sqlalchemy import create_engine

from pief.api.core.config import settings
from pief.logdb import crud
from pief.logdb.config.alembic import alembic_config
from pief.logdb.config.settings import settings as db_settings
from pief.logdb.engine import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Running database migrations")
    engine = create_engine(str(db_settings.SQLALCHEMY_DATABASE_URI))
    try:
        command.upgrade(alembic_config(engine), "head")
    finally:
        engine.dispose()
    logger.info("Migrations complete")

    logger.info("Creating initial data")
    with next(get_session()) as session:
        crud.create_default_user(session=session, username=settings.FIRST_SUPERUSER)
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
