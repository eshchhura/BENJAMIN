from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from apps.api import deps
from apps.api.main import app


def test_create_reminder_and_listed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()

    with TestClient(app) as client:
        run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        response = client.post("/jobs/reminder", json={"message": "Take a break", "run_at_iso": run_at})
        assert response.status_code == 200
        payload = response.json()
        assert payload["job_id"].startswith("reminder:")

        listed = client.get("/jobs")
        assert listed.status_code == 200
        jobs = listed.json()
        assert any(job["id"] == payload["job_id"] for job in jobs)
