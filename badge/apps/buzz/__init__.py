"""Buzz — DRV2605L haptic diagnostic demo.

Press SELECT to fire a buzz and see whether the chip's over-current
fault flag (OC_DETECT) tripped. Built while debugging a real haptic
failure: the DRV2605L shares its Qw/ST power rail with other accessories
(an RGB matrix, a temp sensor), and a power-hungry one drawing current
at the same time can trip the motor driver's fault protection even
though I2C communication itself stays perfectly healthy — this app
makes that visible without needing a serial connection.
"""

import os
import sys

APP_DIR = "/system/apps/buzz"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

ADDRESS = 0x5A

_REG_STATUS = 0x00
_REG_MODE = 0x01
_REG_LIBRARY = 0x03
_REG_WAVESEQ1 = 0x04
_REG_WAVESEQ2 = 0x05
_REG_GO = 0x0C

EFFECT_STRONG_BUZZ = 14  # library 1 (ERM) effect #14 — "Strong Buzz - 100%"

_i2c = None
_available = False
_initialised = False
_presses = 0
_last_status = None
_last_fault = None


def _write(reg, value):
    _i2c.writeto_mem(ADDRESS, reg, bytes([value]))


def _read(reg):
    return _i2c.readfrom_mem(ADDRESS, reg, 1)[0]


def _init_haptic():
    global _i2c, _available, _initialised
    try:
        from machine import I2C
        _i2c = I2C()
        _available = ADDRESS in _i2c.scan()
        if not _available:
            return
        _write(_REG_MODE, 0x00)
        _write(_REG_LIBRARY, 0x01)
        _read(_REG_STATUS)  # clear any stale fault flag from a prior session
        _initialised = True
    except Exception as e:
        print(f"[buzz] init failed: {e}")
        _available = False


def _fire():
    """Fire a buzz, return (status_byte, fault_bool) or None if unavailable."""
    global _presses, _last_status, _last_fault
    if not _available or not _initialised:
        return None
    try:
        _write(_REG_MODE, 0x00)
        _read(_REG_STATUS)  # clear before this attempt
        _write(_REG_WAVESEQ1, EFFECT_STRONG_BUZZ)
        _write(_REG_WAVESEQ2, 0)
        _write(_REG_GO, 1)
        import time
        time.sleep_ms(150)  # let the chip start driving before we check
        status = _read(_REG_STATUS)
        fault = bool(status & 0x01)
        _presses += 1
        _last_status = status
        _last_fault = fault
        return status, fault
    except Exception as e:
        print(f"[buzz] fire failed: {e}")
        return None


_init_haptic()

BG = color.rgb(13, 17, 23)
WHITE = color.rgb(235, 245, 255)
GRAY = color.rgb(100, 110, 120)
GREEN = color.rgb(46, 160, 67)
RED = color.rgb(248, 81, 73)

screen.font = font.ark


def update():
    if badge.pressed(BUTTON_SELECT):
        _fire()

    screen.pen = BG
    screen.clear()

    screen.pen = WHITE
    screen.text("Buzz — DRV2605L test", 2, 2)

    screen.pen = GRAY
    screen.text(f"0x5A on Qw/ST: {'found' if _available else 'not found'}", 2, 16)

    if not _available:
        screen.pen = RED
        screen.text("No haptic driver detected.", 2, 40)
        screen.pen = GRAY
        screen.text("Check Qw/ST connection.", 2, 50)
    elif _last_status is None:
        screen.pen = GRAY
        screen.text("Press SELECT to buzz.", 2, 40)
    else:
        screen.pen = RED if _last_fault else GREEN
        screen.text("FAULT (OC_DETECT)" if _last_fault else "Clean — no fault", 2, 40)
        screen.pen = GRAY
        screen.text(f"STATUS: {bin(_last_status)}", 2, 50)
        screen.text(f"Presses: {_presses}", 2, 60)
        if _last_fault:
            screen.text("Over-current trip —", 2, 74)
            screen.text("check wiring/shared", 2, 84)
            screen.text("Qw/ST power draw.", 2, 94)

    screen.pen = GRAY
    screen.text("Sel:Buzz  Home:Exit", 2, 108)


run(update)
