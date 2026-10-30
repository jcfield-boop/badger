"""Animated crab (claws open/close) on the Qw/ST RGB matrix (Adafruit
13x9, IS31FL3741) while Mimi is thinking.

Pixel data below is a real downsample of Twemoji's crab emoji (U+1F980,
jdecked/twemoji, MIT licensed), not hand-drawn geometry — a detailed
curled shrimp silhouette was tried first and does not survive downsampling
to 13x9 (117 pixels) at all, confirmed visually across four resize
algorithms (LANCZOS/NEAREST/BOX/BILINEAR): all four produced the same
indistinct blob. A crab's bold, compact, symmetric shape with raised
claws does survive at this resolution. Frame B is the same source
horizontally squeezed ~78% before downsampling, so the claws visibly
pull inward — an "claws open -> closing" snap animation derived from
real art, not invented motion.

Uses the is31fl3741.Matrix driver copied from this repo's comfort_matrix
app (same board), but bypasses its draw(pixels, rgb) — that takes one
shared color for every "lit" pixel; this writes the full per-pixel RGB
frame directly to matrix.pwm via matrix.channels(x, y) instead.

KNOWN ISSUE: this animation's current draw can trip the DRV2605L haptic
driver's over-current protection when both share the Qw/ST power rail —
see the note in haptic.py for the full diagnosis (confirmed live: not a
code bug, resolved by not running all three Qw/ST accessories at once).
"""

from is31fl3741 import Matrix

ADDRESS = 0x30
CURRENT = 8       # same conservative default comfort_matrix uses
FRAME_MS = 400

W, H = Matrix.WIDTH, Matrix.HEIGHT  # 13, 9

# fmt: off
_FRAME_A = (
    (0,0,0), (10,1,2), (119,16,31), (149,20,38), (50,2,10), (0,0,0), (0,0,0), (0,0,0), (50,2,10), (149,20,38), (119,16,31), (10,1,2), (0,0,0),
    (0,0,0), (123,16,32), (190,25,49), (139,8,29), (89,2,17), (0,0,0), (0,0,0), (0,0,0), (89,2,17), (139,8,29), (190,25,49), (123,16,32), (0,0,0),
    (4,1,1), (188,25,48), (169,13,37), (91,2,17), (14,9,11), (72,26,37), (11,0,2), (72,26,36), (14,9,11), (91,2,17), (169,13,38), (188,25,48), (4,1,1),
    (0,0,0), (132,4,25), (86,2,16), (60,6,14), (138,14,33), (176,15,40), (176,15,40), (176,15,40), (138,14,33), (60,6,14), (86,2,16), (132,4,25), (0,0,0),
    (100,3,19), (47,1,9), (140,15,34), (206,35,58), (202,33,56), (194,27,51), (190,25,49), (194,28,52), (202,33,56), (205,35,58), (140,15,34), (47,1,9), (100,3,19),
    (41,1,8), (76,2,14), (159,21,41), (193,27,51), (190,25,49), (190,25,49), (190,25,49), (190,25,49), (190,25,49), (193,27,51), (161,21,42), (76,2,14), (41,1,8),
    (46,1,9), (90,2,17), (93,2,18), (111,7,23), (171,27,47), (202,33,56), (201,32,56), (202,33,56), (179,28,49), (124,9,27), (93,2,18), (90,2,17), (46,1,9),
    (22,1,4), (98,3,18), (93,2,18), (58,1,11), (121,3,23), (37,5,9), (49,8,13), (37,5,10), (122,3,23), (58,1,11), (93,2,18), (98,3,18), (22,1,4),
    (0,0,0), (0,0,0), (0,0,0), (66,2,13), (68,2,13), (0,0,0), (0,0,0), (0,0,0), (68,2,13), (66,2,13), (0,0,0), (0,0,0), (0,0,0),
)

_FRAME_B = (
    (0,0,0), (0,0,0), (12,2,3), (130,17,34), (114,12,27), (3,0,0), (0,0,0), (3,0,0), (114,12,27), (130,17,34), (12,2,3), (0,0,0), (0,0,0),
    (0,0,0), (0,0,0), (95,13,25), (188,24,48), (135,5,26), (3,0,1), (0,0,0), (3,0,1), (134,5,26), (188,24,48), (95,13,25), (0,0,0), (0,0,0),
    (0,0,0), (0,0,0), (140,18,36), (161,11,34), (48,1,9), (56,29,36), (23,1,4), (56,29,36), (48,1,9), (161,11,34), (140,18,36), (0,0,0), (0,0,0),
    (0,0,0), (0,0,0), (99,3,19), (71,2,14), (97,9,23), (170,16,40), (176,15,40), (170,16,40), (97,9,23), (71,2,14), (99,3,19), (0,0,0), (0,0,0),
    (0,0,0), (55,1,11), (67,2,13), (158,19,40), (204,35,57), (197,30,53), (190,25,49), (197,30,54), (204,34,57), (158,19,40), (67,2,13), (55,1,11), (0,0,0),
    (0,0,0), (20,1,4), (72,2,14), (171,24,45), (191,26,49), (190,25,49), (190,25,49), (190,25,49), (191,26,50), (174,24,46), (72,2,14), (20,1,4), (0,0,0),
    (0,0,0), (20,0,4), (84,2,16), (93,2,18), (136,16,34), (201,32,56), (201,32,56), (201,33,56), (150,18,38), (93,3,18), (84,2,16), (20,0,4), (0,0,0),
    (0,0,0), (2,0,0), (88,2,17), (87,2,16), (102,3,19), (51,4,11), (49,7,13), (51,4,11), (102,3,19), (87,2,16), (88,2,17), (2,0,0), (0,0,0),
    (0,0,0), (0,0,0), (0,0,0), (0,0,0), (97,3,19), (0,0,0), (0,0,0), (0,0,0), (97,3,19), (0,0,0), (0,0,0), (0,0,0), (0,0,0),
)
# fmt: on

_FRAMES = (_FRAME_A, _FRAME_B)
_N_FRAMES = len(_FRAMES)

_i2c = None
_matrix = None
_available = False
_thinking = False
_frame_index = 0
_last_switch = 0


def _draw(buf):
    for y in range(H):
        for x in range(W):
            r, g, b = buf[y * W + x]
            cr, cg, cb = _matrix.channels(x, y)
            _matrix.pwm[cr] = r
            _matrix.pwm[cg] = g
            _matrix.pwm[cb] = b
    _matrix.show()


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
            _draw([(0, 0, 0)] * (W * H))
        except Exception as e:
            print(f"[matrix] clear failed: {e}")


def update(now_ticks):
    """Call once per frame to advance the claw-snap animation."""
    global _frame_index, _last_switch
    if not _available or not _thinking:
        return
    if now_ticks - _last_switch >= FRAME_MS:
        _last_switch = now_ticks
        _frame_index = (_frame_index + 1) % _N_FRAMES
        try:
            _draw(_FRAMES[_frame_index])
        except Exception as e:
            print(f"[matrix] draw failed: {e}")
