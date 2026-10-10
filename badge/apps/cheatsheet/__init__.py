# Ported from eink/examples/copilot (a Badger 2040 e-book/cheat-sheet
# reader) to the badgeware API used by the 2025 Tufty badge. The original
# streamed the book file word-by-word with manual file.seek() bookkeeping
# to stay within the older badge's tight RAM. The badge in this repo has
# 512kB SRAM, so this version just loads the whole (4.6KB) text file into
# memory once and re-wraps it whenever the font changes - much simpler,
# and still only runs the wrap/paginate pass on state changes, not every
# frame (pages are cached and just blitted from a line list each frame).
import sys
import os
import json

sys.path.insert(0, "/system/apps/cheatsheet")
os.chdir("/system/apps/cheatsheet")

from badgeware import screen, PixelFont, shapes, brushes, io, run

import sound

BG_COLOR = (13, 17, 23)
TEXT_COLOR = (230, 237, 243)
HEADER_COLOR = (139, 148, 158)

TEXT_X = 4
TEXT_TOP = 11
TEXT_BOTTOM = 112
LINE_GAP = 2

FONT_FILES = [
    ("nope", "/system/assets/fonts/nope.ppf"),
    ("ark", "/system/assets/fonts/ark.ppf"),
    ("compass", "/system/assets/fonts/compass.ppf"),
]

STATE_FILE = "/cheatsheet_state.json"

bg_brush = brushes.color(*BG_COLOR)
text_brush = brushes.color(*TEXT_COLOR)
header_brush = brushes.color(*HEADER_COLOR)
header_font = PixelFont.load("/system/assets/fonts/ark.ppf")

fonts = [PixelFont.load(path) for _, path in FONT_FILES]
font_idx = 0

book_text = ""
pages = [[]]       # list of pages, each a list of lines
page_idx = 0
current_lines = []


def load_state():
    global font_idx, page_idx
    try:
        with open(STATE_FILE, "r") as f:
            s = json.load(f)
        font_idx = max(0, min(len(FONT_FILES) - 1, s.get("font_idx", 0)))
        page_idx = max(0, s.get("page_idx", 0))
    except Exception:
        font_idx = 0
        page_idx = 0


def save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"font_idx": font_idx, "page_idx": page_idx}, f)
    except Exception:
        pass  # Storage may be read-only / full - fail gracefully


def wrap_text(text, font, max_width):
    """Word-wrap text (which may contain blank lines as paragraph breaks)
    into a flat list of lines, using the given font's measure_text width."""
    screen.font = font
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = (current + " " + word) if current else word
            w, _ = screen.measure_text(candidate)
            if w > max_width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def rebuild_pages():
    """Re-wrap the book for the current font and re-paginate it."""
    global pages
    font = fonts[font_idx]
    max_width = 160 - TEXT_X * 2
    all_lines = wrap_text(book_text, font, max_width)

    line_height = font.height + LINE_GAP
    rows_per_page = max(1, (TEXT_BOTTOM - TEXT_TOP) // line_height)

    pages = [all_lines[i:i + rows_per_page] for i in range(0, len(all_lines), rows_per_page)]
    if not pages:
        pages = [[]]


def show_page():
    global current_lines, page_idx
    page_idx = max(0, min(len(pages) - 1, page_idx))
    current_lines = pages[page_idx]


def init():
    global book_text
    with open("book.txt", "r") as f:
        book_text = f.read()
    load_state()
    rebuild_pages()
    show_page()


def on_exit():
    save_state()


def update():
    sound.update(io.ticks)

    screen.brush = bg_brush
    screen.clear()

    if io.BUTTON_DOWN in io.pressed:
        if page_idx < len(pages) - 1:
            page_idx_bump(1)
            sound.beep(1100, 30)
        else:
            sound.beep(250, 60)
    elif io.BUTTON_UP in io.pressed:
        if page_idx > 0:
            page_idx_bump(-1)
            sound.beep(900, 30)
        else:
            sound.beep(250, 60)
    elif io.BUTTON_A in io.pressed:
        cycle_font()
        sound.beep(1400, 40)
    elif io.BUTTON_B in io.pressed:
        jump_to_start()
        sound.beep(700, 40)

    font = fonts[font_idx]
    line_height = font.height + LINE_GAP
    screen.font = font
    screen.brush = text_brush
    y = TEXT_TOP
    for line in current_lines:
        screen.text(line, TEXT_X, y)
        y += line_height

    # Header: font name + page position
    screen.font = header_font
    screen.brush = header_brush
    header = f"{FONT_FILES[font_idx][0]}  {page_idx + 1}/{len(pages)}"
    screen.text(header, TEXT_X, 1)


def page_idx_bump(delta):
    global page_idx
    page_idx += delta
    show_page()


def cycle_font():
    global font_idx
    font_idx = (font_idx + 1) % len(FONT_FILES)
    rebuild_pages()
    show_page()


def jump_to_start():
    global page_idx
    page_idx = 0
    show_page()


if __name__ == "__main__":
    run(update)
