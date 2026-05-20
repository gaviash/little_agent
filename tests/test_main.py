from fastapi.testclient import TestClient
import pytest


main_module = pytest.importorskip("main")


def test_generate_creates_session_and_returns_chat_response(monkeypatch):
    created_memories = []

    class FakeMemory:
        @classmethod
        def from_defaults(cls, **kwargs):
            created_memories.append(kwargs)
            return {"memory": kwargs}

    async def fake_query(agent, memory, message):
        assert agent == "fake-agent"
        assert memory == {"memory": created_memories[0]}
        assert message == "bonjour"
        return "salut"

    monkeypatch.setattr(main_module, "start", lambda: "fake-agent")
    monkeypatch.setattr(main_module, "query", fake_query)
    monkeypatch.setattr(main_module, "Memory", FakeMemory)

    with TestClient(main_module.app) as client:
        response = client.post("/generate", json={"message": "bonjour"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "salut"
    assert body["session_id"]
    assert created_memories == [
        {"session_id": body["session_id"], "token_limit": 100000}
    ]


def test_generate_reuses_existing_session_memory(monkeypatch):
    memory_by_session = {}
    calls = []

    class FakeMemory:
        @classmethod
        def from_defaults(cls, **kwargs):
            memory = {"memory": kwargs}
            memory_by_session[kwargs["session_id"]] = memory
            return memory

    async def fake_query(agent, memory, message):
        calls.append((agent, memory, message))
        return f"response to {message}"

    monkeypatch.setattr(main_module, "start", lambda: "fake-agent")
    monkeypatch.setattr(main_module, "query", fake_query)
    monkeypatch.setattr(main_module, "Memory", FakeMemory)

    with TestClient(main_module.app) as client:
        first = client.post(
            "/generate",
            json={"message": "one", "session_id": "session-a"},
        )
        second = client.post(
            "/generate",
            json={"message": "two", "session_id": "session-a"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"response": "response to one", "session_id": "session-a"}
    assert second.json() == {"response": "response to two", "session_id": "session-a"}
    assert len(memory_by_session) == 1
    assert calls == [
        ("fake-agent", memory_by_session["session-a"], "one"),
        ("fake-agent", memory_by_session["session-a"], "two"),
    ]
