"""SQLModel engine and session factory for pief.logdb."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from pief.logdb.config.settings import settings as db_settings

_engine = create_engine(str(db_settings.SQLALCHEMY_DATABASE_URI))


def get_session() -> Generator[Session, None, None]:
    """FastAPI / FastStream dependency that yields a database session per request."""
    with Session(_engine) as session:
        yield session
