"""
LLM agent loop for Mimi.
Calls OpenRouter API, dispatches tool calls, manages session history.
Ported from agent_loop.c + llm_proxy.c.
"""

import gc
import json
import time
import urequests
import memory as mem_module
import context as ctx_module
import tools as tool_registry

# ── Config ────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"
MAX_TOOL_ITERATIONS = 10
MAX_TOKENS = 1000
CHUNK_SIZE = 512  # bytes for reading response
REQUEST_TIMEOUT_S = 60
MAX_RETRIES = 1     # one retry on a transient network error (not on a slow-but-live response)
RETRY_DELAY_S = 1


def _get_api_key():
    """Read OpenRouter key from secrets.py or SERVICES.md."""
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import MIMI_OPENROUTER_KEY
        sys.path.pop(0)
        if MIMI_OPENROUTER_KEY:
            return MIMI_OPENROUTER_KEY
    except (ImportError, AttributeError):
        pass
    # Fall back to SERVICES.md
    services = mem_module.read_services()
    for line in services.splitlines():
        if line.startswith("OPENROUTER_KEY="):
            return line.split("=", 1)[1].strip()
    return None


def _get_model():
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import MIMI_MODEL
        sys.path.pop(0)
        if MIMI_MODEL:
            return MIMI_MODEL
    except (ImportError, AttributeError):
        pass
    return DEFAULT_MODEL


# ── LLM call ─────────────────────────────────────────────────────

# ROOT CAUSE (found): this firmware's bundled HTTP client has a genuine
# byte-counting bug — likely Content-Length computed from character count
# instead of UTF-8 byte count — that corrupts the tail of the request body
# once enough multi-byte UTF-8 characters (em dashes, the "×" in "160×120",
# etc.) accumulate across the payload. Below some accumulated deficit it's
# invisible; past it, bytes get dropped from wherever the body happens to
# end, which lands on the next message's "role" field and produces a bogus
# "messages[x].role missing"/'use'/'ro' truncated-role error that isn't
# present in the JSON we actually send (confirmed via local round-trip).
# Verified live, repeatedly, with a real bisection: small snippets containing
# one non-ASCII char succeed; the same char combined with more surrounding
# content fails; an all-ASCII version of the identical content always
# succeeds regardless of length. We can't patch the frozen HTTP client, so
# the mitigation is to never send non-ASCII to it: _flatten() both strips
# markdown structure AND forces ASCII on every message we send.
#
# NB: str.encode("ascii", "replace") does NOT work on this MicroPython
# build — confirmed live: it silently passes the original UTF-8 bytes
# through unchanged instead of replacing them (no exception, no effect).
# Must filter character-by-character instead; same reason telegram.py's
# fix relies on explicit dictionary substitution rather than that encode
# fallback.
_ASCII_REPLACEMENTS = {
    "—": "-",    # em dash
    "–": "-",    # en dash
    "‘": "'",    # left single quote
    "’": "'",    # right single quote
    "“": '"',    # left double quote
    "”": '"',    # right double quote
    "…": "...",  # ellipsis
    "×": "x",    # multiplication sign
}


def _ascii_only(text):
    for src, dst in _ASCII_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return "".join(c if ord(c) < 128 else "?" for c in text)


def _flatten(text, limit=1500):
    """Defensive flattener for any message content sent to the LLM: strips
    markdown structure (headers/bullets) and forces ASCII (see root-cause
    note above) to stay clear of the firmware HTTP client's byte-counting
    bug. Applied to every tool result / user / assistant message, and to
    the restored system-prompt sections below.
    """
    text = str(text)[:limit]
    parts = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        line = line.lstrip("#").strip()
        # strip "1. ", "2. ", "- ", "* " leading markers
        i = 0
        while i < len(line) and line[i].isdigit():
            i += 1
        if i > 0 and line[i:i + 2] == ". ":
            line = line[i + 2:]
        elif line[:2] in ("- ", "* "):
            line = line[2:]
        parts.append(line)
    return _ascii_only(" ".join(parts))


# Verified safe (live, repeated OpenRouter calls): plain-ASCII intro/tools
# summary, standing in for context.py's SYSTEM_PROMPT_STATIC intro+tools
# section, which contains a "×" that reliably triggers the bug above once
# combined with enough other content. The File Paths/Credentials/Memory
# sections ARE restored below (verbatim from context.py, run through
# _flatten() to strip their em dashes) — those were lost entirely in the
# previous stopgap fix, disabling memory-writing tool use.
_SAFE_PROMPT_INTRO = (
    "You are Mimi, a personal AI assistant running on a GitHub Universe badge. "
    "You interact via Telegram and a small display. Keep responses under 800 words, "
    "prefer bullet points, be concise. Use the web_search tool for current facts, news, "
    "or weather. Use get_current_time for the date or time. Use tools when needed instead "
    "of guessing."
)


def _build_system_prompt(turn_context=""):
    """Safe intro + the real File Paths/Credentials/Memory sections and any
    dynamic SOUL.md/USER.md/MEMORY.md/recent-notes content, all flattened,
    plus this turn's channel/chat_id hint (also flattened)."""
    real_prompt = ctx_module.build_system_prompt()
    cut = real_prompt.find("## File Paths")
    rest = real_prompt[cut:] if cut != -1 else ""
    prompt = _SAFE_PROMPT_INTRO + "\n\n" + _flatten(rest, limit=4000)
    if turn_context:
        prompt += "\n\n" + _flatten(turn_context, limit=500)
    return prompt


