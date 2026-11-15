from functools import cached_property

from fastapi import APIRouter
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.dietary import (
    DietaryRestrictionCreate,
    DietaryRestrictionOut,
    FoodBulkVerify,
    FoodComplianceOut,
    FoodRestrictionStatusOut,
    FoodRestrictionStatusUpdate,
    ToolRestrictionStatusCreate,
    ToolRestrictionStatusOut,
)
from mealie.services.personal.dietary_service import DietaryService

from ._base import run

router = APIRouter(prefix="/households/dietary", tags=["Personal: Dietary Restrictions"])


@controller(router)
class DietaryController(BaseUserController):
    @cached_property
    def service(self) -> DietaryService:
        return DietaryService(self.repos)

    @router.get("/restrictions", response_model=list[DietaryRestrictionOut])
    def get_restrictions(self):
        return self.service.ensure_defaults()

    @router.post("/restrictions", response_model=DietaryRestrictionOut, status_code=201)
    def create_restriction(self, data: DietaryRestrictionCreate):
        return run(lambda: self.service.create_restriction(data))

    @router.put("/restrictions/{restriction_id}", response_model=DietaryRestrictionOut)
    def update_restriction(self, restriction_id: UUID4, data: DietaryRestrictionCreate):
        return run(lambda: self.service.update_restriction(restriction_id, data))

    @router.delete("/restrictions/{restriction_id}", response_model=DietaryRestrictionOut)
    def delete_restriction(self, restriction_id: UUID4):
        return run(lambda: self.service.delete_restriction(restriction_id))

    @router.get("/foods/{food_id}", response_model=FoodComplianceOut)
    def get_food_compliance(self, food_id: UUID4):
        return run(lambda: self.service.food_compliance(food_id))

    @router.put("/foods/{food_id}/restrictions/{restriction_id}", response_model=FoodRestrictionStatusOut)
    def set_food_status(self, food_id: UUID4, restriction_id: UUID4, data: FoodRestrictionStatusUpdate):
        return run(lambda: self.service.set_food_status(food_id, restriction_id, data, self.user.id))

    @router.delete("/foods/{food_id}/restrictions/{restriction_id}", status_code=204)
    def clear_food_status(self, food_id: UUID4, restriction_id: UUID4) -> None:
        run(lambda: self.service.clear_food_status(food_id, restriction_id))

    @router.post("/foods/bulk", response_model=list[FoodRestrictionStatusOut])
    def set_food_status_bulk(self, data: FoodBulkVerify):
        update = FoodRestrictionStatusUpdate(status=data.status, reason=data.reason)
        return run(
            lambda: [
                self.service.set_food_status(food_id, data.restriction_id, update, self.user.id)
                for food_id in data.food_ids
            ]
        )

    @router.get("/tools", response_model=list[ToolRestrictionStatusOut])
    def get_tool_flags(self):
        return self.service.tool_flags()

    @router.post("/tools", response_model=ToolRestrictionStatusOut, status_code=201)
    def flag_tool(self, data: ToolRestrictionStatusCreate):
        return run(lambda: self.service.flag_tool(data))

    @router.delete("/tools/{status_id}", response_model=ToolRestrictionStatusOut)
    def unflag_tool(self, status_id: UUID4):
        return run(lambda: self.service.unflag_tool(status_id))
