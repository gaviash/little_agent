from pathlib import Path
from tavily import TavilyClient
from dotenv import load_dotenv
from typing import Literal
import os
import subprocess
import shutil


load_dotenv(dotenv_path=".env")

MAX_SHELL_OUTPUT_CHARS = 5_000
DEFAULT_SHELL_OUTPUT_CHARS = MAX_SHELL_OUTPUT_CHARS
MAX_FILE_OUTPUT_CHARS = 20_000
DEFAULT_FILE_OUTPUT_CHARS = 5_000
WORKSPACE = Path(os.getenv("WORKSPACE_DIR", os.getcwd())).resolve()
_tavily_client = None


def _get_tavily_client():
    global _tavily_client
    if _tavily_client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured.")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


def _tool_result(success=False, error=None, **data):
    return {"success": success, "error": error, **data}


def _safe_path(user_path: str) -> Path:
    """Resolve a user path inside the configured workspace."""
    if not user_path or not str(user_path).strip():
        raise ValueError("Path cannot be empty.")

    path = Path(str(user_path)).expanduser()
    target = path.resolve() if path.is_absolute() else (WORKSPACE / path).resolve()

    if target != WORKSPACE and WORKSPACE not in target.parents:
        raise ValueError(f"Access denied: '{user_path}' is outside the workspace.")

    return target


def _normalize_file_limit(max_chars):
    if max_chars is None:
        return None
    try:
        limit = int(max_chars)
    except (TypeError, ValueError):
        limit = DEFAULT_FILE_OUTPUT_CHARS
    if limit < 0:
        return None
    return min(limit, MAX_FILE_OUTPUT_CHARS)


def _truncate_file_content(text, max_chars):
    limit = _normalize_file_limit(max_chars)
    if limit is None or len(text) <= limit:
        return text, False

    marker = "\n...[output truncated]...\n"
    if limit <= len(marker):
        return text[:limit], True

    head_len = (limit - len(marker)) // 2
    tail_len = limit - len(marker) - head_len
    return text[:head_len] + marker + text[-tail_len:], True


def read_file(path: str, encoding: str = "utf-8", max_chars: int = DEFAULT_FILE_OUTPUT_CHARS) -> dict:
    """Read a text file inside the workspace and return structured content."""
    try:
        safe = _safe_path(path)
        content = safe.read_text(encoding=encoding)
        original_chars = len(content)
        content, truncated = _truncate_file_content(content, max_chars)
        return _tool_result(
            True,
            path=str(safe),
            content=content,
            truncated=truncated,
            original_chars=original_chars,
        )
    except Exception as e:
        return _tool_result(False, str(e), path=path, content=None, truncated=False)


def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = False,
) -> dict:
    """Create or overwrite a text file inside the workspace."""
    try:
        safe = _safe_path(path)
        if safe.exists() and not overwrite:
            return _tool_result(
                False,
                "File already exists and overwrite=False.",
                path=str(safe),
                bytes_written=0,
            )

        safe.parent.mkdir(parents=True, exist_ok=True)
        data = str(content).encode(encoding)
        safe.write_bytes(data)
        return _tool_result(True, path=str(safe), bytes_written=len(data))
    except Exception as e:
        return _tool_result(False, str(e), path=path, bytes_written=0)


def edit_file(
    path: str,
    old_str: str,
    new_str: str,
    encoding: str = "utf-8",
    allow_multiple: bool = False,
) -> dict:
    """Replace text in a file inside the workspace."""
    try:
        if old_str == "":
            return _tool_result(
                False,
                "old_str cannot be empty.",
                path=path,
                occurrences=0,
                replacements=0,
            )

        safe = _safe_path(path)
        text = safe.read_text(encoding=encoding)
        occurrences = text.count(old_str)
        if occurrences == 0:
            return _tool_result(
                False,
                "Substring not found.",
                path=str(safe),
                occurrences=0,
                replacements=0,
            )
        if occurrences > 1 and not allow_multiple:
            return _tool_result(
                False,
                "Substring appears multiple times. Set allow_multiple=True to replace all occurrences.",
                path=str(safe),
                occurrences=occurrences,
                replacements=0,
            )

        replacements = occurrences if allow_multiple else 1
        safe.write_text(text.replace(old_str, new_str, replacements), encoding=encoding)
        return _tool_result(
            True,
            path=str(safe),
            occurrences=occurrences,
            replacements=replacements,
        )
    except Exception as e:
        return _tool_result(False, str(e), path=path, occurrences=0, replacements=0)


