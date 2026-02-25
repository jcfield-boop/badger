"""Brave Search API tool for Mimi."""

import urequests
import json
import memory as mem_module

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 5


def _get_api_key():
    """Read Brave API key from SERVICES.md."""
    services = mem_module.read_services()
    for line in services.splitlines():
        line = line.strip()
        if line.startswith("BRAVE_KEY=") or line.startswith("BRAVE_API_KEY="):
            return line.split("=", 1)[1].strip()
    # Also check secrets.py
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import MIMI_BRAVE_KEY
        sys.path.pop(0)
        return MIMI_BRAVE_KEY
    except (ImportError, AttributeError):
        pass
    return None


def execute(query):
    """Search the web using Brave Search. Returns formatted results."""
    api_key = _get_api_key()
    if not api_key:
        return "Error: no Brave Search API key found (set MIMI_BRAVE_KEY in secrets.py)"

    try:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }
        url = f"{BRAVE_API_URL}?q={_urlencode(query)}&count={MAX_RESULTS}&text_decorations=false"
        resp = urequests.get(url, headers=headers, timeout=15)
        data = resp.json()
        resp.close()
    except Exception as e:
        return f"Error: search request failed: {e}"

    results = data.get("web", {}).get("results", [])
    if not results:
        return "No results found."

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results[:MAX_RESULTS], 1):
        title = r.get("title", "")
        url_str = r.get("url", "")
        desc = r.get("description", "")
        lines.append(f"{i}. {title}\n   {url_str}\n   {desc}\n")

    return "\n".join(lines)


def _urlencode(s):
    """Minimal URL encoding for query strings."""
    safe = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    result = []
    for c in s:
        if c in safe:
            result.append(c)
        elif c == " ":
            result.append("+")
        else:
            result.append(f"%{ord(c):02X}")
    return "".join(result)
