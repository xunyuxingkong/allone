class SourceSpan:
    def __init__(self, file: str, line: int | None = None, column: int | None = None) -> None:
        self.file = file
        self.line = line
        self.column = column


class ContractError(ValueError):
    """A deterministic structural or semantic contract failure."""

    def __init__(self, code: str, path: str, message: str, *, source: SourceSpan | None = None, details: dict[str, object] | None = None, cause: Exception | None = None) -> None:
        self.code = code
        self.path = path
        self.source = source
        self.details = details or {}
        self.cause = cause
        super().__init__(f"{code} at {path}: {message}")


class DuplicateKeyError(ContractError):
    def __init__(self, key: object) -> None:
        super().__init__("DUPLICATE_KEY", "$", f"duplicate mapping key {key!r}")
