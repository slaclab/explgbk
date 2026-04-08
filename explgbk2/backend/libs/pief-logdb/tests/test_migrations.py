from collections.abc import Generator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine
from testcontainers.postgres import PostgresContainer

import pief.logdb.tables as _tables  # noqa: F401 — registers all tables in SQLModel.metadata
from pief.logdb.config.alembic import alembic_config

POSTGRES_IMAGE = "postgres:18"
POSTGRES_DRIVER = "psycopg"


@pytest.fixture(scope="module")
def postgres_engine() -> Generator[Engine, None, None]:
    """Spin up a PostgreSQL container, apply all migrations, and yield a connected engine."""
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        engine = create_engine(pg.get_connection_url(driver=POSTGRES_DRIVER))
        command.upgrade(alembic_config(engine), "head")
        yield engine
        engine.dispose()


class TestMigrations:
    def test_upgrade_succeeds(self, postgres_engine):
        """alembic upgrade head must complete without error."""
        pass

    def test_no_model_drift(self, postgres_engine):
        """alembic check: no model changes are missing from the migration history."""
        cfg = alembic_config(postgres_engine)
        # command.check raises MigrationSchemaMismatch if drift is detected.
        command.check(cfg)

    def test_downgrade_and_upgrade(self, postgres_engine):
        """All migrations must be reversible back to base and re-applicable to head."""
        cfg = alembic_config(postgres_engine)
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
