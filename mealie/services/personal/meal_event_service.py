import json
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.enums import FindingCode, MealEventStatus, RestrictionScope, VerificationStatus
from mealie.schema.personal.meal_event import (
    AppliedConstraintOut,
    ChecklistItemOut,
    ConstraintSetOut,
    FindingOut,
    MealEventAnalysisOut,
    MealEventAssignmentSet,
    MealEventCreate,
    MealEventGuestCreate,
    MealEventMenuItemCreate,
    MealEventOut,
    MealEventOverrideCreate,
    MealEventSave,
    MealEventStatusUpdate,
    MenuItemAnalysisOut,
    PersonConstraintsOut,
    VariantAnalysisOut,
)
from mealie.schema.personal.person import PersonOut
from mealie.schema.recipe.recipe import RecipeOut

from .dietary_service import DietaryService
from .engine.compliance import ComplianceResult, Finding, evaluate_recipe, worst
from .engine.constraints import (
    AppliedConstraint,
    ConstraintSet,
    PersonRestriction,
    ScopeOverride,
    resolve_constraints,
)
from .engine.portions import (
    Diner,
    MissingServingsError,
    VariantOption,
    assign_variants,
    portions_by_variant,
    scale_for,
)
from .engine.units import quantize, to_decimal
from .errors import PersonalError, PersonalNotFound
from .recipe_needs import RecipeReader

PREPARATION_CHECKLIST = ["CHECK_LABELS", "CLEAN_SURFACES", "DEDICATED_UTENSILS", "SEPARATE_COOKING", "SERVE_SEPARATELY"]
MEAL_CHECKLIST = ["CHECK_LABELS"]


@dataclass
class VariantPlan:
    """What the event needs of one variant: the recipe and the factor to scale it by."""

    variant_id: UUID4
    recipe: RecipeOut
    portions: Decimal
    scale: Decimal
    label: str | None


@dataclass
class EventAnalysis:
    out: MealEventAnalysisOut
    plans: list[VariantPlan] = field(default_factory=list)
    shared_keys: set[str] = field(default_factory=set)


