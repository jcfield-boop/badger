# Ported from eink/examples/wordle (Badger 2040 / badger2040 API, portrait
# via 90-degree rotated text) to the badgeware API used by the 2025 Tufty
# badge. The 160x120 screen is used landscape directly - no rotation hack
# needed. Controls were remapped since badgeware only has A/B/C/UP/DOWN
# (no left/right): UP/DOWN cycle the letter at the cursor, A confirms it and
# advances the cursor, B backspaces, C submits the completed row.
import sys
import os
import gc

sys.path.insert(0, "/system/apps/wordle")
os.chdir("/system/apps/wordle")

from badgeware import screen, PixelFont, shapes, brushes, io, run

import sound

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ALL_WORDS_COUNT = 12972   # words in all_words.txt (5 bytes each, no separator)
WINNERS_COUNT = 2309      # words in winners.txt

CELL_W = 19
CELL_H = 19
GRID_COLS = 5
GRID_ROWS = 6
GRID_X = (160 - GRID_COLS * CELL_W) // 2
GRID_Y = 1

BG_COLOR = (13, 17, 23)
EMPTY_FILL = (22, 27, 34)
EMPTY_OUTLINE = (56, 62, 70)
CURSOR_OUTLINE = (88, 166, 255)
CORRECT_FILL = (46, 160, 67)
PRESENT_FILL = (187, 158, 0)
ABSENT_FILL = (60, 64, 70)
TEXT_COLOR = (230, 237, 243)

font = PixelFont.load("/system/assets/fonts/nope.ppf")

bg_brush = brushes.color(*BG_COLOR)
empty_brush = brushes.color(*EMPTY_FILL)
empty_outline_brush = brushes.color(*EMPTY_OUTLINE)
cursor_outline_brush = brushes.color(*CURSOR_OUTLINE)
correct_brush = brushes.color(*CORRECT_FILL)
present_brush = brushes.color(*PRESENT_FILL)
absent_brush = brushes.color(*ABSENT_FILL)
text_brush = brushes.color(*TEXT_COLOR)


class GameState:
    INTRO = 1
    PLAYING = 2
    WON = 3
    LOST = 4


state = GameState.INTRO
word = ""
grid = []          # submitted rows: list of strings
grid_colors = []   # per submitted row: list of "correct"/"present"/"absent"
row = [""] * GRID_COLS
letter_idx = [-1] * GRID_COLS
cursor = 0
message = ""
message_timer = 0


def select_word():
    import random
    idx = random.randint(0, WINNERS_COUNT - 1)
    with open("winners.txt", "r") as f:
        f.seek(idx * 5)
        return f.read(5).upper()


def valid_word(candidate):
    candidate = candidate.lower()
    with open("all_words.txt", "r") as f:
        lo, hi = 0, ALL_WORDS_COUNT
        while lo < hi:
            mid = (lo + hi) // 2
            f.seek(mid * 5)
            if f.read(5) < candidate:
                lo = mid + 1
            else:
                hi = mid
        f.seek(lo * 5)
        return f.read(5) == candidate


def score_row(guess):
    """Return a list of 'correct' / 'present' / 'absent' per letter."""
    result = [""] * GRID_COLS
    remaining = list(word)
    # First pass: exact matches
    for i in range(GRID_COLS):
        if guess[i] == word[i]:
            result[i] = "correct"
            remaining[i] = None
    # Second pass: wrong position
    for i in range(GRID_COLS):
        if result[i]:
            continue
        if guess[i] in remaining:
            result[i] = "present"
            remaining[remaining.index(guess[i])] = None
        else:
            result[i] = "absent"
    return result


def new_game():
    global word, grid, grid_colors, row, letter_idx, cursor, state, message
    word = select_word()
    grid = []
    grid_colors = []
    row = [""] * GRID_COLS
    letter_idx = [-1] * GRID_COLS
    cursor = 0
    message = ""
    state = GameState.PLAYING
    gc.collect()


def show_message(text, ms=900):
    global message, message_timer
    message = text
    message_timer = io.ticks + ms


CELL_BRUSHES = {
    "correct": correct_brush,
    "present": present_brush,
    "absent": absent_brush,
}


