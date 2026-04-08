"""SQLAlchemy/SQLModel engine and session factory.

Used alongside the existing Beanie/MongoDB stack (app.core.db) until
the migration to relational storage is complete.
"""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), echo=False)


def init_sql_db() -> None:
    """Create all SQLModel tables.

    For development/testing only. Replace with Alembic migrations
    before going to production.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session
