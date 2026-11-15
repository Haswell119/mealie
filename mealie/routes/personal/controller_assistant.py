from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.assistant import (
    AiProposalOut,
    AiProposalPagination,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantStatus,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.assistant_service import AssistantService
from mealie.services.personal.proposal_service import ProposalService
from mealie.services.recipe.recipe_service import RecipeService

from ._base import run

router = APIRouter(prefix="/households/assistant", tags=["Personal: Assistant"])


@controller(router)
class AssistantController(BaseUserController):
    def _recipe_service(self) -> RecipeService:
        return RecipeService(self.repos, self.user, self.household, translator=self.translator)

    @property
    def proposals(self) -> ProposalService:
        return ProposalService(self.repos, self.user.id, self._recipe_service)

    @router.get("/status", response_model=AssistantStatus)
    def get_status(self):
        return AssistantService(self.repos, self.user.id).status()

    @router.post("/chat", response_model=AssistantChatResponse)
    async def chat(self, data: AssistantChatRequest):
        return await AssistantService(self.repos, self.user.id).chat(data)

    @router.get("/proposals", response_model=AiProposalPagination)
    def get_proposals(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_ai_proposals.page_all(pagination=q, override=AiProposalOut)
        response.set_pagination_guides(router.url_path_for("get_proposals"), q.model_dump())
        return response

    @router.get("/proposals/{item_id}", response_model=AiProposalOut)
    def get_proposal(self, item_id: UUID4):
        return run(lambda: self.proposals.get_one(item_id))

    @router.post("/proposals/{item_id}/accept", response_model=AiProposalOut)
    def accept_proposal(self, item_id: UUID4):
        return run(lambda: self.proposals.accept(item_id))

    @router.post("/proposals/{item_id}/reject", response_model=AiProposalOut)
    def reject_proposal(self, item_id: UUID4):
        return run(lambda: self.proposals.reject(item_id))

    @router.delete("/proposals/{item_id}", response_model=AiProposalOut)
    def delete_proposal(self, item_id: UUID4):
        return run(lambda: self.proposals.delete(item_id))
