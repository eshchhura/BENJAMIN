from dataclasses import dataclass


@dataclass
class MemoryDecision:
    save: bool
    reason: str


class MemoryWritePolicy:
    def should_save(self, text: str) -> MemoryDecision:
        if len(text.strip()) < 10:
            return MemoryDecision(save=False, reason="Too short")
        return MemoryDecision(save=True, reason="Useful context")
