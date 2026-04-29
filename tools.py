from tavily import TavilyClient
from dotenv import load_dotenv
import os 
import subprocess


load_dotenv(dotenv_path=".env")
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
                      
       

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


def shell(command : str):
    """Execute a Windows shell command for an agent and return structured output.

    This tool gives the agent controlled access to the local command line through
    `cmd /c`. Use it for operational tasks such as inspecting files, listing
    directories, running scripts, checking dependencies, or launching simple
    diagnostic commands.

    Parameters:
    - command: The exact command to execute as a string. The agent should prefer
      precise, non-interactive commands and avoid destructive operations unless
      the user explicitly requested them.

    Returns:
    A dictionary with:
    - success: True when the command exits with code 0, otherwise False.
    - return_code: The process exit code.
    - stdout: Text written to standard output.
    - stderr: Text written to standard error.

    Execution is limited to 30 seconds. If the command times out, the tool
    returns success=False, return_code=None, and includes the timeout details in
    stderr.
    """
    try :
        result = subprocess.run(
            ["cmd","/c",command],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "return_code":result.returncode,
            "stdout":result.stdout,
            "stderr":result.stderr
        }
    except subprocess.TimeoutExpired as t:
        return {
            "success": False,
            "return_code": None,
            "stdout": t.stdout or "",
            "stderr": f"Command timed out after {t.timeout} seconds."
        }
    
