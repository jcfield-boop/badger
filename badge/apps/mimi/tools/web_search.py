"""Tavily Search API tool for Mimi."""

import urequests
import json
import memory as mem_module

TAVILY_URL = "https://api.tavily.com/search"
MAX_RESULTS = 5


def _get_api_key():
    """Read Tavily API key from secrets.py or SERVICES.md."""
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import MIMI_BRAVE_KEY  # kept the name from secrets.py
        sys.path.pop(0)
        if MIMI_BRAVE_KEY:
            return MIMI_BRAVE_KEY
    except (ImportError, AttributeError):
        pass
    # Also check SERVICES.md
    services = mem_module.read_services()
    for line in services.splitlines():
        line = line.strip()
        for prefix in ("TAVILY_KEY=", "BRAVE_KEY=", "BRAVE_API_KEY=", "SEARCH_KEY="):
            if line.startswith(prefix):
                return line.split("=", 1)[1].strip()
    return None


def execute(query):
    """Search the web using Tavily. Returns formatted results."""
    api_key = _get_api_key()
    if not api_key:
        return "Error: no search API key found (set MIMI_BRAVE_KEY in secrets.py)"

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": MAX_RESULTS,
        "include_answer": True,
    }

    try:
        headers = {"Content-Type": "application/json"}
        resp = urequests.post(
            TAVILY_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=20,
        )
        data = resp.json()
        resp.close()
    except Exception as e:
        return f"Error: search request failed: {e}"

    lines = [f"Search results for: {query}\n"]

    # Tavily sometimes returns a direct answer
    answer = data.get("answer")
    if answer:
        lines.append(f"Answer: {answer}\n")

    results = data.get("results", [])
    if not results:
        return "\n".join(lines) if len(lines) > 1 else "No results found."

    for i, r in enumerate(results[:MAX_RESULTS], 1):
        title   = r.get("title", "")
        url_str = r.get("url", "")
        content = r.get("content", "")[:200]  # trim long snippets
        lines.append(f"{i}. {title}\n   {url_str}\n   {content}\n")

    return "\n".join(lines)
