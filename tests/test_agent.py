import asyncio

import pytest


agent_module = pytest.importorskip("Agent")


def test_start_builds_function_agent_with_all_tools(monkeypatch):
    created = {}

    class FakeOllama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeFunctionAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created["agent"] = self

    class FakeMemory:
        @classmethod
        def from_defaults(cls, **kwargs):
            created["memory_kwargs"] = kwargs
            return {"memory": kwargs}

    monkeypatch.setenv("OLLAMA_MODEL", "llama-test")
    monkeypatch.setattr(agent_module, "Ollama", FakeOllama)
    monkeypatch.setattr(agent_module, "FunctionAgent", FakeFunctionAgent)
    monkeypatch.setattr(agent_module, "Memory", FakeMemory)

    agent, memory = agent_module.start()

    assert agent is created["agent"]
    assert memory == {"memory": {"session_id": "Dev", "token_limit": 150000}}
    assert agent.kwargs["llm"].kwargs == {
        "model": "llama-test",
        "temperature": 0.2,
        "context_window": 262144,
        "request_timeout": 100.0,
    }

    tool_names = [tool.__name__ for tool in agent.kwargs["tools"]]
    assert tool_names == [
        "web_search",
        "web_fetch",
        "shell",
        "read_file",
        "write_file",
        "edit_file",
        "list_files",
        "delete_file",
    ]
    assert "Tu es Gustave" in agent.kwargs["system_prompt"]


def test_query_forwards_user_message_and_memory():
    calls = {}

    class FakeAgent:
        async def run(self, **kwargs):
            calls.update(kwargs)
            return "response"

    memory = object()

    result = asyncio.run(agent_module.query(FakeAgent(), memory, "bonjour"))

    assert result == "response"
    assert calls == {"user_msg": "bonjour", "memory": memory}
