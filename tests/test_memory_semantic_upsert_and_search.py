from benjamin.core.memory.manager import MemoryManager


def test_semantic_upsert_overwrite_and_search(tmp_path) -> None:
    manager = MemoryManager(state_dir=tmp_path)

    manager.semantic.upsert(key="favorite_language", value="Python", scope="global", tags=["pref"])
    manager.semantic.upsert(key="timezone", value="UTC", scope="global", tags=["profile"])
    updated = manager.semantic.upsert(
        key="favorite_language", value="Python 3.11", scope="global", tags=["pref", "runtime"]
    )

    all_items = manager.semantic.list_all(scope="global")
    assert len(all_items) == 2
    assert updated.value == "Python 3.11"

    matches = manager.semantic.search("runtime", limit=5)
    assert len(matches) == 1
    assert matches[0].key == "favorite_language"
