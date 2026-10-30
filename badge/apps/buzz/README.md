# Buzz

Tests and diagnoses the DRV2605L haptic driver on the Qw/ST connector.

Press SELECT to fire a haptic buzz and see the result on screen: whether
the chip acknowledged the command, and whether its over-current fault
flag (`OC_DETECT`) tripped — useful for diagnosing a non-functional
haptic motor without needing a serial connection. Built while debugging
exactly this on a real badge: the DRV2605L shares its power rail with
other Qw/ST accessories (an RGB matrix, a temperature sensor), and a
power-hungry accessory drawing current at the same time can trip the
motor driver's over-current protection even though the I2C bus itself
stays perfectly healthy.

## Requirements

- A DRV2605L haptic breakout on the Qw/ST connector (default I2C address
  `0x5A`). No crash if one isn't present — the screen just reports that.

## Controls

- **SELECT** — fire a buzz, show the result
- **HOME** — return to launcher
