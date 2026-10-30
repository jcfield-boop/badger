"""DRV2605L haptic driver over Qw/ST I2C — one-shot buzz on new messages.

Present on the Qw/ST bus at its default address 0x5A, alongside the SHT45
temp/humidity sensor (0x44) and the IS31FL3741 RGB matrix (0x30) — all
three share one power rail through the daisy-chained Qw/ST cable. Standard
TI/Adafruit register sequence: exit standby into internal-trigger mode,
select a built-in waveform-library effect, set GO to play it.

KNOWN ISSUE (diagnosed live on real hardware, see badge/apps/buzz/):
with all three devices connected, the DRV2605L's STATUS register (0x00)
showed OC_DETECT tripping on every single buzz attempt, and its own
built-in DIAGNOSTIC and AUTO_CAL routines both reported DIAG_RESULT=FAIL -
not a code bug, confirmed by the chip's own self-test. Root cause: the
crab matrix animation lighting ~50-60 pixels across all 3 RGB channels at
once draws enough current to destabilize the shared rail enough to trip
the haptic driver's over-current protection. This was NOT permanent
damage - physically disconnecting the matrix and temp sensor, leaving only
the DRV2605L on the bus, immediately cleared the fault (diagnostic, auto-
cal, and a real buzz all came back clean; confirmed felt on real
hardware). If reconnecting all three, expect this to resurface and budget
for it (lower matrix CURRENT, avoid driving matrix + haptic in the same
moment, or give them separate power if you keep all three permanently).
"""

ADDRESS = 0x5A

_REG_MODE = 0x01
_REG_LIBRARY = 0x03
_REG_WAVESEQ1 = 0x04
_REG_WAVESEQ2 = 0x05
_REG_WAVESEQ3 = 0x06
_REG_GO = 0x0C

EFFECT_STRONG_CLICK = 1   # library 1 (ERM) effect #1 — "Strong Click - 100%" (~100ms tap)
EFFECT_STRONG_BUZZ = 14   # library 1 (ERM) effect #14 — "Strong Buzz - 100%" (~1s sustained)
# NB: if the attached actuator is an LRA rather than ERM, library 6 and a
# different effect set applies — swap _REG_LIBRARY's value below.

_i2c = None
_available = False
_initialised = False


def _write(reg, value):
    _i2c.writeto_mem(ADDRESS, reg, bytes([value]))


def init():
    """Connect to the DRV2605L if present. No-op (not a crash) if it isn't."""
    global _i2c, _available, _initialised
    try:
        from machine import I2C
        _i2c = I2C()
        _available = ADDRESS in _i2c.scan()
        if not _available:
            print("[haptic] DRV2605L not found on the bus")
            return
        _write(_REG_MODE, 0x00)     # exit standby, internal-trigger mode
        _write(_REG_LIBRARY, 0x01)  # ERM effect library
        _initialised = True
    except Exception as e:
        print(f"[haptic] init failed: {e}")
        _available = False


def buzz(effect=EFFECT_STRONG_BUZZ):
    """Fire a haptic effect twice back-to-back for a longer, more noticeable
    buzz (a single "Strong Click" was reported as too short/weak). Non-
    blocking — the chip plays the sequence asynchronously once triggered."""
    if not _available or not _initialised:
        return
    try:
        _write(_REG_WAVESEQ1, effect)
        _write(_REG_WAVESEQ2, effect)
        _write(_REG_WAVESEQ3, 0)  # terminate the sequence
        _write(_REG_GO, 1)        # trigger playback
    except Exception as e:
        print(f"[haptic] buzz failed: {e}")


def click():
    """Single short tap — for per-button-press feedback on the capacitive
    buttons, where buzz()'s longer double-pulse would feel sluggish."""
    if not _available or not _initialised:
        return
    try:
        _write(_REG_WAVESEQ1, EFFECT_STRONG_CLICK)
        _write(_REG_WAVESEQ2, 0)  # terminate the sequence
        _write(_REG_GO, 1)
    except Exception as e:
        print(f"[haptic] click failed: {e}")
