"""
Bring a shopping list in line with a new computation, without undoing what the user did.

The rules:
- A checked item is bought. It is never changed and never created again. Its quantity counts as covered.
- The part of an open item that does not come from the plan belongs to the user. It is kept.
- An item that the user deleted is not created again.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from mealie.schema.personal.enums import ShoppingPlanLineState

from .units import quantize

ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_DELETE = "DELETE"
ACTION_NONE = "NONE"


@dataclass
class LedgerState:
    """What the plan remembers about one line between two computations. Quantities use the unit of the line."""

    key: str
    projected_quantity: Decimal = Decimal("0")
    purchased_quantity: Decimal = Decimal("0")
    item_id: UUID | None = None
    state: ShoppingPlanLineState = ShoppingPlanLineState.ACTIVE


@dataclass(frozen=True)
class ItemState:
    """The current state of a shopping list item. The quantity uses the unit of the line."""

    item_id: UUID
    quantity: Decimal
    checked: bool


@dataclass
class ReconcileResult:
    key: str
    action: str
    item_id: UUID | None
    item_quantity: Decimal
    ledger: LedgerState


def reconcile_line(
    key: str,
    quantity_to_buy: Decimal,
    ledger: LedgerState | None,
    item: ItemState | None,
    *,
    restore_dismissed: bool = False,
) -> ReconcileResult:
    """
    Decide what to do with the shopping list item of one line.

    `item` is the item that the ledger points to, or None when the item does not exist any more.
    `quantity_to_buy` is 0 for a line that the plan no longer needs.
    """
    state = ledger or LedgerState(key=key)

    if state.item_id is not None and item is None:
        # The user deleted the item.
        state.item_id = None
        state.projected_quantity = Decimal("0")
        state.state = ShoppingPlanLineState.DISMISSED

    if state.state == ShoppingPlanLineState.DISMISSED:
        if not restore_dismissed:
            return ReconcileResult(key, ACTION_NONE, None, Decimal("0"), state)
        state.state = ShoppingPlanLineState.ACTIVE

    if item is not None and item.checked:
        # The user bought the item. Everything on it counts as covered for this line.
        state.purchased_quantity = quantize(state.purchased_quantity + item.quantity)
        state.item_id = None
        state.projected_quantity = Decimal("0")
        item = None

    remaining = quantize(max(quantity_to_buy - state.purchased_quantity, Decimal("0")))
    state.state = ShoppingPlanLineState.ACTIVE if quantity_to_buy > 0 else ShoppingPlanLineState.OBSOLETE

    if item is None:
        if remaining > 0:
            state.projected_quantity = remaining
            return ReconcileResult(key, ACTION_CREATE, None, remaining, state)
        return ReconcileResult(key, ACTION_NONE, None, Decimal("0"), state)

    # The share of the open item that the plan did not put there: manual changes and other sources.
    foreign = item.quantity - state.projected_quantity
    new_quantity = quantize(foreign + remaining)
    state.projected_quantity = remaining

    if remaining <= 0 and new_quantity <= 0:
        state.item_id = None
        return ReconcileResult(key, ACTION_DELETE, item.item_id, Decimal("0"), state)

    new_quantity = max(new_quantity, Decimal("0"))
    if new_quantity == quantize(item.quantity):
        return ReconcileResult(key, ACTION_NONE, item.item_id, new_quantity, state)
    return ReconcileResult(key, ACTION_UPDATE, item.item_id, new_quantity, state)
