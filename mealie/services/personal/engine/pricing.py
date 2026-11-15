"""Turn the price of a pack into the cost of a quantity. Exact arithmetic: no database, no network."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from .units import DIMENSION_COUNT, DIMENSION_MASS, DIMENSION_VOLUME, UnitInfo

REASON_NO_FOOD = "NO_FOOD"
REASON_NO_PRICE = "NO_PRICE"
REASON_UNIT_MISMATCH = "UNIT_MISMATCH"

# The size of each pack unit, in grams, milliliters or pieces.
_SIZE_UNITS: dict[str, tuple[str, Decimal]] = {
    "g": (DIMENSION_MASS, Decimal("1")),
    "kg": (DIMENSION_MASS, Decimal("1000")),
    "ml": (DIMENSION_VOLUME, Decimal("1")),
    "l": (DIMENSION_VOLUME, Decimal("1000")),
    "piece": (DIMENSION_COUNT, Decimal("1")),
}
_CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PricePoint:
    """The price of one pack of a food in one shop."""

    store: str
    price: Decimal
    size: Decimal | None = None
    """The size of the pack in grams, milliliters or pieces. None when the price states no size."""
    dimension: str | None = None
    by_weight: bool = False
    label: str | None = None
    on_promotion: bool = False


@dataclass(frozen=True)
class Cost:
    store: str
    cost: Decimal
    used_cost: Decimal
    packs: int | None = None
    label: str | None = None
    on_promotion: bool = False


def price_point(
    store: str,
    price: Decimal,
    size: Decimal | None,
    size_unit: str | None,
    *,
    regular_price: Decimal | None = None,
    promotion: str | None = None,
    promotion_ends_on: date | None = None,
    by_weight: bool = False,
    label: str | None = None,
    today: date | None = None,
) -> PricePoint:
    """
    Build a price point from a stored price.

    A promotion that ended is not a price any more: the regular price replaces it when it is known.
    """
    ended = promotion_ends_on is not None and today is not None and promotion_ends_on < today
    reduced = regular_price is not None and regular_price > price
    if ended and reduced:
        price = regular_price  # type: ignore[assignment]
    on_promotion = not ended and (reduced or bool(promotion))

    dimension, factor = _SIZE_UNITS.get(size_unit or "", (None, None))
    base_size = size * factor if size is not None and factor is not None and size > 0 else None
    return PricePoint(
        store=store,
        price=price,
        size=base_size,
        dimension=dimension if base_size is not None else None,
        by_weight=by_weight,
        label=label,
        on_promotion=on_promotion,
    )


def base_quantity(quantity: Decimal, unit: UnitInfo | None) -> tuple[Decimal, str] | None:
    """A quantity in grams, milliliters or pieces, or None when its unit has no standard size."""
    if unit is None:
        return quantity, DIMENSION_COUNT
    size = unit.base_size
    if size is None:
        return None
    return quantity * size, unit.dimension


def cost_of(quantity: Decimal, unit: UnitInfo | None, point: PricePoint) -> Cost | None:
    """
    What a quantity of a food costs at one price.

    Return None when the quantity and the pack do not measure the same thing (pieces against grams): the
    function never guesses a weight. A pack without a size counts as one piece.
    """
    base = base_quantity(quantity, unit)
    if base is None:
        return None
    amount, dimension = base

    size = point.size if point.size is not None else Decimal("1")
    point_dimension = point.dimension if point.size is not None else DIMENSION_COUNT
    if dimension != point_dimension or size <= 0:
        return None

    share = amount / size
    used = money(share * point.price)
    if point.by_weight:
        return Cost(point.store, used, used, None, point.label, point.on_promotion)

    packs = int(share.to_integral_value(rounding=ROUND_CEILING))
    return Cost(point.store, money(packs * point.price), used, packs, point.label, point.on_promotion)


def costs_of(quantity: Decimal, unit: UnitInfo | None, points: list[PricePoint]) -> list[Cost]:
    """The cost of a quantity in each shop that can price it, the cheapest first."""
    costs = [cost for cost in (cost_of(quantity, unit, point) for point in points) if cost is not None]
    costs.sort(key=lambda cost: (cost.cost, cost.store))
    return costs


def cheapest_used(quantity: Decimal, unit: UnitInfo | None, points: list[PricePoint]) -> Cost | None:
    """The shop where the quantity itself costs the least, without the rest of the pack."""
    costs = costs_of(quantity, unit, points)
    return min(costs, key=lambda cost: (cost.used_cost, cost.store)) if costs else None
