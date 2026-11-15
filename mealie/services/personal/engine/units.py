"""Exact unit conversion for the quantities of the personal edition. No database, no network."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

# Size of each standardized unit, in grams for a mass and in milliliters for a volume.
_MASS: dict[str, Decimal] = {
    "gram": Decimal("1"),
    "kilogram": Decimal("1000"),
    "ounce": Decimal("28.349523125"),
    "pound": Decimal("453.59237"),
}
_VOLUME: dict[str, Decimal] = {
    "milliliter": Decimal("1"),
    "liter": Decimal("1000"),
    "fluid_ounce": Decimal("29.5735295625"),
    "cup": Decimal("236.5882365"),
}

DIMENSION_MASS = "mass"
DIMENSION_VOLUME = "volume"
DIMENSION_COUNT = "count"

_PRECISION = Decimal("0.001")


def to_decimal(value: float | int | str | Decimal | None) -> Decimal:
    """Convert a stored float to a decimal without the binary noise of the float."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize(value: Decimal) -> Decimal:
    """Round a quantity to the precision that the application stores and shows."""
    return value.quantize(_PRECISION, rounding=ROUND_HALF_UP).normalize() + Decimal("0")


@dataclass(frozen=True)
class UnitInfo:
    """The part of a unit that a conversion needs."""

    id: UUID | None
    name: str = ""
    standard_quantity: Decimal | None = None
    standard_unit: str | None = None

    @property
    def dimension(self) -> str:
        if self.standard_quantity and self.standard_quantity > 0:
            if self.standard_unit in _MASS:
                return DIMENSION_MASS
            if self.standard_unit in _VOLUME:
                return DIMENSION_VOLUME
        return f"unit:{self.id}"

    @property
    def base_size(self) -> Decimal | None:
        """The size of one unit in the base unit of its dimension, or None when it has no standard."""
        if not self.standard_quantity or self.standard_quantity <= 0 or not self.standard_unit:
            return None
        table = _MASS if self.standard_unit in _MASS else _VOLUME
        size = table.get(self.standard_unit)
        return None if size is None else self.standard_quantity * size


def dimension_of(unit: UnitInfo | None) -> str:
    return DIMENSION_COUNT if unit is None else unit.dimension


def convert(quantity: Decimal, from_unit: UnitInfo | None, to_unit: UnitInfo | None) -> Decimal | None:
    """Convert a quantity between two units. Return None when the units are not compatible."""
    if from_unit is None and to_unit is None:
        return quantity
    if from_unit is None or to_unit is None:
        return None
    if from_unit.id == to_unit.id:
        return quantity
    if from_unit.dimension != to_unit.dimension:
        return None

    from_size, to_size = from_unit.base_size, to_unit.base_size
    if from_size is None or to_size is None:
        return None
    return quantity * from_size / to_size


def pick_display_unit(base_quantity: Decimal, units: list[UnitInfo]) -> UnitInfo:
    """
    Choose the unit that shows a merged quantity: the largest unit that keeps the quantity at 1 or more,
    or the smallest unit when no unit does.
    """
    ordered = sorted(units, key=lambda unit: (unit.base_size or Decimal("0"), str(unit.id)), reverse=True)
    for unit in ordered:
        size = unit.base_size
        if size and base_quantity / size >= 1:
            return unit
    return ordered[-1]
