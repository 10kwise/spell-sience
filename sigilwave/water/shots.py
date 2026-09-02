"""Drive the water headlessly and photograph it.

Same room as the stage (`stage/world.py` is read-only from here), so a shot
taken by this harness is comparable with one taken by the old renderer.

    python -m sigilwave.water.shots
"""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from ..stage import world
from .ping import Ping, step_all
from .shader import WaterShader

OUT = "debug_output"
DT = 1.0 / 60.0


def _spray(fn, pos, radius, dose, cell):
    """A patch, not a point -- a single cell is smaller than the stencil that
    samples it, so a one-cell feature is read at about half its true strength."""
    n = max(1, int(radius / cell))
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            dx, dy = i * cell, j * cell
            r = (dx * dx + dy * dy) ** 0.5
            if r <= radius:
                fn(pos[0] + dx, pos[1] + dy, dose * (1.0 - 0.6 * r / radius))


def _heat(medium, pos, seconds):
    for _ in range(int(seconds / DT)):
        _spray(medium.add_heat, pos, 34.0, 12.0 * DT, medium.cell_size)
        medium.step(DT)


def _bubbles(medium, pos, seconds):
    for _ in range(int(seconds / DT)):
        _spray(lambda x, y, a: medium.add_bubbles(x, y, a, 1.4),
               pos, 40.0, 0.30 * DT, medium.cell_size)
        medium.step(DT)


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    size = (world.WIDTH, world.HEIGHT)
    screen = pygame.display.set_mode(size)

    # (name, room, diver, where pings are fired from, frames to run)
    scenes = []

    # 1. The room with nobody in it and no light spent on it. This is what
    #    darkness looks like before a ping: almost nothing, which is the point.
    scenes.append(("water_1_room", world.build(), None, [], 0))

    # 2. Somebody in it, having fired nothing. The small bubble you carry is
    #    all you get -- the rest of the room is a rumour.
    scenes.append(("water_2_diver", world.build(), (430.0, 470.0), [], 0))

    # 3. One ping, mid-flight. The wavefront is the brightest thing on screen
    #    because it is the light source, not an object being lit.
    scenes.append(("water_3_ping_flight", world.build(), (430.0, 470.0),
                   [(0, (430.0, 470.0))], 70))

    # 4. The same ping, spent. What is left is the room it found -- the whole
    #    reason the ping exists.
    scenes.append(("water_4_ping_revealed", world.build(), (430.0, 470.0),
                   [(0, (430.0, 470.0))], 240))

    # 5. Three pings from a moving diver, which is how the map actually gets
    #    built in play.
    scenes.append(("water_5_room_by_pings", world.build(), (760.0, 560.0),
                   [(0, (300.0, 430.0)), (60, (560.0, 500.0)),
                    (150, (760.0, 560.0))], 320))

    # 6. A vent, lit by its own heat rather than by a ping. The one warm thing
    #    in the ocean, and the only landmark that announces itself.
    m = world.build()
    _heat(m, (520.0, 660.0), 5.0)
    scenes.append(("water_6_vent_plume", m, (600.0, 600.0), [], 30))

    # 7. A bubble curtain, pinged. Wood's collapse lifts the bands and the
    #    curtain also turns the ping around, so it is cover in both senses.
    m = world.build()
    _bubbles(m, (700.0, 560.0), 3.0)
    scenes.append(("water_7_bubble_curtain", m, (520.0, 500.0),
                   [(0, (520.0, 500.0))], 90))

    # 8. Deep, where the ramp has almost run out and only the ping reads.
    scenes.append(("water_8_deep", world.build(), (900.0, 690.0),
                   [(0, (900.0, 690.0))], 120))

    for name, medium, diver, spawns, frames in scenes:
        shader = WaterShader(size, medium)
        pings = []
        t0 = time.perf_counter()
        n = max(frames, 12)
        for f in range(n):
            for at, pos in spawns:
                if f == at:
                    pings.append(Ping(shader, pos[0], pos[1]))
            pings = step_all(pings, DT)
            shader.draw(screen, diver, DT)
        ms = (time.perf_counter() - t0) / n * 1000.0
        path = os.path.join(OUT, name + ".png")
        pygame.image.save(screen, path)
        print("  {:34s} {:6.2f} ms/frame ({:4.0f} fps)  reveal {:5.1f}%".format(
            path, ms, 1000.0 / ms if ms > 0 else 0.0,
            100.0 * float((shader.reveal > 0.05).mean())))

    pygame.quit()


if __name__ == "__main__":
    main()
