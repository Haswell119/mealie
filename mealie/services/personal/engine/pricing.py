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
    approximate: bool = False
    """The quantity and the pack do not measure the same thing: the cost rests on an assumption."""


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


def cost_of(
    quantity: Decimal,
    unit: UnitInfo | None,
    point: PricePoint,
    *,
    piece_size: Decimal | None = None,
    assume_pack: bool = False,
) -> Cost | None:
    """
    What a quantity of a food costs at one price.

    When the quantity and the pack do not measure the same thing (pieces against grams), the function does not
    guess by itself. The caller can give it two assumptions, and the cost then says that it is approximate:
    `piece_size` is the usual weight of one piece of the food in grams ("2 onions" against a pack of 1 kg), and
    `assume_pack` takes one pack when nothing else is known ("1 bunch of parsley"). Without them the function
    returns None. A pack without a size counts as one piece.
    """
    size = point.size if point.size is not None else Decimal("1")
    point_dimension = point.dimension if point.size is not None else DIMENSION_COUNT
    if size <= 0:
        return None

    approximate = False
    base = base_quantity(quantity, unit)
    if base is not None and base[1] == point_dimension:
        amount = base[0]
    elif unit is None and piece_size is not None and piece_size > 0 and point_dimension == DIMENSION_MASS:
        amount, approximate = quantity * piece_size, True
    elif assume_pack:
        return Cost(point.store, money(point.price), money(point.price), 1, point.label, point.on_promotion, True)
    else:
        return None

    share = amount / size
    used = money(share * point.price)
    if point.by_weight:
        return Cost(point.store, used, used, None, point.label, point.on_promotion, approximate)

    packs = int(share.to_integral_value(rounding=ROUND_CEILING))
    return Cost(point.store, money(packs * point.price), used, packs, point.label, point.on_promotion, approximate)


def costs_of(
    quantity: Decimal,
    unit: UnitInfo | None,
    points: list[PricePoint],
    *,
    piece_size: Decimal | None = None,
    assume_pack: bool = False,
) -> list[Cost]:
    """The cost of a quantity in each shop that can price it, the cheapest first."""
    costs = [
        cost
        for cost in (cost_of(quantity, unit, point, piece_size=piece_size, assume_pack=assume_pack) for point in points)
        if cost is not None
    ]
    costs.sort(key=lambda cost: (cost.cost, cost.store))
    return costs


def cheapest_used(
    quantity: Decimal, unit: UnitInfo | None, points: list[PricePoint], *, piece_size: Decimal | None = None
) -> Cost | None:
    """
    The shop where the quantity itself costs the least, without the rest of the pack.

    The share of a pack that a recipe uses cannot be assumed: one pack is never taken here.
    """
    costs = costs_of(quantity, unit, points, piece_size=piece_size)
    return min(costs, key=lambda cost: (cost.used_cost, cost.store)) if costs else None


@dataclass(frozen=True)
class Basket:
    """What the whole shopping costs in one shop."""

    store: str
    total: Decimal
    """The lines that the shop has a price for."""
    estimated: Decimal
    """The lines that it has no price for, each at the mean of the shops that price it."""
    priced: int
    missing: int
    comparable: bool
    """False when the shop prices less than half of the lines: its total is mostly an estimate."""

    @property
    def basket(self) -> Decimal:
        return self.total + self.estimated


def compare_baskets(lines: list[dict[str, Decimal]]) -> list[Basket]:
    """
    Compare the shops on the whole shopping, the cheapest first.

    `lines` gives the cost of each line in each shop that prices it. A person shops in one shop, so each shop
    gets one total for every line. A line that a shop does not price counts at the mean of the other shops:
    without it, the shop with the fewest prices would look the cheapest. A line that no shop prices is left out
    of every total.
    """
    priceable = [line for line in lines if line]
    needed = (len(priceable) + 1) // 2
    baskets: list[Basket] = []
    for store in sorted({store for line in priceable for store in line}):
        total, estimated, priced = Decimal("0"), Decimal("0"), 0
        for line in priceable:
            if store in line:
                total += line[store]
                priced += 1
            else:
                estimated += money(sum(line.values(), Decimal("0")) / len(line))
        baskets.append(Basket(store, total, estimated, priced, len(priceable) - priced, priced >= needed))
    baskets.sort(key=lambda basket: (not basket.comparable, basket.basket, basket.store))
    return baskets
