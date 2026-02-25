"""
Status bar for the Mimi badge app.
Occupies the top 12px strip: WiFi indicator, title, battery level.
"""

from badgeware import screen, brushes, shapes, PixelFont

BAR_H = 12
BAR_Y = 0

# Colors
BG = brushes.color(22, 27, 34)         # slightly lighter than main bg
FG = brushes.color(235, 245, 255)      # white-ish
GREEN = brushes.color(46, 160, 67)
YELLOW = brushes.color(211, 250, 55)
RED = brushes.color(248, 81, 73)
GRAY = brushes.color(100, 110, 120)
DIVIDER = brushes.color(48, 54, 61)

_font = None


def init():
    global _font
    _font = PixelFont.load("/system/assets/fonts/ark.ppf")  # 6px — fits in 12px bar


def draw(wifi_connected=False, rssi=0, battery_pct=None, is_charging=False, thinking=False):
    """
    Render the top status bar.
    Call this every frame from update() before drawing the conversation area.
    """
    if _font is None:
        return

    # Background strip
    screen.brush = BG
    screen.draw(shapes.rectangle(0, BAR_Y, 160, BAR_H))

    # Divider line at bottom of bar
    screen.brush = DIVIDER
    screen.draw(shapes.line(0, BAR_H, 160, BAR_H, 1))

    screen.font = _font
    y = BAR_Y + 2  # vertical center in 12px strip (matches weather app)

    # ── Left: WiFi indicator ──────────────────────────────────────
    if wifi_connected:
        strength = _rssi_to_bars(rssi)
        screen.brush = GREEN
        screen.text(f"W{strength}", 2, y)
    else:
        screen.brush = GRAY
        screen.text("--", 2, y)

    # ── Centre: title + thinking indicator ───────────────────────
    title = "Mimi"
    if thinking:
        from badgeware import io
        dots = "." * ((io.ticks // 300) % 4)
        title = f"Mimi{dots}"
    title_w, _ = screen.measure_text(title)
    screen.brush = YELLOW if thinking else FG
    screen.text(title, (160 - title_w) // 2, y)

    # ── Right: battery ────────────────────────────────────────────
    if battery_pct is not None:
        if is_charging:
            screen.brush = GREEN
            batt_str = f"+{battery_pct}%"
        elif battery_pct > 40:
            screen.brush = FG
            batt_str = f"{battery_pct}%"
        elif battery_pct > 15:
            screen.brush = YELLOW
            batt_str = f"{battery_pct}%"
        else:
            screen.brush = RED
            batt_str = f"{battery_pct}%!"
        batt_w, _ = screen.measure_text(batt_str)
        screen.text(batt_str, 158 - batt_w, y)
    else:
        try:
            import time
            uptime_s = time.ticks_ms() // 1000
            up_str = f"{uptime_s}s"
            screen.brush = GRAY
            up_w, _ = screen.measure_text(up_str)
            screen.text(up_str, 158 - up_w, y)
        except Exception:
            pass


def _rssi_to_bars(rssi):
    """Convert RSSI dBm to 1-4 bar indicator string."""
    if rssi >= -55:
        return "4"
    if rssi >= -67:
        return "3"
    if rssi >= -78:
        return "2"
    return "1"
