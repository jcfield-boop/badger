"""DRV2605L haptic driver over Qw/ST I2C — one-shot buzz on new messages.

Confirmed present on the Qw/ST bus at its default address 0x5A (verified
live via i2c.scan() alongside the SHT45 temp/humidity sensor at 0x44 and
the IS31FL3741 RGB matrix at 0x30 — all three share the same bus). Standard
TI/Adafruit register sequence: exit standby into internal-trigger mode,
select a built-in waveform-library effect, set GO to play it.
"""

ADDRESS = 0x5A

_REG_MODE = 0x01
_REG_LIBRARY = 0x03
_REG_WAVESEQ1 = 0x04
_REG_WAVESEQ2 = 0x05
_REG_GO = 0x0C

EFFECT_STRONG_CLICK = 1  # library 1 (ERM) effect #1 — "Strong Click - 100%"
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


def buzz(effect=EFFECT_STRONG_CLICK):
    """Fire a single built-in haptic effect. Non-blocking — the chip plays
    it asynchronously once triggered."""
    if not _available or not _initialised:
        return
    try:
        _write(_REG_WAVESEQ1, effect)
        _write(_REG_WAVESEQ2, 0)  # terminate the sequence
        _write(_REG_GO, 1)        # trigger playback
    except Exception as e:
        print(f"[haptic] buzz failed: {e}")
