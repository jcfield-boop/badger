WIFI_SSID = ""
WIFI_PASSWORD = ""

# Optional (Mimi only): try several known networks in order, connecting to
# whichever is actually in range — handy for switching between home and a
# phone hotspot without editing this file each time. Falls back to
# WIFI_SSID/WIFI_PASSWORD above if unset or none are in range.
# WIFI_NETWORKS = [
#     ("home-network", "home-password"),
#     ("phone-hotspot", "hotspot-password"),
# ]

REGION = "eu"  # Options are us, cuba, eu, moldova, lebanon, egypt, chile, australia, nz
TIMEZONE = 0  # Offset from GMT as number of hours, i.e. 0, 1, -7 etc.
GITHUB_USERNAME = ""
GITHUB_TOKEN = ""

# ── Mimi AI assistant ─────────────────────────────────────────────
# Telegram Bot token (from @BotFather)
MIMI_TELEGRAM_TOKEN = ""

# Optional: restrict Telegram to these chat_ids only (your own user ID).
# Empty/unset = allow anyone who finds the bot — not recommended, since
# they'd get full file read/write, http_request, and cron access.
# MIMI_AUTHORIZED_CHAT_IDS = ["123456789"]

# OpenRouter API key (https://openrouter.ai/keys)
MIMI_OPENROUTER_KEY = ""

# Model to use. "openrouter/auto" picks whatever's best/cheapest at the
# time, but that can route to a reasoning-heavy model that burns its whole
# token budget on internal reasoning and returns an empty response for a
# simple prompt — confirmed live during this session's demo testing.
# openai/gpt-4o-mini is the pinned default: fast, cheap, reliable tool
# calling, never once returned empty across dozens of live tests.
MIMI_MODEL = "openai/gpt-4o-mini"

# Brave Search API key (https://brave.com/search/api/) — optional
MIMI_BRAVE_KEY = ""
