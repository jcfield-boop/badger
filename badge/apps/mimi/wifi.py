"""WiFi connect/reconnect helper for Mimi badge app."""

import network
import time

wlan = None
_connected = False
_ssid = None
_password = None


def load_credentials():
    global _ssid, _password
    if _ssid is not None:
        return _ssid is not None
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import WIFI_SSID, WIFI_PASSWORD
        _ssid = WIFI_SSID
        _password = WIFI_PASSWORD
        sys.path.pop(0)
    except (ImportError, AttributeError):
        _ssid = None
        _password = None
    return _ssid is not None


def connect(timeout=30):
    """Connect to WiFi. Returns True if connected."""
    global wlan, _connected

    if not load_credentials():
        print("[wifi] No credentials found in secrets.py")
        return False

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

    if wlan.isconnected():
        _connected = True
        return True

    print(f"[wifi] Connecting to {_ssid}...")
    wlan.connect(_ssid, _password)

    deadline = time.ticks_add(time.ticks_ms(), timeout * 1000)
    while not wlan.isconnected():
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            print("[wifi] Connection timed out")
            _connected = False
            return False
        time.sleep(0.5)

    _connected = True
    ip = wlan.ifconfig()[0]
    print(f"[wifi] Connected: {ip}")
    return True


def is_connected():
    """Check if currently connected."""
    global _connected
    if wlan is None:
        _connected = False
        return False
    _connected = wlan.isconnected()
    return _connected


def get_rssi():
    """Return WiFi signal strength in dBm, or 0 if not connected."""
    if wlan is None or not wlan.isconnected():
        return 0
    try:
        return wlan.status("rssi")
    except Exception:
        return 0


def ensure_connected(timeout=20):
    """Reconnect if connection dropped. Returns True if connected."""
    if is_connected():
        return True
    print("[wifi] Reconnecting...")
    return connect(timeout)
