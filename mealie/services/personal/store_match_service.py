from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.budget import (
    StoreMatchCandidate,
    StoreMatchLine,
    StoreMatchOut,
    StoreMatchRequest,
    StoreMatchStore,
)
from mealie.schema.personal.enums import RetailStore
from mealie.schema.personal.price import PriceOffer

from .engine.pricing import REASON_NO_FOOD, cost_of, price_point
from .engine.store_match import dear_limit, piece_grams, rank, search_names, search_term
from .engine.units import UnitInfo, to_decimal
from .price_source import PriceSource, PriceSourceUnavailable
from .recipe_needs import unit_info
from .shopping_plan_service import ShoppingPlanService

MAX_LINES = 60
"""The lines that one request searches. A plan with more lines is searched in several requests."""
REASON_TOO_MANY = "TOO_MANY"
_WORKERS = 4
_SEARCH_LIMIT = 10
# A food counted in pieces is not sold by the liter: a lemon is not a bottle of lemonade.
_VOLUME_UNITS = frozenset({"l", "dl", "cl", "ml"})
_MAX_QUERY = 80

type _Job = tuple[str, tuple[RetailStore, ...]]


class StoreMatchService:
    """
    Find, for each line of a shopping plan, the product of each shop that fits it.

    Nothing is stored: the person chooses the products, and the application then keeps their prices. A request
    to the price service carries the name of a food and the names of the shops, nothing about a person.
    """

    def __init__(self, repos: AllRepositories, user_id: UUID4, source: PriceSource | None = None) -> None:
        self.repos = repos
        self.user_id = user_id
        self.source = source or PriceSource()
        self._units: dict[UUID4, UnitInfo | None] = {}

    def _unit(self, unit_id: UUID4 | None) -> UnitInfo | None:
        if unit_id is None:
            return None
        if unit_id not in self._units:
            self._units[unit_id] = unit_info(self.repos.ingredient_units.get_one(unit_id))
        return self._units[unit_id]

    def match(self, plan_id: UUID4, data: StoreMatchRequest) -> StoreMatchOut:
        preview = ShoppingPlanService(self.repos, self.user_id).preview(plan_id)
        out = StoreMatchOut(plan_id=plan_id, available=self.source.enabled)

        stored: dict[tuple[UUID4, str], tuple[str | None, float]] = {
            (price.food_id, price.store): (price.label, price.price) for price in self.repos.pe_food_prices.get_all()
        }
        wanted_keys = set(data.keys)
        jobs: dict[str, _Job] = {}

        for line in preview.lines:
            if line.quantity_to_buy <= 0 or (wanted_keys and line.key not in wanted_keys):
                continue
            entry = StoreMatchLine(
                key=line.key,
                display=line.display,
                food_id=line.food_id,
                food_name=line.food_name,
                quantity=line.quantity_to_buy,
                unit_name=line.unit_name,
            )
            out.lines.append(entry)
            if line.food_id is None or not line.food_name:
                entry.reason = REASON_NO_FOOD
                continue

            typed = " ".join(data.queries.get(line.key, "").split())[:_MAX_QUERY]
            if len(typed) >= 2:
                entry.query, entry.translated = typed, False
            else:
                typed = ""
                entry.query, entry.translated = search_term(line.food_name)

            to_search: list[RetailStore] = []
            for store in RetailStore:
                known = stored.get((line.food_id, store.value))
                state = StoreMatchStore(store=store.value)
                if known is not None:
                    state.has_stored, state.stored_label, state.stored_price = True, known[0], known[1]
                # A shop that has a price is searched again only when the person asks for it.
                if known is None or data.refresh or typed:
                    to_search.append(store)
                entry.stores.append(state)

            if not to_search or not self.source.enabled:
                continue
            if len(jobs) >= MAX_LINES:
                entry.reason = REASON_TOO_MANY
                continue
            jobs[line.key] = (entry.query, tuple(to_search))

        if not jobs:
            return out

        answers = self._search(set(jobs.values()))
        if all(answer is None for answer in answers.values()):
            out.available = False
            return out

        today = datetime.now(UTC).date()
        lines = {line.key: line for line in preview.lines}
        for entry in out.lines:
            job = jobs.get(entry.key)
            if job is None:
                continue
            out.searched_lines += 1
            answer = answers[job]
            line = lines[entry.key]
            searches = search_names(entry.query)
            if entry.translated and entry.food_name:
                searches.append(entry.food_name)
            for state in entry.stores:
                if RetailStore(state.store) not in job[1]:
                    continue
                state.searched = True
                if answer is None or state.store in answer[1]:
                    state.failed = True
                    continue
                offers = [offer for offer in answer[0] if offer.store == state.store]
                state.candidates = self._candidates(
                    offers, searches, to_decimal(line.quantity_to_buy), self._unit(line.unit_id), entry.food_name, today
                )
            self._doubt_the_dear(entry)
        return out

    @staticmethod
    def _doubt_the_dear(entry: StoreMatchLine) -> None:
        """
        A product that costs several times the others found for the line is not selected for the person.

        It is a pack of six, or another product with the same name. In its shop, the products that are in
        line come first.
        """
        sure = [item for state in entry.stores for item in state.candidates if item.confident]
        limit = dear_limit([item.cost for item in sure if item.cost is not None])
        for state in entry.stores:
            for item in state.candidates:
                if limit is not None and item.confident and item.cost is not None and item.cost > limit:
                    item.confident = False
            # The first product of a shop is the one that the person sees selected.
            state.candidates.sort(key=lambda item: not item.confident)

    def _search(self, jobs: set[_Job]) -> dict[_Job, tuple[list[PriceOffer], list[str]] | None]:
        """Ask the price service, a few requests at a time. None marks a request that got no answer."""

        def one(job: _Job) -> tuple[list[PriceOffer], list[str]] | None:
            try:
                return self.source.search(job[0], list(job[1]), limit=_SEARCH_LIMIT)
            except PriceSourceUnavailable:
                return None

        ordered = sorted(jobs)
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            return dict(zip(ordered, pool.map(one, ordered), strict=True))

    @staticmethod
    def _candidates(
        offers: list[PriceOffer],
        searches: list[str],
        quantity: Decimal,
        unit: UnitInfo | None,
        food_name: str | None,
        today,
    ) -> list[StoreMatchCandidate]:
        piece_size = piece_grams(food_name)
        costs = []
        for offer in offers:
            point = price_point(
                offer.store,
                to_decimal(offer.price),
                to_decimal(offer.size) if offer.size is not None else None,
                offer.size_unit,
                regular_price=to_decimal(offer.regular_price) if offer.regular_price is not None else None,
                promotion=offer.promotion,
                promotion_ends_on=offer.promotion_ends_on,
                today=today,
            )
            exact = cost_of(quantity, unit, point, piece_size=piece_size)
            costs.append((exact is not None, exact or cost_of(quantity, unit, point, assume_pack=True)))

        products = [(f"{offer.brand or ''} {offer.name}", fits) for offer, (fits, _) in zip(offers, costs, strict=True)]
        candidates: list[StoreMatchCandidate] = []
        for ranked in rank(searches, products):
            cost = costs[ranked.index][1]
            offer = offers[ranked.index]
            drink = unit is None and offer.size is not None and offer.size_unit in _VOLUME_UNITS
            candidates.append(
                StoreMatchCandidate(
                    offer=offer,
                    score=ranked.score,
                    confident=ranked.confident and not drink,
                    fits=ranked.fits,
                    cost=float(cost.cost) if cost is not None else None,
                    packs=cost.packs if cost is not None else None,
                )
            )
        return candidates
