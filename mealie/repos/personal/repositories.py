from datetime import date
from functools import cached_property
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4

from mealie.db.models.household.mealplan import GroupMealPlan
from mealie.db.models.personal import (
    PeAiProposal,
    PeDietaryRestriction,
    PeFoodPackaging,
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
