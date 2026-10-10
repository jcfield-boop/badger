# PWM square-wave audio for a mono amp wired to the badge's SWIC header.
#
# SWIC header pin-out (silkscreen, left to right): GND, VCC, GPIO_A, GPIO_B, ...
# The amp's signal lead goes to the first GPIO pad right of GND/VCC.
#
# !! CONFIRM AMP_GPIO AGAINST YOUR OWN BOARD BEFORE RELYING ON THIS !!
# This repo has no schematic for the SWIC header (it isn't a documented
# Pimoroni/badgeware connector), so this pin number is a placeholder - swap
# it for whatever GPIO your continuity check / board silkscreen confirms.
AMP_GPIO = 18

try:
    from machine import Pin, PWM
    _pwm = PWM(Pin(AMP_GPIO))
    _pwm.duty_u16(0)
    _available = True
except Exception:
    # No `machine.PWM` (e.g. running under the desktop simulator) or the
    # pin is unavailable - fall back to a silent no-op so apps don't crash.
    _pwm = None
    _available = False

_end_tick = 0
_queue = []  # list of (freq_hz, duration_ms) still to play


def _start(freq):
    if not _available or freq <= 0:
        return
    _pwm.freq(int(freq))
    _pwm.duty_u16(32768)  # 50% duty square wave


def _stop():
    if _available:
        _pwm.duty_u16(0)


def beep(freq=880, ms=80):
    """Queue a single tone. Safe to call every frame; non-blocking."""
    _queue.append((freq, ms))


def notes(sequence):
    """Queue a list of (freq_hz, duration_ms) tuples, e.g. a jump jingle."""
    _queue.extend(sequence)


def stop():
    """Cancel anything queued/playing immediately."""
    _queue.clear()
    _stop()


def update(now_ticks):
    """Call once per frame (e.g. with io.ticks) to advance playback."""
    global _end_tick
    if now_ticks >= _end_tick:
        _stop()
        if _queue:
            freq, ms = _queue.pop(0)
            _start(freq)
            _end_tick = now_ticks + ms
