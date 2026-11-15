from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ._common import JSONText, PersonalHouseholdScoped


class PeInspiration(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """A cooking idea that is not a validated recipe yet."""

    __tablename__ = "pe_inspirations"

    title: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    kind: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    url: FilterableColumn[str | None] = mapped_column(sa.String)
    text: FilterableColumn[str | None] = mapped_column(sa.String)
    image: FilterableColumn[str | None] = mapped_column(sa.String)
    tags: FilterableColumn[list | None] = mapped_column(JSONText)
    status: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="INSPIRATION", index=True)
    draft: FilterableColumn[dict | None] = mapped_column(JSONText)
    recipe_id: FilterableColumn[GUID | None] = mapped_column(
        GUID, sa.ForeignKey("recipes.id", ondelete="SET NULL"), index=True
    )

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeAiProposal(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """A change that the assistant suggests. The application applies it only after the user accepts it."""

    __tablename__ = "pe_ai_proposals"

    kind: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    status: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="PENDING", index=True)
    title: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    payload: FilterableColumn[dict | None] = mapped_column(JSONText)
    event_id: FilterableColumn[GUID | None] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id", ondelete="SET NULL"), index=True
    )
    created_by: FilterableColumn[GUID | None] = mapped_column(GUID, index=True)
    decided_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)
    result: FilterableColumn[dict | None] = mapped_column(JSONText)

    @auto_init()
    def __init__(self, **_) -> None:
        pass
