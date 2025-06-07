import pathlib
import importlib
import pytest

try:
    importlib.import_module("rasa.nlu.model")
except Exception:
    pytest.skip("rasa not available", allow_module_level=True)

from jarvis.nlu.rasa_interpreter import RasaInterpreter

MODEL_DIR = pathlib.Path("models/rasa_nlu")

@pytest.mark.skipif(not MODEL_DIR.exists(), reason="Rasa model not available")
def test_rasa_interpreter_greet():
    interpreter = RasaInterpreter(str(MODEL_DIR))
    intent, entities = interpreter.parse("hello")
    assert intent == "greet"
    assert isinstance(entities, dict)
