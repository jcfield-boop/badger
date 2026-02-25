"""
Conversation history renderer for the 160×120 Tufty display.
Renders chat messages in the scroll area below the status bar.
"""

from badgeware import screen, brushes, shapes, PixelFont

# ── Layout constants ──────────────────────────────────────────────
STATUS_BAR_H = 12       # pixels reserved at top for status bar
MARGIN_X = 3
LINE_H = 9              # pixels per text line (nope.ppf = 8px + 1px gap)
SCROLL_AREA_Y = STATUS_BAR_H + 1
SCROLL_AREA_H = 120 - SCROLL_AREA_Y - 12  # leave 12px at bottom for hint
MAX_LINES = SCROLL_AREA_H // LINE_H        # ~9 visible lines

# ── Colors ────────────────────────────────────────────────────────
BG = brushes.color(13, 17, 23)
USER_COLOR = brushes.color(88, 166, 255)      # GitHub blue
MIMI_COLOR = brushes.color(210, 168, 255)     # purple
SYSTEM_COLOR = brushes.color(139, 148, 158)   # grey
THINKING_COLOR = brushes.color(211, 250, 55)  # phosphor yellow

# ── State ─────────────────────────────────────────────────────────
_font = None
_messages = []      # list of (role, text) — "user", "mimi", "system"
_scroll_offset = 0  # lines scrolled up from bottom
_thinking = False


def init():
    global _font
    _font = PixelFont.load("/system/assets/fonts/nope.ppf")


def _measure_width(text):
    """Return pixel width of text string. measure_text returns an int in badgeware."""
    return screen.measure_text(text)


def _word_wrap(text, max_width):
    """Break text into lines that fit within max_width pixels."""
    if _font is None:
        return [text]

    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        w = _measure_width(test)
        if w <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [""]


def add_message(role, text):
    """Add a message to the conversation. role: 'user', 'mimi', 'system'."""
    global _scroll_offset
    _messages.append((role, text))
    _scroll_offset = 0  # snap to bottom on new message


def clear():
    """Clear conversation history."""
    global _messages, _scroll_offset
    _messages = []
    _scroll_offset = 0


def scroll_up():
    """Scroll up by one line."""
    _scroll_offset += 1


def scroll_down():
    """Scroll down by one line."""
    global _scroll_offset
    _scroll_offset = max(0, _scroll_offset - 1)


def set_thinking(state):
    """Show/hide the 'Thinking…' indicator."""
    global _thinking
    _thinking = state


def draw():
    """Render the conversation area. Called every frame from update()."""
    if _font is None:
        return

    screen.font = _font
    avail_w = 160 - MARGIN_X * 2

    # Build all display lines in order
    all_lines = []  # list of (color, prefix, text_line)
    for role, text in _messages:
        if role == "user":
            color = USER_COLOR
            prefix = "You: "
            indent = "     "
        elif role == "mimi":
            color = MIMI_COLOR
            prefix = "Mimi: "
            indent = "      "
        else:
            color = SYSTEM_COLOR
            prefix = ""
            indent = ""

        # First line with prefix
        first_text = prefix + text
        wrapped = _word_wrap(first_text, avail_w)
        if not wrapped:
            continue
        all_lines.append((color, wrapped[0]))
        for continuation in wrapped[1:]:
            all_lines.append((color, indent + continuation))
        all_lines.append((SYSTEM_COLOR, ""))  # blank separator

    # Thinking indicator
    if _thinking:
        # Animate with dots based on ticks
        from badgeware import io
        dots = "." * ((io.ticks // 400) % 4)
        all_lines.append((THINKING_COLOR, f"Mimi: Thinking{dots}"))

    # Apply scroll
    total = len(all_lines)
    visible_start = max(0, total - MAX_LINES - _scroll_offset)
    visible = all_lines[visible_start: visible_start + MAX_LINES]

    # Draw visible lines
    y = SCROLL_AREA_Y
    for color, line_text in visible:
        screen.brush = color
        if line_text:
            screen.text(line_text, MARGIN_X, y)
        y += LINE_H

    # Scroll indicator
    if _scroll_offset > 0:
        screen.brush = SYSTEM_COLOR
        screen.text(f"^ +{_scroll_offset}", 140, SCROLL_AREA_Y)
