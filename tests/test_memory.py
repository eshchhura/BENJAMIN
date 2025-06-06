import os
import datetime

from jarvis.memory.short_term import ShortTermMemory
from jarvis.memory.long_term import LongTermMemory
import jarvis.memory.long_term as lt_module


def test_short_term_memory_basic():
    stm = ShortTermMemory(capacity=2)
    stm.append({"input": "hi", "intent": "greet", "entities": {}, "response": "hello"})
    stm.append({"input": "bye", "intent": "goodbye", "entities": {}, "response": "bye"})
    assert len(stm.get_recent_turns()) == 2
    stm.append({"input": "again", "intent": "again", "entities": {}, "response": "again"})
    turns = stm.get_recent_turns()
    assert len(turns) == 2
    assert turns[-1]["intent"] == "again"
    context = stm.get_context()
    assert context["last_intent"] == "again"


def test_long_term_memory_store_and_retrieve(tmp_path):
    # Patch missing datetime import in module
    lt_module.datetime = datetime.datetime

    db_path = tmp_path / "memory.db"
    ltm = LongTermMemory(str(db_path))
    ltm.store_fact("food", "pizza")
    assert ltm.retrieve_fact("food") == "pizza"
    ltm.store_fact("food", "sushi")
    assert ltm.retrieve_fact("food") == "sushi"
    ltm.log_interaction("hi", "greet", "hello")
    ltm.log_interaction("bye", "goodbye", "bye")
    count = ltm.conn.execute("SELECT COUNT(*) FROM interaction_log").fetchone()[0]
    assert count == 2
    ltm.close()
