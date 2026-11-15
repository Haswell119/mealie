from datetime import date, datetime

from pydantic import UUID4, ConfigDict, Field, field_validator, model_validator

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .common import PersonalFoodSummary
from .enums import PriceSizeUnit, PriceSourceKind, RetailStore


class FoodPriceCreate(MealieModel):
    food_id: UUID4
    store: str = Field(min_length=1, max_length=60)
    """A shop of the application ("migros"), or any other name ("marché")."""
    label: str | None = None
    brand: str | None = None
    price: float = Field(gt=0)
    """The price of one pack."""
    regular_price: float | None = Field(None, gt=0)
    size: float | None = Field(None, gt=0)
    size_unit: PriceSizeUnit | None = None
    by_weight: bool = False
    """The shop sells any quantity at this rate: the cost is not rounded up to whole packs."""
    promotion: str | None = None
    promotion_ends_on: date | None = None
    source: PriceSourceKind = PriceSourceKind.MANUAL
    external_id: str | None = None
    product_url: str | None = None
    image_url: str | None = None

    @field_validator("store")
    @classmethod
    def clean_store(cls, value: str) -> str:
        cleaned = " ".join(value.split()).lower()
        if not cleaned:
            raise ValueError("store must not be empty")
        return cleaned

    @model_validator(mode="after")
    def check_size(self):
        if (self.size is None) != (self.size_unit is None):
            raise ValueError("size and size_unit go together")
        for url in (self.product_url, self.image_url):
            if url and not url.strip().lower().startswith(("http://", "https://")):
                raise ValueError("a url must use http or https")
        return self


class FoodPriceSave(FoodPriceCreate):
    group_id: UUID4
    household_id: UUID4
    currency: str = "CHF"
    fetched_at: datetime | None = None


class FoodPriceOut(MealieOutModel):
    id: UUID4
    group_id: UUID4
    household_id: UUID4
    food_id: UUID4
    food: PersonalFoodSummary
    store: str
    label: str | None = None
    brand: str | None = None
    price: float
    regular_price: float | None = None
    currency: str = "CHF"
    size: float | None = None
    size_unit: PriceSizeUnit | None = None
    by_weight: bool = False
    promotion: str | None = None
    promotion_ends_on: date | None = None
    source: PriceSourceKind = PriceSourceKind.MANUAL
    external_id: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    fetched_at: datetime | None = None
    update_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class FoodPricePagination(PaginationBase):
    items: list[FoodPriceOut]


class PriceOffer(MealieOutModel):
    """A product with its price, as a price source gives it. Nothing is stored until the user keeps it."""

    store: str
    external_id: str
    name: str
    brand: str | None = None
    price: float
    regular_price: float | None = None
    currency: str = "CHF"
    size: float | None = None
    size_unit: PriceSizeUnit | None = None
    unit_price: float | None = None
    unit_price_per: str | None = None
    tags: list[str] = []
    image_url: str | None = None
    product_url: str | None = None
    promotion: str | None = None
    promotion_ends_on: date | None = None


class PriceOfferSearchOut(MealieOutModel):
    query: str
    store: RetailStore | None = None
    available: bool = True
    """False when no price source is configured, or when it did not answer. Prices typed by hand still work."""
    offers: list[PriceOffer] = []
    failed_stores: list[str] = []
    """The shops that did not answer. An empty list of offers for one of them does not mean "no product"."""


class PriceSourceStatus(MealieOutModel):
    enabled: bool = False
    name: str | None = None
    stores: list[RetailStore] = []


class PriceRefreshOut(MealieOutModel):
    available: bool = True
    updated: int = 0
    unchanged: int = 0
    failed: int = 0


class BudgetOffer(MealieOutModel):
    """What one line costs in one shop."""

    store: str
    cost: float
    """What the user pays: whole packs."""
    used_cost: float
    """The share of that cost that the quantity really uses."""
    packs: int | None = None
    label: str | None = None
    on_promotion: bool = False
    approximate: bool = False
    """The pack does not measure what the line counts: the cost assumes a usual weight, or one pack."""


class BudgetLine(MealieOutModel):
    key: str
    display: str = ""
    food_id: UUID4 | None = None
    quantity: float = 0
    unit_name: str = ""
    offers: list[BudgetOffer] = []
    reason: str | None = None
    """Why the line has no price: NO_FOOD, NO_PRICE or UNIT_MISMATCH."""


class BudgetTotal(MealieOutModel):
    store: str
    total: float = 0
    used_total: float = 0
    priced_lines: int = 0
    missing_lines: int = 0
    promotions: int = 0
    estimated_missing: float = 0
    """An estimate of the lines that the shop has no price for: the mean of the shops that price them."""
    basket_total: float = 0
    """The whole shopping in this shop: `total` and `estimated_missing`. The shops are compared on it."""
    comparable: bool = True
    """False when the shop prices less than half of the lines: its basket is mostly an estimate."""


class PlanBudgetOut(MealieOutModel):
    plan_id: UUID4
    currency: str = "CHF"
    line_count: int = 0
    """The lines of the plan with something to buy."""
    stores: list[BudgetTotal] = []
    """One total for each shop that has at least one price, the cheapest whole shopping first."""
    recommended_store: str | None = None
    """The shop where the whole shopping costs the least. None when no shop prices enough lines."""
    unpriced_lines: int = 0
    """The lines that no shop has a price for. They are in no total."""
    best: BudgetTotal | None = None
    """The cheapest shop for each line. `store` is "*"."""
    lines: list[BudgetLine] = []


class RecipeCostIngredient(MealieOutModel):
    display: str
    food_id: UUID4 | None = None
    cost: float | None = None
    store: str | None = None
    reason: str | None = None
    approximate: bool = False


class RecipeCostOut(MealieOutModel):
    recipe_id: UUID4 | None = None
    recipe_name: str = ""
    servings: float = 0
    currency: str = "CHF"
    total: float = 0
    """The cost of the quantities that the recipe uses, at the cheapest known price of each food."""
    per_serving: float | None = None
    priced_ingredients: int = 0
    ingredient_count: int = 0
    ingredients: list[RecipeCostIngredient] = []
