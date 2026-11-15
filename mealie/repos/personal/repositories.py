from datetime import date
from functools import cached_property
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4

from mealie.db.models.household.mealplan import GroupMealPlan
from mealie.db.models.household.preferences import HouseholdPreferencesModel
from mealie.db.models.personal import (
    PeAiProposal,
    PeDietaryRestriction,
    PeFoodPackaging,
    PeFoodPrice,
    PeFoodRestrictionStatus,
    PeInspiration,
    PeMealEvent,
    PeMealEventAssignment,
    PeMealEventGuest,
    PeMealEventHistory,
    PeMealEventMenuItem,
    PeMealEventMenuVariant,
    PeMealEventOverride,
    PePantryItem,
    PePerson,
    PePersonFoodPreference,
    PePersonRestriction,
    PeProduct,
    PeShoppingPlan,
    PeShoppingPlanLine,
    PeToolRestrictionStatus,
)
from mealie.db.models.recipe.category import Category, recipes_to_categories
from mealie.db.models.recipe.ingredient import (
    IngredientFoodModel,
    RecipeIngredientModel,
    households_to_ingredient_foods,
)
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.tag import Tag, recipes_to_tags
from mealie.db.models.recipe.tool import Tool, recipes_to_tools
from mealie.db.models.users.users import User
from mealie.schema.personal.assistant import AiProposalOut
from mealie.schema.personal.dietary import (
    DietaryRestrictionOut,
    FoodRestrictionStatusOut,
    ToolRestrictionStatusOut,
)
from mealie.schema.personal.inspiration import InspirationOut
from mealie.schema.personal.meal_event import (
    MealEventAssignmentOut,
    MealEventGuestOut,
    MealEventHistoryOut,
    MealEventMenuItemOut,
    MealEventOut,
    MealEventOverrideOut,
    MealEventVariantOut,
)
from mealie.schema.personal.pantry import FoodPackagingOut, PantryItemOut, ProductOut
from mealie.schema.personal.person import PersonFoodPreferenceOut, PersonOut, PersonRestrictionOut
from mealie.schema.personal.price import FoodPriceOut
from mealie.schema.personal.shopping_plan import ShoppingPlanLineOut, ShoppingPlanOut

from ..repository_generic import GroupRepositoryGeneric, HouseholdRepositoryGeneric

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .._utils import NotSet

PK_ID = "id"


