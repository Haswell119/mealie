import json
from functools import lru_cache
from pathlib import Path

_MESSAGES_FILE = Path(__file__).parent / "data" / "messages.json"


class PersonalError(Exception):
    """
    A request that the personal edition cannot fulfil.

    `code` is stable. `message` is the English text, with `params` as its values. `localized` gives the
    text in the language of the user when a translation exists.
    """

    def __init__(self, code: str, message: str, **params) -> None:
        self.code = code
        self.params = params
        self.message = message.format(**params) if params else message
        super().__init__(self.message)

    def localized(self, locale: str | None) -> str:
        template = _messages(_language(locale)).get("codes", {}).get(self.code)
        if template is None:
            return self.message
        try:
            return template.format(**self.params)
        except KeyError, IndexError:
            return self.message


class PersonalNotFound(PersonalError):
    def __init__(self, message: str = "Not found.") -> None:
        super().__init__("NOT_FOUND", message)

    def localized(self, locale: str | None) -> str:
        return _messages(_language(locale)).get("not_found", {}).get(self.message, self.message)


def _language(locale: str | None) -> str:
    return (locale or "").strip().lower().replace("_", "-").split(",")[0].split("-")[0]


@lru_cache(maxsize=1)
def _all_messages() -> dict:
    return json.loads(_MESSAGES_FILE.read_text(encoding="utf-8"))


def _messages(language: str) -> dict:
    return _all_messages().get(language, {})
