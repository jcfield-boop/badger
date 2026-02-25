"""
Telegram long-poll bot for Mimi.
Ported from telegram_bot.c. Runs on core 1 via _thread.
"""

import urequests
import json
import time
import memory as mem_module

TG_BASE = "https://api.telegram.org/bot"
POLL_TIMEOUT = 30   # seconds for long-poll
DEDUP_SIZE = 64     # ring buffer for seen message IDs

_token = None
_update_offset = 0
_seen = []          # dedup ring buffer of (chat_id_hash ^ msg_id)


def _get_token():
    global _token
    if _token:
        return _token
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import MIMI_TELEGRAM_TOKEN
        sys.path.pop(0)
        _token = MIMI_TELEGRAM_TOKEN
        return _token
    except (ImportError, AttributeError):
        pass
    # Fall back to SERVICES.md
    services = mem_module.read_services()
    for line in services.splitlines():
        if line.startswith("TELEGRAM_TOKEN="):
            _token = line.split("=", 1)[1].strip()
            return _token
    return None


def _msg_key(chat_id, msg_id):
    """Simple dedup key from chat_id + msg_id."""
    h = hash(str(chat_id)) & 0xFFFF
    return (h << 16) ^ (int(msg_id) & 0xFFFFFFFF)


def _seen_add(key):
    global _seen
    _seen.append(key)
    if len(_seen) > DEDUP_SIZE:
        _seen = _seen[-DEDUP_SIZE:]


def _seen_check(key):
    return key in _seen


# ── API helpers ───────────────────────────────────────────────────

def _api_get(method, params=None):
    token = _get_token()
    if not token:
        return None
    url = f"{TG_BASE}{token}/{method}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    try:
        resp = urequests.get(url, timeout=POLL_TIMEOUT + 5)
        data = resp.json()
        resp.close()
        return data
    except Exception as e:
        print(f"[telegram] GET {method} error: {e}")
        return None


def _api_post(method, payload):
    token = _get_token()
    if not token:
        return None
    url = f"{TG_BASE}{token}/{method}"
    headers = {"Content-Type": "application/json"}
    try:
        resp = urequests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        data = resp.json()
        resp.close()
        return data
    except Exception as e:
        print(f"[telegram] POST {method} error: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────

def send_message(chat_id, text):
    """Send a Telegram message. Splits if > 4096 chars."""
    MAX_LEN = 4096
    for i in range(0, len(text), MAX_LEN):
        chunk = text[i:i + MAX_LEN]
        result = _api_post("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        })
        if not result or not result.get("ok"):
            print(f"[telegram] sendMessage failed: {result}")
            return False
    return True


def poll_once(message_queue):
    """
    Poll for new updates. Appends (chat_id, text) tuples to message_queue.
    Returns number of new messages found.
    """
    global _update_offset

    params = {"timeout": POLL_TIMEOUT, "allowed_updates": "message"}
    if _update_offset > 0:
        params["offset"] = _update_offset

    data = _api_get("getUpdates", params)
    if not data or not data.get("ok"):
        return 0

    updates = data.get("result", [])
    count = 0

    for update in updates:
        uid = update.get("update_id", 0)
        _update_offset = uid + 1

        msg = update.get("message")
        if not msg:
            continue

        chat_id = str(msg.get("chat", {}).get("id", ""))
        msg_id = msg.get("message_id", 0)
        text = msg.get("text", "")

        if not text or not chat_id:
            continue

        # Dedup
        key = _msg_key(chat_id, msg_id)
        if _seen_check(key):
            continue
        _seen_add(key)

        print(f"[telegram] [{chat_id}] {text[:80]}")
        message_queue.append((chat_id, text))
        count += 1

    return count


def poll_loop(message_queue, stop_flag):
    """
    Continuous poll loop. Run on core 1 via _thread.
    stop_flag is a list; set stop_flag[0] = True to exit.
    """
    import wifi
    while not stop_flag[0]:
        if not wifi.ensure_connected(20):
            time.sleep(5)
            continue
        try:
            poll_once(message_queue)
        except Exception as e:
            print(f"[telegram] poll_loop error: {e}")
            time.sleep(5)
