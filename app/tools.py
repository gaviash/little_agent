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


def _normalize_limit(value, default, maximum, allow_unlimited=False):
    if value is None and allow_unlimited:
        return None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    if limit < 0 and allow_unlimited:
        return None
    return max(0, min(limit, maximum))


def _truncate_text(text, limit, marker="\n...[truncated output]...\n"):
    if limit is None or len(text) <= limit:
        return text, False

    if limit <= 0:
        return "", True
    if limit <= len(marker):
        return text[:limit], True

    head_len = (limit - len(marker)) // 2
    tail_len = limit - len(marker) - head_len
    return text[:head_len] + marker + text[-tail_len:], True


def read_file(path: str, encoding: str = "utf-8", max_chars: int = DEFAULT_FILE_OUTPUT_CHARS) -> dict:
    """Read a text file from the workspace.

    Use this tool when the agent needs to inspect source code, configuration,
    notes, logs, or any other text file before answering or editing. The path is
    resolved relative to the configured WORKSPACE_DIR, or to the current working
    directory when WORKSPACE_DIR is not set. Absolute paths are accepted only if
    they remain inside the workspace.

    Parameters:
    - path: File path to read, relative to the workspace whenever possible.
    - encoding: Text encoding used to decode the file. Defaults to "utf-8".
    - max_chars: Maximum number of characters returned in content. Negative
      values or None disable truncation. Values above MAX_FILE_OUTPUT_CHARS are
      capped to protect the agent context.

    Returns:
    A dictionary with:
    - success: True when the file was read successfully.
    - error: Error message when success is False, otherwise None.
    - path: Resolved absolute file path when available.
    - content: File content, possibly truncated.
    - truncated: True when content was shortened.
    - original_chars: Original character count before truncation.
    """
    try:
        safe = _safe_path(path)
        content = safe.read_text(encoding=encoding)
        original_chars = len(content)
        limit = _normalize_limit(
            max_chars,
            DEFAULT_FILE_OUTPUT_CHARS,
            MAX_FILE_OUTPUT_CHARS,
            allow_unlimited=True,
        )
        content, truncated = _truncate_text(content, limit, "\n...[output truncated]...\n")
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
    """Create or overwrite a text file inside the workspace.

    Use this tool when the agent needs to create a new file or replace the full
    content of an existing file. Parent directories are created automatically.
    For targeted changes inside an existing file, prefer edit_file.

    Parameters:
    - path: Destination file path, relative to the workspace whenever possible.
    - content: Full text content to write. Non-string values are converted with
      str before encoding.
    - encoding: Text encoding used to write the file. Defaults to "utf-8".
    - overwrite: When False, an existing file is left untouched and the tool
      returns an error. Set True only when replacing the full file is intended.

    Returns:
    A dictionary with:
    - success: True when the file was written successfully.
    - error: Error message when success is False, otherwise None.
    - path: Resolved absolute file path when available.
    - bytes_written: Number of encoded bytes written, or 0 on failure.
    """
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
    """Replace an exact text fragment inside a workspace file.

    Use this tool for precise edits where the original text is known. By default
    the tool refuses ambiguous replacements when old_str appears more than once;
    this prevents accidental broad edits. Set allow_multiple=True only when all
    occurrences should be replaced.

    Parameters:
    - path: File path to edit, relative to the workspace whenever possible.
    - old_str: Exact text fragment to find. Empty strings are rejected.
    - new_str: Replacement text.
    - encoding: Text encoding used to read and write the file. Defaults to
      "utf-8".
    - allow_multiple: Replace every occurrence when True. When False, the tool
      only edits the file if old_str appears exactly once.

    Returns:
    A dictionary with:
    - success: True when at least one replacement was written.
    - error: Error message when success is False, otherwise None.
    - path: Resolved absolute file path when available.
    - occurrences: Number of matches found before editing.
    - replacements: Number of replacements written.
    """
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


def _posix_shell_command_args(command: str):
    bash = shutil.which("bash")
    if bash:
        return [bash, "-lc", command]

    sh = shutil.which("sh")
    if sh:
        return [sh, "-c", command]

    raise FileNotFoundError("No POSIX shell was found. Install bash or sh.")


def _shell_command_args(command: str):
    if os.name == "nt":
        return [_git_bash_executable(), "--noprofile", "--norc", "-lc", command]
    return _posix_shell_command_args(command)


def _ensure_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _limit_shell_output(stdout, stderr, max_output_chars):
    stdout = _ensure_text(stdout)
    stderr = _ensure_text(stderr)
    limit = _normalize_limit(
        max_output_chars,
        DEFAULT_SHELL_OUTPUT_CHARS,
        MAX_SHELL_OUTPUT_CHARS,
    )
    total_chars = len(stdout) + len(stderr)

    if total_chars <= limit: # type: ignore
        return {
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": False,
            "original_stdout_chars": len(stdout),
            "original_stderr_chars": len(stderr),
            "max_output_chars": limit,
        }

    if stdout and stderr:
        stdout_limit = limit * len(stdout) // total_chars # type: ignore
        stderr_limit = limit - stdout_limit # type: ignore
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
    time_range=timerange, # type: ignore
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
    """Execute a shell command for an agent and return structured output.

    This tool gives the agent controlled access to the local command line through
    the best available shell for the current operating system. On Windows, it
    uses Git Bash (`bash -lc`) to provide POSIX-style commands. On Linux/macOS,
    it uses `bash -lc` when bash is available, then falls back to `sh -c`.

    Use it for operational tasks such as inspecting files, listing directories,
    running scripts, checking dependencies, or launching simple diagnostic
    commands. Prefer precise, non-interactive commands such as ls, pwd, grep,
    sed, cat, and python invocations available from the shell.

    The shell is not interactive: it cannot answer prompts, menus, password
    requests, or y/N confirmations after the command has started. When a command
    may ask for confirmation, pass explicit non-interactive flags such as -y,
    --yes, --no-input, --force, or the tool-specific equivalent when that is the
    intended behavior.

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
            _shell_command_args(command),
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
    
