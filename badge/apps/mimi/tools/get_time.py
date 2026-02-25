"""
get_current_time tool — HEAD request to api.telegram.org, parse Date header.
Returns: "YYYY-MM-DD HH:MM:SS TZ (Day) [unix: NNNN]"
Ported from tool_get_time.c.
"""

import urequests
import time

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_cached_epoch = None
_cached_at_ms = None


def _parse_http_date(date_str):
    """
    Parse RFC 2616 date: "Sat, 01 Feb 2025 10:25:00 GMT"
    Returns unix epoch (int) or None.
    """
    try:
        # Strip day-of-week prefix
        if "," in date_str:
            date_str = date_str.split(",", 1)[1].strip()
        parts = date_str.split()
        if len(parts) < 5:
            return None
        day = int(parts[0])
        mon = MONTHS.index(parts[1]) + 1
        year = int(parts[2])
        h, m, s = (int(x) for x in parts[3].split(":"))

        # mktime equivalent via time.mktime
        # MicroPython time.mktime takes (y, mo, d, h, min, s, wd, yd)
        epoch = time.mktime((year, mon, day, h, m, s, 0, 0))
        return epoch
    except Exception as e:
        print(f"[get_time] Date parse error: {e}")
        return None


def execute():
    """Fetch time via HEAD request; update RTC; return formatted string."""
    global _cached_epoch, _cached_at_ms

    try:
        resp = urequests.head("https://api.telegram.org/", timeout=10)
        date_hdr = resp.headers.get("Date") or resp.headers.get("date")
        resp.close()
    except Exception as e:
        # Fall back to cached or RTC
        return _fallback(f"fetch error: {e}")

    if not date_hdr:
        return _fallback("no Date header in response")

    epoch = _parse_http_date(date_hdr)
    if epoch is None:
        return _fallback(f"could not parse: {date_hdr}")

    # Update MicroPython RTC
    try:
        import machine
        t = time.gmtime(epoch)
        rtc = machine.RTC()
        rtc.datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
    except Exception as e:
        print(f"[get_time] RTC set error: {e}")

    _cached_epoch = epoch
    _cached_at_ms = time.ticks_ms()

    return _format(epoch)


def _fallback(reason):
    """Return best available time when network fetch fails."""
    if _cached_epoch is not None and _cached_at_ms is not None:
        elapsed_s = time.ticks_diff(time.ticks_ms(), _cached_at_ms) // 1000
        epoch = _cached_epoch + elapsed_s
        return _format(epoch) + f" [cached+{elapsed_s}s; {reason}]"
    try:
        epoch = time.time()
        if epoch > 1000000000:  # RTC was set
            return _format(epoch) + f" [rtc; {reason}]"
    except Exception:
        pass
    return f"Error: could not get time ({reason})"


def _format(epoch):
    """Format epoch as 'YYYY-MM-DD HH:MM:SS UTC (Weekday) [unix: NNNN]'."""
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    t = time.gmtime(epoch)
    day_name = DAYS[t[6]]
    return (
        f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} "
        f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d} UTC "
        f"({day_name}) [unix: {epoch}]"
    )
