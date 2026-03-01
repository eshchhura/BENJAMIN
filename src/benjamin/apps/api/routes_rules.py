from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request

from benjamin.core.rules.evaluator import run_rules_evaluation
from benjamin.core.rules.schemas import Rule, RuleActionNotify, RuleCondition, RuleCreate, RuleTrigger
from benjamin.core.rules.store import RuleStore


router = APIRouter()


def _store_from_request(request: Request) -> RuleStore:
    return RuleStore(state_dir=request.app.state.memory_manager.state_dir)


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

    rule = Rule(
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
    return store.upsert(rule)


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
