"""System info tool — heap, uptime, WiFi RSSI, battery level."""

import gc
import time

_boot_time_ms = None


def _get_boot_time_ms():
    global _boot_time_ms
    if _boot_time_ms is None:
        _boot_time_ms = time.ticks_ms()
    return _boot_time_ms


def execute():
    """Return a summary of device health."""
    gc.collect()

    # Free heap
    free_heap = gc.mem_free()
    alloc_heap = gc.mem_alloc()
    total_heap = free_heap + alloc_heap

    # Uptime
    uptime_ms = time.ticks_diff(time.ticks_ms(), _get_boot_time_ms())
    uptime_s = uptime_ms // 1000
    uptime_str = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m {uptime_s % 60}s"

    # WiFi RSSI
    rssi_str = "N/A"
    try:
        import wifi
        rssi = wifi.get_rssi()
        if rssi != 0:
            rssi_str = f"{rssi} dBm"
    except Exception:
        pass

    # Battery level
    battery_str = "N/A"
    try:
        from badgeware import get_battery_level, is_charging
        level = get_battery_level()
        charging = is_charging()
        battery_str = f"{level}%{' (charging)' if charging else ''}"
    except Exception:
        pass

    lines = [
        "## System Info",
        f"Free heap:  {free_heap:,} / {total_heap:,} bytes ({100 * free_heap // total_heap}% free)",
        f"Uptime:     {uptime_str}",
        f"WiFi RSSI:  {rssi_str}",
        f"Battery:    {battery_str}",
    ]
    return "\n".join(lines)
