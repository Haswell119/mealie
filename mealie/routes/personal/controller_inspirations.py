from functools import cached_property

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.assistant import AiProposalOut
from mealie.schema.personal.enums import AiProposalKind
from mealie.schema.personal.inspiration import (
    InspirationCreate,
    InspirationOut,
    InspirationPagination,
    InspirationUpdate,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.assistant_service import AssistantService
from mealie.services.personal.errors import PersonalError
from mealie.services.personal.inspiration_service import MAX_IMAGE_BYTES, InspirationService
from mealie.services.personal.proposal_service import ProposalService
from mealie.services.recipe.recipe_service import RecipeService

from ._base import run

router = APIRouter(prefix="/households/inspirations", tags=["Personal: Inspirations"])


@controller(router)
class InspirationController(BaseUserController):
    def _recipe_service(self) -> RecipeService:
        return RecipeService(self.repos, self.user, self.household, translator=self.translator)

    @cached_property
    def service(self) -> InspirationService:
        return InspirationService(self.repos, self._recipe_service)

    @router.get("", response_model=InspirationPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_inspirations.page_all(pagination=q, override=InspirationOut)
        response.items = [self.service.with_recipe_slug(item) for item in response.items]
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=InspirationOut, status_code=201)
    def create_one(self, data: InspirationCreate):
        return run(lambda: self.service.create(data))

    @router.get("/{item_id}", response_model=InspirationOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.put("/{item_id}", response_model=InspirationOut)
    def update_one(self, item_id: UUID4, data: InspirationUpdate):
        return run(lambda: self.service.update(item_id, data))

    @router.delete("/{item_id}", response_model=InspirationOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))

    @router.post("/{item_id}/draft", response_model=InspirationOut)
    def start_draft(self, item_id: UUID4):
        return run(lambda: self.service.start_draft(item_id))

    @router.post("/{item_id}/validate", response_model=InspirationOut)
    def validate(self, item_id: UUID4):
        return run(lambda: self.service.validate(item_id))

    @router.post("/{item_id}/structure", response_model=AiProposalOut)
    async def structure(self, item_id: UUID4):
        """Ask the assistant for a draft of the recipe. The answer is a proposal, never a recipe."""
        inspiration = run(lambda: self.service.get_one(item_id))
        text = "\n".join(part for part in [inspiration.text, inspiration.url] if part)
        if not text.strip():
            run(lambda: self._raise("INSPIRATION_EMPTY", "Add a note to the inspiration first."))

        draft = await AssistantService(self.repos, self.user.id).structure_note(inspiration.title, text)
        if draft is None:
            run(
                lambda: self._raise("ASSISTANT_UNAVAILABLE", "The assistant is not available. Write the draft by hand.")
            )

        payload = {"inspiration_id": str(inspiration.id), "draft": draft.model_dump()}  # type: ignore[union-attr]
        return ProposalService(self.repos, self.user.id).create(
            AiProposalKind.RECIPE_DRAFT, f"Brouillon – {inspiration.title}", payload
        )

    @staticmethod
    def _raise(code: str, message: str) -> None:
        raise PersonalError(code, message)

    @router.put("/{item_id}/image", response_model=InspirationOut)
    async def set_image(self, item_id: UUID4, image: UploadFile):
        content = await image.read(MAX_IMAGE_BYTES + 1)
        return run(lambda: self.service.set_image(item_id, image.content_type, content))

    @router.get("/{item_id}/image", response_class=FileResponse)
    def get_image(self, item_id: UUID4):
        return FileResponse(run(lambda: self.service.image_path(item_id)))
