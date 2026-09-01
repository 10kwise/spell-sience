"""Photograph the stage headlessly.

Nobody building this can watch the screen while a test runs, and 13.3's
question ("is this hypnotic?") is answered by looking. So every scenario the
stage is supposed to make legible gets rendered to `debug_output/` where it
can be examined a frame at a time.

    python -m sigilwave.stage.shots
"""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from .app import MOUTHS, Renderer, Stage
from . import world

OUT = "debug_output"
DT = 1.0 / 60.0


def _advance(stage, renderer, screen, seconds, draw_every=True):
    """Run the stage forward, drawing every frame so the reveal surface
    accumulates the way it does in play. Skipping the draw would produce a
    picture of a room nobody had lit."""
    steps = int(seconds / DT)
    for _ in range(steps):
        stage.update(DT)
        if draw_every:
            renderer.draw(screen, stage)


def _save(screen, name, label, font):
    if label:
        screen.blit(font.render(label, True, (95, 140, 170)), (12, 12))
    path = os.path.join(OUT, f"stage_{name}.png")
    pygame.image.save(screen, path)
    print(f"  wrote {path}")


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((world.WIDTH, world.HEIGHT))
    font = pygame.font.SysFont("consolas,menlo,monospace", 14)
    size = (world.WIDTH, world.HEIGHT)

    # --- the room itself, with the truth showing ----------------------
    stage = Stage()
    renderer = Renderer(size, stage.medium)
    stage.show_field = True
    renderer.draw(screen, stage)
    axis = world.channel_depth(stage.medium)
    _save(screen, "1_field", f"c-field (TAB). channel axis at y={axis:.0f}px", font)
    print(f"  sound-channel axis: y = {axis:.1f} px "
          f"({axis / world.HEIGHT * 100:.0f}% of the way down)")

    # --- one omni ping, three moments ---------------------------------
    stage = Stage()
    renderer = Renderer(size, stage.medium)
    stage.mouth_index = 3
    stage.diver.update(300.0, axis)
    stage.fire((900.0, axis))
    for tag, secs in (("early", 0.7), ("mid", 1.6), ("late", 2.5)):
        _advance(stage, renderer, screen, secs)
        renderer.draw(screen, stage)
        e = sum(f.total_energy() for f in stage.fronts)
        _save(screen, f"2_omni_{tag}",
              f"OMNI  t={secs:.1f}s cumulative  fronts={len(stage.fronts)}  E={e:.3f}", font)

    # --- the three mouths, same energy, same aim ----------------------
    for i, m in enumerate(MOUTHS[:3]):
        stage = Stage()
        renderer = Renderer(size, stage.medium)
        stage.mouth_index = i
        stage.diver.update(160.0, 430.0)
        stage.fire((1150.0, 430.0))
        _advance(stage, renderer, screen, 2.2)
        renderer.draw(screen, stage)
        alive = len(stage.fronts)
        arc = stage.fronts[0].arc_length() if alive else 0.0
        _save(screen, f"3_mouth_{m.name.lower()}",
              f"{m.name}: {m.hint}   arc={arc:.0f}px", font)

    # --- the channel: shallow angle on the axis vs the same ping steep -
    for tag, target_dy, label in (
        ("shallow", 0.0, "launched flat on the axis - trapped"),
        ("steep", -260.0, "same ping, steep - punches through"),
    ):
        stage = Stage()
        renderer = Renderer(size, stage.medium)
        stage.mouth_index = 1
        stage.diver.update(120.0, axis)
        stage.fire((1150.0, axis + target_dy))
        _advance(stage, renderer, screen, 4.0)
        renderer.draw(screen, stage)
        _save(screen, f"4_channel_{tag}", f"CHANNEL: {label}", font)

    # --- the mirror you build out of warm water -----------------------
    stage = Stage()
    renderer = Renderer(size, stage.medium)
    stage.mouth_index = 1
    # A LAYER, struck at a shallow angle. At 1.2x contrast the critical angle
    # is 57 degrees from normal, so a ping arriving nearly flat reflects and
    # one arriving steeply passes straight through -- which is why a warm
    # mirror is a thing you have to ping shallow to use.
    for x in range(430, 970, 20):
        for _ in range(70):
            stage.heat((float(x), 336.0), DT)
        stage.medium.step(DT)
    stage.diver.update(190.0, 452.0)
    stage.fire((1180.0, 322.0))
    _advance(stage, renderer, screen, 3.2)
    renderer.draw(screen, stage)
    _save(screen, "5_heat_mirror",
          "MIRROR: warm layer struck at a shallow angle - sound skips off it", font)

    # --- the bubble curtain -------------------------------------------
    stage = Stage()
    renderer = Renderer(size, stage.medium)
    stage.mouth_index = 1
    for y in range(280, 540, 24):
        for _ in range(40):
            stage.bubble((640.0, float(y)), DT)
    stage.diver.update(220.0, 410.0)
    stage.fire((1150.0, 410.0))
    _advance(stage, renderer, screen, 2.4)
    renderer.draw(screen, stage)
    _save(screen, "6_bubble_curtain", "CURTAIN: Wood's collapse bends and eats", font)

    # --- what the room looks like after a few pings, unaided ----------
    stage = Stage()
    renderer = Renderer(size, stage.medium)
    stage.mouth_index = 3
    stage.diver.update(400.0, 500.0)
    for _ in range(3):
        stage.fire((900.0, 500.0))
        _advance(stage, renderer, screen, 1.1)
    renderer.draw(screen, stage)
    _save(screen, "7_room_by_sound", "the room, drawn only by its own echoes", font)

    # --- frame cost ----------------------------------------------------
    stage = Stage()
    renderer = Renderer(size, stage.medium)
    stage.mouth_index = 3
    for _ in range(4):
        stage.fire((900.0, 400.0))
        _advance(stage, renderer, screen, 0.35)
    n = sum(len(f) for f in stage.fronts)
    t0 = time.perf_counter()
    for _ in range(30):
        stage.update(DT)
        renderer.draw(screen, stage)
    ms = (time.perf_counter() - t0) / 30 * 1000.0
    print(f"\n  {len(stage.fronts)} fronts / {n} vertices: "
          f"{ms:.1f} ms per frame ({1000.0 / ms:.0f} fps ceiling)")

    pygame.quit()


if __name__ == "__main__":
    main()
