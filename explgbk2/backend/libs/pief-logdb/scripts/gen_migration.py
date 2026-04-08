"""Generate an Alembic migration from SQLModel metadata.

Uses testcontainers to spin up a throwaway Postgres instance, runs all
existing migrations to head, then autogenerates a new revision.

Usage (from the backend/ directory):
    uv run python scripts/gen_migration.py
"""

import sys
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine
from testcontainers.postgres import PostgresContainer

import pief.logdb.tables as _tables  # noqa: F401 — registers tables on SQLModel.metadata
from pief.logdb.config.alembic import alembic_config

POSTGRES_IMAGE = "postgres:18"
POSTGRES_DRIVER = "psycopg"
VERSIONS_DIR = Path(__file__).parent.parent / "src/pief/logdb/alembic/versions"


def main() -> None:
    message = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else input("Migration name: ").strip()
    )
    if not message:
        print("Aborted: migration name cannot be empty.")
        sys.exit(1)

    before = {f for f in VERSIONS_DIR.glob("*.py") if f.name != "__init__.py"}

    print(f"Starting {POSTGRES_IMAGE}...")
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        engine = create_engine(pg.get_connection_url(driver=POSTGRES_DRIVER))
        cfg = alembic_config(engine)
        command.upgrade(cfg, "head")
        command.revision(cfg, autogenerate=True, message=message)
        engine.dispose()

    new_files = {
        f for f in VERSIONS_DIR.glob("*.py") if f.name != "__init__.py"
    } - before
    for f in sorted(new_files):
        print(f"Generated: {f.name}")


if __name__ == "__main__":
    main()
