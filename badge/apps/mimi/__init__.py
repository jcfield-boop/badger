"""
Mimi — AI assistant badge app for GitHub Universe 2026.

Non-blocking startup: WiFi connection happens inside update() so the frame
loop stays alive and shows a "Connecting..." screen (same pattern as the
weather app). No threading — Telegram polling and cron run synchronously
from update().
"""

import sys
import os

APP_DIR = "/system/apps/mimi"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

# screen, color, font, badge, and run are runtime-provided globals (2026 API).

BG    = color.rgb(13, 17, 23)
RED   = color.rgb(200, 50, 50)
WHITE = color.rgb(235, 245, 255)
GRAY  = color.rgb(100, 110, 120)
YELLOW = color.rgb(211, 250, 55)


def _crash(e):
    """Show exception traceback on the display and block."""
    import io as _io
    buf = _io.StringIO()
    sys.print_exception(e, buf)
    tb = buf.getvalue()
    print("[mimi] CRASH:", tb)

    try:
        screen.font = font.ark
    except Exception:
        pass

    lines = []
    for raw in tb.split("\n"):
        raw = raw.strip()
        if raw:
            while len(raw) > 25:
                lines.append(raw[:25])
                raw = raw[25:]
            lines.append(raw)

    def _err_update():
        try:
            screen.pen = RED
            screen.clear()
            screen.pen = WHITE
            screen.text("MIMI CRASH", 2, 2)
            screen.pen = GRAY
            for i, ln in enumerate(lines[:10]):
                screen.text(ln, 2, 13 + i * 10)
        except Exception:
            pass

    try:
        run(_err_update)
    except Exception as re:
        print("[mimi] crash display failed:", re)


# ─────────────────────────────────────────────────────────────────
# Everything else runs inside a try block so crashes are visible
# ─────────────────────────────────────────────────────────────────
try:
    import gc

    import wifi
    import memory as mem
    import agent
    import tools as tool_registry
    import cron as cron_module
    import telegram
    import leds
    import haptic
    import matrix as shrimp_matrix
    from ui import conversation as conv
    from ui import status_bar as sbar

except Exception as _e:
    _crash(_e)
    raise SystemExit


# ── Shared state ──────────────────────────────────────────────────
_wifi_connected   = False
_rssi             = 0
_battery_pct      = None
_is_charging      = False
_thinking         = False
_view             = "chat"
_menu_sel         = 0
_msg_queue        = []
_font             = None

# Startup state machine
_ready            = False   # True after WiFi connected + time sync done
_wifi_creds_found = True    # False if no WiFi credentials in secrets.py

# Timing for periodic background work (badge.ticks is ms)
_POLL_INTERVAL_MS = 5000    # Telegram poll every 5 s (timeout=0 = instant)
_CRON_INTERVAL_MS = 1000    # Cron check every 1 s
_WIFI_INTERVAL_MS = 15000   # WiFi status refresh every 15 s
_WIFI_CONNECT_TIMEOUT_MS = 15000  # show the offline-skip prompt after 15 s

# ── Startup (fast — no blocking calls) ─────────────────────────────
# Runs once at module load, replacing the 2025 init() hook (the 2026
# runtime only calls run(update) — there is no separate init()/on_exit()).

gc.collect()
mem.init()
sbar.init()
conv.init()

_font = font.ark
screen.font = _font

cron_module.init()
tool_registry.init(cron_instance=cron_module)
haptic.init()          # DRV2605L on Qw/ST — no-op if not present
shrimp_matrix.init()   # IS31FL3741 RGB matrix on Qw/ST — no-op if not present

# Start WiFi without blocking — update() will poll for connection
_wifi_creds_found = wifi.start_connect()
_connect_started_ticks = badge.ticks

_last_poll_ticks = badge.ticks - _POLL_INTERVAL_MS
_last_cron_ticks = badge.ticks
_last_wifi_ticks = badge.ticks


# ── Frame update ─────────────────────────────────────────────────

