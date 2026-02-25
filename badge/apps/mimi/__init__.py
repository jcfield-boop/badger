"""
Mimi — AI assistant badge app for GitHub Universe 2025 / Pimoroni Tufty RP2350.
"""

import sys
import os

sys.path.insert(0, "/system/apps/mimi")
os.chdir("/system/apps/mimi")

# Badgeware always loads first — needed even for error display
from badgeware import screen, brushes, shapes, PixelFont, io, run

BG    = brushes.color(13, 17, 23)
RED   = brushes.color(200, 50, 50)
WHITE = brushes.color(235, 245, 255)
GRAY  = brushes.color(100, 110, 120)
YELLOW = brushes.color(211, 250, 55)


def _crash(e):
    """Show exception traceback on the display and block."""
    import io as _io
    buf = _io.StringIO()
    sys.print_exception(e, buf)
    tb = buf.getvalue()
    print("[mimi] CRASH:", tb)

    try:
        font = PixelFont.load("/system/assets/fonts/ark.ppf")
        screen.font = font
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
        screen.brush = RED
        screen.clear()
        screen.brush = WHITE
        screen.text("MIMI CRASH", 2, 2)
        screen.brush = GRAY
        for i, ln in enumerate(lines[:10]):
            screen.text(ln, 2, 13 + i * 10)

    run(_err_update)


# ─────────────────────────────────────────────────────────────────
# Everything else runs inside a try block so crashes are visible
# ─────────────────────────────────────────────────────────────────
try:
    import gc
    import time
    import _thread

    try:
        from badgeware import get_battery_level as _get_battery_level
        from badgeware import is_charging as _badge_is_charging
        _HAS_BATTERY = True
    except ImportError:
        _HAS_BATTERY = False

    import wifi
    import memory as mem
    import agent
    import tools as tool_registry
    import cron as cron_module
    import telegram
    from ui import conversation as conv
    from ui import status_bar as sbar

except Exception as _e:
    _crash(_e)
    raise SystemExit


# ── Shared state ──────────────────────────────────────────────────
_wifi_connected = False
_rssi           = 0
_battery_pct    = None
_is_charging    = False
_thinking       = False
_view           = "chat"
_menu_sel       = 0
_stop_flag      = [False]
_msg_queue      = []
_font           = None


# ── Init ──────────────────────────────────────────────────────────

def init():
    global _font, _wifi_connected, _rssi

    gc.collect()
    mem.init()
    sbar.init()
    conv.init()

    _font = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.font = _font

    cron_module.init()
    tool_registry.init(cron_instance=cron_module)

    conv.add_message("system", "Connecting to WiFi\u2026")
    _wifi_connected = wifi.connect(timeout=30)
    _rssi = wifi.get_rssi()

    if _wifi_connected:
        conv.add_message("system", "WiFi connected.")
        try:
            import tools.get_time as gt
            t = gt.execute()
            conv.add_message("system", f"Clock: {t}")
        except Exception as e:
            conv.add_message("system", f"Time sync: {e}")
    else:
        conv.add_message("system", "No WiFi.")

    _stop_flag[0] = False
    _thread.start_new_thread(_background_thread, ())
    conv.add_message("system", "Ready.")


def on_exit():
    _stop_flag[0] = True
    time.sleep(0.3)


# ── Background thread (core 1) ────────────────────────────────────

def _background_thread():
    global _wifi_connected, _rssi, _thinking

    while not _stop_flag[0]:
        _wifi_connected = wifi.ensure_connected(20)
        _rssi = wifi.get_rssi()

        if not _wifi_connected:
            time.sleep(5)
            continue

        try:
            telegram.poll_once(_msg_queue)
        except Exception as e:
            print(f"[bg] poll: {e}")

        while _msg_queue and not _stop_flag[0]:
            chat_id, text, channel = _msg_queue.pop(0)
            _run_agent(chat_id, text, channel)

        try:
            cron_module.tick(lambda p, ch, cid: _msg_queue.append((cid, p, ch)))
        except Exception as e:
            print(f"[bg] cron: {e}")

        gc.collect()
        time.sleep(1)


def _run_agent(chat_id, text, channel="telegram"):
    global _thinking
    _thinking = True
    conv.set_thinking(True)
    conv.add_message("user", text)

    try:
        response = agent.run(text, chat_id=chat_id, channel=channel)
    except Exception as e:
        response = f"Error: {e}"
        print(f"[app] agent: {e}")

    conv.add_message("mimi", response)
    conv.set_thinking(False)
    _thinking = False

    if channel == "telegram" and _wifi_connected:
        try:
            telegram.send_message(chat_id, response)
        except Exception as e:
            print(f"[app] send: {e}")


# ── Frame update (core 0) ─────────────────────────────────────────

def update():
    global _battery_pct, _is_charging, _view, _menu_sel

    if _HAS_BATTERY:
        try:
            _battery_pct = _get_battery_level()
            _is_charging = _badge_is_charging()
        except Exception:
            pass

    _handle_buttons()

    screen.brush = BG
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


def _handle_buttons():
    global _view, _menu_sel

    if _view == "chat":
        if io.BUTTON_UP   in io.pressed:  conv.scroll_up()
        if io.BUTTON_DOWN in io.pressed:  conv.scroll_down()
        if io.BUTTON_B    in io.pressed:  conv.clear()
        if io.BUTTON_C    in io.pressed:
            _view = "menu"
            _menu_sel = 0
        if io.BUTTON_A    in io.pressed:
            _msg_queue.append(("display", "Quick status?", "display"))

    elif _view == "menu":
        n = len(_MENU)
        if io.BUTTON_UP   in io.pressed:  _menu_sel = (_menu_sel - 1) % n
        if io.BUTTON_DOWN in io.pressed:  _menu_sel = (_menu_sel + 1) % n
        if io.BUTTON_A    in io.pressed or io.BUTTON_C in io.pressed:
            _MENU[_menu_sel][1]()
        if io.BUTTON_B    in io.pressed:
            _view = "chat"


def _draw_hints():
    if _font:
        screen.font = _font
        screen.brush = GRAY
        screen.text("[A]Ping [B]Clear [C]Menu", 2, 113)


def _draw_menu():
    if not _font:
        return
    screen.font = _font
    y0, lh = 14, 11
    for i, (label, _) in enumerate(_MENU):
        y = y0 + i * lh
        if i == _menu_sel:
            screen.brush = YELLOW
            screen.draw(shapes.rectangle(0, y - 1, 160, lh))
            screen.brush = BG
        else:
            screen.brush = WHITE
        screen.text(label, 4, y)


# ── Menu actions ──────────────────────────────────────────────────

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
    ("Memory view",  _action_memory),
    ("System info",  _action_sysinfo),
    ("Cron jobs",    _action_cron),
    ("WiFi status",  _action_wifi),
    ("Clear chat",   _action_clear),
    ("\u2190 Back",  _action_back),
]


if __name__ == "__main__":
    run(update)
