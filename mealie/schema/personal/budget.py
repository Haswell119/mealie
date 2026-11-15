from datetime import date, datetime

from pydantic import UUID4, ConfigDict, Field, field_validator

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .price import PriceOffer


def _clean_store(value: str) -> str:
    cleaned = " ".join(value.split()).lower()
    if not cleaned:
        raise ValueError("store must not be empty")
    return cleaned


class ExpenseCreate(MealieModel):
    spent_on: date
    store: str = Field(min_length=1, max_length=60)
    amount: float = Field(gt=0)
    """What the person paid."""
    estimated_amount: float | None = Field(None, ge=0)
    plan_id: UUID4 | None = None
    note: str | None = Field(None, max_length=300)

    @field_validator("store")
    @classmethod
    def clean_store(cls, value: str) -> str:
        return _clean_store(value)


class ExpenseSave(ExpenseCreate):
    group_id: UUID4
    household_id: UUID4
    currency: str = "CHF"
    plan_name: str | None = None


class ExpenseOut(MealieOutModel):
    id: UUID4
    group_id: UUID4
    household_id: UUID4
    spent_on: date
    store: str
    amount: float
    estimated_amount: float | None = None
    currency: str = "CHF"
    plan_id: UUID4 | None = None
    plan_name: str | None = None
    note: str | None = None
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ExpensePagination(PaginationBase):
    items: list[ExpenseOut]


class PlanExpenseCreate(MealieModel):
    """The shopping of a plan is done: keep what it cost."""

    store: str = Field(min_length=1, max_length=60)
    amount: float | None = Field(None, gt=0)
    """What the person paid. None keeps the estimate of the application."""
    spent_on: date | None = None
    note: str | None = Field(None, max_length=300)

    @field_validator("store")
    @classmethod
    def clean_store(cls, value: str) -> str:
        return _clean_store(value)


class BudgetSettingsUpdate(MealieModel):
    monthly_target: float | None = Field(None, gt=0)
    usual_store: str | None = Field(None, max_length=60)
    """The shop whose prices give the cost of a meal. None takes the cheapest known price of each food."""

    @field_validator("usual_store")
    @classmethod
    def clean_store(cls, value: str | None) -> str | None:
        return " ".join(value.split()).lower() or None if value else None


class BudgetSettingsSave(BudgetSettingsUpdate):
    group_id: UUID4
    household_id: UUID4


class BudgetSettingsOut(MealieOutModel):
    id: UUID4 | None = None
    monthly_target: float | None = None
    usual_store: str | None = None
    model_config = ConfigDict(from_attributes=True)


class BudgetStoreTotal(MealieOutModel):
    store: str
    total: float = 0
    count: int = 0


class BudgetMonth(MealieOutModel):
    month: str
    """The month as "2026-11"."""
    total: float = 0
    count: int = 0
    stores: list[BudgetStoreTotal] = []


class BudgetEstimateCheck(MealieOutModel):
    """How the estimates of the application compare with what the person paid, on the expenses that have both."""

    count: int = 0
    estimated: float = 0
    paid: float = 0


class BudgetSummaryOut(MealieOutModel):
    currency: str = "CHF"
    monthly_target: float | None = None
    usual_store: str | None = None
    months: list[BudgetMonth] = []
    """One entry for each month of the period, the oldest first. A month without an expense is present."""
    current: BudgetMonth
    remaining: float | None = None
    """What is left of the monthly target this month. Negative when the target is passed."""
    average_month: float | None = None
    """The mean of the complete months, from the first month that has an expense."""
    stores: list[BudgetStoreTotal] = []
    total: float = 0
    expense_count: int = 0
    estimate_check: BudgetEstimateCheck = BudgetEstimateCheck()


class MealCost(MealieOutModel):
    date: date
    entry_type: str = ""
    recipe_id: UUID4
    recipe_slug: str | None = None
    recipe_name: str = ""
    servings: float = 0
    total: float | None = None
    """The cost of the quantities that the recipe uses. None when too few of its ingredients have a price."""
    per_serving: float | None = None
    priced_ingredients: int = 0
    ingredient_count: int = 0


class MealCostsOut(MealieOutModel):
    date_from: date
    date_to: date
    store: str | None = None
    currency: str = "CHF"
    meals: list[MealCost] = []
    total: float = 0
    """The sum of the meals that have a cost."""
    priced_meals: int = 0


class RecipeCostSummary(MealieOutModel):
    recipe_id: UUID4
    recipe_slug: str | None = None
    recipe_name: str = ""
    servings: float = 0
    total: float | None = None
    per_serving: float | None = None
    priced_ingredients: int = 0
    ingredient_count: int = 0


class RecipeCostsOut(MealieOutModel):
    store: str | None = None
    currency: str = "CHF"
    recipes: list[RecipeCostSummary] = []
    """The recipes with a cost first, the cheapest serving first."""
    priced_count: int = 0


class StoreMatchRequest(MealieModel):
    keys: list[str] = []
    """The lines to search. An empty list searches every line of the plan."""
    queries: dict[str, str] = {}
    """A search text typed by the person, by line key. It replaces the text that the application builds."""
    refresh: bool = False
    """Search also the shops that already have a stored price for the food."""


class StoreMatchCandidate(MealieOutModel):
    offer: PriceOffer
    score: float = 0
    """How well the name of the product fits the search, from 0 to 1."""
    confident: bool = False
    fits: bool = False
    """The size of the pack can price the quantity of the line."""
    cost: float | None = None
    """What the line costs with this product, in whole packs."""
    packs: int | None = None


class StoreMatchStore(MealieOutModel):
    store: str
    stored_label: str | None = None
    stored_price: float | None = None
    """The price that the household already keeps for this food in this shop."""
    has_stored: bool = False
    searched: bool = False
    failed: bool = False
    """The shop did not answer. No candidate does not mean "no product"."""
    candidates: list[StoreMatchCandidate] = []


class StoreMatchLine(MealieOutModel):
    key: str
    display: str = ""
    food_id: UUID4 | None = None
    food_name: str | None = None
    quantity: float = 0
    unit_name: str = ""
    query: str = ""
    translated: bool = False
    """The search text is the German name that the shops use, not the name of the food."""
    reason: str | None = None
    """Why the line was not searched: NO_FOOD or TOO_MANY."""
    stores: list[StoreMatchStore] = []


class StoreMatchOut(MealieOutModel):
    plan_id: UUID4
    available: bool = True
    """False when no price service is configured, or when it did not answer at all."""
    lines: list[StoreMatchLine] = []
    searched_lines: int = 0
