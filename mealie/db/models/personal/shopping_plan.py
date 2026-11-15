from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import AutoInitOptions, auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ._common import JSONText, PersonalHouseholdScoped


class PeShoppingPlanLine(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """
    One line of the ledger of a shopping plan: what a plan needs of one food.

    `projected_quantity` is the share of the linked shopping list item that comes from this line.
    `purchased_quantity` is what the user already bought for this line.
    """

    __tablename__ = "pe_shopping_plan_lines"
    __table_args__ = (sa.UniqueConstraint("plan_id", "key", name="pe_shopping_plan_lines_plan_key_key"),)

    plan_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_shopping_plans.id"), nullable=False, index=True
    )
    key: FilterableColumn[str] = mapped_column(sa.String, nullable=False)

    food_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("ingredient_foods.id"), index=True)
    unit_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("ingredient_units.id"), index=True)
    note: FilterableColumn[str | None] = mapped_column(sa.String)
    display: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="")

    quantity_needed: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)
    quantity_from_stock: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)
    quantity_to_buy: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)
    packs: FilterableColumn[int | None] = mapped_column(sa.Integer)
    pack_label: FilterableColumn[str | None] = mapped_column(sa.String)

    projected_quantity: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)
    purchased_quantity: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)
    # Not a foreign key: the user can delete the item in the native shopping list.
    shopping_list_item_id: FilterableColumn[GUID | None] = mapped_column(GUID, index=True)
    state: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="ACTIVE")

    sources: FilterableColumn[list | None] = mapped_column(JSONText)
    checks: FilterableColumn[list | None] = mapped_column(JSONText)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeShoppingPlan(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """A set of recipes to shop for: one meal event, a range of the meal plan, or a free selection."""

    __tablename__ = "pe_shopping_plans"

    name: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    source_type: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    event_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("pe_meal_events.id"), index=True)
    date_from: FilterableColumn[date | None] = mapped_column(sa.Date)
    date_to: FilterableColumn[date | None] = mapped_column(sa.Date)
    recipes: FilterableColumn[list | None] = mapped_column(JSONText)

    shopping_list_id: FilterableColumn[GUID | None] = mapped_column(
        GUID, sa.ForeignKey("shopping_lists.id"), index=True
    )
    status: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="OPEN")
    use_stock: FilterableColumn[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    use_packaging: FilterableColumn[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    computed_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)

    lines: Mapped[list[PeShoppingPlanLine]] = orm.relationship(
        PeShoppingPlanLine, cascade="all, delete-orphan", order_by="PeShoppingPlanLine.display"
    )

    model_config = AutoInitOptions(exclude={"lines"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass
