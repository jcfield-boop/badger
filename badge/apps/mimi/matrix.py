"""Animated shrimp on the Qw/ST RGB matrix (Adafruit 13x9, IS31FL3741)
while Mimi is thinking — matches Mimi's own shrimp icon/mascot.

Uses the is31fl3741.Matrix driver copied from this repo's comfort_matrix
app (same board). Two-frame wiggle: antenna tips and legs alternate: a
curled body/head/antenna shape stays static, only the extremities move.
"""

from is31fl3741 import Matrix

ADDRESS = 0x30
CURRENT = 8       # same conservative default comfort_matrix uses
COLOR = (255, 90, 60)   # warm coral, shrimp-ish
FRAME_MS = 450

# 13 wide x 9 tall, '#' = lit. Rows 1-6 (head/body/tail) are static across
# both frames; only the antenna tips (row 0) and legs (rows 7-8) animate.
_BODY = (
    "........#.#..",
    ".......#####.",
    "......##.....",
    "....##.......",
    "..##.........",
    ".##..........",
)

_FRAMES = (
    (".........#.#.",) + _BODY + ("#....#.#.#...", ".....#.#.#..."),
    ("........#.#..",) + _BODY + (".....#.#.#...", "#....#.#.#..."),
)

for _frame in _FRAMES:
    assert len(_frame) == 9
    assert all(len(row) == 13 for row in _frame)

_i2c = None
_matrix = None
_available = False
_thinking = False
_frame_index = 0
_last_switch = 0


def _rows_to_pixels(rows):
    pixels = bytearray(Matrix.WIDTH * Matrix.HEIGHT)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                pixels[y * Matrix.WIDTH + x] = 1
    return pixels


_PIXELS = tuple(_rows_to_pixels(frame) for frame in _FRAMES)


def init():
    """Connect to the matrix if present. No-op (not a crash) if it isn't."""
    global _i2c, _matrix, _available
    try:
        from machine import I2C
        _i2c = I2C()
        _matrix = Matrix(_i2c, ADDRESS, CURRENT)
        _available = True
    except Exception as e:
        print(f"[matrix] not available: {e}")
        _available = False


def set_thinking(active):
    global _thinking, _frame_index, _last_switch
    _thinking = active
    if not active and _available:
        try:
            _matrix.draw(bytearray(Matrix.WIDTH * Matrix.HEIGHT), COLOR)
        except Exception as e:
            print(f"[matrix] clear failed: {e}")


def update(now_ticks):
    """Call once per frame to advance the wiggle animation."""
    global _frame_index, _last_switch
    if not _available or not _thinking:
        return
    if now_ticks - _last_switch >= FRAME_MS:
        _last_switch = now_ticks
        _frame_index = 1 - _frame_index
        try:
            _matrix.draw(_PIXELS[_frame_index], COLOR)
        except Exception as e:
            print(f"[matrix] draw failed: {e}")
