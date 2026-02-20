class Retrieval:
    def retrieve(self, query: str) -> list[str]:
        return [f"match:{query}"]
