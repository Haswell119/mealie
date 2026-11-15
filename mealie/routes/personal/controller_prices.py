from functools import cached_property

from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.enums import RetailStore
from mealie.schema.personal.price import (
    FoodPriceCreate,
    FoodPriceOut,
    FoodPricePagination,
    PlanBudgetOut,
    PriceOfferSearchOut,
    PriceRefreshOut,
    PriceSourceStatus,
    RecipeCostOut,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.price_service import PriceService

from ._base import run

router = APIRouter(prefix="/households/prices", tags=["Personal: Prices"])
budget_router = APIRouter(prefix="/households/shopping-plans", tags=["Personal: Prices"])


@controller(router)
class PriceController(BaseUserController):
    @cached_property
    def service(self) -> PriceService:
        return PriceService(self.repos)

    @router.get("", response_model=FoodPricePagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_food_prices.page_all(pagination=q, override=FoodPriceOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=FoodPriceOut, status_code=201)
    def save_one(self, data: FoodPriceCreate):
        """Keep the price of a food in a shop. The food has one price for each shop: a new one replaces it."""
        return run(lambda: self.service.save(data))

    @router.get("/status", response_model=PriceSourceStatus)
    def get_status(self):
        return self.service.status()

    @router.get("/offers", response_model=PriceOfferSearchOut)
    def search_offers(self, query: str, store: RetailStore | None = None):
        """Search the price source. The request carries the search text and the shops, nothing else."""
        return run(lambda: self.service.search_offers(query, store))

    @router.post("/refresh", response_model=PriceRefreshOut)
    def refresh(self):
        return run(lambda: self.service.refresh())

    @router.get("/recipes/{recipe_id}", response_model=RecipeCostOut)
    def get_recipe_cost(self, recipe_id: UUID4):
        return run(lambda: self.service.recipe_cost(recipe_id))

    @router.get("/{item_id}", response_model=FoodPriceOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/{item_id}", response_model=FoodPriceOut)
    def update_one(self, item_id: UUID4, data: FoodPriceCreate):
        return run(lambda: self.service.update(item_id, data))

    @router.delete("/{item_id}", response_model=FoodPriceOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))


@controller(budget_router)
class PlanBudgetController(BaseUserController):
    @budget_router.get("/{item_id}/budget", response_model=PlanBudgetOut)
    def get_budget(self, item_id: UUID4):
        """What the plan costs in each shop, from the prices that the household keeps."""
        return run(lambda: PriceService(self.repos).plan_budget(item_id, self.user.id))
