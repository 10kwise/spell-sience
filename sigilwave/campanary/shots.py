"""Render the game to debug_output/ without a display.

    python -m sigilwave.campanary.shots

Being able to look at the game from a headless machine is not a nicety when
the whole redesign is about how it *reads*: half the fixes in this rebuild
were things that were obviously wrong the moment they were on screen and
invisible in any amount of measurement.
"""

import os

import pygame

from sigilwave.ink import Stroke

from . import audio, shapes
from .app import App
from .arena import Belfry, Player
from .bell import Bell
from .foes import GreatBell
from .metals import BRONZE
from .playtest import DT, Founder, bell_for
from .run import ACTS, Run

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "debug_output")


def _save(app, name):
    os.makedirs(OUT, exist_ok=True)
    app.draw()
    path = os.path.join(OUT, f"cam_{name}.png")
    pygame.image.save(app.screen, path)
    print(f"  saved {path}")


def _play(app, seconds, bot=None, hold=False):
    bot = bot or Founder()
    t = 0.0
    while t < seconds:
        m, s_, h, d, w = bot.act(app.belfry)
        app.belfry.update(DT, m, s_, h or hold, d, w)
        app.camera.follow(app.belfry.player.pos, 0.2)
        t += DT
        if app.belfry.cleared or app.belfry.failed:
            break


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    audio.set_enabled(False)
    app = App(pygame.display.set_mode((1280, 800)))

    app.mode = "TITLE"
    app.time = 1.4
    _save(app, "1_title")

    app.run = Run()
    app.enter_foundry(first=True)
    f = app.foundry
    f.bell.strike()
    for _ in range(40):
        f.update(1 / 60)
    _save(app, "2_foundry")

    # Mid-draw, showing the closure assist and the ladder on the canvas.
    rect = f.canvas_rect(app.screen)
    import math
    f.slot = 1
    f.begin((rect.centerx + 60, rect.centery), rect)
    for i in range(48):
        a = math.tau * i / 50
        f.extend((rect.centerx + 60 * math.cos(a), rect.centery + 60 * math.sin(a)), rect)
    _save(app, "3_foundry_drawing")
    f.drawing = None
    f.slot = 0

    def room(spec, name, seconds, bells=None, hold=False):
        player = Player(pygame.Vector2(0, 0), bells or [bell_for(1), bell_for(3)])
        app.belfry = Belfry(player, spec, seed=7)
        app.camera.snap_to(player.pos)
        app.mode = "BELFRY"
        _play(app, seconds, hold=hold)
        _save(app, name)

    room(ACTS[0]["waves"][0], "4_first_toll", 2.4)
    room(ACTS[0]["waves"][1], "5_deadweight", 4.0)
    room(ACTS[1]["waves"][0], "6_twins", 3.0)
    room(ACTS[1]["waves"][2], "7_overtone_swell", 6.0)
    room(ACTS[0]["waves"][3], "8_great_bell", 8.0,
         bells=[bell_for(1), bell_for(2), bell_for(3)])

    app.run.act = 1
    app.offers = app.run.offers()
    app.mode = "REWARD"
    _save(app, "9_reward")

    app.enter_foundry(anvil=True)
    app.foundry.left = 8.4
    _save(app, "10_anvil")
    print("done")


if __name__ == "__main__":
    main()
