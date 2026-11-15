"""Check recipes against dietary restrictions. Deterministic: no database, no network, no AI."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from mealie.schema.personal.enums import FindingCode, VerificationSource, VerificationStatus

from .rules import classify_text


@dataclass(frozen=True)
class IngredientView:
    """The part of a recipe ingredient that a check needs."""

    display: str
    food_id: UUID | None = None
    food_name: str | None = None
    recipe_id: UUID | None = None
    recipe_name: str | None = None


@dataclass(frozen=True)
class ToolView:
    tool_id: UUID
    name: str


@dataclass(frozen=True)
class StoredStatus:
    status: VerificationStatus
    source: VerificationSource
    reason: str | None = None


@dataclass
class StatusBook:
    """The verification states that the user stored, by food and by tool."""

    foods: dict[tuple[UUID, str], StoredStatus] = field(default_factory=dict)
    tools: dict[tuple[UUID, str], str | None] = field(default_factory=dict)

    def food_status(self, food_id: UUID | None, restriction_key: str) -> StoredStatus | None:
        if food_id is None:
            return None
        return self.foods.get((food_id, restriction_key))


@dataclass(frozen=True)
class Finding:
    restriction_key: str
    status: VerificationStatus
    code: FindingCode
    subject: str
    kind: str = "ingredient"
    term: str | None = None
    detail: str | None = None
    food_id: UUID | None = None
    tool_id: UUID | None = None
    recipe_id: UUID | None = None
    recipe_name: str | None = None


@dataclass
class ComplianceResult:
    """The state of one recipe for each restriction, with the reasons."""

    statuses: dict[str, VerificationStatus] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def status_for(self, keys: set[str] | list[str]) -> VerificationStatus:
        return worst(self.statuses.get(key, VerificationStatus.UNVERIFIED) for key in keys)

    def incompatible_keys(self) -> set[str]:
        return {key for key, status in self.statuses.items() if status == VerificationStatus.INCOMPATIBLE}


def worst(statuses) -> VerificationStatus:
    result = VerificationStatus.VERIFIED
    for status in statuses:
        if status.rank > result.rank:
            result = status
    return result


def evaluate_ingredient(ingredient: IngredientView, restriction_key: str, book: StatusBook) -> Finding | None:
    """
    Return why an ingredient is not verified for a restriction, or None when a person verified its food.

    An ingredient without stored state is never verified: at best it is unverified without a known issue.
    """
    common: dict[str, Any] = {
        "restriction_key": restriction_key,
        "subject": ingredient.display,
        "food_id": ingredient.food_id,
        "recipe_id": ingredient.recipe_id,
        "recipe_name": ingredient.recipe_name,
    }

    stored = book.food_status(ingredient.food_id, restriction_key)
    if stored is not None:
        # The storage layer already rejects a verified state that a person did not set; check it again here
        # so that a row from any other source can never count as verified.
        if stored.status == VerificationStatus.VERIFIED and stored.source == VerificationSource.MANUAL:
            return None
        status = VerificationStatus.UNVERIFIED if stored.status == VerificationStatus.VERIFIED else stored.status
        return Finding(status=status, code=FindingCode.STORED, detail=stored.reason, **common)

    text = ingredient.food_name if ingredient.food_id else ingredient.display
    rule = classify_text(text, restriction_key)
    if rule is not None:
        return Finding(status=rule.status, code=rule.code, term=rule.term, **common)

    code = FindingCode.NO_DATA if ingredient.food_id else FindingCode.FREE_TEXT
    return Finding(status=VerificationStatus.UNVERIFIED, code=code, **common)


def evaluate_recipe(
    ingredients: list[IngredientView],
    restriction_keys: set[str],
    book: StatusBook,
    tools: list[ToolView] | None = None,
    tool_check_keys: set[str] | None = None,
) -> ComplianceResult:
    """
    Check one recipe against a set of restrictions.

    `tool_check_keys` are the restrictions that reach the whole preparation: for these, a tool that the user
    flagged for cross-contamination keeps the recipe unverified.
    """
    result = ComplianceResult()

    for key in sorted(restriction_keys):
        statuses: list[VerificationStatus] = []
        if not ingredients:
            result.findings.append(
                Finding(key, VerificationStatus.UNVERIFIED, FindingCode.NO_INGREDIENTS, subject="", kind="recipe")
            )
            statuses.append(VerificationStatus.UNVERIFIED)

        for ingredient in ingredients:
            finding = evaluate_ingredient(ingredient, key, book)
            if finding is None:
                statuses.append(VerificationStatus.VERIFIED)
                continue
            statuses.append(finding.status)
            result.findings.append(finding)

        if tool_check_keys and key in tool_check_keys:
            for tool in tools or []:
                if (tool.tool_id, key) not in book.tools:
                    continue
                statuses.append(VerificationStatus.UNVERIFIED)
                result.findings.append(
                    Finding(
                        key,
                        VerificationStatus.UNVERIFIED,
                        FindingCode.TOOL_CHECK,
                        subject=tool.name,
                        kind="tool",
                        detail=book.tools[(tool.tool_id, key)],
                        tool_id=tool.tool_id,
                    )
                )

        result.statuses[key] = worst(statuses)

    return result
