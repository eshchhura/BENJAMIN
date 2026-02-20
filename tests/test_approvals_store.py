from datetime import datetime, timedelta, timezone

from core.approvals.schemas import PendingApproval
from core.approvals.store import ApprovalStore
from core.orchestration.schemas import PlanStep


def _record(record_id: str, created_delta_hours: int = 0, expires_delta_hours: int = 2) -> PendingApproval:
    now = datetime.now(timezone.utc)
    created_at = now + timedelta(hours=created_delta_hours)
    expires_at = now + timedelta(hours=expires_delta_hours)
    return PendingApproval(
        id=record_id,
        created_at_iso=created_at.isoformat(),
        expires_at_iso=expires_at.isoformat(),
        status="pending",
        requester={"source": "test"},
        step=PlanStep(description="Create reminder", skill_name="reminders.create", args="{}", requires_approval=True),
        context={"cwd": "/tmp"},
        rationale="test rationale",
    )


def test_store_crud_and_listing(tmp_path) -> None:
    store = ApprovalStore(state_dir=tmp_path)
    first = _record("a")
    second = _record("b", created_delta_hours=1)

    store.upsert(first)
    store.upsert(second)

    listed = store.list_all()
    assert [item.id for item in listed] == ["b", "a"]
    assert store.get("a") is not None

    store.delete("a")
    assert store.get("a") is None


def test_cleanup_expired_marks_or_deletes(tmp_path, monkeypatch) -> None:
    store = ApprovalStore(state_dir=tmp_path)
    expired = _record("expired", expires_delta_hours=-1)
    fresh = _record("fresh", expires_delta_hours=1)
    store.upsert(expired)
    store.upsert(fresh)

    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "off")
    changed = store.cleanup_expired(datetime.now(timezone.utc).isoformat())
    assert changed == 1
    assert store.get("expired").status == "expired"

    monkeypatch.setenv("BENJAMIN_APPROVALS_AUTOCLEAN", "on")
    changed = store.cleanup_expired((datetime.now(timezone.utc) + timedelta(hours=2)).isoformat())
    assert changed == 1
    assert store.get("fresh") is None
