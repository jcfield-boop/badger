"""
Simple scheduled task runner for Mimi.
Jobs are stored in /mimi/config/cron.json and checked each agent tick.
"""

import json
import time
import memory as mem_module

CRON_FILE = "/mimi/config/cron.json"
_next_id = 1
_jobs = []  # list of dicts: {id, unix_time, prompt, channel, chat_id, label}


def _load():
    global _jobs, _next_id
    raw = mem_module.read_file(CRON_FILE, "[]")
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, list):
            _jobs = loaded
            _next_id = max((j.get("id", 0) for j in _jobs), default=0) + 1
    except Exception:
        _jobs = []


def _save():
    mem_module.write_file(CRON_FILE, json.dumps(_jobs))


def init():
    _load()


def add(unix_time, prompt, channel="telegram", chat_id="", label=""):
    """Add a one-shot job. Returns confirmation string."""
    global _next_id
    job = {
        "id": _next_id,
        "unix_time": int(unix_time),
        "prompt": prompt,
        "channel": channel,
        "chat_id": str(chat_id),
        "label": label or prompt[:40],
    }
    _jobs.append(job)
    _next_id += 1
    _save()
    return f"Scheduled job #{job['id']}: '{job['label']}' at unix {unix_time}"


def remove(job_id):
    """Remove a job by ID. Returns confirmation string."""
    global _jobs
    before = len(_jobs)
    _jobs = [j for j in _jobs if j.get("id") != int(job_id)]
    _save()
    if len(_jobs) < before:
        return f"Removed job #{job_id}"
    return f"Error: job #{job_id} not found"


def list_jobs():
    """Return a human-readable list of pending jobs."""
    if not _jobs:
        return "No scheduled jobs."
    lines = ["Scheduled jobs:"]
    now = time.time()
    for j in _jobs:
        delta = j["unix_time"] - now
        when = f"in {int(delta)}s" if delta > 0 else "overdue"
        lines.append(f"  #{j['id']} [{when}] {j['label']} → {j['channel']}:{j['chat_id']}")
    return "\n".join(lines)


def tick(agent_callback):
    """
    Check for due jobs. Call agent_callback(prompt, channel, chat_id) for each.
    Should be called periodically from the agent loop.
    Returns number of jobs fired.
    """
    now = time.time()
    fired = []
    remaining = []
    for j in _jobs:
        if j["unix_time"] <= now:
            fired.append(j)
        else:
            remaining.append(j)

    if fired:
        _jobs[:] = remaining
        _save()
        for j in fired:
            print(f"[cron] Firing job #{j['id']}: {j['label']}")
            try:
                agent_callback(j["prompt"], j["channel"], j["chat_id"])
            except Exception as e:
                print(f"[cron] Callback error: {e}")

    return len(fired)
