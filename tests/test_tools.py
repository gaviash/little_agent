import subprocess
from pathlib import Path

import pytest

import tools


@pytest.fixture()
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path.resolve())
    return tmp_path


def test_file_tools_create_read_edit_list_and_delete(isolated_workspace):
    write_result = tools.write_file("notes/todo.txt", "alpha beta alpha")

    assert write_result["success"] is True
    assert write_result["bytes_written"] == len("alpha beta alpha")
    assert (isolated_workspace / "notes" / "todo.txt").read_text() == "alpha beta alpha"

    duplicate_result = tools.write_file("notes/todo.txt", "new content")
    assert duplicate_result["success"] is False
    assert "overwrite=False" in duplicate_result["error"]

    edit_without_multiple = tools.edit_file("notes/todo.txt", "alpha", "gamma")
    assert edit_without_multiple["success"] is False
    assert edit_without_multiple["occurrences"] == 2
    assert edit_without_multiple["replacements"] == 0

    edit_result = tools.edit_file("notes/todo.txt", "alpha", "gamma", allow_multiple=True)
    assert edit_result["success"] is True
    assert edit_result["replacements"] == 2

    read_result = tools.read_file("notes/todo.txt")
    assert read_result["success"] is True
    assert read_result["content"] == "gamma beta gamma"
    assert read_result["truncated"] is False

    list_result = tools.list_files(".", recursive=True)
    assert list_result["success"] is True
    entries_by_path = {Path(entry["path"]).as_posix(): entry for entry in list_result["entries"]}
    assert entries_by_path["notes/todo.txt"]["type"] == "file"
    assert entries_by_path["notes/todo.txt"]["size"] == len("gamma beta gamma")

    delete_result = tools.delete_file("notes/todo.txt")
    assert delete_result["success"] is True
    assert not (isolated_workspace / "notes" / "todo.txt").exists()


def test_read_file_truncates_large_content(isolated_workspace):
    content = "A" * 50 + "B" * 50
    tools.write_file("large.txt", content)

    result = tools.read_file("large.txt", max_chars=40)

    assert result["success"] is True
    assert result["truncated"] is True
    assert len(result["content"]) == 40
    assert result["original_chars"] == 100


def test_file_tools_reject_paths_outside_workspace(isolated_workspace):
    outside_file = isolated_workspace.parent / "outside.txt"
    outside_file.write_text("secret")

    result = tools.read_file(str(outside_file))

    assert result["success"] is False
    assert "outside the workspace" in result["error"]


def test_shell_returns_structured_success(monkeypatch):
    def fake_run(args, **kwargs):
        assert args[-1] == "pwd"
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(tools, "_git_bash_executable", lambda: "bash.exe")
    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.shell("pwd")

    assert result["success"] is True
    assert result["return_code"] == 0
    assert result["stdout"] == "ok\n"
    assert result["stderr"] == ""


def test_shell_handles_timeouts(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="sleep 99", timeout=30, output="partial")

    monkeypatch.setattr(tools, "_git_bash_executable", lambda: "bash.exe")
    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.shell("sleep 99")

    assert result["success"] is False
    assert result["return_code"] is None
    assert "timed out" in result["stderr"]


def test_web_search_uses_lazy_tavily_client(monkeypatch):
    class FakeClient:
        def search(self, **kwargs):
            return {"query": kwargs["query"], "max_results": kwargs["max_results"]}

    monkeypatch.setattr(tools, "_get_tavily_client", lambda: FakeClient())

    result = tools.web_search("pytest examples", max_results=2)

    assert result == {"query": "pytest examples", "max_results": 2}
