from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from benjamin.core.orchestration.orchestrator import ChatRequest

from .auth import AUTH_COOKIE, get_required_token, is_auth_enabled
from .routes_jobs import create_reminder, upsert_daily_briefing

router = APIRouter()
templates = Jinja2Templates(directory="src/benjamin/apps/api/templates")


@router.get("/")
def ui_root() -> RedirectResponse:
    return RedirectResponse(url="/ui/chat", status_code=303)


@router.get("/login")
def ui_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "auth_enabled": is_auth_enabled()})


@router.post("/login")
def ui_login_post(request: Request, token: str = Form(default="")):
    if is_auth_enabled() and token != get_required_token():
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid token", "auth_enabled": True},
            status_code=401,
        )

    response = RedirectResponse(url="/ui/chat", status_code=303)
    if is_auth_enabled():
        response.set_cookie(AUTH_COOKIE, value=token, httponly=True, samesite="lax")
    return response


@router.post("/logout")
def ui_logout() -> RedirectResponse:
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE)
    return response


@router.get("/chat")
def ui_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request, "result": None})


@router.post("/chat")
def ui_chat_post(request: Request, message: str = Form(...)):
    result = request.app.state.orchestrator.handle(ChatRequest(message=message))
    return templates.TemplateResponse("chat.html", {"request": request, "result": result, "message": message})


@router.get("/approvals")
def ui_approvals(request: Request):
    service = request.app.state.approval_service
    service.cleanup_expired()
    approvals = service.store.list_all()
    return templates.TemplateResponse("approvals.html", {"request": request, "approvals": approvals})


@router.post("/approvals/{approval_id}/approve")
def ui_approve(request: Request, approval_id: str, approver_note: str = Form(default="")):
    service = request.app.state.approval_service
    orchestrator = request.app.state.orchestrator
    service.approve(
        id=approval_id,
        approver_note=approver_note or None,
        executor=orchestrator.executor,
        registry=orchestrator.registry,
    )
    return RedirectResponse(url="/ui/approvals", status_code=303)


@router.post("/approvals/{approval_id}/reject")
def ui_reject(request: Request, approval_id: str, reason: str = Form(default="")):
    request.app.state.approval_service.reject(id=approval_id, reason=reason or None)
    return RedirectResponse(url="/ui/approvals", status_code=303)


@router.get("/jobs")
def ui_jobs(request: Request):
    jobs = request.app.state.scheduler_service.list_jobs()
    return templates.TemplateResponse("jobs.html", {"request": request, "jobs": jobs})


@router.post("/jobs/reminder")
def ui_jobs_reminder(request: Request, message: str = Form(...), minutes_from_now: int = Form(default=30)):
    run_at_iso = (datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)).isoformat()
    create_reminder(
        request=type("ReminderRequestProxy", (), {"message": message, "run_at_iso": run_at_iso})(),
        scheduler=request.app.state.scheduler_service,
        memory_manager=request.app.state.memory_manager,
    )
    return RedirectResponse(url="/ui/jobs", status_code=303)


@router.post("/jobs/daily-briefing")
def ui_jobs_briefing(request: Request, time_hhmm: str = Form(...)):
    upsert_daily_briefing(
        request=type("DailyBriefingProxy", (), {"time_hhmm": time_hhmm})(),
        scheduler=request.app.state.scheduler_service,
        memory_manager=request.app.state.memory_manager,
    )
    return RedirectResponse(url="/ui/jobs", status_code=303)


@router.get("/rules")
def ui_rules(request: Request):
    rules = request.app.state.rule_store.list_all()
    last_results = getattr(request.app.state, "last_rule_results", [])
    return templates.TemplateResponse("rules.html", {"request": request, "rules": rules, "results": last_results})


@router.post("/rules/create")
def ui_create_rule(
    request: Request,
    name: str = Form(...),
    trigger_type: str = Form(...),
    contains: str = Form(default=""),
    action_title: str = Form(...),
    action_body_template: str = Form(default="Rule matched {{count}} items. Top={{top1}} at {{now_iso}}"),
    cooldown_minutes: int = Form(default=0),
    max_actions_per_run: int = Form(default=3),
):
    from benjamin.core.rules.schemas import Rule, RuleActionNotify, RuleCondition, RuleTrigger

    request.app.state.rule_store.upsert(
        Rule(
            name=name,
            trigger=RuleTrigger(type=trigger_type),
            condition=RuleCondition(contains=contains or None),
            actions=[RuleActionNotify(type="notify", title=action_title, body_template=action_body_template)],
            cooldown_minutes=max(0, cooldown_minutes),
            max_actions_per_run=max(1, max_actions_per_run),
        )
    )
    return RedirectResponse(url="/ui/rules", status_code=303)


