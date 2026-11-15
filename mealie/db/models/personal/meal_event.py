from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import AutoInitOptions, auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ._common import PersonalHouseholdScoped
from .dietary import PeDietaryRestriction
from .person import PePerson


class PeMealEventGuest(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_meal_event_guests"
    __table_args__ = (sa.UniqueConstraint("event_id", "person_id", name="pe_meal_event_guests_event_person_key"),)

    event_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id"), nullable=False, index=True
    )
    person_id: FilterableColumn[GUID] = mapped_column(GUID, sa.ForeignKey("pe_persons.id"), nullable=False, index=True)
    person: Mapped[PePerson] = orm.relationship(PePerson, lazy="joined")
    attending: FilterableColumn[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    appetite_override: FilterableColumn[str | None] = mapped_column(sa.String)

    model_config = AutoInitOptions(exclude={"person"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeMealEventMenuVariant(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """One recipe that serves a menu item. A menu item with a dietary variant has more than one."""

    __tablename__ = "pe_meal_event_menu_variants"

    event_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id"), nullable=False, index=True
    )
    menu_item_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_event_menu_items.id"), nullable=False, index=True
    )
    recipe_id: FilterableColumn[GUID] = mapped_column(GUID, sa.ForeignKey("recipes.id"), nullable=False, index=True)
    label: FilterableColumn[str | None] = mapped_column(sa.String)
    position: FilterableColumn[int] = mapped_column(sa.Integer, default=0, nullable=False)
    portions_override: FilterableColumn[float | None] = mapped_column(sa.Float)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeMealEventMenuItem(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_meal_event_menu_items"

    event_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id"), nullable=False, index=True
    )
    course: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="MAIN")
    title: FilterableColumn[str | None] = mapped_column(sa.String)
    position: FilterableColumn[int] = mapped_column(sa.Integer, default=0, nullable=False)

    variants: Mapped[list[PeMealEventMenuVariant]] = orm.relationship(
        PeMealEventMenuVariant, cascade="all, delete-orphan", order_by="PeMealEventMenuVariant.position"
    )

    model_config = AutoInitOptions(exclude={"variants"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeMealEventAssignment(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """A manual choice of variant for one person and one menu item."""

    __tablename__ = "pe_meal_event_assignments"
    __table_args__ = (
        sa.UniqueConstraint("menu_item_id", "person_id", name="pe_meal_event_assignments_menu_item_person_key"),
    )

    event_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id"), nullable=False, index=True
    )
    menu_item_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_event_menu_items.id"), nullable=False, index=True
    )
    person_id: FilterableColumn[GUID] = mapped_column(GUID, sa.ForeignKey("pe_persons.id"), nullable=False, index=True)
    variant_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_event_menu_variants.id"), nullable=False, index=True
    )

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeMealEventOverride(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """An explicit change of scope for one person's restriction, for an event or one menu item."""

    __tablename__ = "pe_meal_event_overrides"

    event_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id"), nullable=False, index=True
    )
    menu_item_id: FilterableColumn[GUID | None] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_event_menu_items.id"), index=True
    )
    person_id: FilterableColumn[GUID] = mapped_column(GUID, sa.ForeignKey("pe_persons.id"), nullable=False, index=True)
    restriction_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_dietary_restrictions.id"), nullable=False, index=True
    )
    restriction: Mapped[PeDietaryRestriction] = orm.relationship(PeDietaryRestriction, lazy="joined")
    scope: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    reason: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    created_by: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("users.id"), index=True)

    model_config = AutoInitOptions(exclude={"restriction"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeMealEventHistory(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_meal_event_history"

    event_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_meal_events.id"), nullable=False, index=True
    )
    user_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("users.id"), index=True)
    action: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    detail: FilterableColumn[str | None] = mapped_column(sa.String)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeMealEvent(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_meal_events"

    name: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    starts_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime, index=True)
    location: FilterableColumn[str | None] = mapped_column(sa.String)
    cook_person_id: FilterableColumn[GUID | None] = mapped_column(GUID, sa.ForeignKey("pe_persons.id"), index=True)
    status: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="DRAFT")
    leftover_portions: FilterableColumn[float] = mapped_column(sa.Float, nullable=False, default=0)
    notes: FilterableColumn[str | None] = mapped_column(sa.String)

    guests: Mapped[list[PeMealEventGuest]] = orm.relationship(
        PeMealEventGuest, cascade="all, delete-orphan", order_by="PeMealEventGuest.created_at"
    )
    menu_items: Mapped[list[PeMealEventMenuItem]] = orm.relationship(
        PeMealEventMenuItem, cascade="all, delete-orphan", order_by="PeMealEventMenuItem.position"
    )
    assignments: Mapped[list[PeMealEventAssignment]] = orm.relationship(
        PeMealEventAssignment, cascade="all, delete-orphan"
    )
    overrides: Mapped[list[PeMealEventOverride]] = orm.relationship(
        PeMealEventOverride, cascade="all, delete-orphan", order_by="PeMealEventOverride.created_at"
    )
    history: Mapped[list[PeMealEventHistory]] = orm.relationship(
        PeMealEventHistory, cascade="all, delete-orphan", order_by="PeMealEventHistory.created_at"
    )

    model_config = AutoInitOptions(exclude={"guests", "menu_items", "assignments", "overrides", "history"})

    @auto_init()
    def __init__(self, **_) -> None:
        pass
