"""WiFi connect/reconnect helper for Mimi badge app."""

import network
import time

wlan = None
_connected = False
_ssid = None
_password = None
_networks = []  # optional list of (ssid, password) fallback candidates


def load_credentials():
    """Load WIFI_SSID/WIFI_PASSWORD and, if present, the WIFI_NETWORKS list
    of (ssid, password) candidates from secrets.py (e.g. home + hotspot)."""
    global _ssid, _password, _networks
    if _ssid is not None or _networks:
        return True
    try:
        import sys
        sys.path.insert(0, "/")
        from secrets import WIFI_SSID, WIFI_PASSWORD
        _ssid = WIFI_SSID
        _password = WIFI_PASSWORD
        try:
            from secrets import WIFI_NETWORKS
            _networks = list(WIFI_NETWORKS)
        except (ImportError, AttributeError):
            _networks = []
        sys.path.pop(0)
    except (ImportError, AttributeError):
        _ssid = None
        _password = None
    return _ssid is not None or bool(_networks)


def _candidates():
    """Configured (ssid, password) pairs, WIFI_NETWORKS first, in order."""
    cands = list(_networks)
    if _ssid and not any(ssid == _ssid for ssid, _ in cands):
        cands.append((_ssid, _password))
    return cands


def _pick_network():
    """Of the configured candidates, pick the first one actually in range."""
    cands = _candidates()
    if not cands:
        return None
    try:
        visible = {n[0].decode("utf-8", "ignore") for n in wlan.scan()}
        for ssid, password in cands:
            if ssid in visible:
                return (ssid, password)
    except Exception as e:
        print(f"[wifi] scan failed: {e}")
    return cands[0]  # fall back to the first configured network anyway


def start_connect():
    """Start WiFi connection without blocking. Call once, then poll is_connected()."""
    global wlan, _ssid, _password
    if not load_credentials():
        return False
    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    if not wlan.isconnected():
        pick = _pick_network()
        if pick is None:
            return False
        _ssid, _password = pick
        print(f"[wifi] Connecting to {_ssid}...")
        wlan.connect(_ssid, _password)
    return True


def connect(timeout=30):
    """Connect to WiFi. Returns True if connected."""
    global wlan, _connected, _ssid, _password

    if not load_credentials():
        print("[wifi] No credentials found in secrets.py")
        return False

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

    if wlan.isconnected():
        _connected = True
        return True

    pick = _pick_network()
    if pick is None:
        print("[wifi] No configured network in range")
        return False
    _ssid, _password = pick

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
