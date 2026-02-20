from fastapi.testclient import TestClient

from apps.api import deps
from apps.api.main import app


def test_daily_briefing_job_scheduling(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_TEST_MODE", "1")
    monkeypatch.setenv("BENJAMIN_STATE_DIR", str(tmp_path))
    deps.get_memory_manager.cache_clear()
    deps.get_scheduler_service.cache_clear()

    with TestClient(app) as client:
        response = client.post("/jobs/daily-briefing", json={"time_hhmm": "09:00"})
        assert response.status_code == 200
        assert response.json()["job_id"] == "daily-briefing"

        jobs = client.get("/jobs").json()
        assert any(job["id"] == "daily-briefing" for job in jobs)