def _call_llm(messages, turn_context, api_key, model):
    """POST to OpenRouter, return parsed response dict or raise."""
    # OpenAI/OpenRouter format: system prompt is the first message
    full_messages = [{"role": "system", "content": _build_system_prompt(turn_context)}] + messages
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": full_messages,
        "tools": tool_registry.TOOL_SCHEMAS,
        "tool_choice": "auto",
    }

    gc.collect()
    free_before = gc.mem_free()
    print(f"[agent] LLM call: {len(messages)} msgs, heap {free_before} free")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/jcfield-boop/badger",
        "X-Title": "Mimi Badge",
    }

    body = json.dumps(payload)
    print(f"[agent] Request: {len(body)} bytes")

    status = None
    raw = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = urequests.post(OPENROUTER_URL, headers=headers, data=body, timeout=REQUEST_TIMEOUT_S)
            try:
                status = resp.status_code
                # Read response body — urequests buffers the whole response in PSRAM
                raw = resp.content
            finally:
                resp.close()  # always release the socket, even if .content raised
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"[agent] LLM request failed ({type(e).__name__}: {e}), retrying...")
                time.sleep(RETRY_DELAY_S)
                continue
            raise RuntimeError(f"request failed ({type(e).__name__}: {e})")

    print(f"[agent] Response: HTTP {status}, {len(raw)} bytes")

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        snippet = raw.decode("utf-8", "ignore")[:200]
        raise RuntimeError(f"HTTP {status}, non-JSON response: {snippet}")

    del raw
    gc.collect()

    # Normally the body carries {"error": {...}} on failure, which
    # _extract_response already surfaces. This is just a safety net for
    # the unexpected case of a bad status with no error payload at all.
    if status != 200 and "error" not in data:
        raise RuntimeError(f"HTTP {status}: {data}")

    return data


def _extract_response(data):
    """
    Extract text + tool_calls from OpenRouter response.
    Returns (text, tool_calls) where tool_calls is a list of dicts.
    """
    choices = data.get("choices", [])
    if not choices:
        error = data.get("error", {})
        if isinstance(error, dict):
            msg = error.get("message", "no choices")
        else:
            msg = str(error) if error else "no choices"
        raise RuntimeError(f"LLM error: {msg}")

    msg = choices[0].get("message", {})
    text = msg.get("content") or ""
    if isinstance(text, list):
        # Content can be array of blocks
        text_parts = [b.get("text", "") for b in text if b.get("type") == "text"]
        text = " ".join(text_parts)

    tool_calls = msg.get("tool_calls") or []
    # Normalise to list of {id, name, input_dict}
    calls = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        raw_input = fn.get("arguments", "{}")
        try:
            input_dict = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
        except ValueError:
            input_dict = {}
        calls.append({
            "id": tc.get("id", f"call_{name}"),
            "name": name,
            "input": input_dict,
        })

    return text, calls


# ── Agent loop ───────────────────────────────────────────────────

def run(user_message, chat_id="default", channel="telegram", status_cb=None):
    """
    Run the full agent loop for a user message.

    Args:
        user_message: The user's text.
        chat_id: Telegram chat ID or "display".
        channel: "telegram" or "display".
        status_cb: Optional callable(str) for status updates (e.g. "Thinking…").

    Returns:
        Final text response string.
    """
    api_key = _get_api_key()
    if not api_key:
        return "Error: no OpenRouter API key configured. Set MIMI_OPENROUTER_KEY in secrets.py."

    model = _get_model()

    # Load session history
    messages = mem_module.load_session(chat_id)

    # Append user message
    messages.append({"role": "user", "content": _flatten(user_message)})

    # Turn context hint — appended to the system prompt inside _call_llm
    # (which builds the full prompt itself; see _build_system_prompt).
    turn_context = (
        f"Current turn context: source_channel={channel}, source_chat_id={chat_id}. "
        f"If using cron_add for Telegram in this turn, set channel=telegram "
        f"and chat_id to source_chat_id."
    )

    final_text = ""

    for iteration in range(MAX_TOOL_ITERATIONS):
        if status_cb:
            status_cb("Thinking…" if iteration == 0 else f"Tool loop {iteration}…")

        try:
            data = _call_llm(messages, turn_context, api_key, model)
        except Exception as e:
            print(f"[agent] LLM error: {e}")
            return f"Error: LLM call failed: {e}"

        text, tool_calls = _extract_response(data)

        if text:
            final_text = text

        # Build assistant message (OpenAI format). final_text (returned to
        # the user/display) keeps the original formatting; only the copy
        # stored in history for future requests gets flattened.
        asst_msg = {"role": "assistant", "content": _flatten(text) if text else ""}
        if tool_calls:
            asst_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["input"]),
                    },
                }
                for tc in tool_calls
            ]
        messages.append(asst_msg)

        # If no tool calls, we're done
        if not tool_calls:
            break

        # Execute tools, append results (OpenAI tool message format)
        for tc in tool_calls:
            if status_cb:
                status_cb(f"Tool: {tc['name']}…")
            print(f"[agent] Tool: {tc['name']} input={tc['input']}")
            result = tool_registry.dispatch(tc["name"], tc["input"])
            print(f"[agent] Tool result: {str(result)[:80]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": _flatten(result),
            })

        gc.collect()
        gc.collect()

    # Persist session
    mem_module.save_session(chat_id, messages)

    return final_text or "(no response)"