def list_files(path: str = ".", pattern: str = "*", recursive: bool = False, max_results: int = 200) -> dict:
    """List files and directories inside the workspace."""
    try:
        safe = _safe_path(path)
        if not safe.exists():
            return _tool_result(False, "Path does not exist.", path=str(safe), entries=[])

        max_results = max(0, min(int(max_results), 1_000))
        iterator = safe.rglob(pattern) if recursive else safe.glob(pattern)
        entries = []
        for item in iterator:
            if item == safe:
                continue
            entries.append(
                {
                    "path": str(item.relative_to(WORKSPACE)),
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )
            if len(entries) >= max_results:
                break

        entries.sort(key=lambda item: (item["type"], item["path"].lower()))
        return _tool_result(True, path=str(safe), entries=entries, count=len(entries))
    except Exception as e:
        return _tool_result(False, str(e), path=path, entries=[], count=0)


def delete_file(path: str) -> dict:
    """Delete one file inside the workspace."""
    try:
        safe = _safe_path(path)
        if not safe.exists():
            return _tool_result(False, "File does not exist.", path=str(safe))
        if not safe.is_file():
            return _tool_result(False, "Path is not a file.", path=str(safe))
        safe.unlink()
        return _tool_result(True, path=str(safe))
    except Exception as e:
        return _tool_result(False, str(e), path=path)


def _git_bash_executable():
    """Return the Git Bash executable path, avoiding Windows/WSL bash shims."""
    candidates = [
        os.getenv("GIT_BASH_PATH"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Git", "bin", "bash.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Git", "usr", "bin", "bash.exe"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Git", "bin", "bash.exe"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Git", "usr", "bin", "bash.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Git", "bin", "bash.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Git", "usr", "bin", "bash.exe"),
    ]

    git_path = shutil.which("git")
    if git_path:
        git_root = os.path.dirname(os.path.dirname(git_path))
        candidates.extend([
            os.path.join(git_root, "bin", "bash.exe"),
            os.path.join(git_root, "usr", "bin", "bash.exe"),
        ])

    path_bash = shutil.which("bash")
    if path_bash and "\\git\\" in os.path.normcase(os.path.normpath(path_bash)):
        candidates.append(path_bash)

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        "Git Bash was not found. Install Git for Windows or set GIT_BASH_PATH "
        "to the full path of bash.exe."
    )


def _normalize_output_limit(max_output_chars):
    try:
        limit = int(max_output_chars)
    except (TypeError, ValueError):
        limit = DEFAULT_SHELL_OUTPUT_CHARS

    return max(0, min(limit, MAX_SHELL_OUTPUT_CHARS))


def _ensure_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _truncate_text(text, limit):
    if len(text) <= limit:
        return text, False
    if limit <= 0:
        return "", True

    marker = "\n...[truncated output]...\n"
    head_len = 0
    tail_len = 0
    for _ in range(3):
        if limit <= len(marker):
            return text[:limit], True

        head_len = (limit - len(marker)) // 2
        tail_len = limit - len(marker) - head_len
        omitted_chars = len(text) - head_len - tail_len
        marker = f"\n...[truncated {omitted_chars} chars]...\n"

    return text[:head_len] + marker + text[-tail_len:], True


def _limit_shell_output(stdout, stderr, max_output_chars):
    stdout = _ensure_text(stdout)
    stderr = _ensure_text(stderr)
    limit = _normalize_output_limit(max_output_chars)
    total_chars = len(stdout) + len(stderr)

    if total_chars <= limit:
        return {
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": False,
            "original_stdout_chars": len(stdout),
            "original_stderr_chars": len(stderr),
            "max_output_chars": limit,
        }

    if stdout and stderr:
        stdout_limit = limit * len(stdout) // total_chars
        stderr_limit = limit - stdout_limit
    elif stdout:
        stdout_limit = limit
        stderr_limit = 0
    else:
        stdout_limit = 0
        stderr_limit = limit

    limited_stdout, stdout_truncated = _truncate_text(stdout, stdout_limit)
    limited_stderr, stderr_truncated = _truncate_text(stderr, stderr_limit)

    return {
        "stdout": limited_stdout,
        "stderr": limited_stderr,
        "output_truncated": stdout_truncated or stderr_truncated,
        "original_stdout_chars": len(stdout),
        "original_stderr_chars": len(stderr),
        "max_output_chars": limit,
    }


def web_search(query : str,search_depth : Literal['basic','advanced','fast','ultra-fast'] ='basic',max_results=5,timerange =None,chunks_per_source=3):
    """Search across the web for any information,news,update or help.\n
    Uses these parameters in the tool call :\n
    
    - query : The query for the search itself. Needs to be well-made and effective,in order to give good results\n
    
    - search_depth : Controls the latency vs. relevance tradeoff and how results[].content is generated:\n
    advanced: Highest relevance with increased latency. Best for detailed, high-precision queries. Returns multiple semantically relevant snippets per URL (configurable via chunks_per_source).\n
    basic: A balanced option for relevance and latency. Ideal for general-purpose searches. Returns one NLP summary per URL.\n
    fast: Prioritizes lower latency while maintaining good relevance. Returns multiple semantically relevant snippets per URL (configurable via chunks_per_source).\n
    ultra-fast: Minimizes latency above all else. Best for time-critical use cases. Returns one NLP summary per URL.\n
    By default,set to basic.
    
    - max_results : The maximum number of search results to return.Required range: 0 <= x <= 20.By default,set to 3.\n
    
    - timerange : The time range back from the current date to filter results based on publish date or last updated date. Useful when looking for sources that have published or updated data.
    Available options: day, week, month, year, d, w, m, y.By default,set to None.
    
    - Chunks_per_source : Chunks are short content snippets (maximum 500 characters each) pulled directly from the source. \n
    Use chunks_per_source to define the maximum number of relevant chunks returned per source and to control the content length. Required range: 1 <= x <= 3

    """
    response = _get_tavily_client().search(
    query=query,
    search_depth=search_depth,
    max_results=max_results,
    time_range=timerange,
    chunks_per_source = chunks_per_source
    )
    
    return response

def web_fetch(url : str,query=None,chunks_per_source=3,extract_depth : Literal['basic','advanced'] ="basic"):
    """Fetch and extract readable content from a URL for an agent.

    This tool lets the agent retrieve page content from a specific source when
    it already has a URL to inspect. Use it after web_search, or whenever the
    user provides a link and the agent needs the actual page content instead of
    search snippets.

    Parameters:
    - url: The URL to fetch and extract.
    - query: Optional user intent used to rerank extracted content chunks. When
      provided, chunks are ordered by relevance to this query.
    - chunks_per_source: Maximum number of short snippets to return from the
      source and include in raw_content. Chunks are at most 500 characters each
      and appear as: <chunk 1> [...] <chunk 2> [...] <chunk 3>. Available only
      when query is provided. Required range: 1 <= x <= 5. By default, set to 3.
    - extract_depth: Extraction depth. Use "basic" for standard extraction, or
      "advanced" to retrieve more data such as tables and embedded content with
      higher success and latency. Basic costs 1 credit per 5 successful URL
      extractions; advanced costs 2 credits per 5 successful URL extractions.
      By default, set to "basic".

    Returns:
    The Tavily extraction response containing the extracted content, raw_content,
    and extraction metadata returned by the API.
    """
    response = _get_tavily_client().extract(
        urls=url,
        query=str(query),
        chunks_per_source=chunks_per_source,
        extract_depth=extract_depth
    )
    return response


def shell(command : str, max_output_chars=DEFAULT_SHELL_OUTPUT_CHARS):
    """Execute a Git Bash command for an agent and return structured output.

    This tool gives the agent controlled access to the local command line through
    Git Bash (`bash -lc`). Use it for operational tasks such as inspecting files, listing
    directories, running scripts, checking dependencies, or launching simple
    diagnostic commands.
    Prefer Git Bash / POSIX-style commands such as ls, pwd, grep, sed, cat, and
    python invocations available from the shell.

    Parameters:
    - command: The exact command to execute as a string. The agent should prefer
      precise, non-interactive commands and avoid destructive operations unless
      the user explicitly requested them.
    - max_output_chars: Maximum total characters to return across stdout and
      stderr. Use a smaller value for quick checks. Values above 5,000 are
      capped to keep tool output compact for the LLM. By default, set to 5,000.

    Returns:
    A dictionary with:
    - success: True when the command exits with code 0, otherwise False.
    - return_code: The process exit code.
    - stdout: Text written to standard output.
    - stderr: Text written to standard error.
    - output_truncated: True when stdout or stderr was shortened.
    - original_stdout_chars: Original stdout length before truncation.
    - original_stderr_chars: Original stderr length before truncation.
    - max_output_chars: Effective output limit after applying the hard cap.

    Execution is limited to 30 seconds. If the command times out, the tool
    returns success=False, return_code=None, and includes the timeout details in
    stderr.
    """
    try :
        result = subprocess.run(
            [_git_bash_executable(), "--noprofile", "--norc", "-lc", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )
        output = _limit_shell_output(result.stdout, result.stderr, max_output_chars)
        return {
            "success": result.returncode == 0,
            "return_code":result.returncode,
            **output
        }
    except FileNotFoundError as e:
        output = _limit_shell_output("", str(e), max_output_chars)
        return {
            "success": False,
            "return_code": None,
            **output
        }
    except subprocess.TimeoutExpired as t:
        output = _limit_shell_output(
            t.stdout,
            f"Command timed out after {t.timeout} seconds.",
            max_output_chars
        )
        return {
            "success": False,
            "return_code": None,
            **output
        }
    
