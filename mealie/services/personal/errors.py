class PersonalError(Exception):
    """A request that the personal edition cannot fulfil. `code` is stable; `message` is for the user."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PersonalNotFound(PersonalError):
    def __init__(self, message: str = "Not found.") -> None:
        super().__init__("NOT_FOUND", message)
