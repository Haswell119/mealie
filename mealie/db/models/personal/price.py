from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import AutoInitOptions, auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ..recipe.ingredient import IngredientFoodModel
from ._common import PersonalHouseholdScoped


class PeFoodPrice(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """
    What one shop asks for one food: the price of a pack, and the size of the pack.

    The household keeps one price for each food and each shop. A person types it, or a price source gives it.
    """

    __tablename__ = "pe_food_prices"
    __table_args__ = (
        sa.UniqueConstraint("household_id", "food_id", "store", name="pe_food_prices_household_food_store_key"),
    )

    food_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("ingredient_foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food: Mapped[IngredientFoodModel] = orm.relationship(IngredientFoodModel, lazy="joined")
    store: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)

    label: FilterableColumn[str | None] = mapped_column(sa.String)
    brand: FilterableColumn[str | None] = mapped_column(sa.String)
    price: FilterableColumn[float] = mapped_column(sa.Float, nullable=False)
    regular_price: FilterableColumn[float | None] = mapped_column(sa.Float)
    currency: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="CHF")
    size: FilterableColumn[float | None] = mapped_column(sa.Float)
    size_unit: FilterableColumn[str | None] = mapped_column(sa.String)
    # True when the shop sells any quantity at this rate (vegetables by weight): the cost is not rounded to packs.
    by_weight: FilterableColumn[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    promotion: FilterableColumn[str | None] = mapped_column(sa.String)
    promotion_ends_on: FilterableColumn[date | None] = mapped_column(sa.Date)

    source: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="manual")
    external_id: FilterableColumn[str | None] = mapped_column(sa.String)
    product_url: FilterableColumn[str | None] = mapped_column(sa.String)
    image_url: FilterableColumn[str | None] = mapped_column(sa.String)
    fetched_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)

    model_config = AutoInitOptions(exclude={"food"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass
