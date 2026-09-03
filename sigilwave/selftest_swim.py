"""Movement, and whether it feels like water. RIGS.md 10.1.

The old diver flew. It had drag and it had a buoyancy term, and everything
else about it was an object in a vacuum with the numbers turned down: drag was
measured against the GROUND, so the ocean might as well have been still; there
was no velocity field to measure against anyway; and force arrived instantly,
which is the one thing that never happens underwater.

Four things separate swimming from flying, and this suite is one section per
thing:

    the water moves, and moving water moves you
    what costs you is speed THROUGH the water, not speed over the ground
    force arrives late, because you drag water with you
    a long body pointed the wrong way is a sail

Run:  python -m sigilwave.selftest_swim
"""

import math

import pygame

from .diver import (
    ADDED_MASS, DRAG_ACROSS, DRAG_ALONG, Diver, KICK, TRIM_RATE, V,
)
from .medium.field import Medium
from .rig import couple
from .rig.chain import Chain, ambient_at
from .sources import Economy, Vent

DT = 1.0 / 60.0

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


def swim(medium, seconds, pos=(600.0, 400.0), thrust=V(0.0, 0.0),
         kick=V(0.0, 0.0), aim=(1.0, 0.0), trim=0.0, economy=None):
    d = Diver(pos)
    d.aim = V(aim)
    d.trim = trim
    d.trim_target = trim
    for _ in range(int(seconds / DT)):
        d.step(DT, medium, thrust=thrust, kick=kick, economy=economy)
    return d


def thruster_acc(depth=400.0):
    """The acceleration a basic rig gives, which is the scale everything else
    in this file is measured against."""
    r = Chain(("INTAKE", "PUMP", "PUMP", "NARROW", "PORT")).evaluate(
        ambient_at(depth))
    return Diver((0, 0)).rig_thrust(r, (1.0, 0.0)), couple.thrust_from(r)


# --- 1. the water moves ------------------------------------------------------


def test_still_water_is_actually_still():
    """The check every one of these rests on, and the one that has now caught
    the same class of bug twice -- once in `_current` and once in
    `_buoyancy`. A stratified column is heavy-under-light everywhere by
    design. It is not an anomaly anywhere and it must move nobody."""
    med = Medium(1200, 800)
    worst = 0.0
    for y in (100.0, 250.0, 396.0, 400.0, 404.0, 600.0, 750.0):
        d = swim(med, 8.0, pos=(600.0, y))
        worst = max(worst, abs(d.pos.y - y))
    check("a diver left alone in an undisturbed column does not sink or rise",
          worst < 0.5, f"worst drift {worst:.4f} px in 8 s")
    _report("worst vertical drift over 8 s", f"{worst:.6f}", " px")

    med2 = Medium(1200, 800)
    worst_anom = 0.0
    for y in range(20, 780, 7):
        worst_anom = max(worst_anom, abs(med2.density_anomaly_at(600.0, y)))
    check("and the density anomaly is zero everywhere, not just at cell centres",
          worst_anom < 1e-9, f"worst {worst_anom:.3e} kg/m^3")


def test_a_current_carries_you():
    """Doing nothing in moving water is not doing nothing."""
    med = Medium(1200, 800)
    rows = []
    for depth, label in ((40.0, "shallow"), (300.0, "mid"), (700.0, "deep")):
        u, _ = med.flow_at(600.0, depth)
        d = swim(med, 8.0, pos=(600.0, depth))
        rows.append((label, depth, u, d.pos.x - 600.0))
    check("in a current, standing still moves you",
          abs(rows[0][3]) > 20.0, f"{rows[0][3]:.1f} px in 8 s at 40 m")
    # Compared against the FINAL velocity rather than the average, because
    # added mass means matching the water takes seconds and an average over
    # the spin-up is guaranteed to come in low. The first version of this
    # compared displacement/time to the flow and read 3.17 against 5.67,
    # which was measuring the acceleration, not the current.
    settled = []
    for label, depth, u, _ in rows:
        d = swim(med, 25.0, pos=(600.0, depth))
        settled.append((label, u, d.vel.x))
    check("and given time you end up going as fast as the water is",
          all(abs(v - u) < abs(u) * 0.25 + 0.25 for _, u, v in settled),
          str([(l, f"{u:.2f} vs {v:.2f}") for l, u, v in settled]))
    for (label, depth, u, dx), (_, _, v) in zip(rows, settled):
        _report(f"{label:8s} ({depth:3.0f} m)",
                f"water {u:+5.2f} px/s, you settle at {v:+5.2f} px/s")


def test_the_shallows_push_and_the_deep_does_not():
    """RIGS.md 9.1 gets another channel nobody added a rule for. A wind-driven
    layer is sheared, so travel is a negotiation near the surface and a
    private matter at depth."""
    med = Medium(1200, 800)
    speeds = [abs(med.flow_at(600.0, d)[0]) for d in (40.0, 200.0, 400.0, 700.0)]
    check("the current falls off with depth, monotonically",
          all(b < a for a, b in zip(speeds, speeds[1:])),
          str([f"{s:.2f}" for s in speeds]))
    check("and the deep is nearly still",
          speeds[-1] < speeds[0] * 0.1,
          f"{speeds[0]:.2f} px/s shallow vs {speeds[-1]:.2f} deep")
    _report("drift by depth", " ".join(f"{s:5.2f}" for s in speeds) + " px/s")


def test_a_vent_is_a_place_you_cannot_stand():
    """Warm water rises and it takes you with it -- through buoyancy, because
    you are in light water, and through the flow itself, because continuity
    says the column has to go somewhere. Two mechanisms, neither authored, and
    the best place to draw power from is the place that will not let you hold
    position."""
    med = Medium(1200, 800)
    vent = Vent((600.0, 600.0))
    for _ in range(int(150 * 15)):
        vent.warm(med, 1 / 15.0)
        med.step(1 / 15.0)
    u, v = med.flow_at(600.0, 584.0)
    lifted = swim(med, 6.0, pos=(600.0, 584.0))
    away = swim(med, 6.0, pos=(950.0, 584.0))
    check("the plume itself is rising", v < -1.0, f"{v:+.2f} px/s")
    check("and it carries a diver who does nothing straight up",
          lifted.pos.y < 584.0 - 40.0,
          f"moved {lifted.pos.y - 584.0:+.1f} px")

    # And the part nobody drew. What goes up has to come down somewhere: the
    # flow is incompressible, so a rising column REQUIRES a sinking one beside
    # it, and continuity puts it there without being asked. The first version
    # of this test assumed "away from the vent" meant "nothing happens" and
    # found the diver sinking 90 px, which is not a bug, it is a convection
    # cell. A vent is not a hazard at a point -- it is a circulation you have
    # to navigate.
    check("and beside it the water is going back DOWN",
          away.pos.y > 584.0 + 20.0, f"{away.pos.y - 584.0:+.1f} px")
    check("so a plume is a circulation, not a point",
          (lifted.pos.y - 584.0) * (away.pos.y - 584.0) < 0.0,
          "both limbs went the same way")
    _report("in the plume, 6 s of doing nothing",
            f"{lifted.pos.y - 584.0:+7.1f} px")
    _report("350 m to the side, same 6 s",
            f"{away.pos.y - 584.0:+7.1f} px")


def test_your_own_machine_changes_the_water_you_swim_in():
    """The coupling this whole project exists for, arriving in the movement
    system without being invited. A rig that dumps heat makes water that lifts
    you; a rig that makes cold water makes water that drops you."""
    # The COIL's line matters here as much as it does anywhere. A "cooler"
    # run with its coil at your own feet still puts net heat into the water
    # you are floating in -- that is RIGS.md 4.1's whole lesson, and the first
    # version of this test found both rigs lifting because of it. Run the line
    # away and only the cold port water is left where you are.
    out = {}
    for label, kinds, coil in (
        ("a heater", ("INTAKE", "SQUEEZE", "SQUEEZE", "PORT"), None),
        ("a cooler, coil at your feet",
         ("INTAKE", "SQUEEZE", "COIL", "EXPAND", "PORT"), None),
        ("a cooler, coil run 200 m off",
         ("INTAKE", "SQUEEZE", "COIL", "EXPAND", "PORT"), (800.0, 400.0)),
    ):
        med = Medium(1200, 800)
        r = Chain(kinds).evaluate(
            couple.ambient_from(med, 600.0, 400.0, coil_at=coil))
        d = Diver((600.0, 400.0))
        for _ in range(int(20.0 / DT)):
            couple.apply(r, med, d.pos.x, d.pos.y, DT, coil_at=coil)
            d.step(DT, med)
            med.step(DT)
        out[label] = d.pos.y - 400.0
    check("running a heater lifts you off your own exhaust",
          out["a heater"] < -1.0, f"{out['a heater']:+.2f} px")
    check("a cooler dumping at your own feet lifts you too -- it is a heater "
          "where you are standing",
          out["a cooler, coil at your feet"] < -1.0,
          f"{out['a cooler, coil at your feet']:+.2f} px")
    check("and only with the line run away does the cold water drop you",
          out["a cooler, coil run 200 m off"] > 1.0,
          f"{out['a cooler, coil run 200 m off']:+.2f} px")
    for label, dy in out.items():
        _report(f"20 s of {label}", f"{dy:+7.1f} px")


# --- 2. what movement costs --------------------------------------------------


def test_drifting_is_free_and_crossing_is_not():
    """The one word that makes a current a force instead of scenery is
    `relative`. Drag reads your speed through the WATER."""
    med = Medium(1200, 800)
    u, _ = med.flow_at(600.0, 40.0)
    drifting = swim(med, 10.0, pos=(600.0, 40.0))
    check("a drifting diver is doing almost no swimming at all",
          drifting.speed_through_water(med) < drifting.speed * 0.2,
          f"{drifting.speed_through_water(med):.3f} px/s through the water"
          f" against {drifting.speed:.3f} over the ground")
    check("even though they are moving over the ground",
          drifting.speed > 3.0, f"{drifting.speed:.2f} px/s over the ground")
    _report("drifting: over the ground",
            f"{drifting.speed:6.2f} px/s")
    _report("drifting: through the water",
            f"{drifting.speed_through_water(med):6.2f} px/s")

    # Going with it is cheaper than going against it, for the same thrust.
    acc, _ = thruster_acc()
    with_it = swim(med, 10.0, pos=(600.0, 40.0), thrust=V(abs(acc.length()), 0))
    against = swim(med, 10.0, pos=(600.0, 40.0), thrust=V(-abs(acc.length()), 0))
    gained = abs(with_it.pos.x - 600.0)
    fought = abs(against.pos.x - 600.0)
    check("the same push carries you further downstream than up",
          gained > fought * 1.15, f"{gained:.1f} px vs {fought:.1f} px")
    _report("10 s of thrust downstream", f"{gained:7.1f} px")
    _report("10 s of thrust upstream", f"{fought:7.1f} px")


def test_a_kick_cannot_outrun_a_rig():
    """SUBMERGED 8's entire premise, and it was FALSE the moment `rig_thrust`
    became honest: 2719 N on a 90 kg diver is 30 px/s^2, and a KICK of 240
    made flailing four times faster than the machine you were told to build."""
    med = Medium(1200, 800)
    acc, newtons = thruster_acc()
    kicked = swim(med, 8.0, kick=V(-KICK, 0.0))
    driven = swim(med, 8.0, thrust=acc)
    check("a rig beats a flutter kick, clearly",
          driven.speed > kicked.speed * 3.0,
          f"rig {driven.speed:.1f} px/s vs kick {kicked.speed:.1f} px/s")
    _report("8 s of kicking", f"{kicked.speed:6.2f} px/s")
    _report(f"8 s of a {newtons:.0f} N rig", f"{driven.speed:6.2f} px/s")

    econ = Economy()
    swim(med, 8.0, kick=V(-KICK, 0.0), economy=econ)
    check("and kicking is not free either", econ.air <= 100.0)


def test_trim_is_the_opposite_of_thrust_in_every_way():
    """Slow, silent, free, and vertical, against fast, loud, expensive and
    horizontal. A player with time uses one and a player in trouble uses the
    other, and nothing had to say so."""
    med = Medium(1200, 800)
    acc, _ = thruster_acc()

    d = Diver((600.0, 400.0))
    d.set_trim(1.0)
    filled_at = None
    for i in range(int(6.0 / DT)):
        d.step(DT, med)
        if filled_at is None and d.trim >= 0.995:
            filled_at = i * DT
    check("the bladder takes real time to fill",
          filled_at is not None and 1.0 < filled_at < 3.0, f"{filled_at} s")

    econ = Economy()
    holder = Diver((600.0, 400.0))
    holder.trim = 1.0
    holder.trim_target = 1.0
    for _ in range(int(10.0 / DT)):
        holder.step(DT, med, economy=econ)
    check("but holding it costs nothing once it is set",
          econ.air == 100.0, f"air {econ.air:.3f}")

    econ2 = Economy()
    changer = Diver((600.0, 400.0))
    changer.set_trim(1.0)
    for _ in range(int(10.0 / DT)):
        changer.step(DT, med, economy=econ2)
    check("and changing it does", econ2.air < 100.0, f"air {econ2.air:.3f}")

    rising = swim(med, 8.0, trim=1.0)
    check("full trim climbs steadily rather than instantly",
          rising.pos.y < 400.0 - 30.0, f"{rising.pos.y - 400.0:+.1f} px")
    check("and slower than a rig would push you",
          abs(rising.pos.y - 400.0) < abs(swim(med, 8.0, thrust=acc).pos.x - 600.0),
          "trim outran the rig")
    _report("time to fill the bladder", f"{filled_at:.2f}", " s")
    _report("8 s at full trim", f"{rising.pos.y - 400.0:+7.1f} px")


# --- 3. force arrives late ---------------------------------------------------


def test_added_mass_makes_everything_arrive_late():
    """The single biggest reason underwater movement FEELS underwater. Drag
    punishes speed; added mass punishes change, and no amount of the first
    reproduces the second."""
    med = Medium(1200, 800)
    acc, _ = thruster_acc()
    d = Diver((600.0, 400.0))
    top = swim(med, 12.0, thrust=acc).speed

    reached = None
    for i in range(int(12.0 / DT)):
        d.step(DT, med, thrust=acc)
        if reached is None and d.speed >= 0.9 * top:
            reached = i * DT
    stopped = None
    for i in range(int(20.0 / DT)):
        d.step(DT, med)
        if stopped is None and d.speed <= 0.1 * top:
            stopped = i * DT
            break
    check("getting up to speed takes seconds, not an instant",
          reached is not None and reached > 1.0, f"{reached} s")
    check("and so does stopping",
          stopped is not None and stopped > 1.5, f"{stopped} s")
    check("added mass is really what is doing it",
          abs(ADDED_MASS - 1.0) < 1e-9, f"{ADDED_MASS}")
    _report("to 90% of cruising speed", f"{reached:5.2f}", " s")
    _report("to coast back under 10%", f"{stopped:5.2f}", " s")
    _report("cruising speed", f"{top:5.2f}", " px/s")


def test_pointing_where_you_are_going_matters():
    """A diver is a long thing. Broadside, you are a sail."""
    med = Medium(1200, 800)
    acc, _ = thruster_acc()
    along = swim(med, 8.0, thrust=acc, aim=(1.0, 0.0))
    across = swim(med, 8.0, thrust=acc, aim=(0.0, 1.0))
    da = abs(along.pos.x - 600.0)
    dc = abs(across.pos.x - 600.0)
    check("streamlined travels further than broadside for the same push",
          da > dc * 1.25, f"{da:.1f} px vs {dc:.1f} px")
    check("and the coefficients say why",
          DRAG_ACROSS > DRAG_ALONG * 2.5,
          f"{DRAG_ALONG} along, {DRAG_ACROSS} across")
    _report("8 s pointed along the push", f"{da:7.1f} px")
    _report("8 s broadside to it", f"{dc:7.1f} px")
    _report("what pointing is worth", f"{100 * (da / dc - 1.0):5.1f}", "%")


def main():
    pygame.init()
    print("=" * 72)
    print("SWIMMING -- is this water, or is it air with the numbers turned down")
    print("=" * 72)
    print("\n[1] the water moves, and moving water moves you")
    test_still_water_is_actually_still()
    test_a_current_carries_you()
    test_the_shallows_push_and_the_deep_does_not()
    test_a_vent_is_a_place_you_cannot_stand()
    test_your_own_machine_changes_the_water_you_swim_in()
    print("\n[2] what movement costs")
    test_drifting_is_free_and_crossing_is_not()
    test_a_kick_cannot_outrun_a_rig()
    test_trim_is_the_opposite_of_thrust_in_every_way()
    print("\n[3] force arrives late")
    test_added_mass_makes_everything_arrive_late()
    test_pointing_where_you_are_going_matters()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
