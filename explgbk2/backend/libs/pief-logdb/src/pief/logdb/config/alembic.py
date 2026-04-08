from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import Engine

# Alembic scripts live alongside this module inside pief/logdb/alembic/.
_ALEMBIC_DIR = Path(__file__).parent.parent / "alembic"


def alembic_config(engine: Engine) -> Config:
    """Return an Alembic Config wired to the bundled alembic directory and *engine*."""
    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option(
        "sqlalchemy.url",
        engine.url.render_as_string(hide_password=False),
    )
    return cfg