def update():
    global _battery_pct, _is_charging, _view, _menu_sel
    global _wifi_connected, _rssi, _thinking, _ready
    global _last_poll_ticks, _last_cron_ticks, _last_wifi_ticks

    now = badge.ticks

    # Battery (fast, always)
    try:
        _battery_pct = badge.battery_level()
        _is_charging = badge.is_charging()
    except Exception:
        pass

    # ── Startup: show connecting screen until WiFi is ready ───────
    if not _ready:
        if not _wifi_creds_found:
            _draw_no_wifi()
            return
        _wifi_connected = wifi.is_connected()
        if not _wifi_connected:
            elapsed = now - _connect_started_ticks
            if elapsed < _WIFI_CONNECT_TIMEOUT_MS:
                _draw_connecting()
                return
            if not badge.pressed(BUTTON_MENU):
                _draw_wifi_timeout()
                return
            # User skipped — continue without WiFi (degraded: no Telegram/LLM)
            conv.add_message("system", "No WiFi — continuing offline.")
            _ready = True
            _last_poll_ticks = now - _POLL_INTERVAL_MS
        else:
            # Connected — do one-time post-connect setup (brief blocking calls OK)
            _rssi = wifi.get_rssi()
            try:
                import tools.get_time as gt
                t = gt.execute()
                conv.add_message("system", f"Clock: {t}")
            except Exception as e:
                conv.add_message("system", f"Time sync: {e}")
            conv.add_message("system", "Ready.")
            _ready = True
            _last_poll_ticks = now - _POLL_INTERVAL_MS  # poll right away

    # ── Normal operation ──────────────────────────────────────────

    leds.update(now)
    shrimp_matrix.update(now)

    # WiFi status refresh (non-blocking)
    if now - _last_wifi_ticks >= _WIFI_INTERVAL_MS:
        _last_wifi_ticks = now
        _wifi_connected = wifi.is_connected()
        _rssi = wifi.get_rssi()

    # Telegram poll (non-blocking, timeout=0)
    if _wifi_connected and not _thinking and (now - _last_poll_ticks) >= _POLL_INTERVAL_MS:
        _last_poll_ticks = now
        try:
            if telegram.poll_once(_msg_queue, timeout=0) > 0:
                haptic.buzz()
        except Exception as e:
            print(f"[poll] {e}")

    # Process one pending message (agent call blocks ~30-60s)
    if _msg_queue and not _thinking:
        chat_id, text, channel = _msg_queue.pop(0)
        _run_agent(chat_id, text, channel)

    # Cron tick (fast, every 1 s)
    if now - _last_cron_ticks >= _CRON_INTERVAL_MS:
        _last_cron_ticks = now
        try:
            cron_module.tick(lambda p, ch, cid: _msg_queue.append((cid, p, ch)))
        except Exception as e:
            print(f"[cron] {e}")

    _handle_buttons()

    screen.pen = BG
    screen.clear()

    if _view == "menu":
        _draw_menu()
    else:
        conv.draw()
        _draw_hints()

    sbar.draw(
        wifi_connected=_wifi_connected,
        rssi=_rssi,
        battery_pct=_battery_pct,
        is_charging=_is_charging,
        thinking=_thinking,
    )


