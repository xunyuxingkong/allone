class ContractError(ValueError):
    """A deterministic structural or semantic contract failure."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


class DuplicateKeyError(ContractError):
    def __init__(self, key: object) -> None:
        super().__init__("DUPLICATE_KEY", "$", f"duplicate mapping key {key!r}")

\n