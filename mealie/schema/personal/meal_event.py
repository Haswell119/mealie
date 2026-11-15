from datetime import datetime

from pydantic import UUID4, ConfigDict, Field

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .dietary import DietaryRestrictionOut
from .enums import (
    Appetite,
    FindingCode,
    MealCourse,
    MealEventStatus,
    RestrictionScope,
    RestrictionSeverity,
    VerificationStatus,
)
from .person import PersonSummary


class MealEventCreate(MealieModel):
    name: str
    starts_at: datetime | None = None
    location: str | None = None
    cook_person_id: UUID4 | None = None
    leftover_portions: float = Field(0, ge=0)
    notes: str | None = None


class MealEventSave(MealEventCreate):
    group_id: UUID4
    household_id: UUID4
    status: MealEventStatus = MealEventStatus.DRAFT


class MealEventGuestCreate(MealieModel):
    person_id: UUID4
    attending: bool = True
    appetite_override: Appetite | None = None


class MealEventGuestOut(MealieOutModel):
    id: UUID4
    person_id: UUID4
    person: PersonSummary
    attending: bool = True
    appetite_override: Appetite | None = None
    model_config = ConfigDict(from_attributes=True)


class MealEventVariantCreate(MealieModel):
    recipe_id: UUID4
    label: str | None = None
    portions_override: float | None = Field(None, ge=0)


class MealEventVariantOut(MealieOutModel):
    id: UUID4
    menu_item_id: UUID4
    recipe_id: UUID4
    label: str | None = None
    position: int = 0
    portions_override: float | None = None
    model_config = ConfigDict(from_attributes=True)


class MealEventMenuItemCreate(MealieModel):
    course: MealCourse = MealCourse.MAIN
    title: str | None = None
    variants: list[MealEventVariantCreate] = []


class MealEventMenuItemOut(MealieOutModel):
    id: UUID4
    course: MealCourse
    title: str | None = None
    position: int = 0
    variants: list[MealEventVariantOut] = []
    model_config = ConfigDict(from_attributes=True)


class MealEventAssignmentSet(MealieModel):
    menu_item_id: UUID4
    person_id: UUID4
    variant_id: UUID4 | None = None
    """None removes the manual choice and gives the person an automatic variant again."""


class MealEventAssignmentOut(MealieOutModel):
    id: UUID4
    menu_item_id: UUID4
    person_id: UUID4
    variant_id: UUID4
    model_config = ConfigDict(from_attributes=True)


class MealEventOverrideCreate(MealieModel):
    person_id: UUID4
    restriction_id: UUID4
    scope: RestrictionScope
    reason: str = Field(min_length=3)
    menu_item_id: UUID4 | None = None


class MealEventOverrideOut(MealieOutModel):
    id: UUID4
    person_id: UUID4
    restriction_id: UUID4
    restriction: DietaryRestrictionOut
    scope: RestrictionScope
    reason: str
    menu_item_id: UUID4 | None = None
    created_by: UUID4 | None = None
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class MealEventHistoryOut(MealieOutModel):
    id: UUID4
    created_at: datetime | None = None
    user_id: UUID4 | None = None
    action: str
    detail: str | None = None
    model_config = ConfigDict(from_attributes=True)


class MealEventSummary(MealieOutModel):
    id: UUID4
    group_id: UUID4
    household_id: UUID4
    name: str
    starts_at: datetime | None = None
    location: str | None = None
    cook_person_id: UUID4 | None = None
    status: MealEventStatus = MealEventStatus.DRAFT
    leftover_portions: float = 0
    notes: str | None = None
    guests: list[MealEventGuestOut] = []
    model_config = ConfigDict(from_attributes=True)


class MealEventOut(MealEventSummary):
    menu_items: list[MealEventMenuItemOut] = []
    assignments: list[MealEventAssignmentOut] = []
    overrides: list[MealEventOverrideOut] = []
    history: list[MealEventHistoryOut] = []


class MealEventPagination(PaginationBase):
    items: list[MealEventSummary]


class MealEventStatusUpdate(MealieModel):
    status: MealEventStatus
    acknowledge_unverified: bool = False
    """The user saw the items that are not verified and accepts to plan the event with them."""


# ==================================================================================================================
# Analysis: computed, never stored


class AppliedConstraintOut(MealieOutModel):
    restriction_key: str
    restriction_name: str
    scope: RestrictionScope
    severity: RestrictionSeverity
    person_ids: list[UUID4] = []
    person_names: list[str] = []
    origins: list[str] = []


class PersonConstraintsOut(MealieOutModel):
    person_id: UUID4
    person_name: str
    constraints: list[AppliedConstraintOut] = []


class ConstraintSetOut(MealieOutModel):
    shared: list[AppliedConstraintOut] = []
    individual: list[PersonConstraintsOut] = []


class FindingOut(MealieOutModel):
    restriction_key: str
    status: VerificationStatus
    code: FindingCode
    subject: str = ""
    kind: str = "ingredient"
    term: str | None = None
    detail: str | None = None
    food_id: UUID4 | None = None
    tool_id: UUID4 | None = None
    recipe_id: UUID4 | None = None
    recipe_name: str | None = None
    person_id: UUID4 | None = None
    person_name: str | None = None


class VariantAnalysisOut(MealieOutModel):
    variant_id: UUID4
    recipe_id: UUID4
    recipe_name: str = ""
    recipe_slug: str = ""
    recipe_servings: float = 0
    label: str | None = None
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    statuses: dict[str, VerificationStatus] = {}
    findings: list[FindingOut] = []
    portions: float = 0
    scale: float | None = None
    person_ids: list[UUID4] = []
    person_names: list[str] = []
    error: str | None = None


class MenuItemAnalysisOut(MealieOutModel):
    menu_item_id: UUID4
    course: MealCourse
    title: str | None = None
    constraints: ConstraintSetOut
    variants: list[VariantAnalysisOut] = []
    unassigned_person_ids: list[UUID4] = []
    unassigned_person_names: list[str] = []


class ChecklistItemOut(MealieOutModel):
    code: str
    restriction_key: str
    subject: str = ""
    detail: str | None = None


class MealEventAnalysisOut(MealieOutModel):
    event_id: UUID4
    total_persons: int = 0
    total_portions: float = 0
    constraints: ConstraintSetOut
    menu: list[MenuItemAnalysisOut] = []
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    blocking: list[FindingOut] = []
    to_verify: list[FindingOut] = []
    checklist: list[ChecklistItemOut] = []
    can_plan: bool = False
