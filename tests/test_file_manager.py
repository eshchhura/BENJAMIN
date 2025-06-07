import os
from jarvis.skills import file_manager


def test_can_handle():
    assert file_manager.can_handle("open_file")
    assert file_manager.can_handle("search_file")
    assert file_manager.can_handle("move_file")
    assert not file_manager.can_handle("unknown_intent")


def test_search_file(tmp_path):
    sample = tmp_path / "note.txt"
    sample.write_text("hello")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = file_manager.handle({"intent": "search_file", "entities": {"query": "note"}, "context": {}})["text"]
    finally:
        os.chdir(cwd)
    assert "note.txt" in result


def test_open_file_missing(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = file_manager.handle({"intent": "open_file", "entities": {"file_name": "missing.txt"}, "context": {}})["text"]
    finally:
        os.chdir(cwd)
    assert "couldn't find" in result.lower()


def test_move_file(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("data")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = file_manager.handle(
            {"intent": "move_file", "entities": {"source": "a.txt", "destination": "dest/b.txt"}, "context": {}}
        )["text"]
    finally:
        os.chdir(cwd)
    dest_file = tmp_path / "dest" / "b.txt"
    assert dest_file.exists()
    assert result == "Moved a.txt to dest/b.txt."
