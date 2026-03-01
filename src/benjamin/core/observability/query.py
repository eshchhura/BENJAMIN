from __future__ import annotations

import json
from typing import Any

from benjamin.core.approvals.schemas import PendingApproval
from benjamin.core.approvals.store import ApprovalStore
from benjamin.core.ledger.ledger import ExecutionLedger
from benjamin.core.memory.episodic import EpisodicMemoryStore
from benjamin.core.memory.schemas import Episode
from benjamin.core.runs.schemas import TaskRecord
from benjamin.core.runs.store import TaskStore


def _task_status(task: TaskRecord) -> str:
    if "skipped" in task.answer.casefold():
        return "skipped"
    if any((event.get("event") == "idempotent_skip") for event in task.trace_events if isinstance(event, dict)):
        return "skipped"

    failures = [step for step in task.step_results if not bool(step.get("ok", False))]
    if not failures:
        return "ok"
    only_approval_required = all((step.get("error") or "").casefold() == "approval_required" for step in failures)
    return "ok" if only_approval_required else "failed"


def _episode_status(episode: Episode) -> str:
    return "failed" if episode.meta.get("ok") is False else "ok"


def _approval_status(approval: PendingApproval) -> str:
    if approval.status in {"rejected", "expired"}:
        return "failed"
    if approval.status == "approved":
        if approval.result and approval.result.output and "\"skipped\":true" in approval.result.output.replace(" ", ""):
            return "skipped"
        if approval.result and approval.result.ok is False:
            return "failed"
        return "ok"
    return "ok"


def _matches_query(text: str, query: str) -> bool:
    return query in text.casefold()


def build_correlation_view(
    correlation_id: str,
    *,
    task_store: TaskStore,
    episodic_store: EpisodicMemoryStore,
    ledger: ExecutionLedger,
    approval_store: ApprovalStore,
    limit: int = 200,
) -> dict[str, Any]:
    tasks = [task for task in task_store.list_recent(limit=limit) if task.correlation_id == correlation_id]
    episodes = episodic_store.find_by_correlation(correlation_id, limit=limit)
    ledger_records = ledger.find_by_correlation(correlation_id, limit=limit)

    task_approval_ids = {approval_id for task in tasks for approval_id in task.approvals_created}
    episode_approval_ids = {
        str(episode.meta.get("approval_id"))
        for episode in episodes
        if episode.meta.get("approval_id")
    }

    approvals_by_id: dict[str, PendingApproval] = {}
    for approval in approval_store.find_by_correlation(correlation_id, limit=limit):
        approvals_by_id[approval.id] = approval

    for approval in approval_store.list_all():
        if approval.id in task_approval_ids or approval.id in episode_approval_ids:
            approvals_by_id[approval.id] = approval

    return {
        "correlation_id": correlation_id,
        "tasks": tasks,
        "episodes": episodes,
        "ledger_records": ledger_records,
        "approvals": sorted(approvals_by_id.values(), key=lambda item: item.created_at_iso, reverse=True),
        "derived_ids": {
            "approval_ids": sorted(task_approval_ids.union(episode_approval_ids)),
            "task_ids": sorted({task.task_id for task in tasks}),
        },
    }


def search_runs(
    *,
    kind: str,
    status: str,
    q: str,
    limit: int,
    task_store: TaskStore,
    episodic_store: EpisodicMemoryStore,
    ledger: ExecutionLedger,
    approval_store: ApprovalStore,
) -> dict[str, Any]:
    limit = max(1, min(200, limit))
    query = q.casefold().strip()

    tasks = task_store.search(query, limit=limit)
    if status != "all":
        tasks = [task for task in tasks if _task_status(task) == status]
    if query:
        tasks = [task for task in tasks if _matches_query(f"{task.task_id} {task.correlation_id} {task.user_message} {task.answer}", query)]

    episodes = episodic_store.search(query, limit=limit)
    if status != "all":
        episodes = [episode for episode in episodes if _episode_status(episode) == status]

    ledger_records = ledger.search(query, limit=limit)
    if status != "all":
        ledger_records = [record for record in ledger_records if record.status == status]

    approvals = approval_store.list_all()
    if query:
        approvals = [
            approval
            for approval in approvals
            if _matches_query(
                " ".join(
                    [
                        approval.id,
                        approval.status,
                        approval.step.id,
                        approval.step.skill_name or "",
                        json.dumps(approval.requester, ensure_ascii=False),
                    ]
                ),
                query,
            )
        ]
    if status != "all":
        approvals = [approval for approval in approvals if _approval_status(approval) == status]

    sections = {
        "tasks": tasks[:limit],
        "rule_runs": [episode for episode in episodes if episode.kind == "rule"][:limit],
        "job_runs": [episode for episode in episodes if episode.kind in {"briefing", "notification", "job"}][:limit],
        "approval_audits": [episode for episode in episodes if episode.kind == "approval"][:limit],
        "ledger_records": ledger_records[:limit],
        "approvals": approvals[:limit],
    }

    if kind == "chat":
        sections.update({"rule_runs": [], "job_runs": [], "approval_audits": [], "ledger_records": [], "approvals": []})
    elif kind == "rule":
        sections.update({"tasks": [], "job_runs": [], "approval_audits": [], "ledger_records": [], "approvals": []})
    elif kind == "job":
        sections.update({"tasks": [], "rule_runs": [], "approval_audits": [], "ledger_records": [], "approvals": []})
    elif kind == "approval":
        sections.update({"tasks": [], "rule_runs": [], "job_runs": [], "ledger_records": []})

    return sections
