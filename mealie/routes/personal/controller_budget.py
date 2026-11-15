from datetime import date
from functools import cached_property

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.budget import (
    BudgetSettingsOut,
    BudgetSettingsUpdate,
    BudgetSummaryOut,
    ExpenseCreate,
    ExpenseOut,
    ExpensePagination,
    MealCostsOut,
    PlanExpenseCreate,
    RecipeCostsOut,
    StoreMatchOut,
    StoreMatchRequest,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.budget_service import MAX_MONTHS, BudgetService
from mealie.services.personal.store_match_service import StoreMatchService

from ._base import run

router = APIRouter(prefix="/households/budget", tags=["Personal: Budget"])
plan_router = APIRouter(prefix="/households/shopping-plans", tags=["Personal: Budget"])


@controller(router)
class BudgetController(BaseUserController):
    @cached_property
    def service(self) -> BudgetService:
        return BudgetService(self.repos, self.user.id)

    @router.get("/summary", response_model=BudgetSummaryOut)
    def get_summary(self, months: int = Query(12, ge=1, le=MAX_MONTHS)):
        """The expenses of the last months, by month and by shop."""
        return run(lambda: self.service.summary(months))

    @router.get("/settings", response_model=BudgetSettingsOut)
    def get_settings(self):
        return self.service.get_settings()

    @router.put("/settings", response_model=BudgetSettingsOut)
    def set_settings(self, data: BudgetSettingsUpdate):
        return run(lambda: self.service.set_settings(data))

    @router.get("/meals", response_model=MealCostsOut)
    def get_meal_costs(
        self,
        date_from: date = Query(..., alias="dateFrom"),
        date_to: date = Query(..., alias="dateTo"),
        store: str | None = Query(None, max_length=60, description="Empty takes the cheapest price of each food."),
    ):
        """What the meals of the meal plan cost. Without `store`, the usual shop of the household prices them."""
        return run(lambda: self.service.meal_costs(date_from, date_to, store))

    @router.get("/recipes", response_model=RecipeCostsOut)
    def get_recipe_costs(self, store: str | None = Query(None, max_length=60)):
        return run(lambda: self.service.recipe_costs(store))

    @router.get("/expenses", response_model=ExpensePagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_expenses.page_all(pagination=q, override=ExpenseOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("/expenses", response_model=ExpenseOut, status_code=201)
    def create_one(self, data: ExpenseCreate):
        return run(lambda: self.service.create(data))

    @router.get("/expenses/{item_id}", response_model=ExpenseOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/expenses/{item_id}", response_model=ExpenseOut)
    def update_one(self, item_id: UUID4, data: ExpenseCreate):
        return run(lambda: self.service.update(item_id, data))

    @router.delete("/expenses/{item_id}", response_model=ExpenseOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))


@controller(plan_router)
class PlanBudgetActionsController(BaseUserController):
    @plan_router.post("/{item_id}/store-match", response_model=StoreMatchOut)
    def match_stores(self, item_id: UUID4, data: StoreMatchRequest):
        """
        Search the shops for the products of each line of the plan. Nothing is stored.

        A request to the price service carries the name of a food and the names of the shops, nothing else.
        """
        return run(lambda: StoreMatchService(self.repos, self.user.id).match(item_id, data))

    @plan_router.post("/{item_id}/expense", response_model=ExpenseOut, status_code=201)
    def record_expense(self, item_id: UUID4, data: PlanExpenseCreate):
        """The shopping of the plan is done: keep what it cost, beside the estimate."""
        return run(lambda: BudgetService(self.repos, self.user.id).record_plan(item_id, data))
