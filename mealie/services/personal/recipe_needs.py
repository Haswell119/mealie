"""Read native recipes into the plain values that the engine of the personal edition works on."""

from decimal import Decimal

from pydantic import UUID4

from mealie.repos.all_repositories import get_repositories
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.recipe.recipe import RecipeOut
from mealie.schema.recipe.recipe_ingredient import IngredientFoodOut, IngredientUnitOut

from .engine.compliance import IngredientView, ToolView
from .engine.requirements import Need, NeedSource
from .engine.units import UnitInfo, to_decimal

MAX_RECIPE_DEPTH = 5


def unit_info(unit) -> UnitInfo | None:
    """The conversion data of a stored unit. A unit that is only text has no id and counts as no unit."""
    unit_id = getattr(unit, "id", None)
    if unit is None or unit_id is None:
        return None
    standard_quantity = getattr(unit, "standard_quantity", None)
    return UnitInfo(
        id=unit_id,
        name=getattr(unit, "name", "") or "",
        standard_quantity=to_decimal(standard_quantity) if standard_quantity else None,
        standard_unit=getattr(unit, "standard_unit", None),
    )


class RecipeReader:
    """Loads recipes of the group and flattens them, sub-recipes included."""

    def __init__(self, repos: AllRepositories) -> None:
        # Any recipe of the group is a valid source, as in the native shopping list.
        self.recipes = get_repositories(repos.session, group_id=repos.group_id, household_id=None).recipes
        self._cache: dict[UUID4, RecipeOut | None] = {}

    def get(self, recipe_id: UUID4) -> RecipeOut | None:
        if recipe_id not in self._cache:
            self._cache[recipe_id] = self.recipes.get_one(recipe_id, "id")
        return self._cache[recipe_id]

    @staticmethod
    def _is_empty(ingredient) -> bool:
        return not (ingredient.food or (ingredient.note or "").strip() or ingredient.referenced_recipe)

    def ingredient_views(self, recipe: RecipeOut, _depth: int = 0) -> list[IngredientView]:
        views: list[IngredientView] = []
        for ingredient in recipe.recipe_ingredient:
            sub_recipe = self._sub_recipe(ingredient)
            if sub_recipe is not None:
                if _depth < MAX_RECIPE_DEPTH:
                    views.extend(self.ingredient_views(sub_recipe, _depth + 1))
                continue
            if self._is_empty(ingredient):
                continue

            food = ingredient.food if isinstance(ingredient.food, IngredientFoodOut) else None
            views.append(
                IngredientView(
                    display=ingredient.display or ingredient.note or "",
                    food_id=food.id if food else None,
                    food_name=food.name if food else None,
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                )
            )
        return views

    def tool_views(self, recipe: RecipeOut) -> list[ToolView]:
        return [ToolView(tool.id, tool.name) for tool in recipe.tools]

    def needs(self, recipe: RecipeOut, scale: Decimal, label: str | None = None, _depth: int = 0) -> list[Need]:
        """The quantity of each ingredient that the recipe needs at a scale."""
        needs: list[Need] = []
        for ingredient in recipe.recipe_ingredient:
            sub_recipe = self._sub_recipe(ingredient)
            if sub_recipe is not None:
                if _depth < MAX_RECIPE_DEPTH:
                    sub_scale = to_decimal(ingredient.quantity or 1) * scale
                    needs.extend(self.needs(sub_recipe, sub_scale, label, _depth + 1))
                continue
            if self._is_empty(ingredient):
                continue

            food = ingredient.food if isinstance(ingredient.food, IngredientFoodOut) else None
            unit = ingredient.unit if isinstance(ingredient.unit, IngredientUnitOut) else None
            base_quantity = to_decimal(ingredient.quantity or 0)
            note = (ingredient.note or "").strip() or None

            needs.append(
                Need(
                    quantity=base_quantity * scale,
                    food_id=food.id if food else None,
                    food_name=food.name if food else None,
                    unit=unit_info(unit),
                    note=note if food else (note or ingredient.display),
                    source=NeedSource(
                        recipe_id=recipe.id,
                        recipe_name=recipe.name,
                        scale=scale,
                        base_quantity=base_quantity,
                        unit_name=unit.name if unit else "",
                        label=label,
                        note=note,
                    ),
                )
            )
        return needs

    def _sub_recipe(self, ingredient) -> RecipeOut | None:
        referenced = ingredient.referenced_recipe
        if referenced is None or getattr(referenced, "id", None) is None:
            return None
        return self.get(referenced.id)
