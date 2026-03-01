from datetime import datetime, timezone

from benjamin.core.runs.schemas import TaskRecord
from benjamin.core.runs.store import TaskStore


def _record(task_id: str) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        ts_iso=datetime.now(timezone.utc).isoformat(),
        user_message=f"message {task_id}",
        plan={"steps": []},
        step_results=[],
        answer="ok",
        trace_events=[],
        correlation_id=f"corr-{task_id}",
    )


def test_task_store_append_list_get_trim(tmp_path) -> None:
    store = TaskStore(state_dir=tmp_path, max_records=3)

    store.append(_record("1"))
    store.append(_record("2"))
    store.append(_record("3"))
    store.append(_record("4"))

    recent = store.list_recent(limit=10)
    assert [record.task_id for record in recent] == ["4", "3", "2"]

    found = store.get("3")
    assert found is not None
    assert found.correlation_id == "corr-3"

    store.trim(2)
    assert [record.task_id for record in store.list_recent(limit=10)] == ["4", "3"]
