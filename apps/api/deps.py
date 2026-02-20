from functools import lru_cache

from core.memory.manager import MemoryManager
from core.notifications.notifier import NotificationRouter, build_notification_router
from core.orchestration.orchestrator import Orchestrator
from core.scheduler.scheduler import SchedulerService


@lru_cache(maxsize=1)
def get_memory_manager() -> MemoryManager:
    return MemoryManager()


@lru_cache(maxsize=1)
def get_orchestrator() -> Orchestrator:
    return Orchestrator(memory_manager=get_memory_manager(), scheduler_service=get_scheduler_service())


@lru_cache(maxsize=1)
def get_scheduler_service() -> SchedulerService:
    return SchedulerService(state_dir=get_memory_manager().state_dir)


@lru_cache(maxsize=1)
def get_notification_router() -> NotificationRouter:
    return build_notification_router()
