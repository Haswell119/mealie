from datetime import date, datetime

from pydantic import UUID4, ConfigDict, Field, model_validator

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .enums import ShoppingPlanLineState, ShoppingPlanSource, ShoppingPlanStatus


class ShoppingPlanRecipeEntry(MealieModel):
    recipe_id: UUID4
    scale: float = Field(1, gt=0)


class ShoppingPlanCreate(MealieModel):
    name: str
    source_type: ShoppingPlanSource
    event_id: UUID4 | None = None
    date_from: date | None = None
    date_to: date | None = None
    recipes: list[ShoppingPlanRecipeEntry] = []
    shopping_list_id: UUID4 | None = None
    use_stock: bool = True
    use_packaging: bool = True

    @model_validator(mode="after")
    def check_source(self):
        if self.source_type == ShoppingPlanSource.EVENT and self.event_id is None:
            raise ValueError("event_id is required for an event plan")
        if self.source_type == ShoppingPlanSource.MEALPLAN:
            if self.date_from is None or self.date_to is None:
                raise ValueError("date_from and date_to are required for a meal plan")
            if self.date_to < self.date_from:
                raise ValueError("date_to must not be before date_from")
        if self.source_type == ShoppingPlanSource.RECIPES and not self.recipes:
            raise ValueError("recipes must not be empty for a recipe plan")
        return self


class ShoppingPlanSave(MealieModel):
    group_id: UUID4
    household_id: UUID4
    name: str
    source_type: ShoppingPlanSource
    event_id: UUID4 | None = None
    date_from: date | None = None
    date_to: date | None = None
    recipes: list[dict] | None = None
    shopping_list_id: UUID4 | None = None
    status: ShoppingPlanStatus = ShoppingPlanStatus.OPEN
    use_stock: bool = True
    use_packaging: bool = True
    computed_at: datetime | None = None


class ShoppingPlanSourceOut(MealieOutModel):
    recipe_id: UUID4 | None = None
    recipe_name: str | None = None
    label: str | None = None
    scale: float = 1
    base_quantity: float = 0
    unit_name: str = ""
    note: str | None = None


class ShoppingPlanCheckOut(MealieOutModel):
    restriction_key: str
    status: str
    code: str
    term: str | None = None
    detail: str | None = None


class ShoppingPlanLineOut(MealieOutModel):
    id: UUID4
    key: str
    food_id: UUID4 | None = None
    unit_id: UUID4 | None = None
    note: str | None = None
    display: str = ""
    quantity_needed: float = 0
    quantity_from_stock: float = 0
    quantity_to_buy: float = 0
    packs: int | None = None
    pack_label: str | None = None
    projected_quantity: float = 0
    purchased_quantity: float = 0
    shopping_list_item_id: UUID4 | None = None
    state: ShoppingPlanLineState = ShoppingPlanLineState.ACTIVE
    sources: list[ShoppingPlanSourceOut] = []
    checks: list[ShoppingPlanCheckOut] = []
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def none_lists_to_empty(cls, data):
        if isinstance(data, dict):
            for field in ("sources", "checks"):
                if data.get(field) is None:
                    data[field] = []
        return data


class ShoppingPlanOut(MealieOutModel):
    id: UUID4
    group_id: UUID4
    household_id: UUID4
    name: str
    source_type: ShoppingPlanSource
    event_id: UUID4 | None = None
    date_from: date | None = None
    date_to: date | None = None
    recipes: list[ShoppingPlanRecipeEntry] = []
    shopping_list_id: UUID4 | None = None
    status: ShoppingPlanStatus = ShoppingPlanStatus.OPEN
    use_stock: bool = True
    use_packaging: bool = True
    computed_at: datetime | None = None
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def none_recipes_to_empty(cls, data):
        if isinstance(data, dict) and data.get("recipes") is None:
            data["recipes"] = []
        return data


class ShoppingPlanPagination(PaginationBase):
    items: list[ShoppingPlanOut]


class ShoppingPlanPreviewLine(MealieOutModel):
    key: str
    display: str = ""
    food_id: UUID4 | None = None
    food_name: str | None = None
    unit_id: UUID4 | None = None
    unit_name: str = ""
    note: str | None = None
    quantity_needed: float = 0
    quantity_from_stock: float = 0
    quantity_to_buy: float = 0
    packs: int | None = None
    pack_label: str | None = None
    stock_warnings: list[str] = []
    sources: list[ShoppingPlanSourceOut] = []
    checks: list[ShoppingPlanCheckOut] = []
    action: str = "NONE"
    """What applying the plan does to the shopping list item of this line."""
    item_quantity: float = 0
    purchased_quantity: float = 0
    state: ShoppingPlanLineState = ShoppingPlanLineState.ACTIVE


class ShoppingPlanIssue(MealieOutModel):
    code: str
    recipe_id: UUID4 | None = None
    recipe_name: str | None = None
    detail: str | None = None


class ShoppingPlanPreviewOut(MealieOutModel):
    plan: ShoppingPlanOut
    lines: list[ShoppingPlanPreviewLine] = []
    issues: list[ShoppingPlanIssue] = []


class ShoppingPlanApply(MealieModel):
    shopping_list_id: UUID4 | None = None
    """The list to write to. None reuses the list of the plan, or creates one."""
    restore_dismissed: bool = False
    """Create again the items that the user deleted from the list."""


class ShoppingPlanApplyOut(MealieOutModel):
    plan: ShoppingPlanOut
    shopping_list_id: UUID4
    created: int = 0
    updated: int = 0
    deleted: int = 0
    lines: list[ShoppingPlanPreviewLine] = []
    issues: list[ShoppingPlanIssue] = []


class ShoppingPlanConsumeOut(MealieOutModel):
    plan: ShoppingPlanOut
    consumed: int = 0
    """The number of stock entries that the plan reduced."""
