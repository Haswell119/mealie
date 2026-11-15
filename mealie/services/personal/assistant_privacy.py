"""
The single place where text leaves the application for the AI provider.

The provider never receives the name of a person, a note about a person, or the medical nature of a
restriction. It receives constraints without names: "guest 2 eats no meat".
"""

import re
from uuid import UUID

PLACEHOLDER = "convive"


class Anonymizer:
    """Replaces the names of persons with numbered placeholders, and puts the names back in a reply."""

    def __init__(self, names_by_id: dict[UUID, str]) -> None:
        self._labels: dict[UUID, str] = {}
        self._patterns: list[tuple[re.Pattern[str], str]] = []
        self._names_by_label: dict[str, str] = {}

        ordered = sorted(names_by_id.items(), key=lambda entry: (-len(entry[1]), str(entry[0])))
        numbering = {person_id: index + 1 for index, person_id in enumerate(sorted(names_by_id, key=str))}
        for person_id, name in ordered:
            label = f"{PLACEHOLDER} {numbering[person_id]}"
            self._labels[person_id] = label
            self._names_by_label[label] = name
            cleaned = name.strip()
            if len(cleaned) >= 2:
                self._patterns.append((re.compile(rf"(?<!\w){re.escape(cleaned)}(?!\w)", re.IGNORECASE), label))

    def label(self, person_id: UUID) -> str:
        return self._labels.get(person_id, PLACEHOLDER)

    def scrub(self, text: str) -> str:
        """Remove every known name from a text that goes to the provider."""
        for pattern, label in self._patterns:
            text = pattern.sub(label, text)
        return text

    def restore(self, text: str) -> str:
        """Put the names back into a text that came from the provider. This happens only inside the application."""
        for label in sorted(self._names_by_label, key=len, reverse=True):
            text = re.sub(rf"(?<!\w){re.escape(label)}(?!\d)", self._names_by_label[label], text, flags=re.IGNORECASE)
        return text
