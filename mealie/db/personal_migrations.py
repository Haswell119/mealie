"""
Run the migrations of the personal edition.

The personal edition keeps its tables apart from the tables of Mealie:
- every table name starts with `pe_`;
- the migrations live in `mealie/alembic_personal` and record their version in their own table.

A downgrade to `base` removes every table of the personal edition and leaves a database that an
unmodified Mealie can use.
"""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, pool

from mealie.core.config import get_app_settings
from mealie.core.root_logger import get_logger

ALEMBIC_PERSONAL_DIR = Path(__file__).parent.parent / "alembic_personal"
VERSION_TABLE = "alembic_version_personal"
TABLE_PREFIX = "pe_"

# The backup of Mealie rebuilds dates from the name of their column. These are the names that the
# personal edition adds; `register_backup_columns` hands them to the backup.
DATETIME_COLUMNS = frozenset(
    {"starts_at", "consent_given_at", "verified_at", "computed_at", "confirmed_at", "decided_at", "fetched_at"}
)
DATE_COLUMNS = frozenset({"date_from", "date_to", "expires_on", "promotion_ends_on", "spent_on"})

logger = get_logger()


def register_backup_columns(exporter: Any) -> None:
    """Tell the backup which columns of the personal edition hold a date, so that a restore rebuilds them."""
    exporter.look_for_datetime = set(exporter.look_for_datetime) | DATETIME_COLUMNS
    exporter.look_for_date = set(exporter.look_for_date) | DATE_COLUMNS


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_PERSONAL_DIR))
    config.set_main_option(
        "file_template", "%%(year)d-%%(month).2d-%%(day).2d-%%(hour).2d.%%(minute).2d.%%(second).2d_%%(rev)s_%%(slug)s"
    )
    return config


def _run(action, *args, **kwargs) -> None:
    url = get_app_settings().DB_URL
    if not url:
        raise ValueError("No database url found")

    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.begin() as connection:
            config = _config()
            config.attributes["connection"] = connection
            action(config, *args, **kwargs)
    finally:
        engine.dispose()


def upgrade(revision: str = "head") -> None:
    """Create or update the tables of the personal edition."""
    _run(command.upgrade, revision)


def downgrade(revision: str = "base") -> None:
    """Remove tables of the personal edition, down to a revision. `base` removes all of them."""
    _run(command.downgrade, revision)


def revision(message: str, rev_id: str | None = None) -> None:
    """Write a new migration from the difference between the models and the database."""
    _run(command.revision, message=message, autogenerate=True, rev_id=rev_id)


def upgrade_for_restore(db_dump: dict) -> None:
    """
    Create the tables of the personal edition at the version that a backup holds, before its rows go in.

    A backup of an unmodified Mealie holds no such version: nothing happens, and the next start of the
    application creates the tables empty.
    """
    rows = db_dump.get(VERSION_TABLE) or []
    if not rows:
        return
    version = rows[0].get("version_num")
    if version:
        logger.info(f"Restoring the tables of the personal edition at version {version}")
        upgrade(version)


def current_version() -> str | None:
    """The version of the personal edition tables, or None when they do not exist."""
    url = get_app_settings().DB_URL
    if not url:
        return None
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            if VERSION_TABLE not in inspect(connection).get_table_names():
                return None
            row = connection.exec_driver_sql(f"SELECT version_num FROM {VERSION_TABLE}").first()  # noqa: S608
            return row[0] if row else None
    finally:
        engine.dispose()
