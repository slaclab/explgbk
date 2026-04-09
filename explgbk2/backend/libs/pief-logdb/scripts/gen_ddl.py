"""Generate artifacts/db.sql from SQLAlchemy ORM metadata.

Emits CREATE TYPE and CREATE TABLE/INDEX DDL for the PostgreSQL dialect
directly from the ORM models, keeping artifacts/db.sql in sync with the
source of truth (libs/pief-logdb/src/pief/logdb/tables.py).

Usage (from the backend/ directory):
    uv run python scripts/gen_ddl.py
"""

from pathlib import Path

from sqlalchemy import Enum
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

import pief.logdb.tables as _tables  # noqa: F401 — registers tables on Base.metadata
from pief.logdb.tables import Base

ROOT = Path(__file__).parent.parent
OUTPUT_FILE = ROOT / "artifacts" / "db.sql"

HEADER = """\
-- PostgreSQL schema for pief-logdb
-- Auto-generated from SQLAlchemy ORM metadata via backend/scripts/gen_ddl.py
-- DO NOT EDIT MANUALLY — run `make schema` to regenerate.

"""


def collect_enums() -> dict[str, Enum]:
    seen: dict[str, Enum] = {}
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if (
                isinstance(col.type, Enum)
                and col.type.name
                and col.type.name not in seen
            ):
                seen[col.type.name] = col.type
    return seen


def emit_create_type(name: str, enum: Enum) -> str:
    values = ", ".join(f"'{v}'" for v in enum.enums)
    return f"CREATE TYPE {name} AS ENUM ({values});"


def emit_table_ddl(dialect: postgresql.dialect) -> list[str]:
    blocks: list[str] = []
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect)).strip() + ";"
        index_lines = [
            str(CreateIndex(idx).compile(dialect=dialect)).strip() + ";"
            for idx in table.indexes
        ]
        block = ddl
        if index_lines:
            block += "\n" + "\n".join(index_lines)
        blocks.append(block)
    return blocks


def main() -> None:
    dialect = postgresql.dialect()

    lines: list[str] = [HEADER.rstrip()]

    enums = collect_enums()
    if enums:
        lines.append("")
        lines.append("-- ENUMs")
        for name, enum in enums.items():
            lines.append(emit_create_type(name, enum))

    lines.append("")
    for block in emit_table_ddl(dialect):
        lines.append("")
        lines.append(block)

    output = "\n".join(lines) + "\n"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output)
    print(f"Written: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
