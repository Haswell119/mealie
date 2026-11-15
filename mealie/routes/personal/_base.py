from collections.abc import Callable

from fastapi import HTTPException, status

from mealie.routes._base.permissions import not_found
from mealie.schema.response import ErrorResponse
from mealie.services.personal.errors import PersonalError, PersonalNotFound


def run[T](action: Callable[[], T]) -> T:
    """Run a service call and turn its domain errors into HTTP errors that the frontend can show."""
    try:
        return action()
    except PersonalNotFound as e:
        raise not_found(e.message) from e
    except PersonalError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.respond(message=e.message, exception=e.code),
        ) from e
