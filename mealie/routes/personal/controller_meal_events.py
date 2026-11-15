from functools import cached_property

from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.meal_event import (
    MealEventAnalysisOut,
    MealEventAssignmentSet,
    MealEventCreate,
    MealEventGuestCreate,
    MealEventMenuItemCreate,
    MealEventOut,
    MealEventOverrideCreate,
    MealEventPagination,
    MealEventStatusUpdate,
    MealEventSummary,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.meal_event_service import MealEventService

from ._base import run

router = APIRouter(prefix="/households/meal-events", tags=["Personal: Meal Events"])


@controller(router)
class MealEventController(BaseUserController):
    @cached_property
    def service(self) -> MealEventService:
        return MealEventService(self.repos, self.user.id)

    @router.get("", response_model=MealEventPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_meal_events.page_all(pagination=q, override=MealEventSummary)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=MealEventOut, status_code=201)
    def create_one(self, data: MealEventCreate):
        return run(lambda: self.service.create(data))

    @router.get("/{item_id}", response_model=MealEventOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/{item_id}", response_model=MealEventOut)
    def update_one(self, item_id: UUID4, data: MealEventCreate):
        return run(lambda: self.service.update(item_id, data))

    @router.delete("/{item_id}", response_model=MealEventOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))

    @router.put("/{item_id}/guests", response_model=MealEventOut)
    def set_guests(self, item_id: UUID4, data: list[MealEventGuestCreate]):
        return run(lambda: self.service.set_guests(item_id, data))

    @router.put("/{item_id}/menu", response_model=MealEventOut)
    def set_menu(self, item_id: UUID4, data: list[MealEventMenuItemCreate]):
        return run(lambda: self.service.set_menu(item_id, data))

    @router.put("/{item_id}/assignments", response_model=MealEventOut)
    def set_assignment(self, item_id: UUID4, data: MealEventAssignmentSet):
        return run(lambda: self.service.set_assignment(item_id, data))

    @router.post("/{item_id}/overrides", response_model=MealEventOut, status_code=201)
    def add_override(self, item_id: UUID4, data: MealEventOverrideCreate):
        return run(lambda: self.service.add_override(item_id, data))

    @router.delete("/{item_id}/overrides/{override_id}", response_model=MealEventOut)
    def delete_override(self, item_id: UUID4, override_id: UUID4):
        return run(lambda: self.service.delete_override(item_id, override_id))

    @router.put("/{item_id}/status", response_model=MealEventOut)
    def set_status(self, item_id: UUID4, data: MealEventStatusUpdate):
        return run(lambda: self.service.set_status(item_id, data))

    @router.get("/{item_id}/analysis", response_model=MealEventAnalysisOut)
    def get_analysis(self, item_id: UUID4):
        return run(lambda: self.service.analyze(item_id))
