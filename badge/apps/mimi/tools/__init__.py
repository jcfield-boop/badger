"""Tool registry for Mimi — maps tool names to callables and JSON schemas."""

import gc

# ── Tool definitions (Anthropic tool_use format) ─────────────────

TOOL_SCHEMAS = [
    {
        "name": "get_current_time",
        "description": (
            "Get the current date and time. Call this whenever you need to know "
            "the current time or date. Returns a formatted string including unix epoch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use when you need up-to-date "
            "facts, news, weather, or anything beyond your training data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from LittleFS. Returns file contents as text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to file"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or append text to a file on LittleFS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to file"},
                "content": {"type": "string", "description": "Text to write"},
                "append": {"type": "boolean", "description": "If true, append instead of overwrite"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace a specific string in an existing file. "
            "Provide old_str (exact substring to replace) and new_str."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to file"},
                "old_str": {"type": "string", "description": "Exact substring to replace"},
                "new_str": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and directories at a path on LittleFS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "http_request",
        "description": (
            "Make an HTTPS GET or POST request to an external URL. "
            "Returns the response body as text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full HTTPS URL"},
                "method": {"type": "string", "description": "HTTP method: GET or POST"},
                "headers": {"type": "object", "description": "Optional request headers"},
                "body": {"type": "string", "description": "Optional request body (JSON string)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "cron_add",
        "description": (
            "Schedule a one-shot task to run at a specific unix timestamp. "
            "The task will send a Telegram message or trigger an agent turn. "
            "Required fields: unix_time (int), prompt (str), channel, chat_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unix_time": {"type": "integer", "description": "Unix epoch when to fire"},
                "prompt": {"type": "string", "description": "Agent prompt to run at trigger time"},
                "channel": {"type": "string", "description": "Output channel: 'telegram'"},
                "chat_id": {"type": "string", "description": "Telegram chat_id for delivery"},
                "label": {"type": "string", "description": "Optional human-readable label"},
            },
            "required": ["unix_time", "prompt", "channel", "chat_id"],
        },
    },
    {
        "name": "cron_list",
        "description": "List all pending scheduled tasks.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "cron_remove",
        "description": "Remove a scheduled task by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "Job ID to remove"},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "system_info",
        "description": (
            "Get live device health: free heap, uptime seconds, WiFi RSSI, "
            "battery level percentage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# Populated by init()
_registry = {}


def init(cron_instance=None):
    """Register all tool handler functions."""
    from tools import get_time, files, web_search, http_request, system_info

    _registry["get_current_time"] = get_time.execute
    _registry["web_search"] = web_search.execute
    _registry["read_file"] = files.read_file
    _registry["write_file"] = files.write_file
    _registry["edit_file"] = files.edit_file
    _registry["list_dir"] = files.list_dir
    _registry["http_request"] = http_request.execute
    _registry["system_info"] = system_info.execute

    if cron_instance is not None:
        _registry["cron_add"] = cron_instance.add
        _registry["cron_list"] = cron_instance.list_jobs
        _registry["cron_remove"] = cron_instance.remove


def dispatch(name, input_dict):
    """
    Dispatch a tool call by name with the given input dict.
    Returns a string result (success or error).
    """
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
