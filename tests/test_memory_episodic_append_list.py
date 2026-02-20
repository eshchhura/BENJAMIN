from benjamin.core.memory.manager import MemoryManager


def test_episodic_append_and_recent_order(tmp_path) -> None:
    manager = MemoryManager(state_dir=tmp_path)

    manager.episodic.append(kind="task", summary="first", meta={})
    manager.episodic.append(kind="task", summary="second", meta={})
    manager.episodic.append(kind="task", summary="third", meta={})

    recent = manager.episodic.list_recent(limit=2)
    assert [item.summary for item in recent] == ["second", "third"]
