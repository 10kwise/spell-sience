"""Proof that the water is drawing the medium, and that the ping is the only
way to see past your own arm.

A shader is easy to test wrongly. Checking that it produces pixels proves
nothing -- the old renderer produced pixels. What has to hold is that the
picture is a FUNCTION OF THE FIELD, and that the seeing mechanic is real: that
distant land is genuinely invisible until a ping finds it, that a ping is
stopped and turned by rock rather than passing through it, and that the tone
stays dark and desaturated instead of drifting back toward a sunlit lagoon.
Each check measures the consequence and prints the number, because a number
that moves when a constant is tuned is the only honest way to know whether the
tuning helped.

    python -m sigilwave.water.selftest_water

Like `medium/selftest_field.py` this runner does not stop at the first
failure: these are independent claims about one picture, and knowing that the
bands still track depth while the ping has stopped reflecting is information
the first failure would hide.
"""

import math
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame

from ..stage import world
from .palette import WATER
from .ping import Ping, step_all
from .shader import WAKE_SCALE, WaterShader

FAILURES = []
DT = 1.0 / 60.0


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        FAILURES.append(name)


def note(text):
    print(f"       {text}")


def _run(medium=None, diver=None, frames=8, ping_at=None):
    """Render a room and hand back the shader, the pixels and the pings.

    `ping_at` is a position rather than a Ping, because a Ping needs the
    shader that it stamps into and the shader does not exist until here."""
    medium = medium if medium is not None else world.build()
    size = (world.WIDTH, world.HEIGHT)
    screen = pygame.Surface(size)
    shader = WaterShader(size, medium)
    pings = [Ping(shader, ping_at[0], ping_at[1])] if ping_at else []
    for _ in range(frames):
        pings = step_all(pings, DT)
        shader.draw(screen, diver, DT)
    return shader, pygame.surfarray.array3d(screen).astype(float), pings


def _luma(rgb):
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


# ----------------------------------------------------------------------
def test_deep_is_darker_than_shallow():
    """The mood invariant, and the progression axis.

    Sampled at two points EQUIDISTANT from the diver, one above and one below.
    Distance is what the fog is a function of, so comparing a near band with a
    far one measures the fog and not the ramp -- and measuring it in an empty
    room measures neither, because at 0.08 of full brightness the whole ramp
    is thinner than the film grain sitting on top of it."""
    diver = (600.0, 400.0)
    _, px, _ = _run(diver=diver, frames=12)
    lum = _luma(px)
    above = float(lum[400:800, 235:265].mean())
    below = float(lum[400:800, 535:565].mean())
    note(f"150 px above the diver {above:.2f}, "
         f"the same distance below {below:.2f}")
    check("deep water reads darker than shallow", below < above * 0.85)


def test_the_ramp_is_monotonic():
    """Every band darker than the one above it. A single inversion would put a
    bright stripe in the abyss and read as a light source that is not there."""
    lum = [c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114 for c in WATER]
    falls = all(b < a for a, b in zip(lum, lum[1:]))
    note(f"{len(WATER)} bands, luma {lum[0]:.0f} down to {lum[-1]:.0f}")
    check("the palette ramp is monotonic", falls)


def test_the_tone_is_dark_and_desaturated():
    """The brief, as two numbers. LIMBO and Little Nightmares are near-grey and
    mostly black; a picture that drifts back toward saturated teal has stopped
    being the thing that was asked for, and it will drift the moment somebody
    brightens a constant to see something more clearly."""
    _, px, _ = _run(diver=(430.0, 470.0), frames=12)
    lum = _luma(px)
    chroma = px.max(axis=2) - px.min(axis=2)
    note(f"mean luma {lum.mean():.1f}/255, mean chroma {chroma.mean():.1f}")
    check("the picture is dark", lum.mean() < 34.0)
    check("the picture is near-monochrome", chroma.mean() < 12.0)


