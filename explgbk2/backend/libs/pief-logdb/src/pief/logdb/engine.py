"""SQLModel engine and session factory for pief.logdb.

Uses a factory pattern so callers supply the database URL at startup
rather than importing settings. This keeps pief.logdb free of any
dependency on pief.api or pief.streams configuration.
"""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

_engine = None


def init_db(database_url: str, echo: bool = False) -> None:
    """Initialise the SQLModel engine and create all tables.

    Call once at application startup (e.g. in lifespan) before any other
    pief.logdb functions are called.
    """
    global _engine
    _engine = create_engine(database_url, echo=echo)
    SQLModel.metadata.create_all(_engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI / FastStream dependency that yields a database session per request."""
    assert _engine is not None, "pief.logdb.engine.init_db() must be called first"
    with Session(_engine) as session:
        yield session
