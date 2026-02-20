class SemanticMemory:
    def __init__(self) -> None:
        self._facts: dict[str, str] = {}

    def remember(self, key: str, fact: str) -> None:
        self._facts[key] = fact

    def recall(self, key: str) -> str | None:
        return self._facts.get(key)
