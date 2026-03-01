from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from benjamin.core.rules.evaluator import run_rules_evaluation
from benjamin.core.rules.nl_builder import RuleNLBuilder
from benjamin.core.rules.engine import RuleEngine
from benjamin.core.rules.schemas import Rule, RuleActionNotify, RuleCondition, RuleCreate, RuleTestPreview, RuleTrigger
from benjamin.core.rules.store import RuleStore


router = APIRouter()
templates = Jinja2Templates(directory="src/benjamin/apps/api/templates")


class RuleFromTextRequest(BaseModel):
    text: str


class RuleFromTextResponse(BaseModel):
    ok: bool
    rule_preview: RuleCreate | None = None
    error: str | None = None


def _store_from_request(request: Request) -> RuleStore:
    return RuleStore(state_dir=request.app.state.memory_manager.state_dir)


def _build_rule_from_form(
    *,
    name: str,
    trigger_type: str,
    contains: str | None,
    action_title: str,
    action_body_template: str | None,
    cooldown_minutes: int,
    max_actions_per_run: int,
    rule_id: str | None = None,
) -> Rule:
    return Rule(
        id=rule_id or str(uuid4()),
        name=name,
        trigger=RuleTrigger(type=trigger_type),
        condition=RuleCondition(contains=contains or None),
        actions=[
            RuleActionNotify(
                type="notify",
                title=action_title,
                body_template=action_body_template or "Rule {{count}} matched at {{now_iso}}",
            )
        ],
        cooldown_minutes=max(0, cooldown_minutes),
        max_actions_per_run=max(1, max_actions_per_run),
    )


def _build_engine(request: Request) -> RuleEngine:
    orchestrator = request.app.state.orchestrator
    return RuleEngine(
        memory_manager=request.app.state.memory_manager,
        approval_service=request.app.state.approval_service,
        registry=orchestrator.registry,
        notifier=request.app.state.notification_router,
        email_connector=request.app.state.email_connector,
        calendar_connector=request.app.state.calendar_connector,
        ledger=request.app.state.approval_service.ledger,
    )


def _test_response(request: Request, preview: RuleTestPreview):
    if request.headers.get("hx-request", "").casefold() == "true":
        return templates.TemplateResponse(
            "partials/rule_test_result.html",
            {"request": request, "preview": preview},
        )
    return JSONResponse(content=preview.model_dump(mode="json"))


@router.get("", response_model=list[Rule])
def list_rules(request: Request) -> list[Rule]:
    return _store_from_request(request).list_all()


@router.post("", response_model=Rule)
async def create_rule(
    request: Request,
    name: str | None = Form(default=None),
    trigger_type: str | None = Form(default=None),
    contains: str | None = Form(default=None),
    action_title: str | None = Form(default=None),
    action_body_template: str | None = Form(default=None),
    cooldown_minutes: int = Form(default=0),
    max_actions_per_run: int = Form(default=3),
) -> Rule:
    store = _store_from_request(request)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = RuleCreate.model_validate(await request.json())
        rule = Rule(**payload.model_dump())
        return store.upsert(rule)

    if not name or not trigger_type or not action_title:
        raise HTTPException(status_code=400, detail="name, trigger_type, and action_title are required")

    rule = _build_rule_from_form(
        name=name,
        trigger_type=trigger_type,
        contains=contains,
        action_title=action_title,
        action_body_template=action_body_template,
        cooldown_minutes=cooldown_minutes,
        max_actions_per_run=max_actions_per_run,
    )
    return store.upsert(rule)


@router.post("/from-text", response_model=RuleFromTextResponse)
def rules_from_text(payload: RuleFromTextRequest, request: Request) -> RuleFromTextResponse:
    builder = RuleNLBuilder()
    known_write_skills = {
        skill.name
        for skill in request.app.state.orchestrator.registry._skills.values()
        if getattr(skill, "side_effect", "read") == "write"
    }
    try:
        preview = builder.from_text(payload.text, known_write_skills=known_write_skills)
        return RuleFromTextResponse(ok=True, rule_preview=preview)
    except Exception as exc:
        return RuleFromTextResponse(ok=False, error=str(exc))


@router.put("/{rule_id}", response_model=Rule)
def update_rule(rule_id: str, payload: RuleCreate, request: Request) -> Rule:
    store = _store_from_request(request)
    existing = store.get(rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="rule not found")
    updated = existing.model_copy(update=payload.model_dump())
    return store.upsert(updated)


@router.post("/{rule_id}/enable", response_model=Rule)
def enable_rule(rule_id: str, request: Request) -> Rule:
    updated = _store_from_request(request).set_enabled(rule_id, True)
    if updated is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return updated


@router.post("/{rule_id}/disable", response_model=Rule)
def disable_rule(rule_id: str, request: Request) -> Rule:
    updated = _store_from_request(request).set_enabled(rule_id, False)
    if updated is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return updated


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, request: Request) -> dict[str, str]:
    deleted = _store_from_request(request).delete(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="rule not found")
    return {"status": "deleted", "rule_id": rule_id}


@router.post("/{rule_id}/reset-state", response_model=Rule)
def reset_rule_state(rule_id: str, request: Request) -> Rule:
    store = _store_from_request(request)
    existing = store.get(rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="rule not found")
    reset_state = existing.state.model_copy(
        update={
            "last_run_iso": None,
            "last_match_iso": None,
            "cooldown_until_iso": None,
            "seen_ids": [],
            "last_cursor_iso": None,
        }
    )
    return store.upsert(existing.model_copy(update={"state": reset_state, "last_run_iso": None, "last_match_iso": None}))


@router.post("/evaluate-now")
def evaluate_now(request: Request) -> dict[str, list[dict]]:
    results = run_rules_evaluation(
        state_dir=str(request.app.state.memory_manager.state_dir),
        router=request.app.state.notification_router,
        calendar_connector=request.app.state.calendar_connector,
        email_connector=request.app.state.email_connector,
    )
    return {"results": [item.model_dump() for item in results]}


@router.post("/{rule_id}/test", response_model=RuleTestPreview)
def test_existing_rule(rule_id: str, request: Request, include_seen: bool = Query(default=False)):
    store = _store_from_request(request)
    rule = store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    preview = _build_engine(request).evaluate_rule_preview(rule, include_seen=include_seen)
    return _test_response(request, preview)


@router.post("/test", response_model=RuleTestPreview)
async def test_draft_rule(
    request: Request,
    include_seen: bool = Query(default=False),
    name: str | None = Form(default=None),
    trigger_type: str | None = Form(default=None),
    contains: str | None = Form(default=None),
    action_title: str | None = Form(default=None),
    action_body_template: str | None = Form(default=None),
    cooldown_minutes: int = Form(default=0),
    max_actions_per_run: int = Form(default=3),
):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = RuleCreate.model_validate(await request.json())
        draft_rule = Rule(id="draft", **payload.model_dump())
    else:
        if not name or not trigger_type or not action_title:
            raise HTTPException(status_code=400, detail="name, trigger_type, and action_title are required")
        draft_rule = _build_rule_from_form(
            name=name,
            trigger_type=trigger_type,
            contains=contains,
            action_title=action_title,
            action_body_template=action_body_template,
            cooldown_minutes=cooldown_minutes,
            max_actions_per_run=max_actions_per_run,
            rule_id="draft",
        )

    preview = _build_engine(request).evaluate_rule_preview(draft_rule, include_seen=include_seen)
    return _test_response(request, preview)
