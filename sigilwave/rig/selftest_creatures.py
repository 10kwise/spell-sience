"""One rule, five behaviours. RIGS.md 9.

`creatures.py` contains no code for herding, luring, hunting, hiding or taking
cover. It contains a comfort function and a body that climbs its gradient.
This suite is the claim that the five behaviours in RIGS.md 9's table EMERGE
from that, measured on the real `Medium` rather than a mock.

HOW THESE TESTS HAD TO BE REBUILT, WHICH IS THE USEFUL PART
------------------------------------------------------------
The first version of this file failed 9 checks of 18, and every single failure
was the TEST being wrong rather than the creature. Three mistakes, all worth
recording because they are the mistakes anyone reasoning about a gradient
system makes:

1. **Creatures were placed in water they already liked.** A lantern wants
   2-8 degC and the deep column IS 4 degC, so comfort was 1.0 everywhere and
   the gradient was correctly zero. Nothing moved, and nothing SHOULD have. A
   preference system can only be observed where a preference is unmet.

2. **Features were point sources, read one cell at a time.** A creature probes
   one cell either side, so a single hot cell 240 px away is invisible to it --
   not because sensing is broken but because there genuinely is no gradient out
   there. Heat has to DIFFUSE before it is a signal, so these tests run the
   medium. That is true in play too: a wake is a thing that spreads.

3. **A sound source was placed exactly on the creature.** Perfectly symmetric,
   so both probes read the same and the gradient was exactly zero. The creature
   sat at a saddle point, which is correct and useless.

AND ONE FINDING THAT IS ABOUT THE GAME, NOT THE TESTS
-------------------------------------------------------
Chasing the failures turned up a range law nobody designed, and it is worth
more than the tests that produced it.

**A thermal feature is a SHORT-RANGE signal.** `field.py` diffuses heat at
60 px^2/s, so five seconds spreads a patch about 17 px and the usable gradient
around it dies by 140 px. Measured, on a cold pocket at x=470:

    220 px away   comfort 5.196e-04     no usable gradient
    140 px away   comfort 5.204e-04     0.2% -- still nothing
     90 px away   comfort 6.638e-04     the gradient begins
     40 px away   comfort 6.546e-02     strong
      0 px        comfort 9.509e-01

**Sound is the long-range sense**, because it falls off as 1/(1+(d/120)^2)
rather than by diffusion, and a shoalfish crosses 260 px to a groan.

So heat HERDS, locally and slowly, and sound CALLS, at range and at once. That
is a real division of labour between two of the player's verbs, it was not
designed, and it means the sonar a player builds for navigation is also the
only tool that reaches across a room. Every thermal test below is therefore
staged at about 100 px, which is the distance the physics actually supports.

The corrected tests place creatures in water they want to leave, let features
diffuse, and offset every source. Nothing in `creatures.py` changed.

Test [7] is the honest negative and the one most likely to catch a real bug: a
creature with nothing to climb toward must not drift. `field.py` shipped
exactly this class of bug once (SUBMERGED 8.4, "a stable column produces no
current") and floated a motionless diver 193 px through still water.

Run:  python -m sigilwave.rig.selftest_creatures
"""

import math

from ..medium.field import Medium
from . import creatures
from .modules import NOTES

_passed = 0
_failed = []


def check(name, condition, detail=""):
    global _passed
    if condition:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed.append((name, detail))
        print(f"  FAIL {name}   {detail}")


def _report(name, value, unit=""):
    print(f"       {name}: {value}{unit}")


def _fresh(w=640, h=760):
    return Medium(w, h, cell_size=16.0)


def _run(c, medium, seconds, sounds=(), dt=1.0 / 30.0):
    start = c.pos
    for _ in range(int(seconds / dt)):
        c.step(dt, medium, sounds)
    return start, c.pos


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _settle(medium, seconds=5.0, dt=1.0 / 30.0):
    """Let what was just injected spread out. A feature nothing can sense yet
    is not a feature."""
    for _ in range(int(seconds / dt)):
        medium.step(dt)


