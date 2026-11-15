from pydantic import UUID4, ConfigDict

from mealie.schema._mealie.mealie_model import MealieOutModel


class PersonalFoodSummary(MealieOutModel):
    id: UUID4
    name: str
    plural_name: str | None = None
    label_id: UUID4 | None = None
    model_config = ConfigDict(from_attributes=True)


class PersonalUnitSummary(MealieOutModel):
    id: UUID4
    name: str
    plural_name: str | None = None
    abbreviation: str | None = None
    use_abbreviation: bool | None = False
    standard_quantity: float | None = None
    standard_unit: str | None = None
    model_config = ConfigDict(from_attributes=True)


class PersonalRecipeSummary(MealieOutModel):
    id: UUID4
    name: str
    slug: str
    recipe_servings: float = 0
    image: str | None = None
    model_config = ConfigDict(from_attributes=True)
