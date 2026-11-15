from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import AutoInitOptions, auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ..recipe.ingredient import IngredientFoodModel, IngredientUnitModel
from ._common import JSONText, PersonalGroupScoped, PersonalHouseholdScoped


class PeProduct(PersonalGroupScoped, SqlAlchemyBase, BaseMixins):
    """A retail product, cached from an open product database."""

    __tablename__ = "pe_products"
    __table_args__ = (sa.UniqueConstraint("group_id", "barcode", name="pe_products_group_id_barcode_key"),)

    barcode: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    name: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    brand: FilterableColumn[str | None] = mapped_column(sa.String)
    stores: FilterableColumn[list | None] = mapped_column(JSONText)
    quantity: FilterableColumn[float | None] = mapped_column(sa.Float)
    quantity_unit: FilterableColumn[str | None] = mapped_column(sa.String)
    quantity_text: FilterableColumn[str | None] = mapped_column(sa.String)
    labels: FilterableColumn[list | None] = mapped_column(JSONText)
    allergens: FilterableColumn[list | None] = mapped_column(JSONText)
    traces: FilterableColumn[list | None] = mapped_column(JSONText)
    image_url: FilterableColumn[str | None] = mapped_column(sa.String)
    source: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    source_url: FilterableColumn[str | None] = mapped_column(sa.String)
    fetched_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)

    food_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("ingredient_foods.id"), index=True)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeFoodPackaging(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """The size of the pack a food is sold in."""

    __tablename__ = "pe_food_packagings"

    food_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("ingredient_foods.id"), nullable=False, index=True
    )
    food: Mapped[IngredientFoodModel] = orm.relationship(IngredientFoodModel, lazy="joined")
    unit_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("ingredient_units.id"), index=True)
    unit: Mapped[IngredientUnitModel | None] = orm.relationship(IngredientUnitModel, lazy="joined")
    quantity: FilterableColumn[float] = mapped_column(sa.Float, nullable=False)
    label: FilterableColumn[str | None] = mapped_column(sa.String)
    store: FilterableColumn[str | None] = mapped_column(sa.String)
    is_default: FilterableColumn[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    product_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("pe_products.id"), index=True)

    model_config = AutoInitOptions(exclude={"food", "unit"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PePantryItem(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """A quantity of one food that the household holds."""

    __tablename__ = "pe_pantry_items"

    food_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("ingredient_foods.id"), nullable=False, index=True
    )
    food: Mapped[IngredientFoodModel] = orm.relationship(IngredientFoodModel, lazy="joined")
    unit_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("ingredient_units.id"), index=True)
    unit: Mapped[IngredientUnitModel | None] = orm.relationship(IngredientUnitModel, lazy="joined")
    quantity: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)

    confirmed_usable: FilterableColumn[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    confirmed_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)
    expires_on: FilterableColumn[date | None] = mapped_column(sa.Date, index=True)
    location: FilterableColumn[str | None] = mapped_column(sa.String)
    note: FilterableColumn[str | None] = mapped_column(sa.String)
    product_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("pe_products.id"), index=True)

    model_config = AutoInitOptions(exclude={"food", "unit"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass
