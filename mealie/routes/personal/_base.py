from collections.abc import Callable
from contextvars import ContextVar

from fastapi import Header, HTTPException, status

from mealie.routes._base.permissions import not_found
from mealie.schema.response import ErrorResponse
from mealie.services.personal.errors import PersonalError, PersonalNotFound

_locale: ContextVar[str | None] = ContextVar("personal_locale", default=None)


async def remember_locale(accept_language: str | None = Header(None)) -> None:
    """Keep the language of the request, so that an error message can use it."""
    _locale.set(accept_language)


def run[T](action: Callable[[], T]) -> T:
    """Run a service call and turn its domain errors into HTTP errors that the frontend can show."""
    try:
        return action()
    except PersonalNotFound as e:
        raise not_found(e.localized(_locale.get())) from e
    except PersonalError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.respond(message=e.localized(_locale.get()), exception=e.code),
        ) from e
