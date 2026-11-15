from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.enums import PriceSourceKind, RetailStore
from mealie.schema.personal.price import (
    BudgetLine,
    BudgetOffer,
    BudgetTotal,
    FoodPriceCreate,
    FoodPriceOut,
    FoodPriceSave,
    PlanBudgetOut,
    PriceOfferSearchOut,
    PriceRefreshOut,
    PriceSourceStatus,
    RecipeCostIngredient,
    RecipeCostOut,
)

from .engine.pricing import (
    REASON_NO_FOOD,
    REASON_NO_PRICE,
    REASON_UNIT_MISMATCH,
    Cost,
    PricePoint,
    cheapest_used,
    costs_of,
    money,
    price_point,
)
from .engine.requirements import Need
from .engine.units import UnitInfo, to_decimal
from .errors import PersonalError, PersonalNotFound
from .price_source import PriceSource, PriceSourceUnavailable
from .recipe_needs import RecipeReader, unit_info

BEST_STORE = "*"


class PriceService:
    """The prices of foods in shops, and what a plan or a recipe costs with them."""

    def __init__(self, repos: AllRepositories, source: PriceSource | None = None) -> None:
        self.repos = repos
        self.prices = repos.pe_food_prices
        self.source = source or PriceSource()
        self._units: dict[UUID4, UnitInfo | None] = {}

    # ================================================================
    # Stored prices

    def get_one(self, price_id: UUID4) -> FoodPriceOut:
        price = self.prices.get_one(price_id)
        if price is None:
            raise PersonalNotFound("Price not found.")
        return price

    def _to_save(self, data: FoodPriceCreate) -> FoodPriceSave:
        if self.repos.ingredient_foods.get_one(data.food_id) is None:
            raise PersonalNotFound("Food not found.")
        if data.regular_price is not None and data.regular_price < data.price:
            raise PersonalError("PRICE_ABOVE_REGULAR", "The regular price cannot be lower than the price.")
        return data.cast(
            FoodPriceSave,
            group_id=self.repos.group_id,
            household_id=self.repos.household_id,
            fetched_at=datetime.now(UTC),
        )

    def save(self, data: FoodPriceCreate) -> FoodPriceOut:
        """Keep the price of a food in a shop. A second price for the same food and shop replaces the first."""
        save = self._to_save(data)
        existing = self.prices.multi_query({"food_id": data.food_id, "store": save.store}, limit=1)
        if existing:
            return self.prices.update(existing[0].id, save)
        return self.prices.create(save)

    def update(self, price_id: UUID4, data: FoodPriceCreate) -> FoodPriceOut:
        current = self.get_one(price_id)
        save = self._to_save(data)
        for other in self.prices.multi_query({"food_id": save.food_id, "store": save.store}):
            if other.id != current.id:
                raise PersonalError("PRICE_EXISTS", "This food already has a price in this shop.")
        return self.prices.update(price_id, save)

    def delete(self, price_id: UUID4) -> FoodPriceOut:
        price = self.get_one(price_id)
        self.prices.delete(price_id)
        return price

    # ================================================================
    # Price source

    def status(self) -> PriceSourceStatus:
        if not self.source.enabled:
            return PriceSourceStatus()
        return PriceSourceStatus(enabled=True, name=self.source.name, stores=list(RetailStore))

    def search_offers(self, query: str, store: RetailStore | None = None) -> PriceOfferSearchOut:
        query = query.strip()
        if len(query) < 2:
            raise PersonalError("QUERY_TOO_SHORT", "Type at least two characters.")
        stores = [store] if store is not None else list(RetailStore)
        try:
            offers, failed = self.source.search(query, stores)
        except PriceSourceUnavailable:
            return PriceOfferSearchOut(query=query, store=store, available=False)
        offers.sort(key=lambda offer: (offer.unit_price is None, offer.unit_price or offer.price, offer.store))
        return PriceOfferSearchOut(query=query, store=store, offers=offers, failed_stores=failed)

    def refresh(self) -> PriceRefreshOut:
        """Read again the price of every stored price that came from the price source."""
        out = PriceRefreshOut()
        tracked = [
            price for price in self.prices.get_all() if price.source != PriceSourceKind.MANUAL and price.external_id
        ]
        if not tracked:
            out.available = self.source.enabled
            return out

        for stored in tracked:
            try:
                offer = self.source.product(stored.store, stored.external_id or "")
            except PriceSourceUnavailable:
                out.failed += 1
                continue
            if offer is None:
                out.failed += 1
                continue

            changes = {
                "price": offer.price,
                "regular_price": offer.regular_price,
                "promotion": offer.promotion,
                "promotion_ends_on": offer.promotion_ends_on,
            }
            # The size stays when the shop no longer states it: the user may have typed it.
            if offer.size is not None:
                changes.update(size=offer.size, size_unit=offer.size_unit)
            same = all(getattr(stored, field) == value for field, value in changes.items())
            self.prices.update(stored.id, {**changes, "fetched_at": datetime.now(UTC)})
            if same:
                out.unchanged += 1
            else:
                out.updated += 1

        out.available = out.failed < len(tracked)
        return out

    # ================================================================
    # Costs

    def _unit(self, unit_id: UUID4 | None) -> UnitInfo | None:
        if unit_id is None:
            return None
        if unit_id not in self._units:
            self._units[unit_id] = unit_info(self.repos.ingredient_units.get_one(unit_id))
        return self._units[unit_id]

    def price_points(self, today: date | None = None) -> dict[UUID4, list[PricePoint]]:
        """The prices of the household, by food."""
        today = today or datetime.now(UTC).date()
        points: dict[UUID4, list[PricePoint]] = {}
        for stored in self.prices.get_all():
            points.setdefault(stored.food_id, []).append(
                price_point(
                    stored.store,
                    to_decimal(stored.price),
                    to_decimal(stored.size) if stored.size is not None else None,
                    stored.size_unit,
                    regular_price=to_decimal(stored.regular_price) if stored.regular_price is not None else None,
                    promotion=stored.promotion,
                    promotion_ends_on=stored.promotion_ends_on,
                    by_weight=stored.by_weight,
                    label=stored.label,
                    today=today,
                )
            )
        return points

    def plan_budget(self, plan_id: UUID4, user_id: UUID4) -> PlanBudgetOut:
        """
        What the lines of a shopping plan cost, shop by shop.

        The total of a shop covers the lines that the shop has a price for; `missing_lines` says how many it
        leaves out. Nothing is written.
        """
        from .shopping_plan_service import ShoppingPlanService  # the plan service is the heavier module

        preview = ShoppingPlanService(self.repos, user_id).preview(plan_id)
        points = self.price_points()

        out = PlanBudgetOut(plan_id=plan_id)
        totals: dict[str, BudgetTotal] = {}
        best = BudgetTotal(store=BEST_STORE)
        best_total, best_used = Decimal("0"), Decimal("0")
        sums: dict[str, tuple[Decimal, Decimal]] = {}

        to_buy = [line for line in preview.lines if line.quantity_to_buy > 0]
        out.line_count = len(to_buy)
        for line in to_buy:
            budget_line = BudgetLine(
                key=line.key,
                display=line.display,
                food_id=line.food_id,
                quantity=line.quantity_to_buy,
                unit_name=line.unit_name,
            )
            out.lines.append(budget_line)

            costs: list[Cost] = []
            if line.food_id is None:
                budget_line.reason = REASON_NO_FOOD
            elif line.food_id not in points:
                budget_line.reason = REASON_NO_PRICE
            else:
                costs = costs_of(to_decimal(line.quantity_to_buy), self._unit(line.unit_id), points[line.food_id])
                if not costs:
                    budget_line.reason = REASON_UNIT_MISMATCH

            for cost in costs:
                budget_line.offers.append(_offer(cost))
                total = totals.setdefault(cost.store, BudgetTotal(store=cost.store))
                total.priced_lines += 1
                total.promotions += 1 if cost.on_promotion else 0
                paid, used = sums.get(cost.store, (Decimal("0"), Decimal("0")))
                sums[cost.store] = (paid + cost.cost, used + cost.used_cost)

            if costs:
                cheapest = costs[0]
                best.priced_lines += 1
                best.promotions += 1 if cheapest.on_promotion else 0
                best_total += cheapest.cost
                best_used += cheapest.used_cost

        for store, total in totals.items():
            paid, used = sums[store]
            total.total, total.used_total = float(paid), float(used)
            total.missing_lines = out.line_count - total.priced_lines

        out.stores = sorted(totals.values(), key=lambda total: (total.missing_lines, total.total, total.store))
        if best.priced_lines:
            best.total, best.used_total = float(best_total), float(best_used)
            best.missing_lines = out.line_count - best.priced_lines
            out.best = best
        return out

    def recipe_cost(self, recipe_id: UUID4) -> RecipeCostOut:
        """What one recipe costs at the cheapest known price of each of its foods."""
        reader = RecipeReader(self.repos)
        recipe = reader.get(recipe_id)
        if recipe is None:
            raise PersonalNotFound("Recipe not found.")

        servings = recipe.recipe_servings or 0
        out = cost_needs(reader.needs(recipe, Decimal("1")), self.price_points())
        out.recipe_id = recipe.id
        out.recipe_name = recipe.name or ""
        out.servings = servings
        if servings > 0 and out.priced_ingredients:
            out.per_serving = float(money(to_decimal(out.total) / to_decimal(servings)))
        return out


