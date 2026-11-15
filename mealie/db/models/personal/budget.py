from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

from .._model_base import BaseMixins, FilterableColumn, SqlAlchemyBase
from .._model_utils.auto_init import auto_init
from .._model_utils.guid import GUID
from ._common import PersonalHouseholdScoped


class PeExpense(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """
    What the household paid in one shop on one day.

    `amount` is what the person paid. `estimated_amount` is what the application expected for the shopping plan,
    when the expense comes from one. The two stay apart, so that the person can see how good the estimate was.
    """

    __tablename__ = "pe_expenses"

    spent_on: FilterableColumn[date] = mapped_column(sa.Date, nullable=False, index=True)
    store: FilterableColumn[str] = mapped_column(sa.String, nullable=False, index=True)
    amount: FilterableColumn[float] = mapped_column(sa.Float, nullable=False)
    estimated_amount: FilterableColumn[float | None] = mapped_column(sa.Float)
    currency: FilterableColumn[str] = mapped_column(sa.String, nullable=False, default="CHF")

    plan_id: FilterableColumn[GUID | None] = mapped_column(
        GUID, sa.ForeignKey("pe_shopping_plans.id", ondelete="SET NULL"), index=True
    )
    # The name stays when the plan is deleted: the expense is still a fact.
    plan_name: FilterableColumn[str | None] = mapped_column(sa.String)
    note: FilterableColumn[str | None] = mapped_column(sa.String)

    @auto_init()
    def __init__(self, **_) -> None:
        pass


class PeBudgetSetting(PersonalHouseholdScoped, SqlAlchemyBase, BaseMixins):
    """The budget that the household gives itself. One row for each household."""

    __tablename__ = "pe_budget_settings"
    __table_args__ = (sa.UniqueConstraint("household_id", name="pe_budget_settings_household_key"),)

    monthly_target: FilterableColumn[float | None] = mapped_column(sa.Float)
    # The shop whose prices give the cost of a meal. None takes the cheapest known price of each food.
    usual_store: FilterableColumn[str | None] = mapped_column(sa.String)

    @auto_init()
    def __init__(self, **_) -> None:
        pass
