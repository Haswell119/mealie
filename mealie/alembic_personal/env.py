"""
The migration environment of the personal edition.

It is separate from the migrations of Mealie: it has its own version table and it only sees the tables
whose name starts with `pe_`. The migration history of Mealie therefore stays exactly as upstream wrote it.
"""

from typing import Any, Literal

from alembic import context

import mealie.db.models._all_models  # noqa: F401
import mealie.db.models.personal  # noqa: F401
from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models.personal._common import JSONText
from mealie.db.personal_migrations import TABLE_PREFIX, VERSION_TABLE

target_metadata = SqlAlchemyBase.metadata


def include_object(object: Any, name: str | None, type_: str, reflected: bool, compare_to: Any) -> bool:
    if type_ == "table":
        return bool(name and name.startswith(TABLE_PREFIX))
    table = getattr(object, "table", None)
    table_name = getattr(table, "name", None)
    return table_name is None or table_name.startswith(TABLE_PREFIX)


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | Literal[False]:
    """Write the JSON text type as the plain text that it is in the database."""
    if type_ == "type" and isinstance(obj, JSONText):
        return "sa.Text()"
    return False


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is None:
        raise RuntimeError("The migrations of the personal edition need a connection. Use `personal_migrations`.")

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        user_module_prefix="mealie.db.migration_types.",
        render_as_batch=True,
        include_object=include_object,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
