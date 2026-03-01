from fastapi.testclient import TestClient

from benjamin.apps.api.main import app


client = TestClient(app)


def test_chat_endpoint_returns_trace_and_answer(tmp_path) -> None:
    (tmp_path / "notes.txt").write_text("banana bread", encoding="utf-8")

    response = client.post(
        "/chat",
        json={"message": "find banana", "cwd": str(tmp_path)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "answer" in payload
    assert "trace" in payload
    assert "task_id" in payload["trace"]
    assert isinstance(payload["trace"]["events"], list)
