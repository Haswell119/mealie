from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.enums import RestrictionScope
from mealie.schema.personal.meal_event import FindingOut, RecipeComplianceOut

from .dietary_service import DietaryService
from .engine.compliance import evaluate_recipe
from .errors import PersonalNotFound
from .recipe_needs import RecipeReader


class RecipeComplianceService:
    """Checks one recipe against restrictions, without an event."""

    def __init__(self, repos: AllRepositories, user_id: UUID4) -> None:
        self.repos = repos
        self.user_id = user_id
        self.dietary = DietaryService(repos)
        self.reader = RecipeReader(repos)

    def owner_restrictions(self) -> dict[str, RestrictionScope]:
        """The restrictions of the person who uses the application, with the scope of each."""
        by_id = self.dietary.restrictions_by_id()
        result: dict[str, RestrictionScope] = {}
        for person in self.repos.pe_persons.multi_query({"linked_user_id": self.user_id}):
            for row in person.restrictions:
                if row.restriction_id in by_id:
                    result[by_id[row.restriction_id].key] = row.default_scope
        return result

    def check(self, recipe_id: UUID4, restriction_keys: list[str] | None = None) -> RecipeComplianceOut:
        """
        Check a recipe. Without a list of restrictions, use the restrictions of the user.

        A tool that is flagged for cross-contamination counts for the restrictions that the user applies
        to the whole preparation.
        """
        recipe = self.reader.get(recipe_id)
        if recipe is None:
            raise PersonalNotFound("Recipe not found.")

        owner = self.owner_restrictions()
        known = set(self.dietary.restrictions_by_key())
        keys = {key for key in restriction_keys if key in known} if restriction_keys else set(owner)
        tool_keys = {key for key in keys if owner.get(key) == RestrictionScope.ENTIRE_PREPARATION}

        result = evaluate_recipe(
            self.reader.ingredient_views(recipe),
            keys,
            self.dietary.status_book(),
            self.reader.tool_views(recipe),
            tool_check_keys=tool_keys,
        )
        return RecipeComplianceOut(
            recipe_id=recipe.id,
            recipe_name=recipe.name or "",
            recipe_slug=recipe.slug or "",
            restriction_keys=sorted(keys),
            status=result.status_for(keys),
            statuses=dict(sorted(result.statuses.items())),
            findings=[
                FindingOut(
                    restriction_key=finding.restriction_key,
                    status=finding.status,
                    code=finding.code,
                    subject=finding.subject,
                    kind=finding.kind,
                    term=finding.term,
                    detail=finding.detail,
                    food_id=finding.food_id,
                    tool_id=finding.tool_id,
                    recipe_id=finding.recipe_id,
                    recipe_name=finding.recipe_name,
                )
                for finding in result.findings
            ],
        )