def _patch(medium, x, y, degrees, radius=2, times=6):
    """A broad thermal feature the size a real rig leaves.

    Calibrated against `couple.py` rather than guessed, and the first version
    was not: 40 passes of 1.2 degC built a 53.5 degC blob, which the stalker
    correctly FLED because it is outside any creature's tolerance. A heater
    measured through the coupling layer puts about 3.5 degC per second into a
    cell, so a few seconds of running is a wake of a handful of degrees, and
    that is what a creature is supposed to be reading.
    """
    for _ in range(times):
        for i in range(-radius, radius + 1):
            for k in range(-radius, radius + 1):
                medium.add_heat(x + i * medium.cell_size,
                                y + k * medium.cell_size, degrees)


def _curtain(medium, x, y):
    for _ in range(6):
        for k in range(-3, 4):
            for i in range(-2, 3):
                medium.add_bubbles(x + i * medium.cell_size,
                                   y + k * medium.cell_size, 0.25, 0.004)


# --- 1 ----------------------------------------------------------------------


def test_herding():
    """A warm layer a cold-lover will not cross.

    The lantern starts SHALLOW, where it is uncomfortable and wants to go
    down. That descent is the gradient the barrier has to beat.
    """
    print("\n[1] herding -- a warm layer is a wall")

    open_med = _fresh()
    a = creatures.lantern((320.0, 120.0))
    _, open_end = _run(a, open_med, 14.0)

    walled = _fresh()
    for _ in range(60):
        for i in range(-12, 13):
            walled.add_heat(320.0 + i * walled.cell_size, 240.0, 2.0)
    _settle(walled, 4.0)
    b = creatures.lantern((320.0, 120.0))
    _, wall_end = _run(b, walled, 14.0)

    check("it descends freely when nothing is in the way", open_end[1] > 300.0,
          f"reached y={open_end[1]:.0f}")
    check("and a warm layer holds it above", wall_end[1] < open_end[1] - 60.0,
          f"held at y={wall_end[1]:.0f} vs {open_end[1]:.0f}")
    _report("open water", f"y 120 -> {open_end[1]:.0f}")
    _report("warm layer at y=240", f"y 120 -> {wall_end[1]:.0f}")


def test_luring():
    """A cold pocket in warm water pulls a cold-lover sideways.

    Sideways matters: depth alone would explain a vertical move, so the test
    is built on the one axis only temperature can drive.
    """
    print("\n[2] luring -- a cold pocket is bait")
    bait = (470.0, 500.0)

    # Warm the whole depth band first, so the lantern is uncomfortable in
    # TEMPERATURE while remaining perfectly comfortable in DEPTH. That leaves
    # exactly one axis for it to climb, which is the only way to attribute a
    # sideways move to the bait rather than to the depth profile. The first
    # version put the bait in shallow water and measured a creature that was
    # simply diving.
    def _stage():
        # The WHOLE column is set outside the lantern's band, not a seven-cell
        # layer of it. With a layer, the creature simply dived out from under
        # the warm water -- a better solution than swimming 220 px, and the
        # right thing for it to do. Making the water uniformly wrong leaves
        # the cold pocket as the only maximum anywhere.
        m = _fresh()
        m.set_temperature_profile(lambda f: 13.5)
        return m

    med = _stage()
    _patch(med, bait[0], bait[1], -1.1, radius=2, times=10)
    _settle(med)
    c = creatures.lantern((370.0, 500.0))
    start, end = _run(c, med, 16.0)

    plain = _stage()
    _settle(plain)
    d = creatures.lantern((370.0, 500.0))
    _, plain_end = _run(d, plain, 16.0)

    moved_x = end[0] - start[0]
    plain_x = plain_end[0] - start[0]
    check("it moves toward the cold pocket", moved_x > 25.0,
          f"moved {moved_x:+.0f} px in x")
    check("and does not, when there is no pocket",
          abs(plain_x) < abs(moved_x) * 0.5,
          f"baited {moved_x:+.0f} px, plain {plain_x:+.0f} px")
    _report("baited", f"x {start[0]:.0f} -> {end[0]:.0f}")
    _report("no bait", f"x {start[0]:.0f} -> {plain_end[0]:.0f}")