class PersonalRepositories:
    """The repositories of the personal edition. `AllRepositories` inherits them."""

    session: Session
    group_id: UUID4 | None | NotSet
    household_id: UUID4 | None | NotSet

    def _pe_group[S, M](self, model: type[M], schema: type[S]) -> GroupRepositoryGeneric:
        return GroupRepositoryGeneric(self.session, PK_ID, model, schema, group_id=self.group_id)  # type: ignore

    def _pe_household[S, M](self, model: type[M], schema: type[S]) -> HouseholdRepositoryGeneric:
        return HouseholdRepositoryGeneric(  # type: ignore
            self.session, PK_ID, model, schema, group_id=self.group_id, household_id=self.household_id
        )

    # ================================================================
    # Dietary restrictions

    @cached_property
    def pe_dietary_restrictions(self) -> GroupRepositoryGeneric[DietaryRestrictionOut, PeDietaryRestriction]:
        return self._pe_group(PeDietaryRestriction, DietaryRestrictionOut)

    @cached_property
    def pe_food_restriction_status(self) -> GroupRepositoryGeneric[FoodRestrictionStatusOut, PeFoodRestrictionStatus]:
        return self._pe_group(PeFoodRestrictionStatus, FoodRestrictionStatusOut)

    @cached_property
    def pe_tool_restriction_status(self) -> GroupRepositoryGeneric[ToolRestrictionStatusOut, PeToolRestrictionStatus]:
        return self._pe_group(PeToolRestrictionStatus, ToolRestrictionStatusOut)

    # ================================================================
    # Persons

    @cached_property
    def pe_persons(self) -> HouseholdRepositoryGeneric[PersonOut, PePerson]:
        return self._pe_household(PePerson, PersonOut)

    @cached_property
    def pe_person_restrictions(self) -> HouseholdRepositoryGeneric[PersonRestrictionOut, PePersonRestriction]:
        return self._pe_household(PePersonRestriction, PersonRestrictionOut)

    @cached_property
    def pe_person_food_preferences(self) -> HouseholdRepositoryGeneric[PersonFoodPreferenceOut, PePersonFoodPreference]:
        return self._pe_household(PePersonFoodPreference, PersonFoodPreferenceOut)

    # ================================================================
    # Meal events

    @cached_property
    def pe_meal_events(self) -> HouseholdRepositoryGeneric[MealEventOut, PeMealEvent]:
        return self._pe_household(PeMealEvent, MealEventOut)

    @cached_property
    def pe_meal_event_guests(self) -> HouseholdRepositoryGeneric[MealEventGuestOut, PeMealEventGuest]:
        return self._pe_household(PeMealEventGuest, MealEventGuestOut)

    @cached_property
    def pe_meal_event_menu_items(self) -> HouseholdRepositoryGeneric[MealEventMenuItemOut, PeMealEventMenuItem]:
        return self._pe_household(PeMealEventMenuItem, MealEventMenuItemOut)

    @cached_property
    def pe_meal_event_variants(self) -> HouseholdRepositoryGeneric[MealEventVariantOut, PeMealEventMenuVariant]:
        return self._pe_household(PeMealEventMenuVariant, MealEventVariantOut)

    @cached_property
    def pe_meal_event_assignments(self) -> HouseholdRepositoryGeneric[MealEventAssignmentOut, PeMealEventAssignment]:
        return self._pe_household(PeMealEventAssignment, MealEventAssignmentOut)

    @cached_property
    def pe_meal_event_overrides(self) -> HouseholdRepositoryGeneric[MealEventOverrideOut, PeMealEventOverride]:
        return self._pe_household(PeMealEventOverride, MealEventOverrideOut)

    @cached_property
    def pe_meal_event_history(self) -> HouseholdRepositoryGeneric[MealEventHistoryOut, PeMealEventHistory]:
        return self._pe_household(PeMealEventHistory, MealEventHistoryOut)

    # ================================================================
    # Shopping plans

    @cached_property
    def pe_shopping_plans(self) -> HouseholdRepositoryGeneric[ShoppingPlanOut, PeShoppingPlan]:
        return self._pe_household(PeShoppingPlan, ShoppingPlanOut)

    @cached_property
    def pe_shopping_plan_lines(self) -> HouseholdRepositoryGeneric[ShoppingPlanLineOut, PeShoppingPlanLine]:
        return self._pe_household(PeShoppingPlanLine, ShoppingPlanLineOut)

    # ================================================================
    # Pantry and products

    @cached_property
    def pe_pantry_items(self) -> HouseholdRepositoryGeneric[PantryItemOut, PePantryItem]:
        return self._pe_household(PePantryItem, PantryItemOut)

    @cached_property
    def pe_food_packagings(self) -> HouseholdRepositoryGeneric[FoodPackagingOut, PeFoodPackaging]:
        return self._pe_household(PeFoodPackaging, FoodPackagingOut)

    @cached_property
    def pe_products(self) -> GroupRepositoryGeneric[ProductOut, PeProduct]:
        return self._pe_group(PeProduct, ProductOut)

    @cached_property
    def pe_food_prices(self) -> HouseholdRepositoryGeneric[FoodPriceOut, PeFoodPrice]:
        return self._pe_household(PeFoodPrice, FoodPriceOut)

    # ================================================================
    # Inspirations and assistant

    @cached_property
    def pe_inspirations(self) -> HouseholdRepositoryGeneric[InspirationOut, PeInspiration]:
        return self._pe_household(PeInspiration, InspirationOut)

    @cached_property
    def pe_ai_proposals(self) -> HouseholdRepositoryGeneric[AiProposalOut, PeAiProposal]:
        return self._pe_household(PeAiProposal, AiProposalOut)

    # ================================================================
    # Read helpers on native tables

    def pe_mealplan_entries_between(self, date_from: date, date_to: date) -> list[GroupMealPlan]:
        """The meal plan entries of the household that fall in a range of days, week entries included."""
        end = sa.func.coalesce(GroupMealPlan.end_date, GroupMealPlan.date)
        stmt = (
            sa.select(GroupMealPlan)
            .where(
                GroupMealPlan.group_id == self.group_id,
                GroupMealPlan.household_id == self.household_id,
                GroupMealPlan.recipe_id.is_not(None),
                GroupMealPlan.date <= date_to,
                end >= date_from,
            )
            .order_by(GroupMealPlan.date)
        )
        return list(self.session.execute(stmt).scalars().all())

    def pe_set_food_on_hand(self, food_id: UUID4, on_hand: bool) -> None:
        """
        Set the native "on hand" flag of a food for the household.

        The native recipe finder and the native shopping list read this flag, so the pantry keeps it current.
        """
        table = households_to_ingredient_foods
        match = sa.and_(table.c.household_id == self.household_id, table.c.food_id == food_id)
        exists = self.session.execute(sa.select(table.c.food_id).where(match)).first() is not None

        if on_hand and not exists:
            self.session.execute(sa.insert(table).values(household_id=self.household_id, food_id=food_id))
        elif not on_hand and exists:
            self.session.execute(sa.delete(table).where(match))
        self.session.commit()

    def pe_foods_on_hand(self) -> set[UUID4]:
        """The foods that carry the native "on hand" flag for the household."""
        table = households_to_ingredient_foods
        rows = self.session.execute(sa.select(table.c.food_id).where(table.c.household_id == self.household_id))
        return {row[0] for row in rows}

    def _pe_readable_recipes(self) -> sa.ColumnElement[bool]:
        """The recipes that the household may read: its own, and those of the households that share theirs."""
        preferences = HouseholdPreferencesModel
        sharing = sa.select(preferences.household_id).where(preferences.private_household.is_(False))
        owner = sa.select(User.id).where(sa.or_(User.household_id == self.household_id, User.household_id.in_(sharing)))
        return sa.and_(RecipeModel.group_id == self.group_id, RecipeModel.user_id.in_(owner))

    def pe_recipe_overviews(self) -> list[sa.Row]:
        """One light row for each recipe that the household may read. The idea feed reads every recipe at once."""
        stmt = sa.select(
            RecipeModel.id,
            RecipeModel.slug,
            RecipeModel.name,
            RecipeModel.description,
            RecipeModel.image,
            RecipeModel.total_time,
            RecipeModel.prep_time,
            RecipeModel.perform_time,
            RecipeModel.total_time_seconds,
            RecipeModel.prep_time_seconds,
            RecipeModel.perform_time_seconds,
            RecipeModel.recipe_servings,
            RecipeModel.rating,
            RecipeModel.last_made,
            RecipeModel.date_added,
        ).where(self._pe_readable_recipes())
        return list(self.session.execute(stmt).all())

    def pe_recipe_ingredient_rows(self) -> list[sa.Row]:
        """The ingredient lines of every recipe of the group, in the order of each recipe."""
        line = RecipeIngredientModel
        stmt = (
            sa.select(
                line.recipe_id,
                line.food_id,
                IngredientFoodModel.name.label("food_name"),
                line.unit_id,
                line.quantity,
                line.note,
                line.referenced_recipe_id,
            )
            .join(RecipeModel, line.recipe_id == RecipeModel.id)
            .outerjoin(IngredientFoodModel, line.food_id == IngredientFoodModel.id)
            .where(RecipeModel.group_id == self.group_id)
            .order_by(line.recipe_id, line.position)
        )
        return list(self.session.execute(stmt).all())

    def pe_recipe_label_rows(self) -> list[sa.Row]:
        """The tags and the categories of every recipe of the group, as (recipe_id, name)."""
        tags = (
            sa.select(recipes_to_tags.c.recipe_id, Tag.name)
            .join(Tag, recipes_to_tags.c.tag_id == Tag.id)
            .where(Tag.group_id == self.group_id)
        )
        categories = (
            sa.select(recipes_to_categories.c.recipe_id, Category.name)
            .join(Category, recipes_to_categories.c.category_id == Category.id)
            .where(Category.group_id == self.group_id)
        )
        return [*self.session.execute(tags).all(), *self.session.execute(categories).all()]

    def pe_recipe_tool_rows(self) -> list[sa.Row]:
        """The tools of every recipe of the group, as (recipe_id, tool_id, name)."""
        stmt = (
            sa.select(recipes_to_tools.c.recipe_id, Tool.id, Tool.name)
            .join(Tool, recipes_to_tools.c.tool_id == Tool.id)
            .where(Tool.group_id == self.group_id)
        )
        return list(self.session.execute(stmt).all())
