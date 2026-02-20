from typing import Protocol


class MemoryStore(Protocol):
    def put(self, key: str, value: str) -> None: ...

    def get(self, key: str) -> str | None: ...
