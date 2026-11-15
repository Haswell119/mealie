"""What the idea feed derives from a recipe: its duration, its season, its place in the feed. No database."""

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .rules import normalize_text

_SEASONS_FILE = Path(__file__).parent.parent / "data" / "seasonal_foods.json"
_PLURAL = r"(?:s|x|es|n|en|e)?"

QUICK_MINUTES = 30
STOCK_SHARE = 0.6
COST_COVERAGE = 0.5

_DAY = ("d", "day", "days", "jour", "jours", "j", "tag", "tage", "giorno", "giorni")
_HOUR = ("h", "hr", "hrs", "hour", "hours", "heure", "heures", "std", "stunde", "stunden", "ora", "ore")
_MINUTE = ("m", "min", "mins", "mn", "minute", "minutes", "minuten", "minuto", "minuti")
_ISO = re.compile(r"^p(?:(\d+)d)?t?(?:(\d+)h)?(?:(\d+)m)?(?:\d+s)?$")
_COMPACT = re.compile(r"(\d+)\s*h\s*(\d{1,2})(?![\d\w])")
_TOKEN = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-z]+)")
_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?$")


def parse_minutes(text: str | None) -> int | None:
    """
    Read a duration that a person typed: "45 min", "1 h 30", "1 heure 15 minutes", "PT1H30M", "2 Stunden".

    Return None when the text holds no duration: the function never guesses.
    """
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return None

    iso = _ISO.match(cleaned.replace(" ", ""))
    if iso and any(iso.groups()):
        days, hours, minutes = (int(part or 0) for part in iso.groups())
        return days * 1440 + hours * 60 + minutes

    if _NUMBER.match(cleaned):
        return round(float(cleaned.replace(",", ".")))

    total = 0.0
    found = False
    compact = _COMPACT.search(cleaned)
    if compact:
        total += int(compact.group(1)) * 60 + int(compact.group(2))
        cleaned = cleaned[: compact.start()] + " " + cleaned[compact.end() :]
        found = True

    for value, unit in _TOKEN.findall(cleaned):
        number = float(value.replace(",", "."))
        if unit in _DAY:
            total += number * 1440
        elif unit in _HOUR:
            total += number * 60
        elif unit in _MINUTE:
            total += number
        else:
            continue
        found = True

    return round(total) if found and total > 0 else None


def _minutes(seconds: int | None, text: str | None) -> int | None:
    """A duration in minutes: from its number of seconds when the recipe stores one, or else from its text."""
    if seconds is not None and seconds > 0:
        return max(1, round(seconds / 60))
    return parse_minutes(text)


def recipe_minutes(
    total_time: str | None = None,
    prep_time: str | None = None,
    perform_time: str | None = None,
    total_seconds: int | None = None,
    prep_seconds: int | None = None,
    perform_seconds: int | None = None,
) -> int | None:
    """The time a recipe takes: its total time, or else its preparation and its cooking added up."""
    total = _minutes(total_seconds, total_time)
    if total is not None:
        return total
    parts = [
        minutes
        for minutes in (_minutes(prep_seconds, prep_time), _minutes(perform_seconds, perform_time))
        if minutes is not None
    ]
    return sum(parts) if parts else None


@dataclass(frozen=True)
class _Season:
    key: str
    months: frozenset[int]
    patterns: tuple[re.Pattern[str], ...]
    exceptions: tuple[str, ...]


def _pattern(name: str) -> re.Pattern[str]:
    normalized = normalize_text(name).strip()
    return re.compile(rf"(?<![a-z0-9]){re.escape(normalized)}{_PLURAL}(?![a-z0-9])")


@lru_cache(maxsize=1)
def load_seasons() -> tuple[_Season, ...]:
    raw = json.loads(_SEASONS_FILE.read_text(encoding="utf-8"))
    return tuple(
        _Season(
            key=entry["key"],
            months=frozenset(entry["months"]),
            patterns=tuple(_pattern(name) for name in entry["names"]),
            exceptions=tuple(normalize_text(exception) for exception in entry.get("exceptions", [])),
        )
        for entry in raw["foods"]
    )


def seasonal_keys(food_names: list[str], month: int) -> list[str]:
    """The produce in season this month among the foods of a recipe, each one once, in the order found."""
    found: list[str] = []
    for name in food_names:
        normalized = normalize_text(name)
        for season in load_seasons():
            if month not in season.months or season.key in found:
                continue
            text = normalized
            for exception in season.exceptions:
                text = text.replace(exception, " ")
            if any(pattern.search(text) for pattern in season.patterns):
                found.append(season.key)
    return found


def daily_rank(seed: str, key: str) -> float:
    """A number from 0 to 1 that is stable for one seed and one card: the feed changes each day, not each load."""
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def label_key(name: str) -> str:
    """The filter key of a label that the user gave to a recipe or to an inspiration."""
    return "label:" + "-".join(normalize_text(name).split())
