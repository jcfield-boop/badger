"""Tavily Search API tool for Mimi."""

import time
import urequests
import json
import memory as mem_module

TAVILY_URL = "https://api.tavily.com/search"
MAX_RESULTS = 5
REQUEST_TIMEOUT_S = 12
MAX_RETRIES = 1          # one retry on a transient network error
RETRY_DELAY_S = 1
MAX_FIELD_CHARS = 300     # defensive cap on title/url/content from the API


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


def _trim(value, limit=MAX_FIELD_CHARS):
    text = str(value)
    return text[:limit]


def _error_detail(data):
    """Pull a human-readable message out of Tavily's error shapes, which
    vary between a flat string and a nested {"detail": {"error": "..."}}."""
    if not data:
        return ""
    detail = data.get("detail") or data.get("error") or ""
    if isinstance(detail, dict):
        detail = detail.get("error") or detail.get("message") or str(detail)
    return _trim(detail, 200)


def _request(query, api_key):
    """One request attempt. Returns (status_code, parsed_json_or_None, raw_text)."""
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": MAX_RESULTS,
        "include_answer": True,
    }
    headers = {"Content-Type": "application/json"}
    resp = urequests.post(
        TAVILY_URL,
        headers=headers,
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT_S,
    )
    try:
        status = resp.status_code
        try:
            data = resp.json()
            raw = None
        except Exception:
            data = None
            raw = _trim(resp.text, 200)
        return status, data, raw
    finally:
        resp.close()  # always release the socket, even if .json()/.text raised


def execute(query):
    """Search the web using Tavily. Returns formatted results."""
    api_key = _get_api_key()
    if not api_key:
        return "Error: no search API key found (set MIMI_BRAVE_KEY in secrets.py)"

    query = _trim(query, 300)

    status = data = raw = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            status, data, raw = _request(query, api_key)
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
                continue
            kind = type(e).__name__
            return f"Error: search request failed ({kind}: {e})"

    if status != 200:
        detail = _error_detail(data) or raw or ""
        if status in (401, 403):
            return f"Error: search API rejected the key (HTTP {status}). Check MIMI_BRAVE_KEY. {detail}".strip()
        if status == 429:
            return "Error: search API rate-limited (HTTP 429). Try again shortly."
        return f"Error: search API returned HTTP {status}. {detail}".strip()

    if data is None:
        return f"Error: search API returned an unreadable response. {raw or ''}".strip()

    lines = [f"Search results for: {query}\n"]

    # Tavily sometimes returns a direct answer
    answer = data.get("answer")
    if answer:
        lines.append(f"Answer: {_trim(answer, 500)}\n")

    results = data.get("results", [])
    if not results:
        return "\n".join(lines) if len(lines) > 1 else "No results found."

    for i, r in enumerate(results[:MAX_RESULTS], 1):
        title   = _trim(r.get("title", ""), 120)
        url_str = _trim(r.get("url", ""), 200)
        content = _trim(r.get("content", ""), 200)  # trim long snippets
        lines.append(f"{i}. {title}\n   {url_str}\n   {content}\n")

    return "\n".join(lines)
