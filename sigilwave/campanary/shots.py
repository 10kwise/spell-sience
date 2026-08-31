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
from .run import Session
from .arena import Belfry, Player
from .bell import Bell
from .foes import GreatBell
from .metals import BRONZE
from .playtest import DT, Founder, bell_for
from .run import spec_for

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
    app.codex.runs = 0
    _save(app, "1_title")

    app.session = Session()
    app.enter_foundry(first=True)
    f = app.foundry
    f.bell.strike()
    for _ in range(40):
        f.update(1 / 60)
    _save(app, "2_foundry")

    # Mid-draw, showing the closure assist and the ladder on the canvas.
    rect = f.canvas_rect(app.screen)
    import math
    # Mid-gesture with the RING tool, showing the snap and the live note.
    f.slot = 2
    f.tool = 0
    f._begin(f.to_canvas(rect.center, rect))
    f._drag(f.to_canvas((rect.centerx + 96, rect.centery - 30), rect))
    f.hover = -1
    _save(app, "3_foundry_ring_tool")
    f.pending = None
    f.slot = 0

    def room(spec, name, seconds, bells=None, hold=False):
        player = Player(pygame.Vector2(0, 0), bells or [bell_for(1), bell_for(3)])
        app.belfry = Belfry(player, spec, seed=7)
        app.camera.snap_to(player.pos)
        app.mode = "BELFRY"
        _play(app, seconds, hold=hold)
        _save(app, name)

    room(spec_for(0), "4_first_toll", 3.2)
    room(spec_for(1), "5_deadweight", 5.0)
    room(spec_for(3), "6_twins", 4.0)
    room(spec_for(5), "7_overtone_swell", 7.0)
    room(spec_for(6), "8_great_bell", 9.0,
         bells=[bell_for(1), bell_for(2), bell_for(3)])
    print("done")


if __name__ == "__main__":
    main()
