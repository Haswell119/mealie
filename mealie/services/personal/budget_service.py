from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.budget import (
    BudgetEstimateCheck,
    BudgetMonth,
    BudgetSettingsOut,
    BudgetSettingsSave,
    BudgetSettingsUpdate,
    BudgetStoreTotal,
    BudgetSummaryOut,
    ExpenseCreate,
    ExpenseOut,
    ExpenseSave,
    MealCost,
    MealCostsOut,
    PlanExpenseCreate,
    RecipeCostsOut,
    RecipeCostSummary,
)

from .engine.ideas import COST_COVERAGE
from .engine.pricing import PricePoint, money
from .engine.requirements import Need
from .engine.units import UnitInfo, to_decimal
from .errors import PersonalError, PersonalNotFound
from .price_service import PriceService, cost_needs
from .recipe_needs import needs_from_rows, unit_info

MAX_MONTHS = 36
MAX_MEAL_DAYS = 62


def _month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _add_months(first_day: date, months: int) -> date:
    index = first_day.year * 12 + first_day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


class BudgetService:
    """What the household spends on food, month by month, and what its meals cost."""

    def __init__(self, repos: AllRepositories, user_id: UUID4) -> None:
        self.repos = repos
        self.user_id = user_id
        self.expenses = repos.pe_expenses
        self.settings = repos.pe_budget_settings

    # ================================================================
    # Expenses

    def get_one(self, expense_id: UUID4) -> ExpenseOut:
        expense = self.expenses.get_one(expense_id)
        if expense is None:
            raise PersonalNotFound("Expense not found.")
        return expense

    def _to_save(self, data: ExpenseCreate, today: date | None = None) -> ExpenseSave:
        today = today or datetime.now(UTC).date()
        # One day of margin: the server counts in UTC, the person does not.
        if data.spent_on > today + timedelta(days=1):
            raise PersonalError("EXPENSE_IN_FUTURE", "An expense cannot be in the future.")
        plan_name = None
        if data.plan_id is not None:
            plan = self.repos.pe_shopping_plans.get_one(data.plan_id)
            if plan is None:
                raise PersonalNotFound("Shopping plan not found.")
            plan_name = plan.name
        return data.cast(
            ExpenseSave,
            group_id=self.repos.group_id,
            household_id=self.repos.household_id,
            plan_name=plan_name,
            amount=float(money(to_decimal(data.amount))),
        )

    def create(self, data: ExpenseCreate) -> ExpenseOut:
        return self.expenses.create(self._to_save(data))

    def update(self, expense_id: UUID4, data: ExpenseCreate) -> ExpenseOut:
        self.get_one(expense_id)
        return self.expenses.update(expense_id, self._to_save(data))

    def delete(self, expense_id: UUID4) -> ExpenseOut:
        expense = self.get_one(expense_id)
        self.expenses.delete(expense_id)
        return expense

    def record_plan(self, plan_id: UUID4, data: PlanExpenseCreate) -> ExpenseOut:
        """
        The shopping of a plan is done in one shop: keep the expense.

        The estimate of the application for that shop stays beside what the person paid.
        """
        if self.repos.pe_shopping_plans.get_one(plan_id) is None:
            raise PersonalNotFound("Shopping plan not found.")
        budget = PriceService(self.repos).plan_budget(plan_id, self.user_id)
        # The estimate is what the plan shows for the shop: the whole shopping.
        estimate = next((total.basket_total for total in budget.stores if total.store == data.store), None)
        amount = data.amount if data.amount is not None else estimate
        if not amount or amount <= 0:
            raise PersonalError("EXPENSE_AMOUNT_REQUIRED", "Give the amount that you paid.")
        return self.create(
            ExpenseCreate(
                spent_on=data.spent_on or datetime.now(UTC).date(),
                store=data.store,
                amount=amount,
                estimated_amount=estimate,
                plan_id=plan_id,
                note=data.note,
            )
        )

    # ================================================================
    # Settings

    def get_settings(self) -> BudgetSettingsOut:
        rows = self.settings.get_all(limit=1)
        return rows[0] if rows else BudgetSettingsOut()

    def set_settings(self, data: BudgetSettingsUpdate) -> BudgetSettingsOut:
        save = data.cast(BudgetSettingsSave, group_id=self.repos.group_id, household_id=self.repos.household_id)
        rows = self.settings.get_all(limit=1)
        if rows and rows[0].id is not None:
            return self.settings.update(rows[0].id, save)
        return self.settings.create(save)

    # ================================================================
    # Summary

    def summary(self, months: int = 12, today: date | None = None) -> BudgetSummaryOut:
        """The expenses of the last months, the current month included."""
        today = today or datetime.now(UTC).date()
        months = max(1, min(months, MAX_MONTHS))
        current_first = today.replace(day=1)
        first = _add_months(current_first, -(months - 1))
        after = _add_months(current_first, 1)

        buckets: dict[str, dict[str, tuple[Decimal, int]]] = {
            _month_key(_add_months(first, offset)): {} for offset in range(months)
        }
        stores: dict[str, tuple[Decimal, int]] = {}
        checked, estimated, paid = 0, Decimal("0"), Decimal("0")
        for expense in self.expenses.get_all():
            if not first <= expense.spent_on < after:
                continue
            amount = to_decimal(expense.amount)
            bucket = buckets[_month_key(expense.spent_on)]
            for totals in (bucket, stores):
                total, count = totals.get(expense.store, (Decimal("0"), 0))
                totals[expense.store] = (total + amount, count + 1)
            if expense.estimated_amount:
                checked += 1
                estimated += to_decimal(expense.estimated_amount)
                paid += amount

        settings = self.get_settings()
        month_list = [_month(key, bucket) for key, bucket in buckets.items()]
        out = BudgetSummaryOut(
            monthly_target=settings.monthly_target,
            usual_store=settings.usual_store,
            months=month_list,
            current=month_list[-1],
            stores=_store_totals(stores),
            estimate_check=BudgetEstimateCheck(count=checked, estimated=float(estimated), paid=float(paid)),
        )
        out.total = float(sum((to_decimal(month.total) for month in month_list), Decimal("0")))
        out.expense_count = sum(month.count for month in month_list)
        if settings.monthly_target is not None:
            out.remaining = float(money(to_decimal(settings.monthly_target) - to_decimal(out.current.total)))

        # The current month is not complete, and the months before the first expense say nothing.
        complete = month_list[:-1]
        started = next((index for index, month in enumerate(complete) if month.count), None)
        if started is not None:
            history = complete[started:]
            mean = sum((to_decimal(month.total) for month in history), Decimal("0")) / len(history)
            out.average_month = float(money(mean))
        return out

    # ================================================================
    # Cost of the meals

    def _store(self, store: str | None) -> str | None:
        """The shop that prices the meals: the one of the request, or else the usual shop of the household."""
        if store is not None:
            return " ".join(store.split()).lower() or None
        return self.get_settings().usual_store

    def _recipe_costs(self, points: dict[UUID4, list[PricePoint]]) -> dict[UUID4, RecipeCostSummary]:
        units: dict[UUID4, UnitInfo | None] = {
            unit.id: unit_info(unit) for unit in self.repos.ingredient_units.get_all()
        }
        rows: dict[UUID4, list] = {}
        for row in self.repos.pe_recipe_ingredient_rows():
            rows.setdefault(row.recipe_id, []).append(row)

        costs: dict[UUID4, RecipeCostSummary] = {}
        for recipe in self.repos.pe_recipe_overviews():
            needs: list[Need] = needs_from_rows(recipe.id, recipe.name or "", rows, units)
            cost = cost_needs(needs, points)
            servings = recipe.recipe_servings or 0
            summary = RecipeCostSummary(
                recipe_id=recipe.id,
                recipe_slug=recipe.slug,
                recipe_name=recipe.name or "",
                servings=servings,
                priced_ingredients=cost.priced_ingredients,
                ingredient_count=cost.ingredient_count,
            )
            # A cost that leaves out most of the ingredients would look cheap and be wrong: it is not shown.
            if cost.ingredient_count and cost.priced_ingredients / cost.ingredient_count >= COST_COVERAGE:
                summary.total = cost.total
                if servings > 0:
                    summary.per_serving = float(money(to_decimal(cost.total) / to_decimal(servings)))
            costs[recipe.id] = summary
        return costs

    def recipe_costs(self, store: str | None = None) -> RecipeCostsOut:
        """What each recipe costs, from the prices that the household keeps."""
        store = self._store(store)
        costs = list(self._recipe_costs(PriceService(self.repos).price_points(store=store)).values())
        costs.sort(
            key=lambda cost: (
                cost.per_serving is None,
                cost.per_serving if cost.per_serving is not None else 0,
                cost.recipe_name.lower(),
            )
        )
        return RecipeCostsOut(
            store=store,
            recipes=costs,
            priced_count=sum(1 for cost in costs if cost.total is not None),
        )

    def meal_costs(self, date_from: date, date_to: date, store: str | None = None) -> MealCostsOut:
        """What the meals of the meal plan cost in a range of days."""
        if date_to < date_from:
            raise PersonalError("DATE_RANGE_INVALID", "The end date is before the start date.")
        if (date_to - date_from).days > MAX_MEAL_DAYS:
            raise PersonalError("DATE_RANGE_TOO_LONG", "The range of days is too long.")

        store = self._store(store)
        out = MealCostsOut(date_from=date_from, date_to=date_to, store=store)
        entries = self.repos.pe_mealplan_entries_between(date_from, date_to)
        if not entries:
            return out

        costs = self._recipe_costs(PriceService(self.repos).price_points(store=store))
        total = Decimal("0")
        for entry in entries:
            cost = costs.get(entry.recipe_id)
            if cost is None:
                continue
            scale = to_decimal(entry.recipe_scale or 1)
            meal = MealCost(
                date=entry.date,
                entry_type=entry.entry_type or "",
                recipe_id=cost.recipe_id,
                recipe_slug=cost.recipe_slug,
                recipe_name=cost.recipe_name,
                servings=float(to_decimal(cost.servings) * scale),
                per_serving=cost.per_serving,
                priced_ingredients=cost.priced_ingredients,
                ingredient_count=cost.ingredient_count,
            )
            if cost.total is not None:
                scaled = money(to_decimal(cost.total) * scale)
                meal.total = float(scaled)
                total += scaled
                out.priced_meals += 1
            out.meals.append(meal)
        out.total = float(total)
        return out


def _store_totals(totals: dict[str, tuple[Decimal, int]]) -> list[BudgetStoreTotal]:
    stores = [
        BudgetStoreTotal(store=store, total=float(total), count=count) for store, (total, count) in totals.items()
    ]
    stores.sort(key=lambda entry: (-entry.total, entry.store))
    return stores


def _month(key: str, bucket: dict[str, tuple[Decimal, int]]) -> BudgetMonth:
    return BudgetMonth(
        month=key,
        total=float(sum((total for total, _ in bucket.values()), Decimal("0"))),
        count=sum(count for _, count in bucket.values()),
        stores=_store_totals(bucket),
    )