def _draw_connecting():
    dots = "." * ((badge.ticks // 400) % 4)
    screen.pen = BG
    screen.clear()
    if _font:
        screen.font = _font
        screen.pen = WHITE
        screen.text(f"Connecting{dots}", 2, 55)
        screen.pen = GRAY
        screen.text("WiFi...", 2, 64)


def _draw_no_wifi():
    screen.pen = BG
    screen.clear()
    if _font:
        screen.font = _font
        screen.pen = RED
        screen.text("No WiFi config", 2, 55)
        screen.pen = GRAY
        screen.text("Add to secrets.py", 2, 64)


def _draw_wifi_timeout():
    screen.pen = BG
    screen.clear()
    if _font:
        screen.font = _font
        screen.pen = RED
        screen.text("No WiFi yet", 2, 46)
        screen.pen = GRAY
        screen.text("Still trying...", 2, 55)
        screen.pen = WHITE
        screen.text("[Menu] Go offline", 2, 66)


def _run_agent(chat_id, text, channel="telegram"):
    global _thinking
    _thinking = True
    conv.set_thinking(True)
    leds.set_thinking(True)
    shrimp_matrix.set_thinking(True)
    conv.add_message("user", text)

    try:
        response = agent.run(text, chat_id=chat_id, channel=channel)
    except Exception as e:
        response = f"Error: {e}"
        print(f"[app] agent: {e}")

    conv.add_message("mimi", response)
    conv.set_thinking(False)
    leds.set_thinking(False)
    shrimp_matrix.set_thinking(False)
    _thinking = False

    if channel == "telegram" and _wifi_connected:
        try:
            telegram.send_message(chat_id, response)
        except Exception as e:
            print(f"[app] send: {e}")

    gc.collect()


# ── Button handling ───────────────────────────────────────────────

def _handle_buttons():
    global _view, _menu_sel

    if badge.pressed():  # non-empty set = at least one action newly pressed this frame
        haptic.click()

    if _view == "chat":
        if badge.pressed(BUTTON_UP):   conv.scroll_up()
        if badge.pressed(BUTTON_DOWN): conv.scroll_down()
        if badge.pressed(BUTTON_BACK): conv.clear()
        if badge.pressed(BUTTON_MENU):
            _view = "menu"
            _menu_sel = 0
        if badge.pressed(BUTTON_SELECT):
            _msg_queue.append(("display", "Quick status?", "display"))

    elif _view == "menu":
        n = len(_MENU)
        if badge.pressed(BUTTON_UP):   _menu_sel = (_menu_sel - 1) % n
        if badge.pressed(BUTTON_DOWN): _menu_sel = (_menu_sel + 1) % n
        if badge.pressed(BUTTON_SELECT):
            _MENU[_menu_sel][1]()
        if badge.pressed(BUTTON_BACK):
            _view = "chat"


def _draw_hints():
    if _font:
        screen.font = _font
        screen.pen = GRAY
        screen.text("Sel:Ping Back:Clear Menu:Open", 2, 108)


def _draw_menu():
    if not _font:
        return
    screen.font = _font
    y0, lh = 14, 11
    for i, (label, _) in enumerate(_MENU):
        y = y0 + i * lh
        if i == _menu_sel:
            screen.pen = YELLOW
            screen.rectangle(0, y - 1, 160, lh)
            screen.pen = BG
        else:
            screen.pen = WHITE
        screen.text(label, 4, y)


# ── Menu actions ──────────────────────────────────────────────────

def _action_demo_search():
    global _view
    _view = "chat"
    _msg_queue.append(("display",
        "Search the web for the latest GitHub Universe 2026 news and give me a one-sentence summary.",
        "display"))

def _action_demo_intro():
    global _view
    _view = "chat"
    _msg_queue.append(("display",
        "Introduce yourself in one sentence and tell me what you can do.",
        "display"))

def _action_memory():
    global _view
    _view = "chat"
    conv.add_message("system", mem.read_memory()[:400] or "(empty)")

def _action_sysinfo():
    global _view
    _view = "chat"
    try:
        import tools.system_info as si
        conv.add_message("system", si.execute())
    except Exception as e:
        conv.add_message("system", f"Error: {e}")

def _action_cron():
    global _view
    _view = "chat"
    conv.add_message("system", cron_module.list_jobs())

def _action_wifi():
    global _view
    _view = "chat"
    if _wifi_connected:
        import network
        cfg = network.WLAN(network.STA_IF).ifconfig()
        conv.add_message("system", f"IP: {cfg[0]}\nRSSI: {_rssi} dBm")
    else:
        conv.add_message("system", "Not connected")

def _action_clear():
    global _view
    conv.clear()
    _view = "chat"

def _action_back():
    global _view
    _view = "chat"


_MENU = [
    ("Demo: Web search", _action_demo_search),
    ("Demo: Introduce",  _action_demo_intro),
    ("Memory view",  _action_memory),
    ("System info",  _action_sysinfo),
    ("Cron jobs",    _action_cron),
    ("WiFi status",  _action_wifi),
    ("Clear chat",   _action_clear),
    ("\u2190 Back",  _action_back),
]


run(update)
