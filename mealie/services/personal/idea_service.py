import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import UUID4, BaseModel, ValidationError, field_validator

from mealie.core.root_logger import get_logger
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.enums import (
    FindingCode,
    IdeaKind,
    IdeaTagKind,
    InspirationKind,
    InspirationStatus,
    RestrictionScope,
    VerificationStatus,
)
from mealie.schema.personal.ideas import (
    IdeaCard,
    IdeaFeedOut,
    IdeaGenerateOut,
    IdeaGenerateRequest,
    IdeaTag,
    IdeaTagCount,
)
from mealie.schema.personal.inspiration import InspirationDraft, InspirationSave
from mealie.services.openai import OpenAIService

from .assistant_privacy import Anonymizer
from .assistant_service import MAX_TIMEOUT_SECONDS, AssistantService
from .dietary_service import DietaryService
from .engine.compliance import IngredientView, StatusBook, ToolView, evaluate_recipe
from .engine.ideas import (
    COST_COVERAGE,
    QUICK_MINUTES,
    STOCK_SHARE,
    daily_rank,
    label_key,
    load_seasons,
    recipe_minutes,
    seasonal_keys,
)
from .engine.pricing import PricePoint
from .engine.requirements import Need, NeedSource
from .engine.rules import normalize_text
from .engine.units import UnitInfo, to_decimal
from .pantry_service import PantryService
from .price_service import PriceService, cost_needs
from .recipe_compliance_service import RecipeComplianceService
from .recipe_needs import MAX_RECIPE_DEPTH, unit_info

logger = get_logger()

IDEAS_PROMPT = (Path(__file__).parent / "data" / "assistant_ideas_prompt.txt").read_text(encoding="utf-8").strip()

TAG_QUICK = "QUICK"
TAG_IN_STOCK = "IN_STOCK"
TAG_ALL_IN_STOCK = "ALL_IN_STOCK"
TAG_SEASONAL = "SEASONAL"
TAG_COST = "COST"
TAG_PROMOTION = "PROMOTION"
TAG_COMPATIBLE = "COMPATIBLE"
TAG_TO_CHECK = "TO_CHECK"
TAG_INCOMPATIBLE = "INCOMPATIBLE"
TAG_HINT_VEGETARIAN = "HINT_VEGETARIAN"
TAG_HINT_VEGAN = "HINT_VEGAN"
TAG_NEVER_MADE = "NEVER_MADE"
TAG_NEW = "NEW"
TAG_TOP_RATED = "TOP_RATED"
TAG_INSPIRATION = "INSPIRATION"

NEW_DAYS = 14
TOP_RATING = 4
AI_LABEL = "ia"
MAX_STOCK_NAMES = 40
MAX_LIMIT = 100

_VEGETARIAN_KEYS = {"meat", "fish", "shellfish"}
_VEGAN_KEYS = _VEGETARIAN_KEYS | {"dairy", "egg"}
_RULE_CODES = {FindingCode.RULE_MATCH, FindingCode.LABEL_CHECK}
_COMPLIANCE_TAGS = {
    VerificationStatus.VERIFIED: TAG_COMPATIBLE,
    VerificationStatus.UNVERIFIED: TAG_TO_CHECK,
    VerificationStatus.INCOMPATIBLE: TAG_INCOMPATIBLE,
}
# How a restriction reads as a plain cooking constraint. A restriction that is not listed never goes out.
_CONSTRAINT_TEXT = {
    "gluten": "sans gluten",
    "meat": "sans viande",
    "fish": "sans poisson",
    "shellfish": "sans crustacés ni mollusques",
    "dairy": "sans produits laitiers",
    "lactose": "sans lactose",
    "egg": "sans œuf",
    "peanut": "sans arachide",
    "tree_nut": "sans fruits à coque",
    "soy": "sans soja",
    "pork": "sans porc",
    "alcohol": "sans alcool",
}
_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]  # fmt: skip


