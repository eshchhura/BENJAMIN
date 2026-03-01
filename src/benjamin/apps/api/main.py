from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4
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
from .routes_security import router as security_router
from .routes_tasks import router as tasks_router
from .routes_ui import router as ui_router
from benjamin.core.cache.ttl import TTLCache
from benjamin.core.http.client import request_with_retry
from benjamin.core.http.errors import BenjaminHTTPError
from benjamin.core.logging import configure_logging
from benjamin.core.logging.context import log_context
from benjamin.core.models.llm_provider import BenjaminLLM


def _is_on(name: str, default: str = "off") -> bool:
    return os.getenv(name, default).strip().casefold() == "on"


def _state_dir() -> Path:
    configured = os.getenv("BENJAMIN_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".benjamin"


def _google_token_path(state_dir: Path) -> Path:
    configured = os.getenv("BENJAMIN_GOOGLE_TOKEN_PATH")
    if configured:
        return Path(configured).expanduser()
    return state_dir / "google_token.json"


def _state_dir_writable(state_dir: Path) -> bool:
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        probe = state_dir / ".write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _llm_base_url(provider: str) -> str:
    if provider == "vllm":
        url = os.getenv("BENJAMIN_VLLM_URL", "http://127.0.0.1:8001/v1/chat/completions")
    elif provider == "http":
        url = os.getenv("BENJAMIN_HTTP_URL", os.getenv("BENJAMIN_VLLM_URL", "http://127.0.0.1:8001/v1/chat/completions"))
    else:
        return ""
    if url.endswith("/v1/chat/completions"):
        return url[: -len("/v1/chat/completions")]
    return url.rstrip("/")




_HEALTH_PING_CACHE = TTLCache(default_ttl_s=int(os.getenv("BENJAMIN_PING_CACHE_TTL_S", "10")))

def _llm_reachable_uncached(provider: str, timeout_s: float = 1.0) -> bool:
    if provider not in {"vllm", "http"}:
        return False
    base_url = _llm_base_url(provider)
    if not base_url:
        return False
    endpoint = f"{base_url}/v1/models"
    try:
        response = request_with_retry(
            "GET",
            endpoint,
            timeout_override=timeout_s,
            retries=0,
            allowed_statuses={200},
            redact_url=True,
        )
        return response.status_code == 200
    except BenjaminHTTPError:
        return False


def _llm_reachable(provider: str, timeout_s: float = 1.0) -> bool:
    base_url = _llm_base_url(provider)
    if not base_url:
        return False
    ttl_s = int(os.getenv("BENJAMIN_PING_CACHE_TTL_S", "10"))
    cache_key = f"llm_ping:{provider}:{base_url}"
    return bool(_HEALTH_PING_CACHE.get_or_set(cache_key, ttl_s, lambda: _llm_reachable_uncached(provider, timeout_s=timeout_s)))

app = FastAPI(title="Benjamin API")
configure_logging(_state_dir())
app.mount("/ui/static", StaticFiles(directory="src/benjamin/apps/api/static"), name="ui-static")

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
app.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
app.include_router(rules_router, prefix="/rules", tags=["rules"])
app.include_router(security_router, prefix="/v1/security", tags=["security"])
app.include_router(ui_router, prefix="/ui", tags=["ui"])


@app.middleware("http")
async def request_context_middleware(request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    with log_context(correlation_id=correlation_id):
        response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


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

    protected_prefixes = ("/approvals", "/jobs", "/rules", "/memory", "/v1/security")
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
    normalized_kind = kind if kind in {"chat", "rule", "job", "approval", "policy", "all"} else "all"
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


@app.get("/healthz/full")
def healthz_full() -> dict[str, object]:
    provider = os.getenv("BENJAMIN_LLM_PROVIDER", "off").strip().casefold()
    state_dir = _state_dir()
    google_enabled = _is_on("BENJAMIN_GOOGLE_ENABLED", "off")
    token_path = _google_token_path(state_dir)
    auth_mode = os.getenv("BENJAMIN_AUTH_MODE", "token").strip().casefold()
    auth_enabled = auth_mode != "off"

    calendar_ready = get_calendar_connector() is not None
    gmail_ready = get_email_connector() is not None
    llm_reachable = _llm_reachable(provider)
    llm_features = {
        "planner": BenjaminLLM.feature_enabled("BENJAMIN_LLM_PLANNER"),
        "summarizer": BenjaminLLM.feature_enabled("BENJAMIN_LLM_SUMMARIZER"),
        "drafter": BenjaminLLM.feature_enabled("BENJAMIN_LLM_DRAFTER"),
        "rule_builder": BenjaminLLM.feature_enabled("BENJAMIN_LLM_RULE_BUILDER"),
        "retrieval": BenjaminLLM.feature_enabled("BENJAMIN_LLM_RETRIEVAL"),
    }

    state_writable = _state_dir_writable(state_dir)
    payload: dict[str, object] = {
        "ok": True,
        "python": {"version": sys.version.split()[0]},
        "state_dir": {"path": str(state_dir), "writable": state_writable},
        "auth": {"mode": auth_mode, "enabled": auth_enabled},
        "llm": {
            "provider": provider,
            "url": _llm_base_url(provider),
            "reachable": llm_reachable,
            "features": llm_features,
        },
        "google": {
            "enabled": google_enabled,
            "token_present": token_path.exists(),
            "calendar_ready": calendar_ready,
            "gmail_ready": gmail_ready,
        },
        "scheduler": {
            "rules_enabled": _is_on("BENJAMIN_RULES_ENABLED", "off"),
            "daily_briefing_enabled": any(job.id == "daily-briefing" for job in app.state.scheduler_service.list_jobs()),
        },
    }

    if auth_enabled and not os.getenv("BENJAMIN_AUTH_TOKEN"):
        payload["ok"] = False
    if not state_writable:
        payload["ok"] = False
    if google_enabled and not token_path.exists():
        payload["ok"] = False

    return payload


def run() -> None:
    uvicorn.run("benjamin.apps.api.main:app", reload=True, host="127.0.0.1", port=8000)
