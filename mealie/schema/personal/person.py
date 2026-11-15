from datetime import datetime

from pydantic import UUID4, ConfigDict

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .common import PersonalFoodSummary
from .dietary import DietaryRestrictionOut
from .enums import Appetite, FoodPreferenceKind, RestrictionScope, RestrictionSeverity


class PersonRestrictionCreate(MealieModel):
    restriction_id: UUID4
    severity: RestrictionSeverity = RestrictionSeverity.STRICT
    default_scope: RestrictionScope = RestrictionScope.INDIVIDUAL
    applies_when_cooking: bool = False
    notes: str | None = None


class PersonRestrictionSave(PersonRestrictionCreate):
    group_id: UUID4
    household_id: UUID4
    person_id: UUID4


class PersonRestrictionOut(MealieOutModel):
    id: UUID4
    person_id: UUID4
    restriction_id: UUID4
    restriction: DietaryRestrictionOut
    severity: RestrictionSeverity
    default_scope: RestrictionScope
    applies_when_cooking: bool = False
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class PersonFoodPreferenceCreate(MealieModel):
    food_id: UUID4
    kind: FoodPreferenceKind
    note: str | None = None


class PersonFoodPreferenceSave(PersonFoodPreferenceCreate):
    group_id: UUID4
    household_id: UUID4
    person_id: UUID4


class PersonFoodPreferenceOut(MealieOutModel):
    id: UUID4
    person_id: UUID4
    food_id: UUID4
    food: PersonalFoodSummary
    kind: FoodPreferenceKind
    note: str | None = None
    model_config = ConfigDict(from_attributes=True)


class PersonCreate(MealieModel):
    display_name: str
    appetite: Appetite = Appetite.NORMAL
    notes: str | None = None
    is_me: bool = False
    """True for the person who uses the application. That person needs no consent record."""
    consent_given: bool = False
    consent_note: str | None = None
    restrictions: list[PersonRestrictionCreate] = []
    food_preferences: list[PersonFoodPreferenceCreate] = []


class PersonSave(MealieModel):
    group_id: UUID4
    household_id: UUID4
    display_name: str
    appetite: Appetite = Appetite.NORMAL
    notes: str | None = None
    linked_user_id: UUID4 | None = None
    consent_given_at: datetime | None = None
    consent_note: str | None = None


class PersonSummary(MealieOutModel):
    id: UUID4
    display_name: str
    appetite: Appetite = Appetite.NORMAL
    linked_user_id: UUID4 | None = None
    model_config = ConfigDict(from_attributes=True)


class PersonOut(PersonSummary):
    group_id: UUID4
    household_id: UUID4
    notes: str | None = None
    consent_given_at: datetime | None = None
    consent_note: str | None = None
    restrictions: list[PersonRestrictionOut] = []
    food_preferences: list[PersonFoodPreferenceOut] = []
    created_at: datetime | None = None


class PersonPagination(PaginationBase):
    items: list[PersonOut]
