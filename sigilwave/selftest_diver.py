"""Does the water feel like water? SUBMERGED.md 8.

    python -m sigilwave.selftest_diver
"""

import math

import pygame

from .diver import KICK, Diver
from .medium.field import Medium
from .medium.front import Front

_p = _f = 0


def check(ok, label):
    global _p, _f
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    globals().__setitem__("_p" if ok else "_f", (_p if ok else _f) + 1)


def note(t):
    print(f"       {t}")


def _still():
    m = Medium(1200, 800, 16.0)
    m.set_temperature_profile(lambda d: 10.0)
    return m


def main():
    global _p, _f
    print("--- drag: water is not air ---")
    m = _still()
    d = Diver((600, 400))
    d.vel = pygame.Vector2(240.0, 0.0)
    speeds = []
    for i in range(240):
        d.step(1 / 60.0, m)
        if i % 40 == 0:
            speeds.append(d.speed)
    note("coasting from 240 px/s: " + ", ".join(f"{s:.0f}" for s in speeds))
    check(speeds[-1] < speeds[0] * 0.25, "released, you coast to a near stop")
    check(all(b <= a + 1e-6 for a, b in zip(speeds, speeds[1:])),
          "and slow monotonically - no bounce, no sudden halt")

    d2 = Diver((600, 400))
    for _ in range(600):
        d2.step(1 / 60.0, m, thrust=pygame.Vector2(900.0, 0.0))
    note(f"under constant 900 thrust, terminal speed {d2.speed:.0f} px/s")
    check(20.0 < d2.speed < 260.0, "constant thrust reaches a terminal speed")

    print("")
    print("--- buoyancy: light water lifts, heavy water drops ---")
    # The anomaly is written straight into the field and the medium is NOT
    # stepped. An earlier version made it with add_heat and then let the
    # medium settle, which meant the cold blob sank away from the diver
    # before the measurement and left LIGHTER water where they stood - so
    # cold water appeared to lift them. That is real convection, and it is
    # a different claim from this one; mixing the two tested neither.
    for label, delta, expect in (("light", +6.0, "up"), ("heavy", -6.0, "down")):
        mm = _still()
        r = int(400 / mm.cell_size)
        c = int(600 / mm.cell_size)
        mm.temp[r - 2:r + 3, c - 2:c + 3] += delta
        dd = Diver((600, 400))
        for _ in range(240):
            dd.step(1 / 60.0, mm)
        moved = dd.pos.y - 400.0
        note(f"{label} water ({delta:+.0f} C): the diver moved {moved:+.1f} px"
             f" ({'up' if moved < 0 else 'down'})")
        check((moved < -1.0) if expect == "up" else (moved > 1.0),
              f"{label} water carries a diver {expect}")

    print("")
    print("--- thrust: a mouth pushes back ---")
    m3 = _still()
    d3 = Diver((600, 400))
    east = Front((600, 400), (1.0, 0.0), 90.0, 0.0, 0.4, 900.0, n_vertices=32)
    push = d3.impulse_from([east])
    note(f"a front thrown east gives thrust {push.x:+.1f}, {push.y:+.1f}")
    check(push.x < 0.0, "a mouth firing east pushes the diver west")
    d3.push([east])
    for _ in range(60):
        d3.step(1 / 60.0, m3)
    note(f"after a second the diver is at x={d3.pos.x:.1f} (started 600)")
    check(d3.pos.x < 599.0, "and it actually moves them")

    big = Front((600, 400), (1.0, 0.0), 90.0, 0.0, 1.6, 900.0, n_vertices=32)
    small = Front((600, 400), (1.0, 0.0), 90.0, 0.0, 0.1, 900.0, n_vertices=32)
    pb = Diver((0, 0)).impulse_from([big]).length()
    ps = Diver((0, 0)).impulse_from([small]).length()
    note(f"a strong front pushes {pb:.0f}, a weak one {ps:.0f} ({pb/max(ps,1e-9):.0f}x)")
    check(pb > ps * 4.0, "a better machine pushes harder - thrust is earned")

    print("")
    print("--- the kick is a last resort, not a mode of travel ---")
    m4 = _still()
    dk = Diver((600, 400))
    for _ in range(120):
        dk.step(1 / 60.0, m4, kick=pygame.Vector2(KICK, 0.0))
    dm = Diver((600, 400))
    for i in range(120):
        if i % 12 == 0:
            dm.push([big])
        dm.step(1 / 60.0, m4)
    note(f"two seconds of kicking: {dk.pos.x - 600:+.0f} px;"
         f" two seconds of a machine: {dm.pos.x - 600:+.0f} px")
    check(abs(dm.pos.x - 600) > abs(dk.pos.x - 600),
          "a drawn machine outruns flailing - which is the whole point of 8")

    print("")
    print("--- rock is solid ---")
    m5 = _still()
    m5.carve(700, 380, 120, 120)
    d5 = Diver((690, 420))
    d5.vel = pygame.Vector2(200.0, 0.0)
    for _ in range(90):
        d5.step(1 / 60.0, m5)
    inside = m5.is_solid(d5.pos.x, d5.pos.y)
    note(f"driven into a wall, ended at ({d5.pos.x:.0f}, {d5.pos.y:.0f}),"
         f" inside rock: {inside}")
    check(not inside, "a diver cannot end up inside rock")

    print("")
    print(f"{_p} passed, {_f} failed.")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
