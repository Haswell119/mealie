"""The functions that the assistant may call. Each one reads data or creates a proposal; none changes data."""

from typing import Any
from uuid import UUID

from pydantic import UUID4, ValidationError

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.assistant import AiProposalOut
from mealie.schema.personal.enums import AiProposalKind, MealCourse, ShoppingPlanSource
from mealie.schema.personal.shopping_plan import ShoppingPlanCreate, ShoppingPlanRecipeEntry
from mealie.schema.response.pagination import PaginationQuery

from .assistant_privacy import Anonymizer
from .dietary_service import DietaryService
from .engine.compliance import evaluate_recipe
from .engine.rules import classify_text
from .errors import PersonalError
from .meal_event_service import MealEventService
from .pantry_service import PantryService
from .proposal_service import ProposalService
from .recipe_needs import RecipeReader
from .shopping_plan_service import ShoppingPlanService

PENDING_MESSAGE = "Proposal created. Nothing changed. The user must accept it in the application."
SAFETY_NOTE = (
    "UNVERIFIED means that a person must check the label. Never state that a product is guaranteed free of an allergen."
)


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_ID = {"type": "string", "description": "A UUID returned by another function."}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    _function(
        "search_recipes",
        "Search the recipes of the user by text.",
        {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}},
        ["query"],
    ),
    _function("get_recipe", "Read one recipe: servings, ingredients, steps.", {"recipe_id": _ID}, ["recipe_id"]),
    _function("get_available_ingredients", "List the food in stock that the user confirmed as usable.", {}, []),
    _function(
        "get_event_guests",
        "Read the guests of a meal event as anonymous constraints. Names are never available.",
        {"event_id": _ID},
        ["event_id"],
    ),
    _function(
        "check_dietary_constraints",
        "Check a recipe against dietary restrictions with the rules of the application.",
        {
            "recipe_id": _ID,
            "restrictions": {"type": "array", "items": {"type": "string"}, "description": "Restriction keys."},
            "event_id": {**_ID, "description": "Use the restrictions of this event instead of a list of keys."},
        },
        ["recipe_id"],
    ),
    _function(
        "calculate_portions",
        "Compute the portions and the scale of each recipe of a meal event.",
        {"event_id": _ID},
        ["event_id"],
    ),
    _function(
        "propose_recipe_variant",
        "Suggest a variant of a recipe with substitutions. Creates a proposal that the user must accept.",
        {
            "recipe_id": _ID,
            "title": {"type": "string"},
            "substitutions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ingredient": {"type": "string"},
                        "replacement": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["ingredient", "replacement"],
                },
            },
            "notes": {"type": "string"},
            "event_id": _ID,
        },
        ["recipe_id", "title", "substitutions"],
    ),
    _function(
        "propose_menu",
        "Suggest dishes for a meal event. Creates a proposal that the user must accept.",
        {
            "event_id": _ID,
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "course": {"type": "string", "enum": [course.value for course in MealCourse]},
                        "recipe_id": _ID,
                        "label": {"type": "string"},
                    },
                    "required": ["recipe_id"],
                },
            },
        },
        ["event_id", "items"],
    ),
    _function(
        "draft_shopping_list",
        "Compute a shopping list for a meal event or for recipes. Creates a proposal that the user must accept.",
        {
            "event_id": _ID,
            "recipes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"recipe_id": _ID, "scale": {"type": "number", "exclusiveMinimum": 0}},
                    "required": ["recipe_id"],
                },
            },
        },
        [],
    ),
]