def test_hunting():
    """Lure it, then tear the water where it now is."""
    print("\n[3] hunting -- lure it, then tear the water there")
    trap = (470.0, 500.0)
    med = _fresh()
    med.set_temperature_profile(lambda f: 13.5)
    _patch(med, trap[0], trap[1], -1.1, radius=2, times=10)
    _settle(med)
    c = creatures.lantern((370.0, 500.0))
    _run(c, med, 22.0)
    d = _dist(c.pos, trap)
    check("it is inside the trap radius when the charge goes off", d < 60.0,
          f"{d:.0f} px from the trap")
    _report("distance at the moment of the tear", f"{d:.0f} px")


def test_hiding():
    """A heat-hunter tracks a warm anomaly, and loses it when it matches ambient.

    This is the claim that your rig's efficiency is also your camouflage: the
    stalker is not following YOU, it is following a temperature difference, so
    removing the difference removes you.
    """
    print("\n[4] hiding -- match ambient and the heat-hunter loses you")
    mark = (440.0, 400.0)

    hot = _fresh()
    _patch(hot, mark[0], mark[1], 0.4, radius=2, times=6)
    _settle(hot, 5.0)
    a = creatures.stalker((340.0, 400.0))
    start, hot_end = _run(a, hot, 16.0)

    cold = _fresh()
    _settle(cold, 5.0)
    b = creatures.stalker((340.0, 400.0))
    _, cold_end = _run(b, cold, 16.0)

    closed = _dist(start, mark) - _dist(hot_end, mark)
    check("it closes on a warm anomaly", closed > 30.0, f"closed {closed:.0f} px")
    check("and does not, when there is no anomaly to follow",
          _dist(cold_end, mark) > _dist(hot_end, mark) + 25.0,
          f"warm {_dist(hot_end, mark):.0f} px, "
          f"matched {_dist(cold_end, mark):.0f} px")
    _report("hunting a wake",
            f"{_dist(start, mark):.0f} -> {_dist(hot_end, mark):.0f} px")
    _report("wake matched to ambient",
            f"{_dist(start, mark):.0f} -> {_dist(cold_end, mark):.0f} px")


