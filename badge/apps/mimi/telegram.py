"""
Telegram long-poll bot for Mimi.
Ported from telegram_bot.c. Runs on core 1 via _thread.
"""

import urequests
import json
import time
import memory as mem_module

TG_BASE = "https://api.telegram.org/bot"
POLL_TIMEOUT = 30   # seconds for long-poll (use 0 for non-blocking check)
DEDUP_SIZE = 64     # ring buffer for seen message IDs

_token = None
_update_offset = 0
_seen = []          # dedup ring buffer of (chat_id_hash ^ msg_id)
_authorized_ids = None  # None = not loaded yet; [] once loaded = allow all


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


def _get_authorized_ids():
    """Load MIMI_AUTHORIZED_CHAT_IDS from secrets.py. Empty/unset = allow
    all senders (preserves pre-allowlist behavior for anyone who hasn't
    set it)."""
    global _authorized_ids
    if _authorized_ids is not None:
        return _authorized_ids
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import MIMI_AUTHORIZED_CHAT_IDS
        sys.path.pop(0)
        _authorized_ids = [str(i) for i in MIMI_AUTHORIZED_CHAT_IDS]
    except (ImportError, AttributeError):
        _authorized_ids = []
    return _authorized_ids


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

# This firmware's HTTP client corrupts the request body for sendMessage
# whenever the text contains a multi-byte UTF-8 character — confirmed live:
# a message containing only an em dash got "Bad Request: message text is
# empty" from Telegram, while the identical message in plain ASCII sent
# fine. Mimi's real LLM responses routinely contain em dashes/smart quotes
# (or other non-ASCII a model happens to use, e.g. a degree symbol in a
# weather answer), so this silently broke real delivery - reproduced again
# live via a real weather-tool response that still had a non-ASCII char
# the dictionary below didn't cover. Map the common ones to ASCII
# equivalents, then filter anything else non-ASCII character-by-character.
#
# NB: str.encode("ascii", "replace") does NOT work on this MicroPython
# build - confirmed live, it silently passes the original UTF-8 bytes
# through unchanged (no exception, no effect). That's why the dictionary
# substitution alone wasn't enough - the broken fallback let anything not
# in the dictionary straight through. Must filter character-by-character
# instead (same fix already applied to agent.py's _flatten()).
_ASCII_REPLACEMENTS = {
    "—": "-",    # em dash
    "–": "-",    # en dash
    "‘": "'",    # left single quote
    "’": "'",    # right single quote
    "“": '"',    # left double quote
    "”": '"',    # right double quote
    "…": "...",  # ellipsis
}


def _to_ascii(text):
    for src, dst in _ASCII_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return "".join(c if ord(c) < 128 else "?" for c in text)


def send_message(chat_id, text):
    """Send a Telegram message. Splits if > 4096 chars."""
    text = _to_ascii(text)
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


def poll_once(message_queue, timeout=POLL_TIMEOUT):
    """
    Poll for new updates. Appends (chat_id, text, channel) tuples to message_queue.
    Use timeout=0 for a non-blocking check (returns immediately).
    Returns number of new messages found.
    """
    global _update_offset

    params = {"timeout": timeout, "allowed_updates": "message"}
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

        # Allowlist (empty = allow all, for backward compat). Silent skip —
        # don't reply, don't confirm the bot's existence to a stranger.
        authorized = _get_authorized_ids()
        if authorized and chat_id not in authorized:
            print(f"[telegram] dropped message from unauthorized chat_id {chat_id}")
            continue

        # Dedup
        key = _msg_key(chat_id, msg_id)
        if _seen_check(key):
            continue
        _seen_add(key)

        print(f"[telegram] [{chat_id}] {text[:80]}")
        message_queue.append((chat_id, text, "telegram"))
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
