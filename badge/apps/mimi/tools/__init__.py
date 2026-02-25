"""Tool registry for Mimi — maps tool names to callables and JSON schemas."""

import gc

# ── Tool definitions (OpenAI function-calling format for OpenRouter) ──

def _fn(name, description, properties=None, required=None):
    """Build an OpenAI-format tool schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


TOOL_SCHEMAS = [
    _fn(
        "get_current_time",
        "Get the current date and time. Call this whenever you need to know "
        "the current time or date. Returns a formatted string including unix epoch.",
    ),
    _fn(
        "web_search",
        "Search the web for current information. Use when you need up-to-date "
        "facts, news, weather, or anything beyond your training data.",
        {"query": {"type": "string", "description": "The search query"}},
        ["query"],
    ),
    _fn(
        "read_file",
        "Read a file from LittleFS. Returns file contents as text.",
        {"path": {"type": "string", "description": "Absolute path to file"}},
        ["path"],
    ),
    _fn(
        "write_file",
        "Write or append text to a file on LittleFS.",
        {
            "path":    {"type": "string",  "description": "Absolute path to file"},
            "content": {"type": "string",  "description": "Text to write"},
            "append":  {"type": "boolean", "description": "If true, append instead of overwrite"},
        },
        ["path", "content"],
    ),
    _fn(
        "edit_file",
        "Replace a specific string in an existing file. "
        "Provide old_str (exact substring to replace) and new_str.",
        {
            "path":    {"type": "string", "description": "Absolute path to file"},
            "old_str": {"type": "string", "description": "Exact substring to replace"},
            "new_str": {"type": "string", "description": "Replacement text"},
        },
        ["path", "old_str", "new_str"],
    ),
    _fn(
        "list_dir",
        "List files and directories at a path on LittleFS.",
        {"path": {"type": "string", "description": "Directory path"}},
        ["path"],
    ),
    _fn(
        "http_request",
        "Make an HTTPS GET or POST request to an external URL. "
        "Returns the response body as text.",
        {
            "url":     {"type": "string", "description": "Full HTTPS URL"},
            "method":  {"type": "string", "description": "HTTP method: GET or POST"},
            "headers": {"type": "object", "description": "Optional request headers"},
            "body":    {"type": "string", "description": "Optional request body (JSON string)"},
        },
        ["url"],
    ),
    _fn(
        "cron_add",
        "Schedule a one-shot task. IMPORTANT: use seconds_from_now for relative "
        "times ('in 5 minutes' = 300). Only use at_epoch if you have called "
        "get_current_time and have the verified current unix epoch.",
        {
            "name":            {"type": "string",  "description": "Short label for the job"},
            "schedule_type":   {"type": "string",  "description": "Always 'at' for one-shot"},
            "seconds_from_now":{"type": "integer", "description": "PREFERRED: fire N seconds from now"},
            "at_epoch":        {"type": "integer", "description": "Absolute unix timestamp (only if verified)"},
            "message":         {"type": "string",  "description": "Prompt to run when job fires"},
            "channel":         {"type": "string",  "description": "'telegram' for Telegram delivery"},
            "chat_id":         {"type": "string",  "description": "Telegram chat_id (required for telegram)"},
        },
        ["name", "schedule_type", "message"],
    ),
    _fn(
        "cron_list",
        "List all pending scheduled tasks.",
    ),
    _fn(
        "cron_remove",
        "Remove a scheduled task by its ID.",
        {"job_id": {"type": "integer", "description": "Job ID to remove"}},
        ["job_id"],
    ),
    _fn(
        "system_info",
        "Get live device health: free heap, uptime, WiFi RSSI, battery level.",
    ),
]

# Populated by init()
_registry = {}


def init(cron_instance=None):
    """Register all tool handler functions."""
    from tools import get_time, files, web_search, http_request, system_info

    _registry["get_current_time"] = get_time.execute
    _registry["web_search"]       = web_search.execute
    _registry["read_file"]        = files.read_file
    _registry["write_file"]       = files.write_file
    _registry["edit_file"]        = files.edit_file
    _registry["list_dir"]         = files.list_dir
    _registry["http_request"]     = http_request.execute
    _registry["system_info"]      = system_info.execute

    if cron_instance is not None:
        _registry["cron_add"]    = cron_instance.add
        _registry["cron_list"]   = cron_instance.list_jobs
        _registry["cron_remove"] = cron_instance.remove


def dispatch(name, input_dict):
    """Dispatch a tool call. Returns a string result."""
    gc.collect()
    fn = _registry.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        result = fn(**input_dict) if input_dict else fn()
        return str(result) if result is not None else "(no output)"
    except TypeError as e:
        return f"Error: bad arguments for tool '{name}': {e}"
    except Exception as e:
        return f"Error: tool '{name}' raised {type(e).__name__}: {e}"
