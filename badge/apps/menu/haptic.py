"""DRV2605L haptic click for main-menu navigation — optional Qw/ST
accessory, no-op (not a crash) on any badge that doesn't have one.

Trimmed copy of apps/mimi/haptic.py's init()/click() — same board, same
register sequence, colocated per this repo's existing convention (see
apps/*/sound.py) rather than importing across app directories.
"""

ADDRESS = 0x5A

_REG_MODE = 0x01
_REG_LIBRARY = 0x03
_REG_WAVESEQ1 = 0x04
_REG_WAVESEQ2 = 0x05
_REG_GO = 0x0C

EFFECT_STRONG_CLICK = 1  # library 1 (ERM) effect #1 — "Strong Click - 100%"

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
            return
        _write(_REG_MODE, 0x00)     # exit standby, internal-trigger mode
        _write(_REG_LIBRARY, 0x01)  # ERM effect library
        _initialised = True
    except Exception:
        _available = False


def click():
    """Single short tap for per-navigation-action feedback."""
    if not _available or not _initialised:
        return
    try:
        _write(_REG_WAVESEQ1, EFFECT_STRONG_CLICK)
        _write(_REG_WAVESEQ2, 0)
        _write(_REG_GO, 1)
    except Exception:
        pass
