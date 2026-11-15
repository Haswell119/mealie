from functools import cached_property

from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.person import PersonCreate, PersonOut, PersonPagination
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.person_service import PersonService

from ._base import run

router = APIRouter(prefix="/households/persons", tags=["Personal: Persons"])


@controller(router)
class PersonController(BaseUserController):
    @cached_property
    def service(self) -> PersonService:
        return PersonService(self.repos)

    @router.get("", response_model=PersonPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_persons.page_all(pagination=q, override=PersonOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=PersonOut, status_code=201)
    def create_one(self, data: PersonCreate):
        return run(lambda: self.service.create(data, self.user.id))

    @router.get("/{item_id}", response_model=PersonOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/{item_id}", response_model=PersonOut)
    def update_one(self, item_id: UUID4, data: PersonCreate):
        return run(lambda: self.service.update(item_id, data, self.user.id))

    @router.delete("/{item_id}", response_model=PersonOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))
