from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column

from .._model_base import FilterableColumn
from .._model_utils.guid import GUID


class PersonalGroupScoped:
    """Columns for a table that belongs to a group."""

    id: FilterableColumn[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)
    group_id: FilterableColumn[GUID] = mapped_column(GUID, ForeignKey("groups.id"), nullable=False, index=True)


class PersonalHouseholdScoped(PersonalGroupScoped):
    """Columns for a table that belongs to a household."""

    household_id: FilterableColumn[GUID] = mapped_column(GUID, ForeignKey("households.id"), nullable=False, index=True)
