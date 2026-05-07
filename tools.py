from tavily import TavilyClient
from dotenv import load_dotenv
import os 
import subprocess
import shutil


load_dotenv(dotenv_path=".env")
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

MAX_SHELL_OUTPUT_CHARS = 5_000
DEFAULT_SHELL_OUTPUT_CHARS = MAX_SHELL_OUTPUT_CHARS
                      

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


def web_search(query : str,search_depth='basic',max_results=5,timerange=None,chunks_per_source=3):
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
    response = client.search(
    query=query,
    search_depth=search_depth,
    max_results=max_results,
    time_range=timerange,
    chunks_per_source = chunks_per_source
    )
    
    return response

def web_fetch(url : str,query=None,chunks_per_source=3,extract_depth="basic"):
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
    response = client.extract(
        urls=url,
        query=query,
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
    
