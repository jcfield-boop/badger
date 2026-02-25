"""LittleFS file I/O for Mimi: MEMORY.md, SOUL.md, sessions, daily notes."""

import os
import json

# Base paths on LittleFS
BASE_DIR = "/mimi"
CONFIG_DIR = "/mimi/config"
MEMORY_DIR = "/mimi/memory"
SESSIONS_DIR = "/mimi/sessions"

SOUL_FILE = "/mimi/config/SOUL.md"
USER_FILE = "/mimi/config/USER.md"
SERVICES_FILE = "/mimi/config/SERVICES.md"
MEMORY_FILE = "/mimi/memory/MEMORY.md"


def _ensure_dirs():
    """Create directory tree if missing."""
    for path in (BASE_DIR, CONFIG_DIR, MEMORY_DIR, SESSIONS_DIR):
        try:
            os.mkdir(path)
        except OSError:
            pass  # already exists


def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def read_file(path, default=""):
    """Read a text file, return default if missing."""
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return default


def write_file(path, content, append=False):
    """Write (or append) text to a file."""
    mode = "a" if append else "w"
    try:
        with open(path, mode) as f:
            f.write(content)
        return True
    except OSError as e:
        print(f"[memory] write_file error {path}: {e}")
        return False


def list_dir(path):
    """List files in a directory. Returns list of names."""
    try:
        return os.listdir(path)
    except OSError:
        return []


def read_memory():
    """Return contents of MEMORY.md."""
    return read_file(MEMORY_FILE)


def read_soul():
    """Return contents of SOUL.md."""
    return read_file(SOUL_FILE)


def read_user():
    """Return contents of USER.md."""
    return read_file(USER_FILE)


def read_services():
    """Return contents of SERVICES.md (API keys — never log this)."""
    return read_file(SERVICES_FILE)


def read_daily_notes(date_str):
    """Read daily notes for a given YYYY-MM-DD date string."""
    path = f"{MEMORY_DIR}/{date_str}.md"
    return read_file(path)


def append_daily_notes(date_str, text):
    """Append text to today's daily notes file."""
    path = f"{MEMORY_DIR}/{date_str}.md"
    return write_file(path, text, append=True)


def read_recent_notes(n=3):
    """Read the most recent n daily notes files."""
    files = sorted(
        [f for f in list_dir(MEMORY_DIR) if f.endswith(".md") and f != "MEMORY.md"],
        reverse=True
    )[:n]
    parts = []
    for fname in files:
        content = read_file(f"{MEMORY_DIR}/{fname}")
        if content:
            parts.append(f"### {fname}\n{content}")
    return "\n\n".join(parts)


# ── Session management ────────────────────────────────────────────

MAX_SESSION_MSGS = 15


def _session_path(chat_id):
    return f"{SESSIONS_DIR}/{chat_id}.json"


def load_session(chat_id):
    """Load message history for a chat_id. Returns list of message dicts."""
    path = _session_path(str(chat_id))
    data = read_file(path, "[]")
    try:
        msgs = json.loads(data)
        if isinstance(msgs, list):
            return msgs[-MAX_SESSION_MSGS:]
        return []
    except (ValueError, TypeError):
        return []


def save_session(chat_id, messages):
    """Save message history (trimmed to MAX_SESSION_MSGS)."""
    path = _session_path(str(chat_id))
    trimmed = messages[-MAX_SESSION_MSGS:]
    try:
        write_file(path, json.dumps(trimmed))
    except Exception as e:
        print(f"[memory] save_session error: {e}")


def init():
    """Initialise directory structure."""
    _ensure_dirs()
