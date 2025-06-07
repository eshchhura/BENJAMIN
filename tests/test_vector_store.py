import numpy as np
from jarvis.memory import vector_store as vs_module
from jarvis.memory.vector_store import VectorStore


class DummyModel:
    def __init__(self):
        self.calls = 0

    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts):
        self.calls += 1
        return np.array([[len(t)] * 3 for t in texts], dtype=np.float32)


def setup_vector_store(tmp_path, monkeypatch):
    monkeypatch.setattr(vs_module, "SentenceTransformer", lambda name="": DummyModel())
    store = VectorStore(str(tmp_path / "index"))
    # type: ignore[attr-defined]
    model = store.model  # type: ignore
    return store, model


def test_store_and_retrieve(tmp_path, monkeypatch):
    store, _ = setup_vector_store(tmp_path, monkeypatch)
    store.store("hello")
    store.store("world")
    res = store.retrieve("hello", top_k=1)
    assert res == ["hello"]


def test_retrieve_uses_cache(tmp_path, monkeypatch):
    store, model = setup_vector_store(tmp_path, monkeypatch)
    store.store("hello")
    first = store.retrieve("hello")
    second = store.retrieve("hello")
    assert first == second
    assert model.calls == 2  # encode called once for store and once for retrieve
