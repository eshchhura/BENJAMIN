from functools import lru_cache

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter, build_notification_router
from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.scheduler.scheduler import SchedulerService


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


@lru_cache(maxsize=1)
def get_approval_store() -> ApprovalStore:
    return ApprovalStore(state_dir=get_memory_manager().state_dir)


@lru_cache(maxsize=1)
def get_approval_service() -> ApprovalService:
    return ApprovalService(store=get_approval_store(), memory_manager=get_memory_manager())