def test_cover_is_conditional():
    """A bubble curtain changes what one creature does and not another.

    WHAT THE MEASUREMENT CHANGED, AND IT IS A FACT ABOUT THE GAME
    -------------------------------------------------------------
    A bubble curtain is a STEP, not a gradient. `field.py` exchanges bubbles
    vertically through buoyancy and never horizontally, so a curtain reads
    0.0000 one cell outside it and 1.0000 one cell inside:

        100 px away   bubbles 0.0000    comfort  1.00
         50 px away   bubbles 0.0000    comfort  1.00
         35 px away   bubbles 1.0000    comfort 54.60

    So nothing can smell a curtain from across a room. It is a wall you are
    either inside or outside of, and that is exactly what a wall of bubbles
    should be. The first version of this test asked a creature 100 px away to
    be drawn to one, which is asking it to sense something that is genuinely
    not there.

    That makes the honest claim the better one anyway: a curtain does not
    ATTRACT, it HOLDS what likes bubbles and STOPS what does not -- which is
    the same shape as the warm wall in [1], from a different field.

    And it turned out not to be thermally silent either. See the comment
    beside the heat-hunter check: bubbles drive convection, convection stirs
    temperature, and cover from one sense advertises you to another.
    """
    print("\n[5] cover -- a curtain holds one thing and stops another")
    curtain_x = 430.0

    def _feed(medium, y=300.0):
        for _ in range(6):
            for k in range(-4, 5):
                for i in range(-2, 3):
                    medium.add_bubbles(curtain_x + i * medium.cell_size,
                                       y + k * medium.cell_size, 0.25, 0.004)

    def _hold(medium, c, seconds, feed=True, dt=1.0 / 30.0):
        for _ in range(int(seconds / dt)):
            if feed:
                _feed(medium)
            c.step(dt, medium)
            medium.step(dt)
        return c.pos

    # A bubble-seeker at the edge walks INTO the curtain.
    med = _fresh()
    seeker = creatures.siftling((390.0, 300.0))
    seeker_end = _hold(med, seeker, 12.0)

    plain = _fresh()
    control = creatures.siftling((390.0, 300.0))
    control_end = _hold(plain, control, 12.0, feed=False)

    check("a bubble-seeker at the edge walks into the curtain",
          seeker_end[0] > 410.0,
          f"ended at x={seeker_end[0]:.0f}")
    check("and does not, when there is no curtain",
          abs(control_end[0] - 390.0) < 12.0,
          f"drifted to x={control_end[0]:.0f}")

    # A temperature-hunter ALSO comes -- and that is not a bug, it is the best
    # thing this suite found.
    #
    # Bubbles lighten water (field.py's BUBBLE_LIGHTENING), lighter water
    # rises, and warm water follows it up. Measured across the curtain's own
    # row after ten seconds:
    #
    #     60 px out   +0.02 degC        curtain centre   +0.16 degC
    #
    # So a curtain is NOT thermally silent. Cover from one sense advertises
    # you to another, through a coupling nobody wrote: `field.py` was already
    # doing this and the creature was already reading it. That is RIGS.md 6.1
    # arriving unprompted, and it means bubble cover has a real cost.
    bub = _fresh()
    s1 = creatures.stalker((390.0, 300.0))
    s1_end = _hold(bub, s1, 10.0)
    plain2 = _fresh()
    s2 = creatures.stalker((390.0, 300.0))
    s2_end = _hold(plain2, s2, 10.0, feed=False)
    check("a heat-hunter finds the curtain too, by the convection it drives",
          s1_end[0] > s2_end[0] + 15.0,
          f"curtain x={s1_end[0]:.0f}, none x={s2_end[0]:.0f}")

    # The real asymmetry RIGS.md 9 claims is about SENSING, so the honest
    # control is a creature that reads temperature as a band rather than as an
    # anomaly. A 0.16 degC stir is nothing inside a 6 degC preference.
    lb = _fresh()
    l1 = creatures.lantern((390.0, 520.0))
    l1_end = _hold(lb, l1, 10.0)
    lp = _fresh()
    l2 = creatures.lantern((390.0, 520.0))
    l2_end = _hold(lp, l2, 10.0, feed=False)
    check("and a band-reader genuinely cannot tell it is there",
          abs(l1_end[0] - l2_end[0]) < 8.0,
          f"moved {abs(l1_end[0] - l2_end[0]):.1f} px differently in x")

    _report("bubble-seeker", f"x 390 -> {seeker_end[0]:.0f} with a curtain, "
                             f"{control_end[0]:.0f} without")
    _report("heat-hunter (via convection)",
            f"x 390 -> {s1_end[0]:.0f} with a curtain, {s2_end[0]:.0f} without")
    _report("band-reader",
            f"{abs(l1_end[0] - l2_end[0]):.1f} px difference in x")


