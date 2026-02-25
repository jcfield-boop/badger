"""
LLM agent loop for Mimi.
Calls OpenRouter API, dispatches tool calls, manages session history.
Ported from agent_loop.c + llm_proxy.c.
"""

import gc
import json
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

def _call_llm(messages, system_prompt, api_key, model):
    """POST to OpenRouter, return parsed response dict or raise."""
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": messages,
        "tools": tool_registry.TOOL_SCHEMAS,
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

    resp = urequests.post(OPENROUTER_URL, headers=headers, data=body, timeout=60)

    # Read response body — urequests buffers the whole response in PSRAM
    raw = resp.content
    resp.close()
    print(f"[agent] Response: {len(raw)} bytes")

    data = json.loads(raw.decode("utf-8"))
    del raw
    gc.collect()
    return data


def _extract_response(data):
    """
    Extract text + tool_calls from OpenRouter response.
    Returns (text, tool_calls) where tool_calls is a list of dicts.
    """
    choices = data.get("choices", [])
    if not choices:
        error = data.get("error", {})
        raise RuntimeError(f"LLM error: {error.get('message', 'no choices')}")

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
    messages.append({"role": "user", "content": user_message})

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

        # Build assistant message for history
        assistant_content = []
        if text:
            assistant_content.append({"type": "text", "text": text})
        for tc in tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })

        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls, we're done
        if not tool_calls:
            break

        # Execute tools, collect results
        tool_results = []
        for tc in tool_calls:
            if status_cb:
                status_cb(f"Tool: {tc['name']}…")
            print(f"[agent] Tool: {tc['name']} input={tc['input']}")
            result = tool_registry.dispatch(tc["name"], tc["input"])
            print(f"[agent] Tool result: {str(result)[:80]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": str(result),
            })

        messages.append({"role": "user", "content": tool_results})
        gc.collect()

    # Persist session
    mem_module.save_session(chat_id, messages)

    return final_text or "(no response)"
