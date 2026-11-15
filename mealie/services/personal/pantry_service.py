from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.household.group_shopping_list import ShoppingListItemUpdate
from mealie.schema.personal.pantry import (
    FoodPackagingCreate,
    FoodPackagingOut,
    FoodPackagingSave,
    PantryAdjust,
    PantryItemCreate,
    PantryItemOut,
    PantryItemSave,
    PantryReceive,
    PantryReceiveOut,
)

from .engine.requirements import Packaging, StockEntry
from .engine.units import convert, quantize, to_decimal
from .errors import PersonalError, PersonalNotFound
from .recipe_needs import unit_info

RECEIVED_FLAG = "pe_received"


class PantryService:
    """The stock of the household: what food it holds, how much, and in which packs it buys it."""

    def __init__(self, repos: AllRepositories) -> None:
        self.repos = repos
        self.items = repos.pe_pantry_items
        self.packagings = repos.pe_food_packagings

    @property
    def _scope(self) -> dict:
        return {"group_id": self.repos.group_id, "household_id": self.repos.household_id}

    # ================================================================
    # Stock

    def get_one(self, item_id: UUID4) -> PantryItemOut:
        item = self.items.get_one(item_id)
        if item is None:
            raise PersonalNotFound("Stock entry not found.")
        return item

    def _check_refs(self, food_id: UUID4, unit_id: UUID4 | None) -> None:
        if self.repos.ingredient_foods.get_one(food_id) is None:
            raise PersonalNotFound("Food not found.")
        if unit_id is not None and self.repos.ingredient_units.get_one(unit_id) is None:
            raise PersonalNotFound("Unit not found.")

    def create(self, data: PantryItemCreate) -> PantryItemOut:
        self._check_refs(data.food_id, data.unit_id)
        save = data.cast(
            PantryItemSave, **self._scope, confirmed_at=datetime.now(UTC) if data.confirmed_usable else None
        )
        item = self.items.create(save)
        self._sync_on_hand(data.food_id)
        return item

    def update(self, item_id: UUID4, data: PantryItemCreate) -> PantryItemOut:
        existing = self.get_one(item_id)
        self._check_refs(data.food_id, data.unit_id)

        confirmed_at = None
        if data.confirmed_usable:
            confirmed_at = existing.confirmed_at if existing.confirmed_usable else datetime.now(UTC)
        item = self.items.update(item_id, data.cast(PantryItemSave, **self._scope, confirmed_at=confirmed_at))

        self._sync_on_hand(data.food_id)
        if existing.food_id != data.food_id:
            self._sync_on_hand(existing.food_id)
        return item

    def delete(self, item_id: UUID4) -> PantryItemOut:
        item = self.get_one(item_id)
        self.items.delete(item_id)
        self._sync_on_hand(item.food_id)
        return item

    def adjust(self, item_id: UUID4, data: PantryAdjust) -> PantryItemOut:
        item = self.get_one(item_id)
        quantity = max(to_decimal(item.quantity) + to_decimal(data.delta), Decimal("0"))
        updated = self.items.update(item_id, {"quantity": float(quantize(quantity))})
        self._sync_on_hand(item.food_id)
        return updated

    def confirm(self, item_id: UUID4, usable: bool) -> PantryItemOut:
        self.get_one(item_id)
        return self.items.update(
            item_id, {"confirmed_usable": usable, "confirmed_at": datetime.now(UTC) if usable else None}
        )

    def _sync_on_hand(self, food_id: UUID4) -> None:
        has_stock = any(item.quantity > 0 for item in self.items.multi_query({"food_id": food_id}))
        self.repos.pe_set_food_on_hand(food_id, has_stock)

    def usable_stock(self, today: date | None = None) -> list[StockEntry]:
        """The stock that a plan may count on: confirmed as usable by the user, not empty, not expired."""
        today = today or datetime.now(UTC).date()
        entries: list[StockEntry] = []
        for item in self.items.get_all(order_by="created_at", order_descending=False):
            if not item.confirmed_usable or item.quantity <= 0:
                continue
            if item.expires_on is not None and item.expires_on < today:
                continue
            entries.append(StockEntry(item.food_id, to_decimal(item.quantity), unit_info(item.unit)))
        return entries

    def consume(self, food_id: UUID4, quantity: Decimal, unit) -> Decimal:
        """
        Remove a quantity of a food from the stock. Return the quantity that the stock really held.

        Stock in a unit that does not convert to `unit` is left alone.
        """
        missing = quantity
        for item in self.items.multi_query({"food_id": food_id}):
            if missing <= 0:
                break
            available = convert(to_decimal(item.quantity), unit_info(item.unit), unit)
            if available is None or available <= 0:
                continue

            taken = min(available, missing)
            missing -= taken
            left = convert(available - taken, unit, unit_info(item.unit))
            if left is None or quantize(left) <= 0:
                self.items.delete(item.id)
            else:
                self.items.update(item.id, {"quantity": float(quantize(left))})

        self._sync_on_hand(food_id)
        return quantity - missing

    def receive(self, data: PantryReceive) -> PantryReceiveOut:
        """
        Put the bought items of a shopping list into the stock.

        Only checked items with a food count. An item is received once: it then carries a flag.
        """
        shopping_list = self.repos.group_shopping_lists.get_one(data.shopping_list_id)
        if shopping_list is None:
            raise PersonalNotFound("Shopping list not found.")

        result = PantryReceiveOut()
        now = datetime.now(UTC)
        for list_item in shopping_list.list_items:
            if not list_item.checked or list_item.food_id is None or (list_item.quantity or 0) <= 0:
                continue
            if (list_item.extras or {}).get(RECEIVED_FLAG):
                result.skipped += 1
                continue

            same = [
                item
                for item in self.items.multi_query({"food_id": list_item.food_id})
                if item.unit_id == list_item.unit_id and item.confirmed_usable == data.confirm_usable
            ]
            if same:
                quantity = to_decimal(same[0].quantity) + to_decimal(list_item.quantity)
                stored = self.items.update(same[0].id, {"quantity": float(quantize(quantity))})
            else:
                stored = self.items.create(
                    PantryItemSave(
                        **self._scope,
                        food_id=list_item.food_id,
                        unit_id=list_item.unit_id,
                        quantity=list_item.quantity,
                        confirmed_usable=data.confirm_usable,
                        confirmed_at=now if data.confirm_usable else None,
                    )
                )
            self._sync_on_hand(list_item.food_id)

            extras = {**(list_item.extras or {}), RECEIVED_FLAG: now.date().isoformat()}
            self.repos.group_shopping_list_item.update(
                list_item.id, list_item.cast(ShoppingListItemUpdate, extras=extras)
            )
            result.received += 1
            result.items.append(stored)

        return result

    # ================================================================
    # Packagings

    def get_packaging(self, packaging_id: UUID4) -> FoodPackagingOut:
        packaging = self.packagings.get_one(packaging_id)
        if packaging is None:
            raise PersonalNotFound("Packaging not found.")
        return packaging

    def create_packaging(self, data: FoodPackagingCreate) -> FoodPackagingOut:
        self._check_refs(data.food_id, data.unit_id)
        if data.is_default:
            self._clear_default(data.food_id)
        return self.packagings.create(data.cast(FoodPackagingSave, **self._scope))

    def update_packaging(self, packaging_id: UUID4, data: FoodPackagingCreate) -> FoodPackagingOut:
        self.get_packaging(packaging_id)
        self._check_refs(data.food_id, data.unit_id)
        if data.is_default:
            self._clear_default(data.food_id, keep=packaging_id)
        return self.packagings.update(packaging_id, data.cast(FoodPackagingSave, **self._scope))

    def delete_packaging(self, packaging_id: UUID4) -> FoodPackagingOut:
        packaging = self.get_packaging(packaging_id)
        self.packagings.delete(packaging_id)
        return packaging

    def _clear_default(self, food_id: UUID4, keep: UUID4 | None = None) -> None:
        for packaging in self.packagings.multi_query({"food_id": food_id}):
            if packaging.is_default and packaging.id != keep:
                self.packagings.update(packaging.id, {"is_default": False})

    def default_packagings(self) -> dict[UUID4, Packaging]:
        """The pack size that rounds the quantity to buy, for each food that has one."""
        result: dict[UUID4, Packaging] = {}
        for packaging in self.packagings.get_all(order_by="created_at", order_descending=False):
            if not packaging.is_default or packaging.quantity <= 0:
                continue
            result.setdefault(
                packaging.food_id,
                Packaging(to_decimal(packaging.quantity), unit_info(packaging.unit), packaging.label),
            )
        return result

    def check_quantity(self, quantity: float) -> None:
        if quantity < 0:
            raise PersonalError("NEGATIVE_QUANTITY", "A quantity cannot be negative.")
