from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.household.group_shopping_list import (
    ShoppingListCreate,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListItemRecipeRefCreate,
    ShoppingListItemUpdate,
)
from mealie.schema.personal.enums import (
    FindingCode,
    ShoppingPlanLineState,
    ShoppingPlanSource,
    ShoppingPlanStatus,
)
from mealie.schema.personal.shopping_plan import (
    ShoppingPlanApply,
    ShoppingPlanApplyOut,
    ShoppingPlanCheckOut,
    ShoppingPlanConsumeOut,
    ShoppingPlanCreate,
    ShoppingPlanIssue,
    ShoppingPlanLineOut,
    ShoppingPlanOut,
    ShoppingPlanPreviewLine,
    ShoppingPlanPreviewOut,
    ShoppingPlanSave,
    ShoppingPlanSourceOut,
)
from mealie.services.household_services.shopping_lists import ShoppingListService

from .dietary_service import DietaryService
from .engine.compliance import IngredientView, evaluate_ingredient
from .engine.reconcile import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_NONE,
    ACTION_UPDATE,
    ItemState,
    LedgerState,
    ReconcileResult,
    reconcile_line,
)
from .engine.requirements import Need, RequirementLine, aggregate, apply_packaging, apply_stock
from .engine.units import UnitInfo, convert, quantize, to_decimal
from .errors import PersonalError, PersonalNotFound
from .meal_event_service import MealEventService
from .pantry_service import PantryService
from .recipe_needs import RecipeReader, unit_info

PLAN_EXTRA = "pe_plan_id"


@dataclass
class _Computation:
    lines: list[RequirementLine] = field(default_factory=list)
    issues: list[ShoppingPlanIssue] = field(default_factory=list)
    checks: dict[str, list[ShoppingPlanCheckOut]] = field(default_factory=dict)


@dataclass
class _Step:
    """One line of a plan with what applying the plan does to its shopping list item."""

    key: str
    line: RequirementLine | None
    unit: UnitInfo | None
    result: ReconcileResult
    item: ShoppingListItemOut | None


