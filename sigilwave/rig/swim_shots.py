"""Photograph the water moving. RIGS.md 12.7.

Same reasoning as `bench_shots.py`: the question this system exists to answer
-- does it feel like water -- is not one an assertion can answer. `selftest_swim`
proves the numbers are right. This proves they look right, which is a
different claim and the one a player actually experiences.

    python -m sigilwave.rig.swim_shots
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math

import pygame

from ..diver import Diver, KICK, V
from ..medium.field import Medium
from ..sources import Vent
from .chain import Chain, ambient_at
from .station import Station

OUT = "debug_output"
W, H = 1200, 800
DT = 1.0 / 60.0

GROUND = (14, 22, 27)
INK = (232, 240, 242)
SOFT = (128, 150, 158)
COLD = (60, 140, 180)
HOT = (200, 92, 60)
GOOD = (86, 200, 140)
TRACK = (250, 214, 120)


def _font(size, bold=False):
    return pygame.font.SysFont("consolas,dejavusansmono,monospace", size, bold=bold)


def draw_water(screen, med):
    """Temperature as the ground, so the currents have something to sit on."""
    temp = med.temp
    lo, hi = float(temp.min()), float(temp.max())
    span = max(hi - lo, 0.6)
    cs = med.cell_size
    for r in range(med.ny):
        for c in range(med.nx):
            t = (float(temp[r, c]) - lo) / span
            col = (int(14 + 96 * t), int(26 + 40 * t), int(46 + 30 * (1 - t)))
            pygame.draw.rect(screen, col, (c * cs, r * cs, cs + 1, cs + 1))


def draw_flow(screen, med, step=3):
    """The velocity field, as barbs. Length is speed, and the dot is the tail
    so a stopped cell still reads as a cell rather than as nothing."""
    u, v = med.flow_field
    cs = med.cell_size
    for r in range(0, med.ny, step):
        for c in range(0, med.nx, step):
            if med.solid[r, c]:
                continue
            x = (c + 0.5) * cs
            y = (r + 0.5) * cs
            ux = float(u[r, c])
            vy = float(v[r, c])
            mag = math.hypot(ux, vy)
            if mag < 0.02:
                continue
            k = min(26.0, mag * 3.4)
            ex = x + ux / mag * k
            ey = y + vy / mag * k
            shade = min(1.0, mag / 6.0)
            col = (int(70 + 150 * shade), int(120 + 90 * shade), int(160 + 60 * shade))
            pygame.draw.line(screen, col, (x, y), (ex, ey), 1)
            pygame.draw.circle(screen, col, (int(x), int(y)), 1)


def draw_track(screen, points, colour=TRACK, label=None, font=None):
    if len(points) > 1:
        pygame.draw.lines(screen, colour, False, points, 2)
    if points:
        pygame.draw.circle(screen, colour, (int(points[0][0]), int(points[0][1])), 4, 1)
        pygame.draw.circle(screen, colour, (int(points[-1][0]), int(points[-1][1])), 5)
        if label and font:
            img = font.render(label, True, colour)
            screen.blit(img, (points[-1][0] + 10, points[-1][1] - 7))


def track(med, seconds, pos, thrust=V(0, 0), kick=V(0, 0), aim=(1, 0), trim=0.0):
    d = Diver(pos)
    d.aim = V(aim)
    d.trim = trim
    d.trim_target = trim
    pts = [(d.pos.x, d.pos.y)]
    for i in range(int(seconds / DT)):
        d.step(DT, med, thrust=thrust, kick=kick)
        if i % 4 == 0:
            pts.append((d.pos.x, d.pos.y))
    return pts, d


def caption(screen, lines, font, small):
    y = 12
    for i, line in enumerate(lines):
        f = font if i == 0 else small
        col = INK if i == 0 else SOFT
        screen.blit(f.render(line, True, col), (16, y))
        y += 26 if i == 0 else 20


def shot(screen, name, med, tracks, lines, font, small, marks=()):
    draw_water(screen, med)
    draw_flow(screen, med)
    for mx, my, mcol, mlabel in marks:
        pygame.draw.circle(screen, mcol, (int(mx), int(my)), 9, 2)
        screen.blit(small.render(mlabel, True, mcol), (mx + 14, my - 8))
    for pts, col, label in tracks:
        draw_track(screen, pts, col, label, small)
    caption(screen, lines, font, small)
    path = os.path.join(OUT, f"swim_{name}.png")
    pygame.image.save(screen, path)
    print(f"  {path}")


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    font = _font(19, True)
    small = _font(14)

    thr = Chain(("INTAKE", "PUMP", "PUMP", "NARROW", "PORT")).evaluate(
        ambient_at(400.0))
    acc = Diver((0, 0)).rig_thrust(thr, (1.0, 0.0))

    # 1. the open ocean: sheared drift, and what it does to you
    med = Medium(W, H)
    tracks = []
    for y, lab in ((90.0, "40 m"), (330.0, "330 m"), (700.0, "700 m")):
        pts, d = track(med, 30.0, (240.0, y))
        tracks.append((pts, COLD, f"{lab}: drifted {d.pos.x - 240.0:+.0f} px"))
    shot(screen, "1_drift", med, tracks,
         ["THE OPEN OCEAN -- 30 s of doing absolutely nothing",
          "A wind-driven layer is sheared, so the shallows carry you and the deep does not.",
          "Nobody is swimming in any of these three tracks."],
         font, small)

    # 2. a vent: the convection cell
    med2 = Medium(W, H)
    vent = Vent((600.0, 620.0))
    for _ in range(int(180 * 15)):
        vent.warm(med2, 1 / 15.0)
        med2.step(1 / 15.0)
    tracks = []
    for x, col in ((600.0, HOT), (760.0, COLD), (440.0, COLD)):
        pts, d = track(med2, 14.0, (x, 600.0))
        tracks.append((pts, col, f"{d.pos.y - 600.0:+.0f} px"))
    shot(screen, "2_vent", med2, tracks,
         ["A VENT -- 14 s of doing nothing, at three places",
          "Warm water rises. It is incompressible, so what goes up must come down beside it:",
          "continuity puts a sinking return limb either side without being asked.",
          "A vent is not a hazard at a point. It is a circulation."],
         font, small,
         marks=[(600.0, 620.0, HOT, "vent")])

    # 3. the station, and its weather
    med3 = Medium(W, H)
    st = Station((600.0, 480.0))
    for _ in range(int(180 * 15)):
        st.warm(med3, 1 / 15.0)
        med3.step(1 / 15.0)
    pts, d = track(med3, 10.0, (600.0, 472.0))
    hold, dh = track(med3, 10.0, (600.0, 472.0), trim=-0.55)
    shot(screen, "3_station", med3,
         [(pts, TRACK, f"doing nothing: {d.pos.y - 472.0:+.0f} px"),
          (hold, GOOD, f"trimmed heavy: {dh.pos.y - 472.0:+.0f} px")],
         ["HOME HAS WEATHER -- 10 s at the door",
          "The hull leaks heat, warm water rises, and there is a permanent updraft over",
          "the dock. Holding station is something you do, with the bladder, for free."],
         font, small,
         marks=[(600.0, 480.0, GOOD, "station"),
                (600.0, 480.0, (60, 90, 100), "")])

    # 4. what movement costs: same push, with and against
    med4 = Medium(W, H)
    east, de = track(med4, 22.0, (250.0, 150.0), thrust=V(acc.length(), 0))
    west, dw = track(med4, 22.0, (900.0, 250.0), thrust=V(-acc.length(), 0))
    kick, dk = track(med4, 22.0, (600.0, 350.0), kick=V(-KICK, 0))
    broad, db = track(med4, 22.0, (250.0, 450.0), thrust=V(acc.length(), 0),
                      aim=(0, 1))
    shot(screen, "4_cost", med4,
         [(east, GOOD, f"with the current: {de.pos.x - 250.0:+.0f} px"),
          (west, HOT, f"against it: {dw.pos.x - 900.0:+.0f} px"),
          (kick, SOFT, f"flailing: {dk.pos.x - 600.0:+.0f} px"),
          (broad, COLD, f"broadside: {db.pos.x - 250.0:+.0f} px")],
         ["WHAT MOVEMENT COSTS -- 22 s, identical thrust",
          "Drag reads your speed THROUGH THE WATER, so drifting is free and crossing is not.",
          "A diver is a long thing: broadside you are a sail. And a kick is not travel."],
         font, small)

    pygame.quit()


if __name__ == "__main__":
    main()
