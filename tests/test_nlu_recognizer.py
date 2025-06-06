import sys
import types

# Provide a lightweight spaCy stub so tests run without the real dependency
class _DummyNLP:
    def __call__(self, text):
        return types.SimpleNamespace(ents=[])

sys.modules.setdefault(
    "spacy",
    types.SimpleNamespace(load=lambda name=None: _DummyNLP()),
)

from jarvis.nlu.recognizer import RasaNLUAdapter
from jarvis.nlu.intent_recognizer import IntentRecognizer


def test_rasa_adapter_fallback(monkeypatch):
    class DummyInterpreter:
        def parse(self, text):
            raise RuntimeError("fail")

    monkeypatch.setattr("jarvis.nlu.recognizer.RasaNLUAdapter.__init__", lambda self, model_path="": setattr(self, "interpreter", DummyInterpreter()) or setattr(self, "fallback", IntentRecognizer()) )
    adapter = RasaNLUAdapter()
    intent, _ = adapter.parse("open file test.txt")
    assert intent == "open_file"
