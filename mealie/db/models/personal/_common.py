import json
from typing import Any

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeDecorator

from .._model_base import FilterableColumn
from .._model_utils.guid import GUID


class PersonalGroupScoped:
    """Columns for a table that belongs to a group."""

    id: FilterableColumn[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)
    group_id: FilterableColumn[GUID] = mapped_column(GUID, ForeignKey("groups.id"), nullable=False, index=True)


class PersonalHouseholdScoped(PersonalGroupScoped):
    """Columns for a table that belongs to a household."""

    household_id: FilterableColumn[GUID] = mapped_column(GUID, ForeignKey("households.id"), nullable=False, index=True)


class JSONText(TypeDecorator):
    """
    A list or a dictionary stored as JSON text.

    The backup of Mealie walks every value of a row and rebuilds dates and ids from their names. That walk
    is not written for nested values, so the personal edition stores them as plain text.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None or value == "":
            return None
        return json.loads(value)