@dataclass(frozen=True)
class _Line:
    """One ingredient line of a recipe, with the quantity already scaled."""

    quantity: Decimal
    food_id: UUID4 | None
    food_name: str | None
    unit_id: UUID4 | None
    note: str | None

    @property
    def display(self) -> str:
        return self.food_name or self.note or ""


@dataclass
class _Context:
    """Everything the feed reads once, before it builds the cards."""

    today: date
    seed: str
    restriction_keys: set[str]
    tool_keys: set[str]
    book: StatusBook
    stock: set[UUID4]
    points: dict[UUID4, list[PricePoint]]
    units: dict[UUID4, UnitInfo | None]
    lines: dict[UUID4, list[Any]] = field(default_factory=dict)
    labels: dict[UUID4, list[str]] = field(default_factory=dict)
    tools: dict[UUID4, list[ToolView]] = field(default_factory=dict)
    names: dict[UUID4, str] = field(default_factory=dict)


class _GeneratedIdea(BaseModel):
    """One idea as the provider wrote it. Every field but the title may be missing."""

    title: str
    description: str | None = None
    minutes: int | None = None
    servings: float = 4
    tags: list[str] = []
    ingredients: list[str] = []
    steps: list[str] = []

    @field_validator("minutes", mode="before")
    @classmethod
    def lenient_minutes(cls, value):
        try:
            minutes = round(float(value))
        except TypeError, ValueError:
            return None
        return minutes if 0 < minutes <= 24 * 60 else None

    @field_validator("servings", mode="before")
    @classmethod
    def lenient_servings(cls, value):
        try:
            servings = float(value)
        except TypeError, ValueError:
            return 4
        return servings if 0 < servings <= 100 else 4

    @field_validator("tags", "ingredients", "steps", mode="before")
    @classmethod
    def lenient_lists(cls, value):
        if not isinstance(value, list):
            return []
        return [str(entry).strip() for entry in value if isinstance(entry, str | int | float) and str(entry).strip()]