def test_far_land_is_invisible_until_it_is_pinged():
    """The whole mechanic, in one measurement.

    A patch of rock far from the diver has to be indistinguishable from the
    water beside it before a ping, and clearly brighter after one. If the
    'before' contrast is already high then the fog is too thin and the map can
    be read without spending anything -- which is exactly what the first pass
    at this got wrong.

    Measured across an EDGE -- the top face of a distant pillar against the
    open water just above it -- rather than over the pillar's area. A ping
    lights the rim and top of rock, not its interior, so averaging over the
    whole shape dilutes a three-pixel edge into eleven thousand pixels of
    unlit rock and reports nothing. An edge is also what "can you see it"
    actually means, and averaging along it kills the film grain that makes any
    single-pixel threshold meaningless in an unlit corner."""
    diver = (300.0, 430.0)
    medium = world.build()
    # Where the far pillar's top actually is, read from the medium rather than
    # written down here. The lit top face is only a few pixels tall, so a
    # hardcoded band either misses it or dilutes it into a hundred pixels of
    # unlit rock -- and a band wide enough to be safe reports a sixth of the
    # real signal.
    x0, x1 = 990, 1120
    cs = medium.cell_size
    tops = []
    for x in range(x0, x1, 4):
        rows = np.flatnonzero(medium.solid[:, int(x / cs)])
        if rows.size:
            tops.append(rows[0] * cs)
    y_edge = int(np.median(tops))
    note(f"far pillar's top edge found at y={y_edge}")

    def lift(px):
        lum = _luma(px)
        face = lum[x0:x1, y_edge:y_edge + 6].mean()
        # Open water directly above the same rock, so range, depth and
        # vignette all cancel and only the edge is left.
        water = lum[x0:x1, y_edge - 40:y_edge - 12].mean()
        return float(face - water)

    _, before, _ = _run(medium, diver=diver, frames=12)
    _, after, _ = _run(world.build(), diver=diver, frames=260, ping_at=diver)
    b, a = lift(before), lift(after)
    note(f"far rock edge sits {b:+.2f} above the water above it unpinged, "
         f"{a:+.2f} after a ping")
    check("far land is nearly invisible before a ping", abs(b) < 4.0)
    check("a ping makes far land visible", a > 15.0)


def test_a_ping_reveals_and_the_room_forgets():
    """The map is written by pings and it fades. A reveal that never decayed
    would turn the room permanently legible and destroy the darkness the whole
    design rests on."""
    diver = (430.0, 470.0)
    shader, _, _ = _run(diver=diver, frames=200, ping_at=diver)
    painted = float((shader.reveal > 0.05).mean())
    peak = float(shader.reveal.max())
    note(f"{painted * 100:.1f}% of cells painted, peak {peak:.2f}")
    check("a ping paints a usable amount of the room", painted > 0.05)

    screen = pygame.Surface((world.WIDTH, world.HEIGHT))
    for _ in range(60 * 60):
        shader.draw(screen, diver, DT)
    note(f"after a minute, peak reveal {float(shader.reveal.max()):.3f}")
    check("the room forgets", float(shader.reveal.max()) < peak * 0.3)


def test_a_ping_reflects_off_walls():
    """The complaint that started this. `medium/front.py` reflects correctly --
    fired at a wall it sends 41 of 192 vertices back the way they came -- but
    the stand-in in this package used to be a bare expanding circle that had
    never heard of rock, so in the demo nothing bounced."""
    _, _, pings = _run(diver=(430.0, 470.0), frames=150, ping_at=(430.0, 470.0))
    check("the ping is still alive to be measured", bool(pings))
    if not pings:
        return
    p = pings[0]
    live = p.alive
    # A ray that has turned around is one now heading back toward where it
    # was born.
    rx, ry = p.px - 430.0, p.py - 470.0
    r = np.hypot(rx, ry)
    inward = (live & (r > 40.0)
              & ((p.dx * rx + p.dy * ry) / np.maximum(r, 1e-6) < -0.3))
    note(f"{int(inward.sum())} of {int(live.sum())} live rays heading back, "
         f"{int(p.bounces.sum())} bounces total")
    check("rays come back off walls", int(inward.sum()) > 0)
    check("bounces are recorded", int(p.bounces.sum()) > 0)


