import types
from jarvis.skills import conversation


def test_conversation_handles_any_intent(monkeypatch):
    # Mock OpenAI response
    def fake_create(**kwargs):
        class Resp:
            choices = [types.SimpleNamespace(message=types.SimpleNamespace(content="Hi there"))]

        return Resp()

    monkeypatch.setattr(conversation.openai.chat.completions, "create", fake_create)
    response = conversation.handle("unknown", {"text": "Hello"}, {})
    assert "Hi there" in response
