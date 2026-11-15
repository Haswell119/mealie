from pydantic import UUID4, Field

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel

from .enums import IdeaKind, IdeaTagKind, VerificationStatus
from .inspiration import InspirationOut


class IdeaTag(MealieOutModel):
    """
    One tag of a card.

    `key` is what a filter matches. A tag of the application has a fixed key (QUICK, IN_STOCK, SEASONAL…);
    a label that the user gave has the key `label:<name>`. `value` is the detail to show: "25", "3/4",
    "courge, poireau", "2.40", "migros".
    """

    key: str
    kind: IdeaTagKind
    value: str | None = None


class IdeaCard(MealieOutModel):
    id: UUID4
    kind: IdeaKind
    title: str
    description: str | None = None

    recipe_slug: str | None = None
    image: str | None = None
    """For a recipe, the version of its image. For an inspiration, the name of its image file."""
    url: str | None = None

    minutes: int | None = None
    servings: float = 0
    stock_have: int = 0
    stock_total: int = 0
    missing_foods: list[str] = []
    seasonal_foods: list[str] = []
    cost_per_serving: float | None = None
    promotion_stores: list[str] = []
    compliance: VerificationStatus | None = None
    """The state of the card for the restrictions of the feed. None when the feed checks no restriction."""
    tags: list[IdeaTag] = []
    score: float = 0


class IdeaTagCount(MealieOutModel):
    key: str
    kind: IdeaTagKind
    value: str | None = None
    count: int = 0


class IdeaFeedOut(MealieOutModel):
    items: list[IdeaCard] = []
    total: int = 0
    """The number of cards that match, before `limit` and `offset`."""
    hidden_incompatible: int = 0
    """The cards left out because an ingredient breaks a restriction of the feed."""
    available_tags: list[IdeaTagCount] = []
    restriction_keys: list[str] = []
    month: int = 1
    seed: str = ""
    assistant_enabled: bool = False


class IdeaGenerateRequest(MealieModel):
    count: int = Field(4, ge=1, le=8)
    hint: str | None = Field(None, max_length=300)
    """What the user feels like: "un plat mijoté", "sans four"."""
    use_stock: bool = True
    """Tell the assistant which foods the household holds. Only the names of the foods go out."""
    include_constraints: bool = False
    """
    Tell the assistant what the cook does not eat, as plain cooking constraints ("sans gluten"). No name
    and no medical detail goes out. When false, the application still checks every idea after it comes back.
    """


class IdeaGenerateOut(MealieOutModel):
    available: bool = True
    """False when no AI provider is configured or when it did not answer. The feed works without it."""
    created: list[InspirationOut] = []
