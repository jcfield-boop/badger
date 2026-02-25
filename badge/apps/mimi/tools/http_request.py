"""Generic HTTPS GET/POST tool for Mimi."""

import urequests
import json

MAX_RESPONSE_BYTES = 8192


def execute(url, method="GET", headers=None, body=None):
    """
    Make an HTTPS request and return the response body (truncated to 8KB).
    """
    method = (method or "GET").upper()
    req_headers = {"Content-Type": "application/json"}
    if headers and isinstance(headers, dict):
        req_headers.update(headers)

    try:
        if method == "GET":
            resp = urequests.get(url, headers=req_headers, timeout=20)
        elif method == "POST":
            data = body if isinstance(body, str) else (json.dumps(body) if body else "")
            resp = urequests.post(url, headers=req_headers, data=data, timeout=20)
        elif method == "HEAD":
            resp = urequests.head(url, headers=req_headers, timeout=10)
        else:
            return f"Error: unsupported method '{method}'"

        status = resp.status_code
        content_type = resp.headers.get("Content-Type", "")

        # Read response body
        raw = resp.content
        resp.close()

        if method == "HEAD":
            return f"HEAD {url} → {status}"

        # Truncate if too large
        if len(raw) > MAX_RESPONSE_BYTES:
            raw = raw[:MAX_RESPONSE_BYTES]
            truncated = True
        else:
            truncated = False

        body_str = raw.decode("utf-8", "replace")
        suffix = f"\n[truncated at {MAX_RESPONSE_BYTES} bytes]" if truncated else ""
        return f"HTTP {status}\n{body_str}{suffix}"

    except Exception as e:
        return f"Error: request failed: {e}"