class ShoppingPlanService:
    """
    Turns a set of recipes into a shopping list: what is needed, what the stock covers, what to buy.

    A plan keeps a ledger line for each food. The ledger lets the plan change the native shopping list
    again later without adding back what the user bought or undoing what the user changed by hand.
    """

    def __init__(self, repos: AllRepositories, user_id: UUID4) -> None:
        self.repos = repos
        self.user_id = user_id
        self.plans = repos.pe_shopping_plans
        self.lines = repos.pe_shopping_plan_lines
        self.events = MealEventService(repos, user_id)
        self.dietary = DietaryService(repos)
        self.pantry = PantryService(repos)
        self.reader = RecipeReader(repos)
        self._units: dict[UUID4, UnitInfo | None] = {}

    @property
    def _scope(self) -> dict:
        return {"group_id": self.repos.group_id, "household_id": self.repos.household_id}

    # ================================================================
    # Plans

    def get_one(self, plan_id: UUID4) -> ShoppingPlanOut:
        plan = self.plans.get_one(plan_id)
        if plan is None:
            raise PersonalNotFound("Shopping plan not found.")
        return plan

    def get_lines(self, plan_id: UUID4) -> list[ShoppingPlanLineOut]:
        self.get_one(plan_id)
        return sorted(self.lines.multi_query({"plan_id": plan_id}), key=lambda line: line.display.lower())

    def create(self, data: ShoppingPlanCreate) -> ShoppingPlanOut:
        self._check(data)
        if data.source_type == ShoppingPlanSource.EVENT:
            existing = self.plans.multi_query({"event_id": data.event_id}, limit=1)
            if existing:
                return existing[0]
        return self.plans.create(self._to_save(data))

    def update(self, plan_id: UUID4, data: ShoppingPlanCreate) -> ShoppingPlanOut:
        plan = self.get_one(plan_id)
        self._check(data)
        save = self._to_save(data)
        save.status = plan.status
        save.computed_at = plan.computed_at
        save.shopping_list_id = data.shopping_list_id or plan.shopping_list_id
        return self.plans.update(plan_id, save)

    def delete(self, plan_id: UUID4) -> ShoppingPlanOut:
        plan = self.get_one(plan_id)
        self.plans.delete(plan_id)
        return plan

    def _check(self, data: ShoppingPlanCreate) -> None:
        if not data.name.strip():
            raise PersonalError("PLAN_NAME_REQUIRED", "A shopping plan needs a name.")
        if data.source_type == ShoppingPlanSource.EVENT:
            self.events.get_one(data.event_id)  # type: ignore[arg-type]
        for entry in data.recipes:
            if self.reader.get(entry.recipe_id) is None:
                raise PersonalNotFound("Recipe not found.")
        if data.shopping_list_id is not None and self.repos.group_shopping_lists.get_one(data.shopping_list_id) is None:
            raise PersonalNotFound("Shopping list not found.")

    def _to_save(self, data: ShoppingPlanCreate) -> ShoppingPlanSave:
        return ShoppingPlanSave(
            **self._scope,
            name=data.name.strip(),
            source_type=data.source_type,
            event_id=data.event_id if data.source_type == ShoppingPlanSource.EVENT else None,
            date_from=data.date_from if data.source_type == ShoppingPlanSource.MEALPLAN else None,
            date_to=data.date_to if data.source_type == ShoppingPlanSource.MEALPLAN else None,
            recipes=[{"recipe_id": str(entry.recipe_id), "scale": entry.scale} for entry in data.recipes]
            if data.source_type == ShoppingPlanSource.RECIPES
            else None,
            shopping_list_id=data.shopping_list_id,
            use_stock=data.use_stock,
            use_packaging=data.use_packaging,
        )

    # ================================================================
    # Computation

    def _unit(self, unit_id: UUID4 | None) -> UnitInfo | None:
        if unit_id is None:
            return None
        if unit_id not in self._units:
            self._units[unit_id] = unit_info(self.repos.ingredient_units.get_one(unit_id))
        return self._units[unit_id]

    def _collect_needs(self, plan: ShoppingPlanOut) -> tuple[list[Need], list[ShoppingPlanIssue], set[str]]:
        """The needs of every recipe of the plan, the problems found, and the restrictions to check."""
        needs: list[Need] = []
        issues: list[ShoppingPlanIssue] = []
        restriction_keys: set[str] = set()

        if plan.source_type == ShoppingPlanSource.EVENT and plan.event_id is not None:
            analysis = self.events.analyze_full(plan.event_id)
            restriction_keys = analysis.shared_keys
            for variant_plan in analysis.plans:
                needs.extend(self.reader.needs(variant_plan.recipe, variant_plan.scale, variant_plan.label))
            for finding in analysis.out.blocking:
                if finding.code in (FindingCode.MISSING_SERVINGS, FindingCode.RECIPE_NOT_FOUND, FindingCode.NO_VARIANT):
                    issues.append(
                        ShoppingPlanIssue(
                            code=finding.code,
                            recipe_id=finding.recipe_id,
                            recipe_name=finding.recipe_name,
                            detail=finding.person_name or finding.subject,
                        )
                    )
            return needs, issues, restriction_keys

        restriction_keys = self._owner_restriction_keys()
        entries: list[tuple[UUID4, Decimal, str | None]] = []
        if plan.source_type == ShoppingPlanSource.MEALPLAN and plan.date_from and plan.date_to:
            for meal in self.repos.pe_mealplan_entries_between(plan.date_from, plan.date_to):
                entries.append((meal.recipe_id, to_decimal(meal.recipe_scale or 1), meal.date.isoformat()))
        else:
            entries = [(entry.recipe_id, to_decimal(entry.scale), None) for entry in plan.recipes]

        for recipe_id, scale, label in entries:
            recipe = self.reader.get(recipe_id)
            if recipe is None:
                issues.append(ShoppingPlanIssue(code=FindingCode.RECIPE_NOT_FOUND, recipe_id=recipe_id))
                continue
            needs.extend(self.reader.needs(recipe, scale, label))

        return needs, issues, restriction_keys

    def _owner_restriction_keys(self) -> set[str]:
        """The restrictions of the person who uses the application: they apply to everything that person cooks."""
        by_id = self.dietary.restrictions_by_id()
        keys: set[str] = set()
        for person in self.repos.pe_persons.multi_query({"linked_user_id": self.user_id}):
            keys |= {by_id[r.restriction_id].key for r in person.restrictions if r.restriction_id in by_id}
        return keys

    def _compute(self, plan: ShoppingPlanOut, ledger: dict[str, ShoppingPlanLineOut]) -> _Computation:
        needs, issues, restriction_keys = self._collect_needs(plan)
        preferred = {key: self._unit(row.unit_id) for key, row in ledger.items() if row.unit_id is not None}
        lines = aggregate(needs, preferred)

        if plan.use_stock:
            apply_stock([*self._reservations(plan.id), *lines], self.pantry.usable_stock())
        if plan.use_packaging:
            apply_packaging(lines, self.pantry.default_packagings())

        computation = _Computation(lines=lines, issues=issues)
        if restriction_keys:
            book = self.dietary.status_book()
            for line in lines:
                view = IngredientView(
                    display=line.food_name or line.note or "", food_id=line.food_id, food_name=line.food_name
                )
                for key in sorted(restriction_keys):
                    finding = evaluate_ingredient(view, key, book)
                    if finding is not None:
                        computation.checks.setdefault(line.key, []).append(
                            ShoppingPlanCheckOut(
                                restriction_key=key,
                                status=finding.status,
                                code=finding.code,
                                term=finding.term,
                                detail=finding.detail,
                            )
                        )
        return computation

    def _reservations(self, plan_id: UUID4) -> list[RequirementLine]:
        """The stock that the other open plans already count on. This plan gets what is left."""
        reserved: list[RequirementLine] = []
        for other in self.plans.multi_query({"status": ShoppingPlanStatus.OPEN}):
            if other.id == plan_id:
                continue
            for row in self.lines.multi_query({"plan_id": other.id}):
                if row.food_id is None or row.quantity_from_stock <= 0:
                    continue
                reserved.append(
                    RequirementLine(
                        key=row.key,
                        food_id=row.food_id,
                        unit=self._unit(row.unit_id),
                        quantity_needed=to_decimal(row.quantity_from_stock),
                    )
                )
        return reserved

    # ================================================================
    # Reconciliation

    def _steps(
        self,
        plan: ShoppingPlanOut,
        computation: _Computation,
        ledger: dict[str, ShoppingPlanLineOut],
        items: dict[UUID4, ShoppingListItemOut],
        restore_dismissed: bool,
    ) -> list[_Step]:
        new_lines = {line.key: line for line in computation.lines}
        steps: list[_Step] = []

        for key in [*new_lines, *(key for key in ledger if key not in new_lines)]:
            line = new_lines.get(key)
            row = ledger.get(key)
            unit = line.unit if line is not None else self._unit(row.unit_id if row else None)

            state = None
            item = None
            if row is not None:
                state = LedgerState(
                    key=key,
                    projected_quantity=to_decimal(row.projected_quantity),
                    purchased_quantity=to_decimal(row.purchased_quantity),
                    item_id=row.shopping_list_item_id,
                    state=row.state,
                )
                item = items.get(row.shopping_list_item_id) if row.shopping_list_item_id else None

            item_state = None
            if item is not None:
                quantity = convert(to_decimal(item.quantity), unit_info(item.unit), unit)
                if quantity is None:
                    # The user gave the item a unit that does not convert: the item now belongs to the user.
                    item = None
                else:
                    item_state = ItemState(item.id, quantity, bool(item.checked))

            to_buy = line.quantity_to_buy if line is not None else Decimal("0")
            result = reconcile_line(key, to_buy, state, item_state, restore_dismissed=restore_dismissed)
            steps.append(_Step(key, line, unit, result, item))

        return steps

    def _load(
        self, plan: ShoppingPlanOut, shopping_list_id: UUID4 | None
    ) -> tuple[dict[str, ShoppingPlanLineOut], dict[UUID4, ShoppingListItemOut]]:
        """The ledger of the plan and the items of its shopping list."""
        ledger = {row.key: row for row in self.lines.multi_query({"plan_id": plan.id})}

        shopping_list = self.repos.group_shopping_lists.get_one(shopping_list_id) if shopping_list_id else None
        if shopping_list is None or shopping_list_id != plan.shopping_list_id:
            # The plan starts on a new list: nothing of the old list counts any more.
            for row in ledger.values():
                row.shopping_list_item_id = None
                row.projected_quantity = 0
                row.purchased_quantity = 0
                row.state = ShoppingPlanLineState.ACTIVE
            return ledger, {}

        return ledger, {item.id: item for item in shopping_list.list_items}

    def _preview_line(self, step: _Step, computation: _Computation) -> ShoppingPlanPreviewLine:
        line = step.line
        return ShoppingPlanPreviewLine(
            key=step.key,
            display=(line.food_name or line.note or "") if line else "",
            food_id=line.food_id if line else None,
            food_name=line.food_name if line else None,
            unit_id=step.unit.id if step.unit else None,
            unit_name=step.unit.name if step.unit else "",
            note=line.note if line else None,
            quantity_needed=float(line.quantity_needed) if line else 0,
            quantity_from_stock=float(line.quantity_from_stock) if line else 0,
            quantity_to_buy=float(line.quantity_to_buy) if line else 0,
            packs=line.packs if line else None,
            pack_label=line.pack_label if line else None,
            stock_warnings=line.stock_warnings if line else [],
            sources=self._sources(line) if line else [],
            checks=computation.checks.get(step.key, []),
            action=step.result.action,
            item_quantity=float(step.result.item_quantity),
            purchased_quantity=float(step.result.ledger.purchased_quantity),
            state=step.result.ledger.state,
        )

    @staticmethod
    def _sources(line: RequirementLine) -> list[ShoppingPlanSourceOut]:
        return [
            ShoppingPlanSourceOut(
                recipe_id=source.recipe_id,
                recipe_name=source.recipe_name,
                label=source.label,
                scale=float(source.scale),
                base_quantity=float(source.base_quantity),
                unit_name=source.unit_name,
                note=source.note,
            )
            for source in line.sources
        ]

    def preview(self, plan_id: UUID4, restore_dismissed: bool = False) -> ShoppingPlanPreviewOut:
        """Compute the plan and show what applying it does. Nothing is written."""
        plan = self.get_one(plan_id)
        ledger, items = self._load(plan, plan.shopping_list_id)
        computation = self._compute(plan, ledger)
        steps = self._steps(plan, computation, ledger, items, restore_dismissed)
        return ShoppingPlanPreviewOut(
            plan=plan,
            lines=[self._preview_line(step, computation) for step in steps],
            issues=computation.issues,
        )

    def compute_adhoc(self, data: ShoppingPlanCreate) -> ShoppingPlanPreviewOut:
        """Compute a plan that is not saved. Nothing is written: this serves a draft that waits for approval."""
        self._check(data)
        save = self._to_save(data)
        plan = ShoppingPlanOut(id=uuid4(), **save.model_dump())
        computation = self._compute(plan, {})
        steps = self._steps(plan, computation, {}, {}, False)
        return ShoppingPlanPreviewOut(
            plan=plan,
            lines=[self._preview_line(step, computation) for step in steps],
            issues=computation.issues,
        )

    def apply(self, plan_id: UUID4, data: ShoppingPlanApply) -> ShoppingPlanApplyOut:
        """Compute the plan and write the result to the native shopping list."""
        plan = self.get_one(plan_id)

        shopping_list_id = data.shopping_list_id or plan.shopping_list_id
        if shopping_list_id is None or self.repos.group_shopping_lists.get_one(shopping_list_id) is None:
            if data.shopping_list_id is not None:
                raise PersonalNotFound("Shopping list not found.")
            created = ShoppingListService(self.repos).create_one_list(ShoppingListCreate(name=plan.name), self.user_id)
            shopping_list_id = created.id

        ledger, items = self._load(plan, shopping_list_id)
        if shopping_list_id != plan.shopping_list_id:
            shopping_list = self.repos.group_shopping_lists.get_one(shopping_list_id)
            items_for_merge = {item.id: item for item in shopping_list.list_items} if shopping_list else {}
        else:
            items_for_merge = items

        computation = self._compute(plan, ledger)
        steps = self._steps(plan, computation, ledger, items, data.restore_dismissed)

        item_repo = self.repos.group_shopping_list_item
        owned = {row.shopping_list_item_id for row in ledger.values() if row.shopping_list_item_id}
        out = ShoppingPlanApplyOut(plan=plan, shopping_list_id=shopping_list_id, issues=computation.issues)

        for step in steps:
            result = step.result
            item_id = result.item_id

            if result.action == ACTION_CREATE and step.line is not None:
                target = self._mergeable_item(step.line, items_for_merge, owned)
                if target is not None:
                    quantity = to_decimal(target.quantity) + result.item_quantity
                    self._update_item(target, quantity, step.line)
                    item_id = target.id
                    out.updated += 1
                else:
                    item_id = item_repo.create(
                        self._new_item(plan, shopping_list_id, step.line, result.item_quantity)
                    ).id
                    out.created += 1
                owned.add(item_id)

            elif result.action == ACTION_UPDATE and step.item is not None:
                quantity = convert(result.item_quantity, step.unit, unit_info(step.item.unit))
                self._update_item(step.item, quantity if quantity is not None else result.item_quantity, step.line)
                out.updated += 1

            elif result.action == ACTION_DELETE and step.item is not None:
                item_repo.delete(step.item.id)
                item_id = None
                out.deleted += 1

            elif result.action == ACTION_NONE and step.item is not None and not step.item.checked:
                item_id = step.item.id

            self._store_line(plan, step, computation, item_id, ledger.get(step.key))
            out.lines.append(self._preview_line(step, computation))

        out.plan = self.plans.update(plan.id, {"shopping_list_id": shopping_list_id, "computed_at": datetime.now(UTC)})
        return out

    @staticmethod
    def _mergeable_item(
        line: RequirementLine, items: dict[UUID4, ShoppingListItemOut], owned: set[UUID4]
    ) -> ShoppingListItemOut | None:
        """An open item of the list that holds the same food in the same unit and that no line owns yet."""
        if line.food_id is None:
            return None
        unit_id = line.unit.id if line.unit else None
        for item in items.values():
            if item.checked or item.id in owned:
                continue
            if item.food_id == line.food_id and item.unit_id == unit_id:
                return item
        return None

    def _recipe_refs(self, line: RequirementLine) -> list[ShoppingListItemRecipeRefCreate]:
        """One native recipe reference for each recipe of the line, so the native list shows where it comes from."""
        refs: dict[UUID4, ShoppingListItemRecipeRefCreate] = {}
        for source in line.sources:
            if source.recipe_id is None:
                continue
            ref = refs.get(source.recipe_id)
            if ref is None:
                refs[source.recipe_id] = ShoppingListItemRecipeRefCreate(
                    recipe_id=source.recipe_id,
                    recipe_quantity=float(source.base_quantity),
                    recipe_scale=float(source.scale),
                    recipe_note=source.note,
                )
            else:
                ref.recipe_quantity += float(source.base_quantity)
        return list(refs.values())

    def _new_item(
        self, plan: ShoppingPlanOut, shopping_list_id: UUID4, line: RequirementLine, quantity: Decimal
    ) -> ShoppingListItemCreate:
        label_id = None
        if line.food_id is not None:
            food = self.repos.ingredient_foods.get_one(line.food_id)
            label_id = food.label_id if food else None

        return ShoppingListItemCreate(
            shopping_list_id=shopping_list_id,
            quantity=float(quantize(quantity)),
            food_id=line.food_id,
            unit_id=line.unit.id if line.unit else None,
            label_id=label_id,
            note=line.note or "",
            recipe_references=self._recipe_refs(line),
            extras={PLAN_EXTRA: str(plan.id)},
        )

    def _update_item(self, item: ShoppingListItemOut, quantity: Decimal, line: RequirementLine | None) -> None:
        references = list(item.recipe_references)
        if line is not None:
            ours = {ref.recipe_id: ref for ref in self._recipe_refs(line)}
            kept = [ref for ref in references if ref.recipe_id not in ours]
            references = [*kept, *ours.values()]  # type: ignore[list-item]

        update = item.cast(
            ShoppingListItemUpdate, quantity=float(quantize(max(quantity, Decimal("0")))), recipe_references=references
        )
        self.repos.group_shopping_list_item.update(item.id, update)

    def _store_line(
        self,
        plan: ShoppingPlanOut,
        step: _Step,
        computation: _Computation,
        item_id: UUID4 | None,
        row: ShoppingPlanLineOut | None,
    ) -> None:
        state = step.result.ledger
        line = step.line

        obsolete = line is None and item_id is None and state.purchased_quantity <= 0
        if obsolete and state.state != ShoppingPlanLineState.DISMISSED:
            if row is not None:
                self.lines.delete(row.id)
            return

        values = {
            **self._scope,
            "plan_id": plan.id,
            "key": step.key,
            "projected_quantity": float(state.projected_quantity) if item_id else 0,
            "purchased_quantity": float(state.purchased_quantity),
            "shopping_list_item_id": item_id,
            "state": state.state,
        }
        if line is not None:
            values.update(
                food_id=line.food_id,
                unit_id=line.unit.id if line.unit else None,
                note=line.note,
                display=line.food_name or line.note or "",
                quantity_needed=float(line.quantity_needed),
                quantity_from_stock=float(line.quantity_from_stock),
                quantity_to_buy=float(line.quantity_to_buy),
                packs=line.packs,
                pack_label=line.pack_label,
                sources=[source.model_dump(mode="json") for source in self._sources(line)],
                checks=[check.model_dump(mode="json") for check in computation.checks.get(step.key, [])],
            )
        else:
            values.update(quantity_needed=0, quantity_from_stock=0, quantity_to_buy=0, packs=None)

        if row is None:
            self.lines.create(values)
        else:
            self.lines.update(row.id, values)

    # ================================================================
    # Consumption

    def consume(self, plan_id: UUID4) -> ShoppingPlanConsumeOut:
        """
        Take what the plan needed out of the stock, once the meal is cooked, and close the plan.

        The stock never goes below zero, so a plan whose purchases were not put into the stock removes less.
        """
        plan = self.get_one(plan_id)
        if plan.status == ShoppingPlanStatus.DONE:
            raise PersonalError("PLAN_ALREADY_DONE", "This plan is already closed.")

        consumed = 0
        for row in self.lines.multi_query({"plan_id": plan_id}):
            if row.food_id is None or row.quantity_needed <= 0:
                continue
            taken = self.pantry.consume(row.food_id, to_decimal(row.quantity_needed), self._unit(row.unit_id))
            if taken > 0:
                consumed += 1

        updated = self.plans.update(plan_id, {"status": ShoppingPlanStatus.DONE})
        return ShoppingPlanConsumeOut(plan=updated, consumed=consumed)
