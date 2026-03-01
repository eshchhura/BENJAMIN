from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from benjamin.core.rules.evaluator import run_rules_evaluation
from benjamin.core.rules.store import RuleStore

from .deps import (
    get_approval_service,
    get_calendar_connector,
    get_email_connector,
    get_memory_manager,
    get_notification_router,
    get_orchestrator,
    get_scheduler_service,
)
from .routes_approvals import router as approvals_router
from .routes_chat import router as chat_router
from .routes_integrations import router as integrations_router
from .routes_jobs import router as jobs_router
from .routes_memory import router as memory_router
from .routes_rules import router as rules_router
from .routes_tasks import router as tasks_router
from .routes_ui import router as ui_router

app = FastAPI(title="Benjamin API")
app.mount("/ui/static", StaticFiles(directory="src/benjamin/apps/api/static"), name="ui-static")

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
app.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
app.include_router(rules_router, prefix="/rules", tags=["rules"])
app.include_router(ui_router, prefix="/ui", tags=["ui"])


@app.on_event("startup")
def startup() -> None:
    app.state.memory_manager = get_memory_manager()
    app.state.scheduler_service = get_scheduler_service()
    app.state.orchestrator = get_orchestrator()
    app.state.notification_router = get_notification_router()
    app.state.approval_service = get_approval_service()
    app.state.calendar_connector = get_calendar_connector()
    app.state.email_connector = get_email_connector()
    app.state.rule_store = RuleStore(state_dir=app.state.memory_manager.state_dir)
    app.state.last_rule_results = []

    app.state.scheduler_service.start()

    if os.getenv("BENJAMIN_RULES_ENABLED", "off").casefold() == "on":
        every_minutes = int(os.getenv("BENJAMIN_RULES_EVERY_MINUTES", "5"))
        app.state.scheduler_service.scheduler.add_job(
            run_rules_evaluation,
            trigger="interval",
            id="rules-evaluator",
            minutes=every_minutes,
            kwargs={
                "state_dir": str(app.state.memory_manager.state_dir),
                "router": app.state.notification_router,
                "calendar_connector": app.state.calendar_connector,
                "email_connector": app.state.email_connector,
            },
            replace_existing=True,
        )


@app.on_event("shutdown")
def shutdown() -> None:
    get_scheduler_service().shutdown()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    uvicorn.run("benjamin.apps.api.main:app", reload=True, host="127.0.0.1", port=8000)
