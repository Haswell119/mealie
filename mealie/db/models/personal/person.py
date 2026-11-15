from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import AutoInitOptions, auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ..recipe.ingredient import IngredientFoodModel
from ._common import PersonalHouseholdScoped
from .dietary import PeDietaryRestriction


class PePersonRestriction(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_person_restrictions"
    __table_args__ = (
        sa.UniqueConstraint("person_id", "restriction_id", name="pe_person_restrictions_person_restriction_key"),
    )

    person_id: FilterableColumn[GUID] = mapped_column(GUID, sa.ForeignKey("pe_persons.id"), nullable=False, index=True)
    restriction_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_dietary_restrictions.id"), nullable=False, index=True
    )
    restriction: Mapped[PeDietaryRestriction] = orm.relationship(PeDietaryRestriction, lazy="joined")

    severity: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    default_scope: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    applies_when_cooking: FilterableColumn[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    notes: FilterableColumn[str | None] = mapped_column(sa.String)

    model_config = AutoInitOptions(exclude={"restriction"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PePersonFoodPreference(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_person_food_preferences"
    __table_args__ = (sa.UniqueConstraint("person_id", "food_id", name="pe_person_food_preferences_person_food_key"),)

    person_id: FilterableColumn[GUID] = mapped_column(GUID, sa.ForeignKey("pe_persons.id"), nullable=False, index=True)
    food_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("ingredient_foods.id"), nullable=False, index=True
    )
    food: Mapped[IngredientFoodModel] = orm.relationship(IngredientFoodModel, lazy="joined")
    kind: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    note: FilterableColumn[str | None] = mapped_column(sa.String)

    model_config = AutoInitOptions(exclude={"food"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PePerson(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """A person the household cooks for. A person does not need a user account."""

    __tablename__ = "pe_persons"

    display_name: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    appetite: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="NORMAL")
    notes: FilterableColumn[str | None] = mapped_column(sa.String)
    linked_user_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("users.id"), index=True)
    consent_given_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)
    consent_note: FilterableColumn[str | None] = mapped_column(sa.String)

    restrictions: Mapped[list[PePersonRestriction]] = orm.relationship(
        PePersonRestriction, cascade="all, delete-orphan", order_by="PePersonRestriction.created_at"
    )
    food_preferences: Mapped[list[PePersonFoodPreference]] = orm.relationship(
        PePersonFoodPreference, cascade="all, delete-orphan", order_by="PePersonFoodPreference.created_at"
    )

    model_config = AutoInitOptions(exclude={"restrictions", "food_preferences"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass
