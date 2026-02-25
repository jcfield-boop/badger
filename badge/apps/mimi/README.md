# Mimi — AI Assistant Badge App

Mimi is an AI assistant app for the GitHub Universe 2025 / Pimoroni Tufty RP2350 badge. It receives messages via Telegram, runs them through an LLM (OpenRouter), executes tools, and shows the conversation history on the badge display. Buttons provide direct interaction without a phone or browser.

## Setup

Add these entries to `/secrets.py` on the badge:

```python
WIFI_SSID     = "your-network"
WIFI_PASSWORD = "your-password"

MIMI_TELEGRAM_TOKEN  = "your-bot-token"       # from @BotFather
MIMI_TELEGRAM_CHATID = "your-chat-id"         # your Telegram user ID
MIMI_OPENROUTER_KEY  = "sk-or-..."            # OpenRouter API key
MIMI_TAVILY_KEY      = "tvly-..."             # Tavily search key (optional)
```

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

Non-blocking frame loop — `init()` starts WiFi without waiting; `update()` shows a "Connecting…" screen until WiFi is ready, then switches to normal operation. Telegram is polled every 5 s with `timeout=0` (non-blocking). Cron is ticked every 1 s. Agent calls (LLM + tools) run synchronously in `update()` while the `_thinking` flag prevents further polling.

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
│ Mimi: 14:32 UTC, unix 1740… │  conversation
│                                │  (11 lines × 8 px, ark.ppf)
│ …                              │
├────────────────────────────────┤  y=108
│ [A]Ping [B]Clear [C]Menu      │  hints (ark.ppf)
└────────────────────────────────┘  y=120
```

## Files

```
apps/mimi/
├── __init__.py     App entry: init(), update(), on_exit()
├── agent.py        LLM call + tool dispatch loop
├── telegram.py     Telegram getUpdates poll + sendMessage
├── context.py      System prompt assembly (SOUL.md + MEMORY.md)
├── memory.py       LittleFS read/write for MEMORY.md and sessions
├── wifi.py         Non-blocking WiFi connect helper
├── cron.py         Scheduled task runner
├── tools/
│   ├── __init__.py Tool registry
│   ├── get_time.py HTTP HEAD → Date header, returns epoch
│   ├── files.py    Read/write/list LittleFS files
│   ├── web_search.py Tavily search API
│   ├── http_request.py Generic GET/POST
│   └── system_info.py Heap, uptime, battery
└── ui/
    ├── conversation.py Chat history renderer
    └── status_bar.py   WiFi/battery/title strip
```
