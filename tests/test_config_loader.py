from config.loader import load_config, BenjaminConfig


def test_load_config(tmp_path):
    sample = tmp_path / "cfg.yaml"
    sample.write_text("assistant:\n  name: Test\n  memory:\n    short_term_capacity: 5\n    long_term_db_path: db.sqlite\n    vector_store_path: vec.index")
    cfg = load_config(str(sample))
    assert isinstance(cfg, BenjaminConfig)
    assert cfg.assistant.name == "Test"
    assert cfg.assistant.memory.short_term_capacity == 5
