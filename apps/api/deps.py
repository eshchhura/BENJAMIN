from functools import lru_cache

from core.memory.manager import MemoryManager
from core.orchestration.orchestrator import Orchestrator


@lru_cache(maxsize=1)
def get_memory_manager() -> MemoryManager:
    return MemoryManager()


@lru_cache(maxsize=1)
def get_orchestrator() -> Orchestrator:
    return Orchestrator(memory_manager=get_memory_manager())
