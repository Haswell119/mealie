from functools import cached_property

from fastapi import APIRouter, Query

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.ideas import IdeaFeedOut, IdeaGenerateOut, IdeaGenerateRequest
from mealie.services.personal.idea_service import MAX_LIMIT, IdeaService

from ._base import run

router = APIRouter(prefix="/households/ideas", tags=["Personal: Ideas"])


@controller(router)
class IdeaController(BaseUserController):
    @cached_property
    def service(self) -> IdeaService:
        return IdeaService(self.repos, self.user.id)

    @router.get("", response_model=IdeaFeedOut)
    def get_feed(
        self,
        tags: list[str] = Query([], description="Keep the cards that carry every one of these tags."),
        search: str | None = Query(None, max_length=100),
        restrictions: list[str] = Query(
            [], description="Check these restrictions in place of the restrictions of the user."
        ),
        max_cost: float | None = Query(None, gt=0, alias="maxCost", description="The highest cost of one serving."),
        include_incompatible: bool = Query(False, alias="includeIncompatible"),
        limit: int = Query(30, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
        seed: str | None = Query(None, max_length=40, description="Fixes the order. The default is the day."),
    ):
        """
        The recipes and the inspirations of the household, each with its tags, the most fitting first.

        Everything is computed from the data of the application: nothing leaves it.
        """
        return run(
            lambda: self.service.feed(
                tags=tags,
                search=search,
                restrictions=restrictions,
                max_cost=max_cost,
                include_incompatible=include_incompatible,
                limit=limit,
                offset=offset,
                seed=seed,
            )
        )

    @router.post("/generate", response_model=IdeaGenerateOut)
    async def generate(self, data: IdeaGenerateRequest):
        """Ask the AI provider for new ideas. Each idea is kept as an inspiration, never as a recipe."""
        return await self.service.generate(data)
