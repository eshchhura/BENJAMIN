from __future__ import annotations

import httpx

from benjamin.core.http.client import request_with_retry


def test_request_with_retry_retries_transient_http_status(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    monkeypatch.setattr("benjamin.core.http.client.get_http_client", lambda: client)
    monkeypatch.setattr("benjamin.core.http.client.time.sleep", lambda _: None)
    monkeypatch.setattr("benjamin.core.http.client.random.random", lambda: 0.5)

    response = request_with_retry("GET", "http://service.local/test", retries=2)

    assert response.status_code == 200
    assert calls["count"] == 3
