from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import auto_init
from .._model_utils.datetime import NaiveDateTime
from .._model_utils.guid import GUID
from ._common import PersonalGroupScoped


class PeDietaryRestriction(PersonalGroupScoped, SqlAlchemyBase, BaseMixins):
    __tablename__ = "pe_dietary_restrictions"
    __table_args__ = (sa.UniqueConstraint("group_id", "key", name="pe_dietary_restrictions_group_id_key_key"),)

    key: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    name: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    kind: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    description: FilterableColumn[str | None] = mapped_column(sa.String)
    is_system: FilterableColumn[bool] = mapped_column(sa.Boolean, default=False, nullable=False)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeFoodRestrictionStatus(PersonalGroupScoped, SqlAlchemyBase, BaseMixins):
    """
    The verification state of one food for one restriction.

    A food without a row is unverified. Only a person can mark a food as verified:
    the check constraint rejects a verified row from any other source.
    """

    __tablename__ = "pe_food_restriction_status"
    __table_args__ = (
        sa.UniqueConstraint("food_id", "restriction_id", name="pe_food_restriction_status_food_restriction_key"),
        sa.CheckConstraint(
            "status != 'VERIFIED' OR (source = 'MANUAL' AND verified_by IS NOT NULL)",
            name="pe_food_restriction_status_verified_is_manual",
        ),
    )

    food_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("ingredient_foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    restriction_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_dietary_restrictions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    restriction: Mapped[PeDietaryRestriction] = orm.relationship(PeDietaryRestriction, lazy="joined")

    status: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    source: FilterableColumn[str] = mapped_column(sa.String, nullable=False)
    reason: FilterableColumn[str | None] = mapped_column(sa.String)
    verified_by: FilterableColumn[GUID | None] = mapped_column(GUID, index=True)
    verified_at: FilterableColumn[datetime | None] = mapped_column(NaiveDateTime)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeToolRestrictionStatus(PersonalGroupScoped, SqlAlchemyBase, BaseMixins):
    """A tool that needs a cross-contamination check for one restriction."""

    __tablename__ = "pe_tool_restriction_status"
    __table_args__ = (
        sa.UniqueConstraint("tool_id", "restriction_id", name="pe_tool_restriction_status_tool_restriction_key"),
    )

    tool_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    restriction_id: FilterableColumn[GUID] = mapped_column(
        GUID, sa.ForeignKey("pe_dietary_restrictions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    restriction: Mapped[PeDietaryRestriction] = orm.relationship(PeDietaryRestriction, lazy="joined")

    requires_check: FilterableColumn[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    reason: FilterableColumn[str | None] = mapped_column(sa.String)

    @auto_init()
    def __init__(self, **_) -> None:
        pass