def test_sound_moves_the_right_creatures():
    """Sound is the LONG-range sense, which is why it is the one the player
    builds. Every source here is offset from its listener, because a source
    sitting exactly on one is a symmetric saddle and moves nothing."""
    print("\n[6] a note only reaches what can hear it")
    med = _fresh()
    src = (520.0, 120.0)
    call = [(src[0], src[1], NOTES["groan"], 2.5)]

    a = creatures.shoalfish((260.0, 120.0))
    start, called = _run(a, med, 12.0, sounds=call)
    b = creatures.shoalfish((260.0, 120.0))
    _, quiet = _run(b, med, 12.0)
    check("a shoalfish comes to the note it likes",
          _dist(called, src) < _dist(quiet, src) - 40.0,
          f"called {_dist(called, src):.0f} px, quiet {_dist(quiet, src):.0f} px")

    c = creatures.siftling((260.0, 400.0))
    _, deaf_called = _run(c, med, 10.0,
                          sounds=[(520.0, 400.0, NOTES["groan"], 2.5)])
    d = creatures.siftling((260.0, 400.0))
    _, deaf_quiet = _run(d, med, 10.0)
    check("and a deaf one is not moved by it",
          _dist(deaf_called, deaf_quiet) < 5.0,
          f"moved {_dist(deaf_called, deaf_quiet):.1f} px differently")

    e = creatures.lantern((360.0, 560.0))
    scare = [(300.0, 560.0, NOTES["chirp"], 3.0)]
    _, fled = _run(e, med, 10.0, sounds=scare)
    f = creatures.lantern((360.0, 560.0))
    _, stayed = _run(f, med, 10.0)
    check("and a fearful one flees the note it fears",
          fled[0] > stayed[0] + 30.0,
          f"fled to x={fled[0]:.0f}, stayed at x={stayed[0]:.0f}")
    _report("shoalfish to a groan",
            f"{_dist(start, src):.0f} -> {_dist(called, src):.0f} px "
            f"(quiet: {_dist(quiet, src):.0f})")
    _report("lantern fleeing a chirp",
            f"x 360 -> {fled[0]:.0f} (quiet: {stayed[0]:.0f})")


def test_uniform_water_produces_no_drift():
    """The honest negative.

    Each creature is placed where it is ALREADY comfortable, because that is
    what "nothing to climb toward" means. Putting a shoalfish at 380 m and
    calling the water uniform was the first version's mistake: depth is a
    gradient whether or not temperature is.
    """
    print("\n[7] a creature with nothing to climb toward does not drift")
    med = _fresh()
    med.set_temperature_profile(lambda f: 10.0)

    homes = {"lantern": (320.0, 500.0), "shoalfish": (320.0, 110.0),
             "stalker": (320.0, 380.0), "siftling": (320.0, 380.0)}
    worst = 0.0
    worst_kind = ""
    for kind, home in homes.items():
        c = creatures.make(kind, home)
        start, end = _run(c, med, 20.0)
        if _dist(start, end) > worst:
            worst, worst_kind = _dist(start, end), kind
    check("no species drifts when its comfort is already flat", worst < 2.0,
          f"worst drift {worst:.2f} px by the {worst_kind}")
    _report("worst drift", f"{worst:.3f} px in 20 s ({worst_kind})")


def test_nothing_tunnels_through_rock():
    print("\n[8] nothing swims through rock")
    med = _fresh()
    med.carve(360.0, 300.0, 120.0, 200.0)
    _patch(med, 560.0, 400.0, -0.9)
    _settle(med)
    bad = []
    for kind in creatures.ORDER:
        c = creatures.make(kind, (240.0, 400.0))
        _run(c, med, 16.0)
        if med.is_solid(c.pos[0], c.pos[1]):
            bad.append((kind, c.pos))
    check("no species ends up inside rock", not bad, str(bad))


def test_every_species_is_two_sentences():
    """RIGS.md 9: a creature is a set of preferences, and it must be sayable."""
    print("\n[9] every species says what it wants and what that makes it do")
    for kind in creatures.ORDER:
        c = creatures.make(kind)
        check(f"{kind} is describable", bool(c.wants) and bool(c.does),
              creatures.describe(c))
        _report(kind, creatures.describe(c))


def main():
    print("=" * 72)
    print("RIGS -- one rule, five behaviours")
    print("=" * 72)
    test_herding()
    test_luring()
    test_hunting()
    test_hiding()
    test_cover_is_conditional()
    test_sound_moves_the_right_creatures()
    test_uniform_water_produces_no_drift()
    test_nothing_tunnels_through_rock()
    test_every_species_is_two_sentences()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
