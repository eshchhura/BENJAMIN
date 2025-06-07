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


def test_conversation_includes_history(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured['messages'] = kwargs.get('messages')

        class Resp:
            choices = [
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="Sure")
                )
            ]

        return Resp()

    monkeypatch.setattr(conversation.openai.chat.completions, "create", fake_create)

    history = [
        {"input": "hi", "response": "hello"},
        {"input": "how are you?", "response": "fine"},
    ]

    conversation.handle("unknown", {"text": "tell me a joke"}, {"recent_turns": history})

    msgs = captured['messages']
    expected = [
        {"role": "system", "content": f"You are {conversation.ASSISTANT_NAME}, a helpful assistant."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "how are you?"},
        {"role": "assistant", "content": "fine"},
        {"role": "user", "content": "tell me a joke"},
    ]

    assert msgs == expected