class IdeaService:
    """
    The feed of cooking ideas: the recipes of the household and its inspirations, each with tags.

    The feed works on the data of the application alone. The AI provider only adds new inspirations, when
    the user asks for them.
    """

    def __init__(self, repos: AllRepositories, user_id: UUID4) -> None:
        self.repos = repos
        self.user_id = user_id
        self.dietary = DietaryService(repos)

    # ================================================================
    # Feed

    def feed(
        self,
        tags: list[str] | None = None,
        search: str | None = None,
        restrictions: list[str] | None = None,
        max_cost: float | None = None,
        include_incompatible: bool = False,
        limit: int = 30,
        offset: int = 0,
        seed: str | None = None,
        today: date | None = None,
    ) -> IdeaFeedOut:
        today = today or datetime.now(UTC).date()
        context = self._context(restrictions, seed or today.isoformat(), today)

        cards = [self._recipe_card(row, context) for row in self.repos.pe_recipe_overviews()]
        cards += [
            self._inspiration_card(inspiration, context)
            for inspiration in self.repos.pe_inspirations.get_all()
            if inspiration.status != InspirationStatus.VALIDATED
        ]

        out = IdeaFeedOut(
            restriction_keys=sorted(context.restriction_keys),
            month=today.month,
            seed=context.seed,
            assistant_enabled=AssistantService(self.repos, self.user_id).status().enabled,
        )
        if not include_incompatible:
            kept = [card for card in cards if card.compliance != VerificationStatus.INCOMPATIBLE]
            out.hidden_incompatible = len(cards) - len(kept)
            cards = kept

        words = normalize_text(search or "").split()
        if words:
            cards = [card for card in cards if _matches(card, words)]
        if max_cost is not None:
            cards = [card for card in cards if card.cost_per_serving is not None and card.cost_per_serving <= max_cost]

        out.available_tags = _count_tags(cards)
        wanted = {tag.strip() for tag in tags or [] if tag.strip()}
        if wanted:
            cards = [card for card in cards if wanted <= {tag.key for tag in card.tags}]

        cards.sort(key=lambda card: (-card.score, card.title.lower(), str(card.id)))
        out.total = len(cards)
        limit = max(1, min(limit, MAX_LIMIT))
        out.items = cards[max(offset, 0) : max(offset, 0) + limit]
        return out

    def _context(self, restrictions: list[str] | None, seed: str, today: date) -> _Context:
        compliance = RecipeComplianceService(self.repos, self.user_id)
        owner = compliance.owner_restrictions()
        known = set(self.dietary.restrictions_by_key())
        keys = {key for key in restrictions or [] if key in known} or set(owner)

        context = _Context(
            today=today,
            seed=seed,
            restriction_keys=keys,
            tool_keys={key for key in keys if owner.get(key) == RestrictionScope.ENTIRE_PREPARATION},
            book=self.dietary.status_book(),
            stock={entry.food_id for entry in PantryService(self.repos).usable_stock(today)}
            | self.repos.pe_foods_on_hand(),
            points=PriceService(self.repos).price_points(today),
            units={unit.id: unit_info(unit) for unit in self.repos.ingredient_units.get_all()},
        )
        for row in self.repos.pe_recipe_ingredient_rows():
            context.lines.setdefault(row.recipe_id, []).append(row)
        for recipe_id, name in self.repos.pe_recipe_label_rows():
            context.labels.setdefault(recipe_id, []).append(name)
        for recipe_id, tool_id, name in self.repos.pe_recipe_tool_rows():
            context.tools.setdefault(recipe_id, []).append(ToolView(tool_id, name))
        return context

    def _flatten(self, recipe_id: UUID4, context: _Context, scale: Decimal, depth: int = 0) -> list[_Line]:
        """The ingredient lines of a recipe, with those of its sub-recipes, as `RecipeReader` reads them."""
        lines: list[_Line] = []
        for row in context.lines.get(recipe_id, []):
            if row.referenced_recipe_id is not None:
                if depth < MAX_RECIPE_DEPTH:
                    sub_scale = to_decimal(row.quantity or 1) * scale
                    lines.extend(self._flatten(row.referenced_recipe_id, context, sub_scale, depth + 1))
                continue
            note = (row.note or "").strip() or None
            if row.food_id is None and note is None:
                continue
            lines.append(_Line(to_decimal(row.quantity or 0) * scale, row.food_id, row.food_name, row.unit_id, note))
        return lines

    def _recipe_card(self, row, context: _Context) -> IdeaCard:
        lines = self._flatten(row.id, context, Decimal("1"))
        card = IdeaCard(
            id=row.id,
            kind=IdeaKind.RECIPE,
            title=row.name or "",
            description=(row.description or "").strip() or None,
            recipe_slug=row.slug,
            image=row.image,
            minutes=recipe_minutes(
                row.total_time,
                row.prep_time,
                row.perform_time,
                row.total_time_seconds,
                row.prep_time_seconds,
                row.perform_time_seconds,
            ),
            servings=row.recipe_servings or 0,
        )
        score = daily_rank(context.seed, str(row.id)) * 2

        # Stock: the share of the foods of the recipe that the household holds.
        food_names: dict[UUID4, str] = {}
        for line in lines:
            if line.food_id is not None:
                food_names.setdefault(line.food_id, line.food_name or "")
        card.stock_total = len(food_names)
        card.stock_have = sum(1 for food_id in food_names if food_id in context.stock)
        card.missing_foods = [name for food_id, name in food_names.items() if food_id not in context.stock][:6]
        if card.stock_total:
            share = card.stock_have / card.stock_total
            score += share * 3
            if share >= STOCK_SHARE:
                card.tags.append(_tag(TAG_IN_STOCK, IdeaTagKind.STOCK, f"{card.stock_have}/{card.stock_total}"))
            if card.stock_have == card.stock_total:
                card.tags.append(_tag(TAG_ALL_IN_STOCK, IdeaTagKind.STOCK))

        if card.minutes is not None and card.minutes <= QUICK_MINUTES:
            card.tags.append(_tag(TAG_QUICK, IdeaTagKind.TIME, str(card.minutes)))
            score += 0.5

        card.seasonal_foods = seasonal_keys([line.display for line in lines], context.today.month)
        if card.seasonal_foods:
            card.tags.append(_tag(TAG_SEASONAL, IdeaTagKind.SEASON, ", ".join(card.seasonal_foods)))
            score += 1.5

        score += self._price_tags(card, row, lines, context)
        score += self._compliance_tags(card, row, lines, context)

        if row.last_made is None:
            card.tags.append(_tag(TAG_NEVER_MADE, IdeaTagKind.HISTORY))
            score += 0.5
        if row.date_added is not None and row.date_added >= context.today - timedelta(days=NEW_DAYS):
            card.tags.append(_tag(TAG_NEW, IdeaTagKind.HISTORY))
            score += 0.5
        if row.rating is not None and row.rating >= TOP_RATING:
            card.tags.append(_tag(TAG_TOP_RATED, IdeaTagKind.HISTORY, f"{row.rating:g}"))
            score += 0.5

        card.tags += _labels(context.labels.get(row.id, []))
        card.score = round(score, 4)
        return card

    def _price_tags(self, card: IdeaCard, row, lines: list[_Line], context: _Context) -> float:
        """Add the cost of a serving and the promotions. Return what they add to the score."""
        needs = [
            Need(
                quantity=line.quantity,
                source=NeedSource(row.id, row.name, Decimal("1"), line.quantity),
                food_id=line.food_id,
                food_name=line.food_name,
                unit=context.units.get(line.unit_id) if line.unit_id is not None else None,
                note=line.note,
            )
            for line in lines
        ]
        cost = cost_needs(needs, context.points)
        servings = row.recipe_servings or 0
        # A cost that leaves out most of the ingredients would look cheap and be wrong: it is not shown.
        if servings > 0 and cost.ingredient_count and cost.priced_ingredients / cost.ingredient_count >= COST_COVERAGE:
            card.cost_per_serving = round(cost.total / servings, 2)
            card.tags.append(_tag(TAG_COST, IdeaTagKind.BUDGET, f"{card.cost_per_serving:.2f}"))

        stores: list[str] = []
        for line in lines:
            for point in context.points.get(line.food_id, []) if line.food_id is not None else []:
                if point.on_promotion and point.store not in stores:
                    stores.append(point.store)
        if not stores:
            return 0
        card.promotion_stores = sorted(stores)
        card.tags.append(_tag(TAG_PROMOTION, IdeaTagKind.BUDGET, ", ".join(card.promotion_stores)))
        return 1

    def _compliance_tags(self, card: IdeaCard, row, lines: list[_Line], context: _Context) -> float:
        """
        Add the state of the recipe for the restrictions of the feed, and the diets that its ingredients hint at.

        A hint comes from the keyword rules only. It is never a verification, and its name says so.
        """
        views = [
            IngredientView(
                display=line.display,
                food_id=line.food_id,
                food_name=line.food_name,
                recipe_id=row.id,
                recipe_name=row.name,
            )
            for line in lines
        ]
        if views:
            # A key is clean when no rule names one of the ingredients, not even as "check the label".
            hints = evaluate_recipe(views, _VEGAN_KEYS, StatusBook())
            flagged = {finding.restriction_key for finding in hints.findings if finding.code in _RULE_CODES}
            clean = _VEGAN_KEYS - flagged
            if _VEGAN_KEYS <= clean:
                card.tags.append(_tag(TAG_HINT_VEGAN, IdeaTagKind.DIET))
            if _VEGETARIAN_KEYS <= clean:
                card.tags.append(_tag(TAG_HINT_VEGETARIAN, IdeaTagKind.DIET))

        if not context.restriction_keys:
            return 0
        result = evaluate_recipe(
            views, context.restriction_keys, context.book, context.tools.get(row.id, []), context.tool_keys
        )
        card.compliance = result.status_for(context.restriction_keys)
        concerned = sorted(key for key, status in result.statuses.items() if status == card.compliance)
        card.tags.append(_tag(_COMPLIANCE_TAGS[card.compliance], IdeaTagKind.DIET, ", ".join(concerned)))
        return 1 if card.compliance == VerificationStatus.VERIFIED else 0

    def _inspiration_card(self, inspiration, context: _Context) -> IdeaCard:
        draft = inspiration.draft
        ingredients = [line for line in (draft.ingredients if draft else []) if line.strip()]
        card = IdeaCard(
            id=inspiration.id,
            kind=IdeaKind.INSPIRATION,
            title=inspiration.title,
            description=(draft.description if draft and draft.description else inspiration.text) or None,
            image=inspiration.image,
            url=inspiration.url,
            minutes=draft.minutes if draft else None,
            servings=draft.recipe_servings if draft else 0,
            tags=[_tag(TAG_INSPIRATION, IdeaTagKind.HISTORY)],
        )
        if card.description and len(card.description) > 280:
            card.description = card.description[:277].rstrip() + "…"
        # An inspiration is new by nature: it starts above the recipes that have nothing else for them.
        score = daily_rank(context.seed, str(inspiration.id)) * 2 + 1.5

        if card.minutes is not None and card.minutes <= QUICK_MINUTES:
            card.tags.append(_tag(TAG_QUICK, IdeaTagKind.TIME, str(card.minutes)))
            score += 0.5

        card.seasonal_foods = seasonal_keys([*ingredients, inspiration.title], context.today.month)
        if card.seasonal_foods:
            card.tags.append(_tag(TAG_SEASONAL, IdeaTagKind.SEASON, ", ".join(card.seasonal_foods)))
            score += 1.5

        # A line of free text is never verified: an inspiration is at best "to check".
        if context.restriction_keys and ingredients:
            result = evaluate_recipe(
                [IngredientView(display=line) for line in ingredients], context.restriction_keys, context.book
            )
            card.compliance = result.status_for(context.restriction_keys)
            concerned = sorted(key for key, status in result.statuses.items() if status == card.compliance)
            card.tags.append(_tag(_COMPLIANCE_TAGS[card.compliance], IdeaTagKind.DIET, ", ".join(concerned)))

        card.tags += _labels(inspiration.tags)
        card.score = round(score, 4)
        return card

    # ================================================================
    # New ideas from the AI provider

    async def generate(self, request: IdeaGenerateRequest, today: date | None = None) -> IdeaGenerateOut:
        """
        Ask the AI provider for new ideas and keep each one as an inspiration.

        What goes out: the month, the produce in season, the names of the foods in stock when the user allows
        it, the cooking constraints when the user allows it, and the wish that the user typed, without the
        name of any person. An idea never becomes a recipe by itself: the user validates it.
        """
        today = today or datetime.now(UTC).date()
        try:
            service = OpenAIService(self.repos)
            provider = service._get_provider()
            client = service.get_client(provider)
        except Exception:
            return IdeaGenerateOut(available=False)

        message = self._request_text(request, today)
        try:
            completion = await client.chat.completions.create(
                model=provider.model,
                timeout=min(provider.timeout or MAX_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS),
                messages=[{"role": "system", "content": IDEAS_PROMPT}, {"role": "user", "content": message}],
            )
            ideas = _parse_ideas(completion.choices[0].message.content or "")
        except Exception as e:
            logger.warning(f"Assistant could not suggest ideas: {e.__class__.__name__}")
            return IdeaGenerateOut(available=False)

        out = IdeaGenerateOut()
        existing = {normalize_text(row.title) for row in self.repos.pe_inspirations.get_all()}
        for idea in ideas[: request.count]:
            title = " ".join(idea.title.split())[:120]
            if not title or normalize_text(title) in existing:
                continue
            existing.add(normalize_text(title))
            draft = InspirationDraft(
                name=title,
                description=idea.description,
                recipe_servings=idea.servings,
                ingredients=idea.ingredients,
                instructions=idea.steps,
                minutes=idea.minutes,
            )
            tags = [AI_LABEL]
            for tag in idea.tags:
                cleaned = " ".join(tag.lower().split())[:30]
                if cleaned and cleaned not in tags and len(tags) < 6:
                    tags.append(cleaned)
            out.created.append(
                self.repos.pe_inspirations.create(
                    InspirationSave(
                        group_id=self.repos.group_id,
                        household_id=self.repos.household_id,
                        title=title,
                        kind=InspirationKind.IDEA,
                        text=idea.description,
                        tags=tags,
                        draft=draft.model_dump(),
                    )
                )
            )
        return out

    def _request_text(self, request: IdeaGenerateRequest, today: date) -> str:
        parts = [f"Nombre d'idées : {request.count}.", f"Mois : {_MONTHS[today.month - 1]}."]
        in_season = [season.key for season in load_seasons() if today.month in season.months]
        if in_season:
            parts.append(f"Produits de saison : {', '.join(in_season)}.")

        if request.use_stock:
            names: list[str] = []
            for item in self.repos.pe_pantry_items.get_all():
                name = (item.food.name or "").strip()
                if item.quantity > 0 and name and name not in names:
                    names.append(name)
            if names:
                parts.append(f"Aliments disponibles : {', '.join(sorted(names)[:MAX_STOCK_NAMES])}.")

        if request.include_constraints:
            owner = RecipeComplianceService(self.repos, self.user_id).owner_restrictions()
            constraints = [_CONSTRAINT_TEXT[key] for key in sorted(owner) if key in _CONSTRAINT_TEXT]
            if constraints:
                parts.append(f"Contraintes : {' ; '.join(constraints)}.")

        if request.hint and request.hint.strip():
            anonymizer = Anonymizer({person.id: person.display_name for person in self.repos.pe_persons.get_all()})
            parts.append(f"Envie : {anonymizer.scrub(' '.join(request.hint.split()))}")
        return "\n".join(parts)


