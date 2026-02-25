# Mimi — AI Assistant Badge App

Mimi is an AI assistant app for the GitHub Universe 2025 / Pimoroni Tufty RP2350 badge. It receives messages via Telegram, runs them through an LLM (OpenRouter), executes tools, and shows the conversation history on the badge display. Buttons provide direct interaction without a phone or browser.

## Setup

### 1. Credentials in `/secrets.py`

Add these to `/secrets.py` on the badge root (create it if it doesn't exist):

```python
WIFI_SSID     = "your-network"
WIFI_PASSWORD = "your-password"

MIMI_TELEGRAM_TOKEN  = "your-bot-token"   # from @BotFather
MIMI_TELEGRAM_CHATID = "your-chat-id"     # your Telegram user ID
MIMI_OPENROUTER_KEY  = "sk-or-..."        # OpenRouter API key
MIMI_TAVILY_KEY      = "tvly-..."         # Tavily search key (optional)

# Optional: pin a specific model (default is openrouter/auto)
MIMI_MODEL = "anthropic/claude-3.5-haiku"
```

To get your Telegram chat ID, send a message to your bot then open:
`https://api.telegram.org/bot<TOKEN>/getUpdates` — look for `"id"` inside `"chat"`.

### 2. Config files on LittleFS

Create these files on the badge filesystem under `/mimi/config/`:

| File | Purpose |
|------|---------|
| `SOUL.md` | Mimi's personality — injected into every system prompt |
| `USER.md` | Your profile — name, timezone, preferences |
| `SERVICES.md` | Extra API keys (see below) |

The agent reads these automatically; you can also tell Mimi to update them in conversation.

**Example `SOUL.md`:**
```
You are direct and a little dry. You enjoy wordplay but never sacrifice clarity for it.
You're running on a tiny badge at a conference and you know it — keep things snappy.
```

**Example `USER.md`:**
```
Name: James
Timezone: Europe/London (UTC+0, BST in summer)
Prefers metric units. Dislikes excessive hedging.
```

**`SERVICES.md`** is an alternative place for credentials that the agent can read
when a skill needs them. Put one key per line in `KEY=value` format:

```
OPENROUTER_KEY=sk-or-...
TAVILY_KEY=tvly-...
CUSTOM_WEBHOOK=https://...
```

Secrets in `SERVICES.md` are never echoed back or included in responses — the
system prompt explicitly instructs the agent to treat them as write-only.

### 3. Memory files

These are created and managed by Mimi during conversation:

| File | Purpose |
|------|---------|
| `/mimi/memory/MEMORY.md` | Long-term facts about you — agent appends here automatically |
| `/mimi/memory/YYYY-MM-DD.md` | Daily notes — agent writes here when you ask it to |
| `/mimi/sessions/<chat_id>.json` | Per-chat session history (last 15 messages) |

You can pre-seed `MEMORY.md` with anything you want Mimi to always know.

## Customisation

### Personality

Edit `/mimi/config/SOUL.md`. The entire contents are appended to the system prompt
under a `## Personality` section on every request. You can update it in conversation:

> "Update your SOUL.md to be more laconic"

### Model

Set `MIMI_MODEL` in `secrets.py` to any [OpenRouter model ID](https://openrouter.ai/models).
Defaults to `openrouter/auto` (OpenRouter picks the best available model).

```python
MIMI_MODEL = "anthropic/claude-3.5-haiku"      # fast, cheap
MIMI_MODEL = "openai/gpt-4o-mini"
MIMI_MODEL = "google/gemini-flash-1.5"
```

### Cron jobs (scheduled messages)

Tell Mimi to schedule something in plain English:

> "Remind me to drink water every hour"
> "Send me a morning briefing at 8am tomorrow"

Mimi calls `cron_add` with `channel='telegram'` and your chat ID so the reminder
arrives via Telegram. View pending jobs from the **Cron jobs** menu entry or ask:

> "What have you scheduled for me?"

### Adding a tool

1. Create `apps/mimi/tools/my_tool.py` with an `execute(**kwargs)` function
2. Add its schema to `TOOL_SCHEMAS` in `tools/__init__.py`
3. Register it in the `init()` function in `tools/__init__.py`:
   ```python
   _registry["my_tool"] = my_tool.execute
   ```
4. Add a one-line description to the `## Available Tools` section in `context.py`
   so the agent knows when to use it

## Buttons

| Button | Chat view | Menu view |
|--------|-----------|-----------|
| **UP** | Scroll up | Move selection up |
| **DOWN** | Scroll down | Move selection down |
| **A** | Quick status ping | Confirm selection |
| **B** | Clear conversation | — |
| **C** | Open menu | Confirm selection |
| **HOME** | Return to launcher | Return to launcher |

## Menu

- **Memory view** — show first 400 chars of MEMORY.md
- **System info** — heap free, uptime, battery
- **Cron jobs** — list scheduled tasks
- **WiFi status** — IP address and RSSI
- **Clear chat** — clear conversation history
- **← Back** — return to chat

## Architecture

Non-blocking frame loop — `init()` starts WiFi without waiting; `update()` shows a
"Connecting…" screen until WiFi is ready, then switches to normal operation. Telegram
is polled every 5 s with `timeout=0` (non-blocking). Cron is ticked every 1 s. Agent
calls (LLM + tools) run synchronously in `update()` while the `_thinking` flag
prevents further polling.

```
update() frame loop
├── WiFi state machine (Connecting… → Ready)
├── WiFi status refresh every 15 s
├── Telegram poll every 5 s (timeout=0, non-blocking)
├── Agent call if message queued and not thinking
├── Cron tick every 1 s
├── Button handling
└── Draw: status bar + conversation or menu
```

## Display Layout

```
┌────────────────────────────────┐  y=0
│ W4  Mimi              87%     │  status bar (12 px, ark.ppf)
├────────────────────────────────┤  y=13
│ You: what time is it?         │  y=14
│                                │
│ Mimi: 14:32 UTC, unix 1740…  │  conversation
│                                │  (11 lines × 8 px, ark.ppf)
│ …                              │
├────────────────────────────────┤  y=108
│ [A]Ping [B]Clear [C]Menu      │  hints (ark.ppf)
└────────────────────────────────┘  y=120
```

## Files

```
apps/mimi/
├── __init__.py       App entry: init(), update(), on_exit()
├── agent.py          LLM call + tool dispatch loop
├── telegram.py       Telegram getUpdates poll + sendMessage
├── context.py        System prompt assembly (SOUL.md + MEMORY.md)
├── memory.py         LittleFS read/write for MEMORY.md and sessions
├── wifi.py           Non-blocking WiFi connect helper
├── cron.py           Scheduled task runner
├── tools/
│   ├── __init__.py   Tool registry + schemas
│   ├── get_time.py   HTTP HEAD → Date header, returns epoch
│   ├── files.py      Read/write/list LittleFS files
│   ├── web_search.py Tavily search API
│   ├── http_request.py  Generic HTTPS GET/POST
│   └── system_info.py   Heap, uptime, battery
└── ui/
    ├── conversation.py  Chat history renderer
    └── status_bar.py    WiFi/battery/title strip
```
