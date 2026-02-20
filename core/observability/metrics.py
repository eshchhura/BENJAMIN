class Metrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def increment(self, key: str) -> None:
        self.counters[key] = self.counters.get(key, 0) + 1