def draw_grid():
    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            cx = GRID_X + x * CELL_W + 1
            cy = GRID_Y + y * CELL_H + 1
            if y < len(grid):
                screen.brush = CELL_BRUSHES[grid_colors[y][x]]
                screen.draw(shapes.rectangle(cx, cy, CELL_W - 2, CELL_H - 2))
                letter = grid[y][x]
            elif y == len(grid) and state == GameState.PLAYING:
                screen.brush = empty_brush
                screen.draw(shapes.rectangle(cx, cy, CELL_W - 2, CELL_H - 2))
                if x == cursor:
                    screen.brush = cursor_outline_brush
                    screen.draw(shapes.rectangle(cx, cy, CELL_W - 2, CELL_H - 2).stroke(1))
                letter = row[x]
            else:
                screen.brush = empty_brush
                screen.draw(shapes.rectangle(cx, cy, CELL_W - 2, CELL_H - 2))
                letter = ""

            if letter:
                screen.font = font
                screen.brush = text_brush
                w, h = screen.measure_text(letter)
                screen.text(letter, cx + (CELL_W - 2 - w) / 2, cy + (CELL_H - 2 - h) / 2)


def init():
    new_game()


def update():
    global state, cursor, row, letter_idx, message

    sound.update(io.ticks)

    screen.brush = bg_brush
    screen.clear()

    if state == GameState.INTRO:
        screen.font = font
        screen.brush = text_brush
        screen.text("wordle", 60, 30)
        screen.text("UP/DOWN letter", 24, 50)
        screen.text("A confirm  B back", 16, 62)
        screen.text("C submit row", 30, 74)
        if io.BUTTON_A in io.pressed:
            new_game()
        return

    draw_grid()

    if state in (GameState.WON, GameState.LOST):
        screen.font = font
        screen.brush = text_brush
        if state == GameState.WON:
            msg = "you got it!"
        else:
            msg = "word: " + word
        w, _ = screen.measure_text(msg)
        screen.brush = brushes.color(0, 0, 0, 200)
        screen.draw(shapes.rectangle(80 - w / 2 - 3, 52, w + 6, 12))
        screen.brush = text_brush
        screen.text(msg, 80 - w / 2, 54)
        if io.BUTTON_A in io.pressed:
            new_game()
        return

    # --- PLAYING ---
    if io.BUTTON_UP in io.pressed:
        letter_idx[cursor] = (letter_idx[cursor] + 1) % 26
        row[cursor] = LETTERS[letter_idx[cursor]]
        sound.beep(1000, 20)
    elif io.BUTTON_DOWN in io.pressed:
        letter_idx[cursor] = (letter_idx[cursor] - 1) % 26
        row[cursor] = LETTERS[letter_idx[cursor]]
        sound.beep(900, 20)
    elif io.BUTTON_A in io.pressed:
        if row[cursor] != "" and cursor < GRID_COLS - 1:
            cursor += 1
            sound.beep(1300, 30)
    elif io.BUTTON_B in io.pressed:
        row[cursor] = ""
        letter_idx[cursor] = -1
        cursor = max(0, cursor - 1)
        sound.beep(500, 30)
    elif io.BUTTON_C in io.pressed:
        guess = "".join(row)
        if "" in row:
            show_message("finish the word")
            sound.beep(300, 120)
        elif not valid_word(guess):
            show_message("not a word")
            sound.beep(300, 120)
        else:
            grid.append(row[:])
            grid_colors.append(score_row(guess))
            sound.beep(1500, 40)
            if guess == word:
                state = GameState.WON
                sound.notes([(880, 90), (1100, 90), (1400, 160)])
            elif len(grid) >= GRID_ROWS:
                state = GameState.LOST
                sound.notes([(500, 90), (400, 90), (250, 160)])
            else:
                row = [""] * GRID_COLS
                letter_idx = [-1] * GRID_COLS
                cursor = 0

    if message and io.ticks < message_timer:
        screen.font = font
        w, _ = screen.measure_text(message)
        screen.brush = brushes.color(0, 0, 0, 200)
        screen.draw(shapes.rectangle(80 - w / 2 - 3, 2, w + 6, 10))
        screen.brush = text_brush
        screen.text(message, 80 - w / 2, 3)
    elif message and io.ticks >= message_timer:
        message = ""


if __name__ == "__main__":
    run(update)