def _offer(cost: Cost) -> BudgetOffer:
    return BudgetOffer(
        store=cost.store,
        cost=float(cost.cost),
        used_cost=float(cost.used_cost),
        packs=cost.packs,
        label=cost.label,
        on_promotion=cost.on_promotion,
    )


def cost_needs(needs: list[Need], points: dict[UUID4, list[PricePoint]]) -> RecipeCostOut:
    """
    Add up the cost of the quantities that a recipe uses.

    An ingredient without a quantity (salt, "to taste") is not counted: it has nothing to price.
    """
    out = RecipeCostOut()
    total = Decimal("0")
    for need in needs:
        if need.quantity <= 0:
            continue
        out.ingredient_count += 1
        display = need.food_name or need.note or ""
        entry = RecipeCostIngredient(display=display, food_id=need.food_id)
        out.ingredients.append(entry)

        if need.food_id is None:
            entry.reason = REASON_NO_FOOD
            continue
        if need.food_id not in points:
            entry.reason = REASON_NO_PRICE
            continue
        cost = cheapest_used(need.quantity, need.unit, points[need.food_id])
        if cost is None:
            entry.reason = REASON_UNIT_MISMATCH
            continue

        out.priced_ingredients += 1
        entry.cost, entry.store = float(cost.used_cost), cost.store
        total += cost.used_cost

    out.total = float(money(total))
    return out
