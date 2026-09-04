"""Render the game to PNGs without a window.

Balance can be measured headlessly; legibility cannot be measured at all,
only looked at. This drives the real App through its real modes and saves
real frames, so the thing being judged is the thing that ships rather than a
mock-up of it.

    python -m sigilwave.game.shots
"""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "debug_output",
)


def save(app, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"shot_{name}.png")
    pygame.image.save(app.screen, path)
    print(f"  saved {path}")


def main():
    random.seed(7)
    from .app import App

    app = App()

    # --- title
    app.draw()
    save(app, "1_title")

    # --- forge, with the starter kit and some energy in the ink
    app.start_run()
    forge = app.forge
    forge.slot = 0
    forge.dummy.band = 1
    forge.dummy.distance = 340
    forge.sigil.tap()
    for _ in range(90):
        forge.update(1 / 120.0)
    app.draw()
    save(app, "2_forge_shove")

    # --- forge with the hot sigil sustained, mid-overdrive
    forge.slot = 2
    forge.dummy.band = 4
    forge.dummy.distance = 160
    forge.set_hold(True)
    for _ in range(260):
        forge.update(1 / 120.0)
    app.draw()
    save(app, "3_forge_spark_overdrive")
    forge.set_hold(False)

    # --- field, mid-fight in the Mirror room (Ward + Cinders)
    app.run.room_index = 1
    app.enter_field()
    f = app.field
    p = f.player
    for i in range(700):
        nearest = min(f.enemies, key=lambda e: (e.pos - p.pos).length()) if f.enemies else None
        if nearest is not None:
            to = nearest.pos - p.pos
            if to.length_squared() > 1e-6:
                p.aim = to.normalize()
            move = to.normalize() if to.length() > 300 else pygame.Vector2()
        else:
            move = pygame.Vector2()
        if i % 45 == 0:
            p.try_tap()
        if i > 420:
            p.set_hold(True)
        app.update(1 / 120.0)
        _ = move
    app.draw()
    save(app, "4_field_combat")

    # --- field with a relay placed and lit
    f.stamp_relay(p.pos + pygame.Vector2(150, -90))
    for _ in range(140):
        p.set_hold(True)
        app.update(1 / 120.0)
    app.draw()
    save(app, "5_field_relay")

    # --- the Anchor room, so the elite and its own sigil are on screen
    app.run.room_index = 4
    app.enter_field()
    f = app.field
    p = f.player
    p.switch(2)
    for i in range(600):
        if f.enemies:
            to = f.enemies[0].pos - p.pos
            if to.length_squared() > 1e-6:
                p.aim = to.normalize()
        p.set_hold(True)
        app.update(1 / 120.0)
    app.draw()
    save(app, "6_field_anchor")

    # --- reward screen
    app.finish_room()
    app.draw()
    save(app, "7_reward")

    pygame.quit()
    print("done")


if __name__ == "__main__":
    main()