class AssistantTools:
    def __init__(self, repos: AllRepositories, user_id: UUID4, anonymizer: Anonymizer) -> None:
        self.repos = repos
        self.user_id = user_id
        self.anonymizer = anonymizer
        self.reader = RecipeReader(repos)
        self.dietary = DietaryService(repos)
        self.events = MealEventService(repos, user_id)
        self.shopping = ShoppingPlanService(repos, user_id)
        self.pantry = PantryService(repos)
        self.proposal_service = ProposalService(repos, user_id)
        self.proposals: list[AiProposalOut] = []

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one function. A failure becomes a result that the model can read, never an exception."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None or name not in {tool["function"]["name"] for tool in TOOL_DEFINITIONS}:
            return {"error": f"Unknown function '{name}'."}
        try:
            return handler(**arguments)
        except PersonalError as e:
            return {"error": e.message}
        except (TypeError, ValueError, KeyError, ValidationError) as e:
            return {"error": f"Invalid arguments: {e.__class__.__name__}"}

    @staticmethod
    def _uuid(value: Any) -> UUID:
        return value if isinstance(value, UUID) else UUID(str(value))

    def _recipe(self, recipe_id: Any):
        recipe = self.reader.get(self._uuid(recipe_id))
        if recipe is None:
            raise PersonalError("NOT_FOUND", "Recipe not found.")
        return recipe

    # ================================================================
    # Read

    def _tool_search_recipes(self, query: str, limit: int = 8) -> dict[str, Any]:
        page = self.repos.recipes.page_all(PaginationQuery(page=1, per_page=max(1, min(int(limit), 10)), search=query))
        return {
            "recipes": [
                {
                    "recipe_id": str(recipe.id),
                    "name": recipe.name,
                    "servings": recipe.recipe_servings,
                    "tags": [tag.name for tag in recipe.tags],
                    "categories": [category.name for category in recipe.recipe_category],
                }
                for recipe in page.items
            ]
        }

    def _tool_get_recipe(self, recipe_id: str) -> dict[str, Any]:
        recipe = self._recipe(recipe_id)
        return {
            "recipe_id": str(recipe.id),
            "name": recipe.name,
            "servings": recipe.recipe_servings,
            "ingredients": [view.display for view in self.reader.ingredient_views(recipe)],
            "steps": [(step.text or "")[:500] for step in recipe.recipe_instructions or []],
            "tools": [tool.name for tool in recipe.tools],
        }

    def _tool_get_available_ingredients(self) -> dict[str, Any]:
        foods = {food.id: food.name for food in self.repos.ingredient_foods.get_all()}
        units: dict[Any, str] = {}
        stock = []
        for entry in self.pantry.usable_stock():
            if entry.unit is not None:
                units[entry.unit.id] = entry.unit.name
            stock.append(
                {
                    "food": foods.get(entry.food_id, ""),
                    "quantity": float(entry.quantity),
                    "unit": entry.unit.name if entry.unit else "",
                }
            )
        return {"stock": stock}

    def _tool_get_event_guests(self, event_id: str) -> dict[str, Any]:
        event = self.events.get_one(self._uuid(event_id))
        analysis = self.events.analyze(event.id)

        guests = [
            {
                "guest": self.anonymizer.label(constrained.person_id),
                "constraints": [constraint.restriction_key for constraint in constrained.constraints],
            }
            for constrained in analysis.constraints.individual
        ]

        preferences = []
        for guest in event.guests:
            if not guest.attending:
                continue
            person = self.repos.pe_persons.get_one(guest.person_id)
            if person is None or not person.food_preferences:
                continue
            preferences.append(
                {
                    "guest": self.anonymizer.label(person.id),
                    "likes": [p.food.name for p in person.food_preferences if p.kind == "LIKE"],
                    "dislikes": [p.food.name for p in person.food_preferences if p.kind == "DISLIKE"],
                }
            )

        return {
            "guest_count": analysis.total_persons,
            "portions": analysis.total_portions,
            "constraints_for_every_portion": [
                {"restriction": c.restriction_key, "scope": c.scope, "severity": c.severity}
                for c in analysis.constraints.shared
            ],
            "constraints_for_one_guest": guests,
            "food_preferences": preferences,
            "note": "A constraint for every portion must hold for all dishes. Never relax a constraint.",
        }

    def _event_keys(self, event_id: Any) -> set[str]:
        analysis = self.events.analyze(self._uuid(event_id))
        keys = {constraint.restriction_key for constraint in analysis.constraints.shared}
        for constrained in analysis.constraints.individual:
            keys |= {constraint.restriction_key for constraint in constrained.constraints}
        return keys

    def _tool_check_dietary_constraints(
        self, recipe_id: str, restrictions: list[str] | None = None, event_id: str | None = None
    ) -> dict[str, Any]:
        recipe = self._recipe(recipe_id)
        known = set(self.dietary.restrictions_by_key())
        keys = self._event_keys(event_id) if event_id else {key for key in restrictions or [] if key in known}
        if not keys:
            return {"error": "Give an event_id or at least one known restriction key.", "known": sorted(known)}

        result = evaluate_recipe(
            self.reader.ingredient_views(recipe), keys, self.dietary.status_book(), self.reader.tool_views(recipe)
        )
        return {
            "recipe": recipe.name,
            "statuses": dict(sorted(result.statuses.items())),
            "issues": [
                {
                    "restriction": finding.restriction_key,
                    "status": finding.status,
                    "code": finding.code,
                    "ingredient": finding.subject,
                    "term": finding.term,
                }
                for finding in result.findings[:40]
            ],
            "note": SAFETY_NOTE,
        }

    def _tool_calculate_portions(self, event_id: str) -> dict[str, Any]:
        analysis = self.events.analyze(self._uuid(event_id))
        return {
            "guest_count": analysis.total_persons,
            "portions": analysis.total_portions,
            "menu": [
                {
                    "course": item.course,
                    "guests_without_a_compatible_dish": len(item.unassigned_person_ids),
                    "dishes": [
                        {
                            "recipe_id": str(variant.recipe_id),
                            "recipe": variant.recipe_name,
                            "label": variant.label,
                            "guests": len(variant.person_ids),
                            "portions": variant.portions,
                            "scale": variant.scale,
                            "status": variant.status,
                            "problem": variant.error,
                        }
                        for variant in item.variants
                    ],
                }
                for item in analysis.menu
            ],
        }

    # ================================================================
    # Proposals

    def _propose(self, kind: AiProposalKind, title: str, payload: dict[str, Any], event_id: Any = None) -> str:
        proposal = self.proposal_service.create(kind, title, payload, self._uuid(event_id) if event_id else None)
        self.proposals.append(proposal)
        return str(proposal.id)

    def _tool_propose_recipe_variant(
        self,
        recipe_id: str,
        title: str,
        substitutions: list[dict[str, Any]],
        notes: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        recipe = self._recipe(recipe_id)
        if event_id:
            self.events.get_one(self._uuid(event_id))
        keys = self._event_keys(event_id) if event_id else self.shopping._owner_restriction_keys()

        cleaned = []
        checks = []
        for substitution in substitutions[:30]:
            replacement = str(substitution.get("replacement") or "").strip()
            ingredient = str(substitution.get("ingredient") or "").strip()
            if not replacement or not ingredient:
                continue
            cleaned.append(
                {"ingredient": ingredient, "replacement": replacement, "reason": str(substitution.get("reason") or "")}
            )
            for key in sorted(keys):
                rule = classify_text(replacement, key)
                checks.append(
                    {
                        "replacement": replacement,
                        "restriction": key,
                        "status": rule.status if rule else "UNVERIFIED",
                        "code": rule.code if rule else "FREE_TEXT",
                    }
                )
        if not cleaned:
            return {"error": "No usable substitution."}

        payload = {
            "recipe_id": str(recipe.id),
            "recipe_name": recipe.name,
            "title": title,
            "substitutions": cleaned,
            "notes": notes,
            "checks": checks,
        }
        proposal_id = self._propose(AiProposalKind.RECIPE_VARIANT, f"{recipe.name} – {title}", payload, event_id)
        return {"proposal_id": proposal_id, "checks": checks, "status": "PENDING", "message": PENDING_MESSAGE}

    def _tool_propose_menu(self, event_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        event = self.events.get_one(self._uuid(event_id))
        keys = self._event_keys(event.id)
        book = self.dietary.status_book()

        entries = []
        for item in items[:12]:
            recipe = self._recipe(item.get("recipe_id"))
            course = item.get("course") if item.get("course") in {c.value for c in MealCourse} else "MAIN"
            statuses = evaluate_recipe(self.reader.ingredient_views(recipe), keys, book).statuses if keys else {}
            entries.append(
                {
                    "course": course,
                    "recipe_id": str(recipe.id),
                    "recipe_name": recipe.name,
                    "label": item.get("label"),
                    "statuses": dict(sorted(statuses.items())),
                }
            )
        if not entries:
            return {"error": "No dish."}

        payload = {"event_id": str(event.id), "items": entries}
        proposal_id = self._propose(AiProposalKind.MENU, f"Menu – {event.name}", payload, event.id)
        return {"proposal_id": proposal_id, "items": entries, "status": "PENDING", "message": PENDING_MESSAGE}

    def _tool_draft_shopping_list(
        self, event_id: str | None = None, recipes: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        if event_id:
            event = self.events.get_one(self._uuid(event_id))
            plan = ShoppingPlanCreate(name=event.name, source_type=ShoppingPlanSource.EVENT, event_id=event.id)
            title = f"Courses – {event.name}"
        elif recipes:
            entries = [
                ShoppingPlanRecipeEntry(recipe_id=self._uuid(entry["recipe_id"]), scale=float(entry.get("scale") or 1))
                for entry in recipes[:30]
            ]
            plan = ShoppingPlanCreate(name="Courses", source_type=ShoppingPlanSource.RECIPES, recipes=entries)
            title = "Courses"
        else:
            return {"error": "Give an event_id or a list of recipes."}

        # The application computes the quantities. The model only reads them.
        preview = self.shopping.compute_adhoc(plan)
        lines = [
            {
                "item": line.display,
                "needed": line.quantity_needed,
                "from_stock": line.quantity_from_stock,
                "to_buy": line.quantity_to_buy,
                "unit": line.unit_name,
                "to_check": [f"{check.restriction_key}:{check.status}" for check in line.checks],
            }
            for line in preview.lines
        ]
        payload = {"plan": plan.model_dump(mode="json"), "lines": lines}
        proposal_id = self._propose(AiProposalKind.SHOPPING_LIST, title, payload, event_id)
        return {
            "proposal_id": proposal_id,
            "lines": lines,
            "problems": [issue.code for issue in preview.issues],
            "status": "PENDING",
            "message": PENDING_MESSAGE,
            "note": SAFETY_NOTE,
        }