def test_a_ping_does_not_pass_through_rock():
    """Occlusion is the other half of reflection, and the reason a ping is a
    way of seeing rather than a light that ignores the room."""
    medium = world.build()
    _, _, pings = _run(medium, diver=(430.0, 470.0), frames=120,
                       ping_at=(430.0, 470.0))
    if not pings:
        check("a ping never ends a step inside rock", True)
        return
    p = pings[0]
    live = p.alive
    inside = int(medium.is_solid_at(p.px[live], p.py[live]).sum())
    note(f"{inside} of {int(live.sum())} live rays are inside rock")
    check("a ping never ends a step inside rock", inside == 0)


def test_rock_is_where_the_medium_says():
    """The silhouette is derived, not drawn. Sampled near the diver, where the
    fog is thick enough for a silhouette to have something to sit against."""
    medium = world.build()
    diver = (330.0, 520.0)
    _, px, _ = _run(medium, diver=diver, frames=12)
    lum = _luma(px)
    cs = medium.cell_size
    solid_lum, water_lum = [], []
    for r in range(medium.ny):
        for c in range(medium.nx):
            x, y = int((c + 0.5) * cs), int((r + 0.5) * cs)
            if math.hypot(x - diver[0], y - diver[1]) > 200.0:
                continue
            (solid_lum if medium.solid[r, c] else water_lum).append(lum[x, y])
    s, w = float(np.mean(solid_lum)), float(np.mean(water_lum))
    note(f"nearby rock luma {s:.1f} against water luma {w:.1f}")
    check("rock reads as a silhouette against lit water", s < w * 0.5)


def test_a_vent_bends_the_bands():
    """The load-bearing claim of the design: the cel bands ARE the physics.
    Heat put into the water has to change the picture above it, or the bands
    are decoration that happens to sit near a thermocline."""
    diver = (600.0, 600.0)
    _, before, _ = _run(diver=diver, frames=12)
    hot = world.build()
    for _ in range(300):
        for j in range(-2, 3):
            for i in range(-2, 3):
                hot.add_heat(520.0 + i * hot.cell_size,
                             660.0 + j * hot.cell_size, 12.0 * DT)
        hot.step(DT)
    _, after, _ = _run(hot, diver=diver, frames=12)
    d = np.abs(_luma(after) - _luma(before))
    at, away = d[440:600, 480:720].mean(), d[100:260, 300:540].mean()
    note(f"mean change over the vent {at:.2f}, far from it {away:.2f}")
    check("a vent changes the water above it", at > 2.0)
    check("and does not change water far from it", away < at)


def test_a_curtain_shows_where_the_bubbles_are():
    """Wood's collapse drops c through the floor, so a curtain lifts several
    bands at once and reads milky -- brighter than the water it displaced."""
    diver = (620.0, 540.0)
    _, before, _ = _run(diver=diver, frames=12)
    gas = world.build()
    for _ in range(180):
        for j in range(-2, 3):
            for i in range(-2, 3):
                gas.add_bubbles(700.0 + i * gas.cell_size,
                                560.0 + j * gas.cell_size, 0.30 * DT, 1.4)
        gas.step(DT)
    _, after, _ = _run(gas, diver=diver, frames=12)
    lift = (_luma(after)[660:740, 420:600].mean()
            - _luma(before)[660:740, 420:600].mean())
    note(f"luma lift inside the curtain {lift:+.2f}")
    check("a bubble curtain reads brighter than clear water", lift > 1.5)


def test_the_wake_is_a_front_and_then_forgets():
    """Sound lifts the water it is in, and the water lets go."""
    shader, _, _ = _run(diver=(600.0, 400.0), frames=40, ping_at=(600.0, 400.0))
    peak = float(shader.wake.max())
    lit = int((shader.wake > 0.05).sum())
    note(f"wake peak {peak:.3f} over {lit} cells of {shader.wake.size}")
    check("a front is present in the wake", peak > 0.05)
    # An arc, not a disc: the front has swept a large area by now and only a
    # thin band of it should still be lit.
    check("the wake reads as an arc, not a filled disc",
          lit < shader.wake.size * 0.20)

    screen = pygame.Surface((world.WIDTH, world.HEIGHT))
    for _ in range(120):
        shader.draw(screen, None, DT)
    note(f"after two seconds with no source, peak {float(shader.wake.max()):.5f}")
    check("the wake decays away", float(shader.wake.max()) < 0.01)


