"""Add up what a set of recipes needs, subtract the stock, and round to the packs that a shop sells."""

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from .rules import normalize_text
from .units import UnitInfo, convert, dimension_of, pick_display_unit, quantize


@dataclass(frozen=True)
class NeedSource:
    """Where a quantity comes from: one ingredient line of one recipe."""

    recipe_id: UUID | None
    recipe_name: str | None
    scale: Decimal
    base_quantity: Decimal
    unit_name: str = ""
    label: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Need:
    """A quantity of one food that one recipe needs, already scaled."""

    quantity: Decimal
    source: NeedSource
    food_id: UUID | None = None
    food_name: str | None = None
    unit: UnitInfo | None = None
    note: str | None = None


@dataclass(frozen=True)
class StockEntry:
    food_id: UUID
    quantity: Decimal
    unit: UnitInfo | None = None


@dataclass(frozen=True)
class Packaging:
    quantity: Decimal
    unit: UnitInfo | None = None
    label: str | None = None


@dataclass
class RequirementLine:
    key: str
    quantity_needed: Decimal
    food_id: UUID | None = None
    food_name: str | None = None
    unit: UnitInfo | None = None
    note: str | None = None
    quantity_from_stock: Decimal = Decimal("0")
    quantity_to_buy: Decimal = Decimal("0")
    packs: int | None = None
    pack_label: str | None = None
    sources: list[NeedSource] = field(default_factory=list)
    stock_warnings: list[str] = field(default_factory=list)


def need_key(need: Need) -> str:
    dimension = dimension_of(need.unit)
    if need.food_id is not None:
        return f"food:{need.food_id}:{dimension}"
    return f"note:{normalize_text(need.note or '').strip()}:{dimension}"


def aggregate(needs: list[Need], preferred_units: dict[str, UnitInfo | None] | None = None) -> list[RequirementLine]:
    """
    Merge the needs of the same food into one line.

    Two needs merge when their units convert into each other. Needs with units that do not convert stay on
    separate lines: the function never adds an approximate quantity. `preferred_units` keeps the unit of a
    line stable between two computations.
    """
    preferred_units = preferred_units or {}
    grouped: dict[str, list[Need]] = {}
    for need in needs:
        grouped.setdefault(need_key(need), []).append(need)

    lines: list[RequirementLine] = []
    for key, group in grouped.items():
        first = group[0]
        unit = _line_unit(key, group, preferred_units)

        total = Decimal("0")
        for need in group:
            converted = convert(need.quantity, need.unit, unit)
            # Needs share a key only when their units have the same dimension, so the conversion exists.
            total += converted if converted is not None else need.quantity

        lines.append(
            RequirementLine(
                key=key,
                food_id=first.food_id,
                food_name=first.food_name,
                unit=unit,
                note=first.note if first.food_id is None else None,
                quantity_needed=quantize(total),
                quantity_to_buy=quantize(total),
                sources=[need.source for need in group],
            )
        )

    lines.sort(key=lambda line: (normalize_text(line.food_name or line.note or ""), line.key))
    return lines


def _line_unit(key: str, group: list[Need], preferred_units: dict[str, UnitInfo | None]) -> UnitInfo | None:
    first_unit = group[0].unit
    if first_unit is None:
        return None

    if key in preferred_units:
        preferred = preferred_units[key]
        if preferred is not None and preferred.dimension == first_unit.dimension:
            return preferred

    units = {need.unit.id: need.unit for need in group if need.unit is not None}
    if len(units) == 1 or first_unit.base_size is None:
        return first_unit

    base_total = sum((need.quantity * (need.unit.base_size or 0) for need in group if need.unit), Decimal("0"))
    return pick_display_unit(base_total, list(units.values()))


def apply_stock(lines: list[RequirementLine], stock: list[StockEntry]) -> None:
    """
    Subtract the stock from each line. Pass only the stock that the user confirmed as usable.

    Stock in a unit that does not convert to the unit of the line is not subtracted; the line gets a warning.
    One stock entry serves several lines of the same food in order, and never more than its quantity.
    """
    remaining: dict[int, Decimal] = {index: entry.quantity for index, entry in enumerate(stock)}

    for line in lines:
        line.quantity_from_stock = Decimal("0")
        if line.food_id is None:
            line.quantity_to_buy = line.quantity_needed
            continue

        missing = line.quantity_needed
        for index, entry in enumerate(stock):
            if entry.food_id != line.food_id or remaining[index] <= 0:
                continue

            available = convert(remaining[index], entry.unit, line.unit)
            if available is None:
                if "UNIT_MISMATCH" not in line.stock_warnings:
                    line.stock_warnings.append("UNIT_MISMATCH")
                continue
            if missing <= 0:
                continue

            taken = min(available, missing)
            missing -= taken
            line.quantity_from_stock += taken
            taken_in_entry_unit = convert(taken, line.unit, entry.unit)
            remaining[index] -= taken_in_entry_unit if taken_in_entry_unit is not None else taken

        line.quantity_from_stock = quantize(line.quantity_from_stock)
        line.quantity_to_buy = quantize(max(line.quantity_needed - line.quantity_from_stock, Decimal("0")))


def apply_packaging(lines: list[RequirementLine], packagings: dict[UUID, Packaging]) -> None:
    """Round the quantity to buy up to a whole number of packs, for each food that has a pack size."""
    for line in lines:
        line.packs = None
        line.pack_label = None
        if line.food_id is None or line.food_id not in packagings or line.quantity_to_buy <= 0:
            continue

        packaging = packagings[line.food_id]
        pack_size = convert(packaging.quantity, packaging.unit, line.unit)
        if pack_size is None or pack_size <= 0:
            continue

        packs = (line.quantity_to_buy / pack_size).to_integral_value(rounding=ROUND_CEILING)
        line.packs = int(packs)
        line.pack_label = packaging.label
        line.quantity_to_buy = quantize(packs * pack_size)
