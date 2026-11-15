from functools import cached_property

from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.shopping_plan import (
    ShoppingPlanApply,
    ShoppingPlanApplyOut,
    ShoppingPlanConsumeOut,
    ShoppingPlanCreate,
    ShoppingPlanLineOut,
    ShoppingPlanOut,
    ShoppingPlanPagination,
    ShoppingPlanPreviewOut,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.shopping_plan_service import ShoppingPlanService

from ._base import run

router = APIRouter(prefix="/households/shopping-plans", tags=["Personal: Shopping Plans"])


@controller(router)
class ShoppingPlanController(BaseUserController):
    @cached_property
    def service(self) -> ShoppingPlanService:
        return ShoppingPlanService(self.repos, self.user.id)

    @router.get("", response_model=ShoppingPlanPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_shopping_plans.page_all(pagination=q, override=ShoppingPlanOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=ShoppingPlanOut, status_code=201)
    def create_one(self, data: ShoppingPlanCreate):
        return run(lambda: self.service.create(data))

    @router.get("/{item_id}", response_model=ShoppingPlanOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/{item_id}", response_model=ShoppingPlanOut)
    def update_one(self, item_id: UUID4, data: ShoppingPlanCreate):
        return run(lambda: self.service.update(item_id, data))

    @router.delete("/{item_id}", response_model=ShoppingPlanOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))

    @router.get("/{item_id}/lines", response_model=list[ShoppingPlanLineOut])
    def get_lines(self, item_id: UUID4):
        return run(lambda: self.service.get_lines(item_id))

    @router.get("/{item_id}/preview", response_model=ShoppingPlanPreviewOut)
    def get_preview(self, item_id: UUID4, restore_dismissed: bool = False):
        return run(lambda: self.service.preview(item_id, restore_dismissed))

    @router.post("/{item_id}/apply", response_model=ShoppingPlanApplyOut)
    def apply(self, item_id: UUID4, data: ShoppingPlanApply):
        return run(lambda: self.service.apply(item_id, data))

    @router.post("/{item_id}/consume", response_model=ShoppingPlanConsumeOut)
    def consume(self, item_id: UUID4):
        return run(lambda: self.service.consume(item_id))
