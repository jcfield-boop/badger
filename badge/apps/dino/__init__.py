# Ported from eink/examples/dino (Badger 2040 / badger2040 API) to the
# badgeware API used by the 2025 Tufty badge. Original used a blocking
# while-loop game_loop(); this version drives everything from update()
# since badgeware apps are frame-callback based, not blocking-loop based.
import sys
import os
import json

sys.path.insert(0, "/system/apps/dino")
os.chdir("/system/apps/dino")

from badgeware import screen, PixelFont, shapes, brushes, io, run, Image

import sound

BACKGROUND_COLOR = (13, 17, 23)   # GitHub dark background
GROUND_COLOR = (48, 54, 61)
TEXT_COLOR = (230, 237, 243)

GROUND_Y = 104
GRAVITY = 900.0          # px/s^2
JUMP_VELOCITY = -260.0   # px/s
BASE_SPEED = 60.0        # px/s
SPEED_PER_POINT = 4.0    # px/s added per point scored
MAX_SPEED = 220.0

HIGH_SCORE_FILE = "/dino_highscore.json"

font = PixelFont.load("/system/assets/fonts/nope.ppf")
dino_img = Image.load("assets/dino.png")
cactus_img = Image.load("assets/cactus.png")

bg_brush = brushes.color(*BACKGROUND_COLOR)
ground_brush = brushes.color(*GROUND_COLOR)
text_brush = brushes.color(*TEXT_COLOR)


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


state = GameState.INTRO
high_score = 0
score = 0

player_y = 0.0
player_vy = 0.0
on_ground = True

obstacles = []  # list of [x, width_img] - cactus_img is shared, only x varies


def load_high_score():
    global high_score
    try:
        with open(HIGH_SCORE_FILE, "r") as f:
            high_score = json.load(f).get("high_score", 0)
    except Exception:
        high_score = 0


def save_high_score():
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            json.dump({"high_score": high_score}, f)
    except Exception:
        pass  # Fail gracefully - storage may be read-only / full


def reset_game():
    global score, player_y, player_vy, on_ground, obstacles
    score = 0
    player_y = GROUND_Y - dino_img.height
    player_vy = 0.0
    on_ground = True
    obstacles = [160.0 + 40.0, 160.0 + 40.0 + 90.0]


def obstacle_speed():
    return min(BASE_SPEED + score * SPEED_PER_POINT, MAX_SPEED)


def rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + ah and ay + ah > by


def init():
    load_high_score()
    reset_game()


def draw_ground():
    screen.brush = ground_brush
    screen.draw(shapes.rectangle(0, GROUND_Y + dino_img.height, 160, 1))


def draw_score(x, y):
    screen.brush = text_brush
    screen.font = font
    screen.text("score " + str(score), x, y)


def update():
    global state, player_y, player_vy, on_ground, score, high_score, obstacles

    sound.update(io.ticks)
    dt = io.ticks_delta / 1000.0

    screen.brush = bg_brush
    screen.clear()
    draw_ground()

    jump_pressed = (io.BUTTON_A in io.pressed) or (io.BUTTON_UP in io.pressed)

    if state == GameState.INTRO:
        screen.brush = text_brush
        screen.font = font
        screen.text("dino", 66, 30)
        screen.text("A or UP to start", 36, 50)
        screen.text("high score " + str(high_score), 42, 64)
        screen.blit(dino_img, 10, GROUND_Y - dino_img.height)
        if jump_pressed:
            reset_game()
            state = GameState.PLAYING
        return

    if state == GameState.GAME_OVER:
        screen.brush = text_brush
        screen.font = font
        screen.text("game over", 48, 40)
        screen.text("score " + str(score), 58, 54)
        if jump_pressed:
            state = GameState.INTRO
        return

    # --- PLAYING ---
    if jump_pressed and on_ground:
        player_vy = JUMP_VELOCITY
        on_ground = False
        sound.beep(1200, 60)

    player_vy += GRAVITY * dt
    player_y += player_vy * dt
    floor = GROUND_Y - dino_img.height
    if player_y >= floor:
        player_y = floor
        player_vy = 0.0
        on_ground = True

    speed = obstacle_speed()
    for i in range(len(obstacles)):
        obstacles[i] -= speed * dt
        if obstacles[i] <= -cactus_img.width:
            obstacles[i] += 160.0 + 70.0 + (score % 3) * 20.0
            score += 1
            sound.beep(1600, 40)

    screen.blit(dino_img, 10, player_y)
    for x in obstacles:
        screen.blit(cactus_img, x, GROUND_Y - cactus_img.height)

    draw_score(10, 8)

    for x in obstacles:
        if rects_overlap(10, player_y, dino_img.width, dino_img.height,
                          x, GROUND_Y - cactus_img.height, cactus_img.width, cactus_img.height):
            sound.notes([(600, 90), (400, 90), (250, 140)])
            if score > high_score:
                high_score = score
                save_high_score()
            state = GameState.GAME_OVER
            break


if __name__ == "__main__":
    run(update)