@router.post("/rules/{rule_id}/enable")
def ui_enable_rule(request: Request, rule_id: str):
    request.app.state.rule_store.set_enabled(rule_id, True)
    return RedirectResponse(url="/ui/rules", status_code=303)


@router.post("/rules/{rule_id}/disable")
def ui_disable_rule(request: Request, rule_id: str):
    request.app.state.rule_store.set_enabled(rule_id, False)
    return RedirectResponse(url="/ui/rules", status_code=303)


@router.post("/rules/{rule_id}/delete")
def ui_delete_rule(request: Request, rule_id: str):
    request.app.state.rule_store.delete(rule_id)
    return RedirectResponse(url="/ui/rules", status_code=303)


@router.post("/rules/{rule_id}/reset-state")
def ui_reset_rule_state(request: Request, rule_id: str):
    rule = request.app.state.rule_store.get(rule_id)
    if rule is not None:
        reset_state = rule.state.model_copy(
            update={
                "last_run_iso": None,
                "last_match_iso": None,
                "cooldown_until_iso": None,
                "seen_ids": [],
                "last_cursor_iso": None,
            }
        )
        request.app.state.rule_store.upsert(
            rule.model_copy(update={"state": reset_state, "last_run_iso": None, "last_match_iso": None})
        )
    return RedirectResponse(url="/ui/rules", status_code=303)


@router.post("/rules/evaluate-now")
def ui_rules_eval(request: Request):
    from benjamin.core.rules.evaluator import run_rules_evaluation

    request.app.state.last_rule_results = run_rules_evaluation(
        state_dir=str(request.app.state.memory_manager.state_dir),
        router=request.app.state.notification_router,
        calendar_connector=request.app.state.calendar_connector,
        email_connector=request.app.state.email_connector,
    )
    return RedirectResponse(url="/ui/rules", status_code=303)


@router.get("/memory")
def ui_memory(request: Request):
    semantic = request.app.state.memory_manager.semantic.list_all()
    episodic = request.app.state.memory_manager.episodic.list_recent(limit=50)
    return templates.TemplateResponse("memory.html", {"request": request, "semantic": semantic, "episodic": episodic})


@router.post("/memory/semantic")
def ui_memory_upsert(request: Request, key: str = Form(...), value: str = Form(...), scope: str = Form(default="global")):
    request.app.state.memory_manager.semantic.upsert(key=key, value=value, scope=scope)
    return RedirectResponse(url="/ui/memory", status_code=303)


@router.get("/runs")
def ui_runs(request: Request):
    task_store = request.app.state.task_store
    episodic = request.app.state.memory_manager.episodic.list_recent(limit=200)

    rule_runs = [episode for episode in reversed(episodic) if episode.kind == "rule"][:20]
    job_runs = [episode for episode in reversed(episodic) if episode.kind in {"briefing", "notification"}][:20]
    approval_audits = [episode for episode in reversed(episodic) if episode.kind == "approval"][:20]

    return templates.TemplateResponse(
        "runs.html",
        {
            "request": request,
            "tasks": task_store.list_recent(limit=50),
            "rule_runs": rule_runs,
            "job_runs": job_runs,
            "approval_audits": approval_audits,
        },
    )


@router.get("/runs/chat/{task_id}")
def ui_run_chat_detail(request: Request, task_id: str):
    record = request.app.state.task_store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return templates.TemplateResponse(
        "run_chat_detail.html",
        {
            "request": request,
            "record": record,
            "plan_json": json.dumps(record.plan, indent=2, ensure_ascii=False),
            "step_results_json": json.dumps(record.step_results, indent=2, ensure_ascii=False),
            "trace_json": json.dumps(record.trace_events, indent=2, ensure_ascii=False),
        },
    )


@router.get("/runs/approvals/{approval_id}")
def ui_run_approval_detail(request: Request, approval_id: str):
    record = request.app.state.approval_service.store.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return templates.TemplateResponse(
        "run_approval_detail.html",
        {"request": request, "record": record, "record_json": json.dumps(record.model_dump(), indent=2, ensure_ascii=False)},
    )


@router.get("/runs/rules/{rule_id}")
def ui_run_rule_detail(request: Request, rule_id: str):
    rule = request.app.state.rule_store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    episodes = request.app.state.memory_manager.episodic.list_recent(limit=400)
    rule_runs = [episode for episode in reversed(episodes) if episode.kind == "rule" and episode.meta.get("rule_id") == rule_id][:20]
    return templates.TemplateResponse(
        "run_rule_detail.html",
        {
            "request": request,
            "rule": rule,
            "rule_json": json.dumps(rule.model_dump(), indent=2, ensure_ascii=False),
            "rule_runs": rule_runs,
        },
    )
