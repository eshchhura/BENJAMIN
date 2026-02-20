from __future__ import annotations

import os
from functools import lru_cache

from benjamin.core.approvals.service import ApprovalService
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.integrations.base import CalendarConnector, EmailConnector
from benjamin.core.integrations.google_auth import GoogleDependencyError, GoogleTokenError
from benjamin.core.integrations.google_calendar import GoogleCalendarConnector
from benjamin.core.integrations.google_gmail import GoogleGmailConnector
from benjamin.core.memory.manager import MemoryManager
from benjamin.core.notifications.notifier import NotificationRouter, build_notification_router
from benjamin.core.orchestration.orchestrator import Orchestrator
from benjamin.core.scheduler.scheduler import SchedulerService


@lru_cache(maxsize=1)
def get_memory_manager() -> MemoryManager:
    return MemoryManager()


def _google_enabled() -> bool:
    return os.getenv("BENJAMIN_GOOGLE_ENABLED", "off").casefold() == "on"


def _google_token_path() -> str:
    configured = os.getenv("BENJAMIN_GOOGLE_TOKEN_PATH")
    if configured:
        return configured
    return str(get_memory_manager().state_dir / "google_token.json")


@lru_cache(maxsize=1)
def get_calendar_connector() -> CalendarConnector | None:
    if not _google_enabled():
        return None
    try:
        return GoogleCalendarConnector(token_path=_google_token_path())
    except (GoogleDependencyError, GoogleTokenError):
        return None


@lru_cache(maxsize=1)
def get_email_connector() -> EmailConnector | None:
    if not _google_enabled():
        return None
    try:
        return GoogleGmailConnector(token_path=_google_token_path())
    except (GoogleDependencyError, GoogleTokenError):
        return None


@lru_cache(maxsize=1)
def get_orchestrator() -> Orchestrator:
    return Orchestrator(
        memory_manager=get_memory_manager(),
        scheduler_service=get_scheduler_service(),
        calendar_connector=get_calendar_connector(),
        email_connector=get_email_connector(),
    )


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