def test_the_wake_grid_is_finer_than_the_medium():
    """Deliberate, and worth pinning: the wake is art, and at the medium's
    16 px cell a front comes out visibly stair-stepped."""
    medium = world.build()
    shader, _, _ = _run(medium, frames=1)
    note(f"medium {medium.nx}x{medium.ny}, "
         f"wake {shader.wake.shape[1]}x{shader.wake.shape[0]}")
    check("the wake grid is finer than the medium grid",
          shader.wake.shape == (medium.ny * WAKE_SCALE, medium.nx * WAKE_SCALE))


def test_the_shader_never_writes_to_the_medium():
    """The whole reason this package exists as a separate thing. If a shader
    can perturb the field, an art change becomes a physics change and the two
    sessions working on this repo start overwriting each other's results."""
    medium = world.build()
    before = (medium.temp.copy(), medium.bubbles.copy(),
              medium.solid.copy(), medium.gas.copy())
    _run(medium, diver=(430.0, 470.0), frames=40, ping_at=(430.0, 470.0))
    same = (np.array_equal(medium.temp, before[0])
            and np.array_equal(medium.bubbles, before[1])
            and np.array_equal(medium.solid, before[2])
            and np.array_equal(medium.gas, before[3]))
    check("drawing and pinging leave the medium untouched", same)


def test_frame_cost():
    """A budget, not a benchmark. The water is the thing you look at while
    doing something else, so it has to leave most of the frame for the
    something else. Measured both idle and with a ping in flight, because the
    ping is the expensive case and it is also the common one."""
    medium = world.build()
    size = (world.WIDTH, world.HEIGHT)
    screen = pygame.Surface(size)
    shader = WaterShader(size, medium)
    diver = (430.0, 470.0)
    for _ in range(12):
        shader.draw(screen, diver, DT)
    t0 = time.perf_counter()
    for _ in range(120):
        shader.draw(screen, diver, DT)
    idle = (time.perf_counter() - t0) / 120 * 1000.0

    pings = [Ping(shader, *diver)]
    for _ in range(15):
        pings = step_all(pings, DT)
        shader.draw(screen, diver, DT)
    t0 = time.perf_counter()
    for _ in range(120):
        if not pings:
            pings = [Ping(shader, *diver)]
        pings = step_all(pings, DT)
        shader.draw(screen, diver, DT)
    lit = (time.perf_counter() - t0) / 120 * 1000.0
    note(f"idle {idle:.2f} ms ({1000.0 / idle:.0f} fps), "
         f"with a ping {lit:.2f} ms ({1000.0 / lit:.0f} fps)")
    check("an idle frame costs under 9 ms", idle < 9.0)
    check("a frame with a ping in it costs under 17 ms", lit < 17.0)


def main():
    pygame.init()
    pygame.display.set_mode((world.WIDTH, world.HEIGHT))
    tests = [
        test_deep_is_darker_than_shallow,
        test_the_ramp_is_monotonic,
        test_the_tone_is_dark_and_desaturated,
        test_far_land_is_invisible_until_it_is_pinged,
        test_a_ping_reveals_and_the_room_forgets,
        test_a_ping_reflects_off_walls,
        test_a_ping_does_not_pass_through_rock,
        test_rock_is_where_the_medium_says,
        test_a_vent_bends_the_bands,
        test_a_curtain_shows_where_the_bubbles_are,
        test_the_wake_is_a_front_and_then_forgets,
        test_the_wake_grid_is_finer_than_the_medium,
        test_the_shader_never_writes_to_the_medium,
        test_frame_cost,
    ]
    for test in tests:
        test()
    pygame.quit()
    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed:")
        for name in FAILURES:
            print(f"  - {name}")
        raise SystemExit(1)
    print("\nall checks passed.")


if __name__ == "__main__":
    main()