def _tag(key: str, kind: IdeaTagKind, value: str | None = None) -> IdeaTag:
    return IdeaTag(key=key, kind=kind, value=value)


def _labels(names: list[str] | None) -> list[IdeaTag]:
    tags: list[IdeaTag] = []
    for name in names or []:
        cleaned = " ".join(str(name).split())
        key = label_key(cleaned)
        if cleaned and key != "label:" and key not in {tag.key for tag in tags}:
            tags.append(_tag(key, IdeaTagKind.LABEL, cleaned))
    return tags


def _matches(card: IdeaCard, words: list[str]) -> bool:
    text = normalize_text(
        " ".join(
            [card.title, card.description or "", *card.missing_foods, *card.seasonal_foods]
            + [tag.value or "" for tag in card.tags if tag.kind == IdeaTagKind.LABEL]
        )
    )
    return all(f" {word}" in text for word in words)


def _count_tags(cards: list[IdeaCard]) -> list[IdeaTagCount]:
    """How many cards carry each tag, the most frequent first. The value of a label is its name."""
    counts: dict[str, IdeaTagCount] = {}
    for card in cards:
        for tag in card.tags:
            if tag.key == TAG_COST:
                continue
            entry = counts.setdefault(
                tag.key,
                IdeaTagCount(key=tag.key, kind=tag.kind, value=tag.value if tag.kind == IdeaTagKind.LABEL else None),
            )
            entry.count += 1
    return sorted(counts.values(), key=lambda entry: (-entry.count, entry.key))


def _parse_ideas(raw: str) -> list[_GeneratedIdea]:
    """Read the ideas in the answer of the provider. An idea that cannot be read is dropped, not repaired."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    data = json.loads(raw[start : end + 1])
    entries = data.get("ideas") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError("no list of ideas in the answer")

    ideas: list[_GeneratedIdea] = []
    for entry in entries:
        try:
            ideas.append(_GeneratedIdea.model_validate(entry))
        except ValidationError:
            continue
    return ideas