class MealEventService:
    """Meal events: the guests, the menu, and the check of the menu against the restrictions of the guests."""

    def __init__(self, repos: AllRepositories, user_id: UUID4 | None = None) -> None:
        self.repos = repos
        self.user_id = user_id
        self.events = repos.pe_meal_events
        self.dietary = DietaryService(repos)
        self.reader = RecipeReader(repos)

    @property
    def _scope(self) -> dict:
        return {"group_id": self.repos.group_id, "household_id": self.repos.household_id}

    # ================================================================
    # Event

    def get_one(self, event_id: UUID4) -> MealEventOut:
        event = self.events.get_one(event_id)
        if event is None:
            raise PersonalNotFound("Event not found.")
        return event

    def create(self, data: MealEventCreate) -> MealEventOut:
        self._check_event(data)
        event = self.events.create(data.cast(MealEventSave, **self._scope))
        self._log(event.id, "CREATED")
        return self.get_one(event.id)

    def update(self, event_id: UUID4, data: MealEventCreate) -> MealEventOut:
        event = self.get_one(event_id)
        self._check_event(data)
        self.events.update(event_id, data.model_dump())
        if (event.cook_person_id, event.leftover_portions) != (data.cook_person_id, data.leftover_portions):
            self._reopen(event, "EVENT_CHANGED")
        return self.get_one(event_id)

    def delete(self, event_id: UUID4) -> MealEventOut:
        event = self.get_one(event_id)
        for plan in self.repos.pe_shopping_plans.multi_query({"event_id": event_id}):
            self.repos.pe_shopping_plans.delete(plan.id)
        for proposal in self.repos.pe_ai_proposals.multi_query({"event_id": event_id}):
            self.repos.pe_ai_proposals.update(proposal.id, {"event_id": None})
        self.events.delete(event_id)
        return event

    def _check_event(self, data: MealEventCreate) -> None:
        if not data.name.strip():
            raise PersonalError("EVENT_NAME_REQUIRED", "An event needs a name.")
        if data.cook_person_id is not None and self.repos.pe_persons.get_one(data.cook_person_id) is None:
            raise PersonalNotFound("Person not found.")

    def _log(self, event_id: UUID4, action: str, detail: dict | None = None) -> None:
        self.repos.pe_meal_event_history.create(
            {
                **self._scope,
                "event_id": event_id,
                "user_id": self.user_id,
                "action": action,
                "detail": json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
            }
        )

    def _reopen(self, event: MealEventOut, reason: str) -> None:
        """A planned event whose guests or menu change must be checked and planned again."""
        if event.status == MealEventStatus.PLANNED:
            self.events.update(event.id, {"status": MealEventStatus.DRAFT})
            self._log(event.id, "REOPENED", {"reason": reason})

    # ================================================================
    # Guests

    def set_guests(self, event_id: UUID4, guests: list[MealEventGuestCreate]) -> MealEventOut:
        event = self.get_one(event_id)
        wanted: dict[UUID4, MealEventGuestCreate] = {}
        for guest in guests:
            if self.repos.pe_persons.get_one(guest.person_id) is None:
                raise PersonalNotFound("Person not found.")
            wanted[guest.person_id] = guest

        repo = self.repos.pe_meal_event_guests
        existing = {guest.person_id: guest for guest in event.guests}

        for person_id, row in existing.items():
            if person_id not in wanted:
                repo.delete(row.id)
                for assignment in event.assignments:
                    if assignment.person_id == person_id:
                        self.repos.pe_meal_event_assignments.delete(assignment.id)

        for person_id, guest in wanted.items():
            values = {"attending": guest.attending, "appetite_override": guest.appetite_override}
            if person_id in existing:
                repo.update(existing[person_id].id, values)
            else:
                repo.create({**self._scope, "event_id": event_id, "person_id": person_id, **values})

        self._log(event_id, "GUESTS_CHANGED", {"count": sum(1 for guest in wanted.values() if guest.attending)})
        self._reopen(event, "GUESTS_CHANGED")
        return self.get_one(event_id)

    # ================================================================
    # Menu

    def set_menu(self, event_id: UUID4, items: list[MealEventMenuItemCreate]) -> MealEventOut:
        event = self.get_one(event_id)
        for item in items:
            for variant in item.variants:
                if self.reader.get(variant.recipe_id) is None:
                    raise PersonalNotFound("Recipe not found.")

        items_repo = self.repos.pe_meal_event_menu_items
        variants_repo = self.repos.pe_meal_event_variants
        existing_items = {item.id: item for item in event.menu_items}
        kept_items: set[UUID4] = set()
        kept_variants: set[UUID4] = set()

        for position, item in enumerate(items):
            values = {"course": item.course, "title": item.title, "position": position}
            if item.id is not None and item.id in existing_items:
                items_repo.update(item.id, values)
                item_id = item.id
                existing_variants = {variant.id for variant in existing_items[item.id].variants}
            else:
                item_id = items_repo.create({**self._scope, "event_id": event_id, **values}).id
                existing_variants = set()
            kept_items.add(item_id)

            for variant_position, variant in enumerate(item.variants):
                variant_values = {
                    "recipe_id": variant.recipe_id,
                    "label": variant.label,
                    "position": variant_position,
                    "portions_override": variant.portions_override,
                }
                if variant.id is not None and variant.id in existing_variants:
                    variants_repo.update(variant.id, variant_values)
                    kept_variants.add(variant.id)
                else:
                    created = variants_repo.create(
                        {**self._scope, "event_id": event_id, "menu_item_id": item_id, **variant_values}
                    )
                    kept_variants.add(created.id)

        for assignment in event.assignments:
            if assignment.menu_item_id not in kept_items or assignment.variant_id not in kept_variants:
                self.repos.pe_meal_event_assignments.delete(assignment.id)
        for override in event.overrides:
            if override.menu_item_id is not None and override.menu_item_id not in kept_items:
                self.repos.pe_meal_event_overrides.delete(override.id)
        for existing_item in event.menu_items:
            for existing_variant in existing_item.variants:
                if existing_variant.id not in kept_variants:
                    variants_repo.delete(existing_variant.id)
            if existing_item.id not in kept_items:
                items_repo.delete(existing_item.id)

        self._log(event_id, "MENU_CHANGED", {"items": len(items)})
        self._reopen(event, "MENU_CHANGED")
        return self.get_one(event_id)

    def set_assignment(self, event_id: UUID4, data: MealEventAssignmentSet) -> MealEventOut:
        event = self.get_one(event_id)
        item = next((item for item in event.menu_items if item.id == data.menu_item_id), None)
        if item is None:
            raise PersonalNotFound("Menu item not found.")
        if data.person_id not in {guest.person_id for guest in event.guests}:
            raise PersonalNotFound("The person is not a guest of this event.")

        repo = self.repos.pe_meal_event_assignments
        for assignment in event.assignments:
            if (assignment.menu_item_id, assignment.person_id) == (data.menu_item_id, data.person_id):
                repo.delete(assignment.id)

        if data.variant_id is not None:
            if data.variant_id not in {variant.id for variant in item.variants}:
                raise PersonalNotFound("Variant not found.")
            repo.create({**self._scope, "event_id": event_id, **data.model_dump()})

        self._log(event_id, "ASSIGNMENT_CHANGED", data.model_dump())
        self._reopen(event, "ASSIGNMENT_CHANGED")
        return self.get_one(event_id)

    # ================================================================
    # Overrides

    def add_override(self, event_id: UUID4, data: MealEventOverrideCreate) -> MealEventOut:
        """
        Change how far a restriction of one person reaches, for this event or for one menu item.

        Only a person can do this, and the change stays in the history of the event with its reason.
        """
        event = self.get_one(event_id)
        person = self.repos.pe_persons.get_one(data.person_id)
        if person is None:
            raise PersonalNotFound("Person not found.")
        restriction = self.dietary.get_restriction(data.restriction_id)
        if data.restriction_id not in {r.restriction_id for r in person.restrictions}:
            raise PersonalError("OVERRIDE_WITHOUT_RESTRICTION", "The person does not have this restriction.")
        if data.menu_item_id is not None and data.menu_item_id not in {item.id for item in event.menu_items}:
            raise PersonalNotFound("Menu item not found.")

        repo = self.repos.pe_meal_event_overrides
        for override in event.overrides:
            same = (override.person_id, override.restriction_id, override.menu_item_id) == (
                data.person_id,
                data.restriction_id,
                data.menu_item_id,
            )
            if same:
                repo.delete(override.id)

        repo.create({**self._scope, "event_id": event_id, "created_by": self.user_id, **data.model_dump()})
        self._log(
            event_id,
            "RESTRICTION_SCOPE_OVERRIDDEN",
            {
                "person_id": data.person_id,
                "restriction": restriction.key,
                "scope": data.scope,
                "menu_item_id": data.menu_item_id,
                "reason": data.reason,
            },
        )
        self._reopen(event, "OVERRIDE_CHANGED")
        return self.get_one(event_id)

    def delete_override(self, event_id: UUID4, override_id: UUID4) -> MealEventOut:
        event = self.get_one(event_id)
        if override_id not in {override.id for override in event.overrides}:
            raise PersonalNotFound("Override not found.")
        self.repos.pe_meal_event_overrides.delete(override_id)
        self._log(event_id, "RESTRICTION_SCOPE_OVERRIDE_REMOVED", {"override_id": override_id})
        self._reopen(event, "OVERRIDE_CHANGED")
        return self.get_one(event_id)

    # ================================================================
    # Status

    def set_status(self, event_id: UUID4, data: MealEventStatusUpdate) -> MealEventOut:
        event = self.get_one(event_id)
        if data.status == event.status:
            return event

        if data.status == MealEventStatus.PLANNED:
            analysis = self._analyze(event).out
            if analysis.total_persons == 0:
                raise PersonalError("EVENT_WITHOUT_GUESTS", "Add at least one guest before you plan the event.")
            if not any(item.variants for item in analysis.menu):
                raise PersonalError("EVENT_WITHOUT_MENU", "Add at least one recipe before you plan the event.")
            if analysis.blocking:
                raise PersonalError(
                    "EVENT_HAS_BLOCKING_ISSUES",
                    "The menu has {count} issue(s) that break a restriction. Fix them first.",
                    count=len(analysis.blocking),
                )
            if analysis.to_verify and not data.acknowledge_unverified:
                raise PersonalError(
                    "UNVERIFIED_NOT_ACKNOWLEDGED",
                    "{count} item(s) are not verified. Confirm that you saw them.",
                    count=len(analysis.to_verify),
                )
            detail = {"unverified": len(analysis.to_verify), "acknowledged": data.acknowledge_unverified}
            self._log(event_id, "PLANNED", detail)
        else:
            self._log(event_id, f"STATUS_{data.status}")

        self.events.update(event_id, {"status": data.status})
        return self.get_one(event_id)

    # ================================================================
    # Analysis

    def analyze(self, event_id: UUID4) -> MealEventAnalysisOut:
        return self._analyze(self.get_one(event_id)).out

    def analyze_full(self, event_id: UUID4) -> EventAnalysis:
        return self._analyze(self.get_one(event_id))

    def _analyze(self, event: MealEventOut) -> EventAnalysis:  # noqa: C901
        restrictions_by_id = self.dietary.restrictions_by_id()
        names_by_key = {restriction.key: restriction.name for restriction in restrictions_by_id.values()}

        attending = [guest for guest in event.guests if guest.attending]
        attending_ids = {guest.person_id for guest in attending}
        involved = set(attending_ids)
        if event.cook_person_id is not None:
            involved.add(event.cook_person_id)

        persons: dict[UUID4, PersonOut] = {}
        for person_id in involved:
            person = self.repos.pe_persons.get_one(person_id)
            if person is not None:
                persons[person_id] = person
        person_names = {person_id: person.display_name for person_id, person in persons.items()}

        restrictions = [
            PersonRestriction(
                person.id,
                restrictions_by_id[row.restriction_id].key,
                row.severity,
                row.default_scope,
                row.applies_when_cooking,
            )
            for person in persons.values()
            for row in person.restrictions
            if row.restriction_id in restrictions_by_id
        ]
        overrides = [
            ScopeOverride(o.person_id, restrictions_by_id[o.restriction_id].key, o.scope, o.menu_item_id)
            for o in event.overrides
            if o.restriction_id in restrictions_by_id
        ]
        diners = [Diner(guest.person_id, guest.appetite_override or guest.person.appetite) for guest in attending]
        book = self.dietary.status_book()

        def constraint_out(constraint: AppliedConstraint) -> AppliedConstraintOut:
            return AppliedConstraintOut(
                restriction_key=constraint.restriction_key,
                restriction_name=names_by_key.get(constraint.restriction_key, constraint.restriction_key),
                scope=constraint.scope,
                severity=constraint.severity,
                person_ids=constraint.person_ids,
                person_names=[person_names.get(person_id, "") for person_id in constraint.person_ids],
                origins=constraint.origins,
            )

        def constraints_out(constraints: ConstraintSet) -> ConstraintSetOut:
            return ConstraintSetOut(
                shared=[constraint_out(c) for _, c in sorted(constraints.shared.items())],
                individual=[
                    PersonConstraintsOut(
                        person_id=person_id,
                        person_name=person_names.get(person_id, ""),
                        constraints=[constraint_out(c) for _, c in sorted(keys.items())],
                    )
                    for person_id, keys in sorted(constraints.individual.items(), key=lambda entry: str(entry[0]))
                ],
            )

        def finding_out(finding: Finding, **extra) -> FindingOut:
            return FindingOut(
                restriction_key=finding.restriction_key,
                status=finding.status,
                code=finding.code,
                subject=finding.subject,
                kind=finding.kind,
                term=finding.term,
                detail=finding.detail,
                food_id=finding.food_id,
                tool_id=finding.tool_id,
                recipe_id=finding.recipe_id,
                recipe_name=finding.recipe_name,
                **extra,
            )

        event_constraints = resolve_constraints(attending_ids, event.cook_person_id, restrictions, overrides)
        leftovers = to_decimal(event.leftover_portions)

        result = EventAnalysis(
            out=MealEventAnalysisOut(
                event_id=event.id,
                total_persons=len(attending),
                total_portions=float(quantize(sum((diner.factor for diner in diners), Decimal("0")) + leftovers)),
                constraints=constraints_out(event_constraints),
            )
        )
        blocking: dict[tuple, FindingOut] = {}
        to_verify: dict[tuple, FindingOut] = {}
        checklist: dict[tuple, ChecklistItemOut] = {}
        statuses: list[VerificationStatus] = []

        def collect(finding: FindingOut) -> None:
            key = (finding.restriction_key, finding.code, finding.subject, finding.food_id, finding.recipe_id)
            target = blocking if finding.status == VerificationStatus.INCOMPATIBLE else to_verify
            target.setdefault(key, finding)

        for item in event.menu_items:
            constraints = resolve_constraints(
                attending_ids, event.cook_person_id, restrictions, overrides, menu_item_id=item.id
            )
            result.shared_keys |= constraints.shared_keys
            individual_keys = {person_id: constraints.individual_keys(person_id) for person_id in attending_ids}
            all_individual = set().union(*individual_keys.values()) if individual_keys else set()
            keys_to_check = constraints.shared_keys | all_individual

            for key, constraint in constraints.shared.items():
                codes = (
                    PREPARATION_CHECKLIST if constraint.scope == RestrictionScope.ENTIRE_PREPARATION else MEAL_CHECKLIST
                )
                for code in codes:
                    checklist.setdefault((code, key, ""), ChecklistItemOut(code=code, restriction_key=key))

            recipes: dict[UUID4, RecipeOut | None] = {}
            compliance: dict[UUID4, ComplianceResult] = {}
            options: list[VariantOption] = []
            for variant in item.variants:
                recipe = self.reader.get(variant.recipe_id)
                recipes[variant.id] = recipe
                if recipe is None:
                    compliance[variant.id] = ComplianceResult()
                    options.append(VariantOption(variant.id))
                    continue
                compliance[variant.id] = evaluate_recipe(
                    self.reader.ingredient_views(recipe),
                    keys_to_check,
                    book,
                    self.reader.tool_views(recipe),
                    tool_check_keys=constraints.preparation_keys(),
                )
                options.append(
                    VariantOption(variant.id, frozenset(compliance[variant.id].incompatible_keys() & all_individual))
                )

            manual = {a.person_id: a.variant_id for a in event.assignments if a.menu_item_id == item.id}
            assignment = assign_variants(diners, individual_keys, options, manual)
            portions = portions_by_variant(
                diners,
                assignment,
                options,
                leftovers,
                overrides={v.id: v.portions_override for v in item.variants if v.portions_override is not None},
            )

            item_out = MenuItemAnalysisOut(
                menu_item_id=item.id,
                course=item.course,
                title=item.title,
                constraints=constraints_out(constraints),
                unassigned_person_ids=assignment.unassigned,
                unassigned_person_names=[person_names.get(person_id, "") for person_id in assignment.unassigned],
            )

            for person_id in assignment.unassigned:
                for key in sorted(individual_keys.get(person_id, set())):
                    collect(
                        FindingOut(
                            restriction_key=key,
                            status=VerificationStatus.INCOMPATIBLE,
                            code=FindingCode.NO_VARIANT,
                            subject=item.title or item.course,
                            kind="menu_item",
                            person_id=person_id,
                            person_name=person_names.get(person_id),
                        )
                    )

            for variant in item.variants:
                recipe = recipes[variant.id]
                eaters = [person_id for person_id, chosen in assignment.by_person.items() if chosen == variant.id]
                variant_portions = portions[variant.id]
                variant_out = VariantAnalysisOut(
                    variant_id=variant.id,
                    recipe_id=variant.recipe_id,
                    label=variant.label,
                    portions=float(quantize(variant_portions)),
                    person_ids=eaters,
                    person_names=[person_names.get(person_id, "") for person_id in eaters],
                )
                item_out.variants.append(variant_out)

                if recipe is None:
                    variant_out.error = FindingCode.RECIPE_NOT_FOUND
                    variant_out.status = VerificationStatus.INCOMPATIBLE
                    collect(
                        FindingOut(
                            restriction_key="",
                            status=VerificationStatus.INCOMPATIBLE,
                            code=FindingCode.RECIPE_NOT_FOUND,
                            subject=variant.label or "",
                            kind="recipe",
                            recipe_id=variant.recipe_id,
                        )
                    )
                    statuses.append(VerificationStatus.INCOMPATIBLE)
                    continue

                variant_out.recipe_name = recipe.name or ""
                variant_out.recipe_slug = recipe.slug or ""
                variant_out.recipe_servings = recipe.recipe_servings

                relevant = set(constraints.shared_keys)
                for person_id in eaters:
                    relevant |= individual_keys.get(person_id, set())
                variant_result = compliance[variant.id]
                variant_out.statuses = {key: variant_result.statuses[key] for key in sorted(relevant)}
                variant_out.status = variant_result.status_for(relevant)
                variant_out.findings = [
                    finding_out(finding) for finding in variant_result.findings if finding.restriction_key in relevant
                ]

                for person_id, keys in assignment.conflicts.items():
                    if assignment.by_person.get(person_id) != variant.id:
                        continue
                    for key in sorted(keys):
                        variant_out.findings.append(
                            FindingOut(
                                restriction_key=key,
                                status=VerificationStatus.INCOMPATIBLE,
                                code=FindingCode.MANUAL_ASSIGNMENT,
                                subject=recipe.name or "",
                                kind="assignment",
                                recipe_id=recipe.id,
                                recipe_name=recipe.name,
                                person_id=person_id,
                                person_name=person_names.get(person_id),
                            )
                        )

                if variant_portions <= 0:
                    # Nobody eats this variant, so it is not cooked and cannot break a restriction.
                    continue

                statuses.append(variant_out.status)
                for finding in variant_out.findings:
                    collect(finding)
                    if finding.code == FindingCode.TOOL_CHECK:
                        checklist.setdefault(
                            ("TOOL_CHECK", finding.restriction_key, finding.subject),
                            ChecklistItemOut(
                                code="TOOL_CHECK",
                                restriction_key=finding.restriction_key,
                                subject=finding.subject,
                                detail=finding.detail,
                            ),
                        )

                try:
                    scale = scale_for(variant_portions, recipe.recipe_servings, recipe.id, recipe.name)
                except MissingServingsError:
                    variant_out.error = FindingCode.MISSING_SERVINGS
                    collect(
                        FindingOut(
                            restriction_key="",
                            status=VerificationStatus.INCOMPATIBLE,
                            code=FindingCode.MISSING_SERVINGS,
                            subject=recipe.name or "",
                            kind="recipe",
                            recipe_id=recipe.id,
                            recipe_name=recipe.name,
                        )
                    )
                    continue

                variant_out.scale = float(scale)
                label = variant.label or item.title
                result.plans.append(VariantPlan(variant.id, recipe, variant_portions, scale, label))

            result.out.menu.append(item_out)

        out = result.out
        out.blocking = list(blocking.values())
        out.to_verify = list(to_verify.values())
        out.checklist = list(checklist.values())
        out.status = VerificationStatus.INCOMPATIBLE if blocking else worst(statuses)
        out.can_plan = bool(not blocking and out.total_persons > 0 and result.plans)
        return result
