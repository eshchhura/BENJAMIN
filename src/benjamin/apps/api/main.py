from __future__ import annotations

import os

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from benjamin.core.rules.evaluator import run_rules_evaluation
from benjamin.core.rules.store import RuleStore
from benjamin.core.observability.query import search_runs
from benjamin.core.runs.store import TaskStore

from .deps import (
    get_approval_service,
    get_calendar_connector,
    get_email_connector,
    get_memory_manager,
    get_notification_router,
    get_orchestrator,
    get_scheduler_service,
)
from .auth import is_auth_enabled, is_request_authenticated, should_protect_chat_post
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


@app.middleware("http")
async def auth_middleware(request, call_next):
    path = request.url.path
    method = request.method.upper()

    if path.startswith("/healthz"):
        return await call_next(request)

    if not is_auth_enabled():
        return await call_next(request)

    if path.startswith("/ui"):
        if path == "/ui/login" and method in {"GET", "POST"}:
            return await call_next(request)
        if is_request_authenticated(request):
            return await call_next(request)
        return RedirectResponse(url="/ui/login", status_code=302)

    protected_prefixes = ("/approvals", "/jobs", "/rules", "/memory")
    if method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith(protected_prefixes):
        if not is_request_authenticated(request):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})

    if should_protect_chat_post() and method == "POST" and path.startswith("/chat"):
        if not is_request_authenticated(request):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})

    return await call_next(request)


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
    app.state.task_store = TaskStore(
        state_dir=app.state.memory_manager.state_dir,
        max_records=int(os.getenv("BENJAMIN_TASKS_MAX", "500")),
    )
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
                "job_id": "rules-evaluator",
                "router": app.state.notification_router,
                "calendar_connector": app.state.calendar_connector,
                "email_connector": app.state.email_connector,
            },
            replace_existing=True,
        )


@app.on_event("shutdown")
def shutdown() -> None:
    get_scheduler_service().shutdown()


@app.get("/runs/search")
def runs_search(q: str = Query(default=""), limit: int = Query(default=50), kind: str = Query(default="all"), status: str = Query(default="all")) -> dict:
    normalized_kind = kind if kind in {"chat", "rule", "job", "approval", "all"} else "all"
    normalized_status = status if status in {"ok", "failed", "skipped", "all"} else "all"
    normalized_limit = max(1, min(200, limit))
    sections = search_runs(
        kind=normalized_kind,
        status=normalized_status,
        q=q,
        limit=normalized_limit,
        task_store=app.state.task_store,
        episodic_store=app.state.memory_manager.episodic,
        ledger=app.state.approval_service.ledger,
        approval_store=app.state.approval_service.store,
    )
    return {
        "kind": normalized_kind,
        "status": normalized_status,
        "q": q,
        "limit": normalized_limit,
        **{
            key: [item.model_dump() for item in values]
            for key, values in sections.items()
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


def run() -> None:
    uvicorn.run("benjamin.apps.api.main:app", reload=True, host="127.0.0.1", port=8000)
