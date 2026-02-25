"""LittleFS file tools exposed to the agent."""

import os
import memory as mem_module


def read_file(path):
    """Read a file and return its contents."""
    content = mem_module.read_file(path)
    if content == "" and not _exists(path):
        return f"Error: file not found: {path}"
    return content


def write_file(path, content, append=False):
    """Write or append text to a file. Creates parent dirs as needed."""
    _ensure_parent(path)
    ok = mem_module.write_file(path, content, append=bool(append))
    if ok:
        return f"Written {len(content)} bytes to {path}"
    return f"Error: could not write {path}"


def edit_file(path, old_str, new_str):
    """Replace old_str with new_str in a file."""
    if not _exists(path):
        return f"Error: file not found: {path}"
    content = mem_module.read_file(path)
    if old_str not in content:
        return f"Error: old_str not found in {path}"
    updated = content.replace(old_str, new_str, 1)
    ok = mem_module.write_file(path, updated, append=False)
    if ok:
        return f"Edited {path}"
    return f"Error: could not write {path}"


def list_dir(path="/mimi"):
    """List files in a directory."""
    try:
        entries = os.listdir(path)
        if not entries:
            return f"{path}: (empty)"
        return "\n".join(entries)
    except OSError:
        return f"Error: directory not found: {path}"


# ── Helpers ───────────────────────────────────────────────────────

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _ensure_parent(path):
    """Create parent directory of path if it doesn't exist."""
    parts = path.rsplit("/", 1)
    if len(parts) == 2 and parts[0]:
        parent = parts[0]
        try:
            os.mkdir(parent)
        except OSError:
            pass
