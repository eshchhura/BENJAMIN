from benjamin.core.infra.breaker_manager import BreakerManager


def test_breaker_persists_across_managers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BENJAMIN_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("BENJAMIN_BREAKERS_ENABLED", "on")

    manager = BreakerManager(state_dir=tmp_path)

    for _ in range(2):
        try:
            manager.wrap("gmail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        except RuntimeError:
            pass

    snapshot = manager.snapshot()
    assert snapshot["gmail"]["state"] == "open"

    loaded = BreakerManager(state_dir=tmp_path)
    loaded_snapshot = loaded.snapshot()
    assert loaded_snapshot["gmail"]["state"] == "open"
    assert loaded_snapshot["gmail"]["last_error"]
