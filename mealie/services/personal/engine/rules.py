"""Keyword rules that flag a food name for a dietary restriction. A rule never marks a food as verified."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from text_unidecode import unidecode

from mealie.schema.personal.enums import FindingCode, VerificationStatus

_RULES_FILE = Path(__file__).parent.parent / "data" / "restriction_rules.json"
_PLURAL = r"(?:s|x|es|n|en|e)?"


@dataclass(frozen=True)
class RuleResult:
    status: VerificationStatus
    code: FindingCode
    term: str | None = None


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", unidecode(text).lower())
    return f" {cleaned.strip()} "


@dataclass(frozen=True)
class _CompiledRule:
    incompatible: tuple[tuple[str, re.Pattern[str]], ...]
    check: tuple[tuple[str, re.Pattern[str]], ...]
    claims: tuple[str, ...]
    exceptions: tuple[str, ...]


def _compile(terms: list[str]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    compiled = []
    for term in terms:
        normalized = normalize_text(term).strip()
        compiled.append((term, re.compile(rf"(?<![a-z0-9]){re.escape(normalized)}{_PLURAL}(?![a-z0-9])")))
    return tuple(compiled)


@lru_cache(maxsize=1)
def load_rules() -> dict[str, _CompiledRule]:
    raw: dict[str, dict[str, list[str]]] = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
    return {
        key: _CompiledRule(
            incompatible=_compile(rule.get("incompatible", [])),
            check=_compile(rule.get("check", [])),
            claims=tuple(normalize_text(claim) for claim in rule.get("claims", [])),
            exceptions=tuple(normalize_text(exception) for exception in rule.get("exceptions", [])),
        )
        for key, rule in raw.items()
    }


def classify_text(text: str | None, restriction_key: str) -> RuleResult | None:
    """
    Flag a food name or an ingredient text for one restriction.

    Return None when no rule matches: the text is then unknown, which is not the same as safe.
    """
    if not text:
        return None
    rule = load_rules().get(restriction_key)
    if rule is None:
        return None

    normalized = normalize_text(text)
    for claim in rule.claims:
        if claim in normalized:
            return RuleResult(VerificationStatus.UNVERIFIED, FindingCode.FREE_CLAIM, claim.strip())

    for exception in rule.exceptions:
        normalized = normalized.replace(exception, " ")

    for term, pattern in rule.incompatible:
        if pattern.search(normalized):
            return RuleResult(VerificationStatus.INCOMPATIBLE, FindingCode.RULE_MATCH, term)

    for term, pattern in rule.check:
        if pattern.search(normalized):
            return RuleResult(VerificationStatus.UNVERIFIED, FindingCode.LABEL_CHECK, term)

    return None
