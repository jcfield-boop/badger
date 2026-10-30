"""Case-LED status feedback for Mimi (GPIO0-3, one white LED each).

No existing badge API wraps the case LEDs — driven directly via
machine.PWM, consistent with this codebase's existing raw-GPIO style
(see the 2025-era sound.py helpers). Soft breathing pulse while Mimi is
thinking; off otherwise. Non-blocking: update() just reads badge.ticks
each frame, no sleeps.
"""

import math

try:
    from machine import Pin, PWM
    _pwms = [PWM(Pin(n)) for n in range(4)]
    for _p in _pwms:
        _p.freq(1000)
        _p.duty_u16(0)
    _available = True
except Exception:
    _pwms = []
    _available = False

_thinking = False
_PULSE_PERIOD_MS = 1400
_MAX_DUTY = 40000  # cap brightness well under 65535 — these sit right on the case


def _set_duty(duty_u16):
    if not _available:
        return
    for p in _pwms:
        p.duty_u16(duty_u16)


def set_thinking(active):
    """Start/stop the breathing pulse. Call alongside conv.set_thinking()."""
    global _thinking
    _thinking = active
    if not active:
        _set_duty(0)


def update(now_ticks):
    """Call once per frame to advance the breathing pulse."""
    if not _available or not _thinking:
        return
    phase = (now_ticks % _PULSE_PERIOD_MS) / _PULSE_PERIOD_MS
    level = (math.sin(phase * 2 * math.pi) + 1) / 2  # 0..1
    _set_duty(int(level * _MAX_DUTY))
