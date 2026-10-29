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

# FIXME: Mimi's full markdown system prompt (context.build_system_prompt(),
# headers/bullets/sections) reliably breaks this request on OpenRouter: the
# API reports a bogus "messages[1].role missing" error that isn't present in
# the JSON we actually send (confirmed via local round-trip and byte-level
# inspection — no quotes/backslashes/control chars, correctly escaped).
# Verified live and repeatedly: pure filler text of identical length and a
# fully rewritten plain-prose paragraph both succeed; the real markdown
# content fails even split in half, even with newlines collapsed to a single
# line, even with the "## Credentials" section removed. The exact trigger
# inside the wording is still unidentified — root-causing further needs the
# actual LLM eval harness, not guesswork. Using this known-working flattened
# prompt until that's done; it loses the File Paths/Credentials/Memory
# sections from context.py, so file/memory-writing tool use is unverified.
def _flatten(text, limit=1500):
    """Defensive generic flattener for any message content sent to the LLM.

    Collapses numbered/bulleted lines and multi-line structure to a single
    plain-prose line, and caps length. This is a broad, unproven-per-case
    precaution (see the FIXME above) applied to every tool result / user /
    assistant message, not just the system prompt — the exact trigger for
    the request corruption is still unidentified, so this reduces surface
    area rather than guaranteeing a fix. Test after changing.
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
    return " ".join(parts)


_FALLBACK_SYSTEM_PROMPT = (
    "You are Mimi, a personal AI assistant running on a GitHub Universe badge. "
    "You interact via Telegram and a small display. Keep responses under 800 words, "
    "prefer bullet points, be concise. Use the web_search tool for current facts, news, "
    "or weather. Use get_current_time for the date or time. Use tools when needed instead "
    "of guessing."
)


def _call_llm(messages, system_prompt, api_key, model):
    """POST to OpenRouter, return parsed response dict or raise."""
    # OpenAI/OpenRouter format: system prompt is the first message
    full_messages = [{"role": "system", "content": _FALLBACK_SYSTEM_PROMPT}] + messages
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

    # Build system prompt (includes memory)
    system_prompt = ctx_module.build_system_prompt()

    # Inject turn context hint
    system_prompt += (
        f"\n## Current Turn Context\n"
        f"- source_channel: {channel}\n"
        f"- source_chat_id: {chat_id}\n"
        f"- If using cron_add for Telegram in this turn, set channel='telegram' "
        f"and chat_id to source_chat_id.\n"
    )

    final_text = ""

    for iteration in range(MAX_TOOL_ITERATIONS):
        if status_cb:
            status_cb("Thinking…" if iteration == 0 else f"Tool loop {iteration}…")

        try:
            data = _call_llm(messages, system_prompt, api_key, model)
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
