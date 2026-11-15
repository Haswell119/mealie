from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.assistant import AiProposalOut, AiProposalSave
from mealie.schema.personal.enums import AiProposalKind, AiProposalStatus
from mealie.schema.personal.inspiration import InspirationDraft
from mealie.schema.personal.meal_event import MealEventMenuItemCreate, MealEventVariantCreate
from mealie.schema.personal.shopping_plan import ShoppingPlanApply, ShoppingPlanCreate
from mealie.schema.recipe.recipe import RecipeDraft
from mealie.schema.recipe.request_helpers import RecipeDuplicate
from mealie.services.recipe.recipe_service import RecipeService

from .errors import PersonalError, PersonalNotFound
from .inspiration_service import InspirationService
from .meal_event_service import MealEventService
from .shopping_plan_service import ShoppingPlanService


class ProposalService:
    """
    Changes that the assistant suggests.

    The assistant can only create a proposal. A proposal changes the data of the application when the user
    accepts it, and only then.
    """

    def __init__(
        self, repos: AllRepositories, user_id: UUID4, recipe_service: Callable[[], RecipeService] | None = None
    ) -> None:
        self.repos = repos
        self.user_id = user_id
        self.proposals = repos.pe_ai_proposals
        self._recipe_service = recipe_service

    def get_one(self, proposal_id: UUID4) -> AiProposalOut:
        proposal = self.proposals.get_one(proposal_id)
        if proposal is None:
            raise PersonalNotFound("Proposal not found.")
        return proposal

    def create(
        self, kind: AiProposalKind, title: str, payload: dict[str, Any], event_id: UUID4 | None = None
    ) -> AiProposalOut:
        return self.proposals.create(
            AiProposalSave(
                group_id=self.repos.group_id,  # type: ignore[arg-type]
                household_id=self.repos.household_id,  # type: ignore[arg-type]
                kind=kind,
                title=title[:200] or kind,
                payload=payload,
                event_id=event_id,
                created_by=self.user_id,
            )
        )

    def reject(self, proposal_id: UUID4) -> AiProposalOut:
        self._pending(proposal_id)
        return self.proposals.update(
            proposal_id, {"status": AiProposalStatus.REJECTED, "decided_at": datetime.now(UTC)}
        )

    def delete(self, proposal_id: UUID4) -> AiProposalOut:
        proposal = self.get_one(proposal_id)
        self.proposals.delete(proposal_id)
        return proposal

    def accept(self, proposal_id: UUID4) -> AiProposalOut:
        """Apply a proposal. The user calls this; the assistant has no tool that does."""
        proposal = self._pending(proposal_id)
        payload = proposal.payload or {}

        handlers = {
            AiProposalKind.SHOPPING_LIST: self._accept_shopping_list,
            AiProposalKind.MENU: self._accept_menu,
            AiProposalKind.RECIPE_VARIANT: self._accept_recipe_variant,
            AiProposalKind.SUBSTITUTION: self._accept_recipe_variant,
            AiProposalKind.RECIPE_DRAFT: self._accept_recipe_draft,
        }
        result = handlers[proposal.kind](payload)
        return self.proposals.update(
            proposal_id,
            {"status": AiProposalStatus.ACCEPTED, "decided_at": datetime.now(UTC), "result": result},
        )

    def _pending(self, proposal_id: UUID4) -> AiProposalOut:
        proposal = self.get_one(proposal_id)
        if proposal.status != AiProposalStatus.PENDING:
            raise PersonalError("PROPOSAL_DECIDED", "This proposal is already accepted or rejected.")
        return proposal

    # ================================================================
    # Handlers

    def _accept_shopping_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        service = ShoppingPlanService(self.repos, self.user_id)
        plan = service.create(ShoppingPlanCreate.model_validate(payload["plan"]))
        applied = service.apply(plan.id, ShoppingPlanApply())
        return {
            "plan_id": str(plan.id),
            "shopping_list_id": str(applied.shopping_list_id),
            "created": applied.created,
            "updated": applied.updated,
        }

    def _accept_menu(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Add the suggested dishes to the menu of the event. The dishes already on the menu stay."""
        service = MealEventService(self.repos, self.user_id)
        event = service.get_one(payload["event_id"])

        menu = [
            MealEventMenuItemCreate(
                id=item.id,
                course=item.course,
                title=item.title,
                variants=[
                    MealEventVariantCreate(
                        id=variant.id,
                        recipe_id=variant.recipe_id,
                        label=variant.label,
                        portions_override=variant.portions_override,
                    )
                    for variant in item.variants
                ],
            )
            for item in event.menu_items
        ]
        for item in payload.get("items", []):
            menu.append(
                MealEventMenuItemCreate(
                    course=item.get("course", "MAIN"),
                    title=item.get("title"),
                    variants=[MealEventVariantCreate(recipe_id=item["recipe_id"], label=item.get("label"))],
                )
            )
        service.set_menu(event.id, menu)
        return {"event_id": str(event.id), "added": len(payload.get("items", []))}

    def _accept_recipe_variant(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new recipe from an existing one, with the suggested substitutions.

        The quantities and the units come from the original recipe. A replaced ingredient becomes plain
        text, so it stays unverified until the user links it to a food and verifies that food.
        """
        if self._recipe_service is None:
            raise PersonalError("RECIPE_SERVICE_MISSING", "The recipe cannot be created here.")
        recipe_service = self._recipe_service()

        source = recipe_service.get_one(payload["recipe_id"])
        title = str(payload.get("title") or "variante").strip()
        copy = recipe_service.duplicate_one(source.slug, RecipeDuplicate(name=f"{source.name} – {title}"))

        substitutions = payload.get("substitutions", [])
        matched: set[int] = set()
        for ingredient in copy.recipe_ingredient:
            food_name = getattr(ingredient.food, "name", "") or ""
            text = f"{food_name} {ingredient.note or ''}".lower()
            for index, substitution in enumerate(substitutions):
                target = str(substitution.get("ingredient") or "").strip().lower()
                if target and target in text:
                    ingredient.food = None
                    ingredient.note = str(substitution.get("replacement") or "").strip()
                    ingredient.display = ""
                    matched.add(index)
                    break

        if payload.get("notes"):
            copy.description = f"{copy.description or ''}\n\n{payload['notes']}".strip()

        updated = recipe_service.update_one(copy.slug, RecipeDraft.model_validate(copy.model_dump(round_trip=True)))
        unmatched = [substitutions[i].get("ingredient") for i in range(len(substitutions)) if i not in matched]
        return {"recipe_id": str(updated.id), "recipe_slug": updated.slug, "unmatched": unmatched}

    def _accept_recipe_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Store the suggested draft on its inspiration. The draft is still not a recipe."""
        service = InspirationService(self.repos, self._recipe_service)
        draft = InspirationDraft.model_validate(payload["draft"])
        inspiration = service.set_draft(payload["inspiration_id"], draft)
        return {"inspiration_id": str(inspiration.id)}
