from functools import cached_property

from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.pantry import (
    FoodPackagingCreate,
    FoodPackagingOut,
    FoodPackagingPagination,
    PantryAdjust,
    PantryItemCreate,
    PantryItemOut,
    PantryItemPagination,
    PantryReceive,
    PantryReceiveOut,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.pantry_service import PantryService

from ._base import run

router = APIRouter(prefix="/households/pantry", tags=["Personal: Pantry"])
packaging_router = APIRouter(prefix="/households/packagings", tags=["Personal: Pantry"])


@controller(router)
class PantryController(BaseUserController):
    @cached_property
    def service(self) -> PantryService:
        return PantryService(self.repos)

    @router.get("", response_model=PantryItemPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_pantry_items.page_all(pagination=q, override=PantryItemOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=PantryItemOut, status_code=201)
    def create_one(self, data: PantryItemCreate):
        return run(lambda: self.service.create(data))

    @router.post("/receive", response_model=PantryReceiveOut)
    def receive(self, data: PantryReceive):
        return run(lambda: self.service.receive(data))

    @router.get("/{item_id}", response_model=PantryItemOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/{item_id}", response_model=PantryItemOut)
    def update_one(self, item_id: UUID4, data: PantryItemCreate):
        return run(lambda: self.service.update(item_id, data))

    @router.delete("/{item_id}", response_model=PantryItemOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))

    @router.post("/{item_id}/adjust", response_model=PantryItemOut)
    def adjust(self, item_id: UUID4, data: PantryAdjust):
        return run(lambda: self.service.adjust(item_id, data))

    @router.post("/{item_id}/confirm", response_model=PantryItemOut)
    def confirm(self, item_id: UUID4, usable: bool = True):
        return run(lambda: self.service.confirm(item_id, usable))


@controller(packaging_router)
class FoodPackagingController(BaseUserController):
    @cached_property
    def service(self) -> PantryService:
        return PantryService(self.repos)

    @packaging_router.get("", response_model=FoodPackagingPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_food_packagings.page_all(pagination=q, override=FoodPackagingOut)
        response.set_pagination_guides(packaging_router.url_path_for("get_all"), q.model_dump())
        return response

    @packaging_router.post("", response_model=FoodPackagingOut, status_code=201)
    def create_one(self, data: FoodPackagingCreate):
        return run(lambda: self.service.create_packaging(data))

    @packaging_router.put("/{item_id}", response_model=FoodPackagingOut)
    def update_one(self, item_id: UUID4, data: FoodPackagingCreate):
        return run(lambda: self.service.update_packaging(item_id, data))

    @packaging_router.delete("/{item_id}", response_model=FoodPackagingOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete_packaging(item_id))
