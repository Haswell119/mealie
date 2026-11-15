from datetime import datetime

from pydantic import UUID4, ConfigDict, field_validator

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel

from .enums import FindingCode, RestrictionKind, VerificationSource, VerificationStatus


class DietaryRestrictionCreate(MealieModel):
    key: str
    name: str
    kind: RestrictionKind = RestrictionKind.PREFERENCE
    description: str | None = None

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        key = value.strip().lower().replace(" ", "_")
        if not key:
            raise ValueError("key must not be empty")
        return key


class DietaryRestrictionSave(DietaryRestrictionCreate):
    group_id: UUID4
    is_system: bool = False


class DietaryRestrictionOut(MealieOutModel):
    id: UUID4
    group_id: UUID4
    key: str
    name: str
    kind: RestrictionKind
    description: str | None = None
    is_system: bool = False
    model_config = ConfigDict(from_attributes=True)


class FoodRestrictionStatusUpdate(MealieModel):
    status: VerificationStatus
    reason: str | None = None


class FoodRestrictionStatusSave(MealieModel):
    group_id: UUID4
    food_id: UUID4
    restriction_id: UUID4
    status: VerificationStatus
    source: VerificationSource
    reason: str | None = None
    verified_by: UUID4 | None = None
    verified_at: datetime | None = None


class FoodRestrictionStatusOut(MealieOutModel):
    id: UUID4
    food_id: UUID4
    restriction_id: UUID4
    restriction: DietaryRestrictionOut
    status: VerificationStatus
    source: VerificationSource
    reason: str | None = None
    verified_by: UUID4 | None = None
    verified_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class FoodRestrictionEffective(MealieOutModel):
    """The state the application uses for one food and one restriction, with the reason."""

    restriction_id: UUID4
    restriction_key: str
    restriction_name: str
    status: VerificationStatus
    code: FindingCode | None = None
    term: str | None = None
    reason: str | None = None
    source: VerificationSource | None = None
    stored: bool = False


class FoodComplianceOut(MealieOutModel):
    food_id: UUID4
    food_name: str
    statuses: list[FoodRestrictionEffective] = []


class FoodBulkVerify(MealieModel):
    food_ids: list[UUID4]
    restriction_id: UUID4
    status: VerificationStatus
    reason: str | None = None


class ToolRestrictionStatusCreate(MealieModel):
    tool_id: UUID4
    restriction_id: UUID4
    reason: str | None = None


class ToolRestrictionStatusSave(ToolRestrictionStatusCreate):
    group_id: UUID4
    requires_check: bool = True


class ToolRestrictionStatusOut(MealieOutModel):
    id: UUID4
    tool_id: UUID4
    restriction_id: UUID4
    restriction: DietaryRestrictionOut
    requires_check: bool = True
    reason: str | None = None
    model_config = ConfigDict(from_attributes=True)
