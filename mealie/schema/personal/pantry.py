from datetime import date, datetime

from pydantic import UUID4, ConfigDict, Field, field_validator

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .common import PersonalFoodSummary, PersonalUnitSummary
from .enums import RetailStore


class PantryItemCreate(MealieModel):
    food_id: UUID4
    quantity: float = Field(0, ge=0)
    unit_id: UUID4 | None = None
    confirmed_usable: bool = False
    expires_on: date | None = None
    location: str | None = None
    note: str | None = None
    product_id: UUID4 | None = None


class PantryItemSave(PantryItemCreate):
    group_id: UUID4
    household_id: UUID4
    confirmed_at: datetime | None = None


class PantryItemOut(MealieOutModel):
    id: UUID4
    group_id: UUID4
    household_id: UUID4
    food_id: UUID4
    food: PersonalFoodSummary
    unit_id: UUID4 | None = None
    unit: PersonalUnitSummary | None = None
    quantity: float = 0
    confirmed_usable: bool = False
    confirmed_at: datetime | None = None
    expires_on: date | None = None
    location: str | None = None
    note: str | None = None
    product_id: UUID4 | None = None
    model_config = ConfigDict(from_attributes=True)


class PantryItemPagination(PaginationBase):
    items: list[PantryItemOut]


class PantryAdjust(MealieModel):
    delta: float
    """The quantity to add. A negative value removes stock; the stock never goes below zero."""


class PantryReceive(MealieModel):
    shopping_list_id: UUID4
    confirm_usable: bool = True


class PantryReceiveOut(MealieOutModel):
    received: int = 0
    skipped: int = 0
    items: list[PantryItemOut] = []


class FoodPackagingCreate(MealieModel):
    food_id: UUID4
    unit_id: UUID4 | None = None
    quantity: float = Field(gt=0)
    label: str | None = None
    store: str | None = None
    is_default: bool = True
    product_id: UUID4 | None = None


class FoodPackagingSave(FoodPackagingCreate):
    group_id: UUID4
    household_id: UUID4


class FoodPackagingOut(MealieOutModel):
    id: UUID4
    food_id: UUID4
    food: PersonalFoodSummary
    unit_id: UUID4 | None = None
    unit: PersonalUnitSummary | None = None
    quantity: float
    label: str | None = None
    store: str | None = None
    is_default: bool = True
    product_id: UUID4 | None = None
    model_config = ConfigDict(from_attributes=True)


class FoodPackagingPagination(PaginationBase):
    items: list[FoodPackagingOut]


class ProductBase(MealieModel):
    barcode: str
    name: str
    brand: str | None = None
    stores: list[str] = []
    quantity: float | None = None
    quantity_unit: str | None = None
    quantity_text: str | None = None
    labels: list[str] = []
    allergens: list[str] = []
    traces: list[str] = []
    image_url: str | None = None
    source: str = "openfoodfacts"
    source_url: str | None = None

    @field_validator("stores", "labels", "allergens", "traces", mode="before")
    @classmethod
    def none_lists_to_empty(cls, value):
        return [] if value is None else value


class ProductSave(ProductBase):
    group_id: UUID4
    food_id: UUID4 | None = None
    fetched_at: datetime | None = None


class ProductOut(ProductBase, MealieOutModel):
    id: UUID4
    group_id: UUID4
    food_id: UUID4 | None = None
    fetched_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ProductPagination(PaginationBase):
    items: list[ProductOut]


class ProductSearchOut(MealieOutModel):
    query: str
    store: RetailStore | None = None
    available: bool = True
    """False when the product database did not answer. The application works without it."""
    products: list[ProductBase] = []


class ProductImport(MealieModel):
    barcode: str
    food_id: UUID4 | None = None
    create_packaging: bool = True
    """Create a pack size for the food from the quantity of the product."""


class ProductImportOut(MealieOutModel):
    product: ProductOut
    packaging: FoodPackagingOut | None = None
    hints: list[str] = []
    """What the label of the product says. A hint is never a verification."""
