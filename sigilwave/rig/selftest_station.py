"""The station is a place, not a menu. RIGS.md 13.

Every check here is of the form "the station is made of the same physics as
everything else, and therefore something inconvenient is true about it". If
this file ever passes trivially, the station has become a menu with a
position.

Run:  python -m sigilwave.rig.selftest_station
"""

import pygame

from ..diver import Diver, V
from ..medium.field import Medium
from ..sources import AIR_MAX, Body, Economy
from .chain import Chain
from . import couple
from .station import (
    AIR_RATE, CHARGE_RATE, DOCK_RADIUS, STATION_REACH, Station,
)

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


HOME = (600.0, 500.0)


def warmed(seconds=150.0, dt=1 / 15.0):
    """A station that has been running as long as a station has been running."""
    med = Medium(1200, 800)
    st = Station(HOME)
    for _ in range(int(seconds / dt)):
        st.warm(med, dt)
        med.step(dt)
    return med, st


# --- 1. it gives, at a rate ---------------------------------------------------


def test_resupply_takes_time_and_proximity():
    st = Station(HOME)
    econ = Economy()
    econ.air = 20.0

    far = st.resupply((HOME[0] + 200.0, HOME[1]), econ, 1.0)
    check("nothing happens if you are not at the door",
          far["air"] == 0.0 and not far["docked"], str(far))
    check("and your air did not move", econ.air == 20.0, f"{econ.air}")

    seconds = 0.0
    while econ.air < AIR_MAX - 1e-9 and seconds < 60.0:
        st.resupply(HOME, econ, DT)
        seconds += DT
    check("docked, a tank fills in seconds rather than instantly",
          5.0 < seconds < 20.0, f"{seconds:.2f} s from 20% to full")
    _report("empty-ish to full", f"{seconds:.2f}", " s")

    econ2 = Economy()
    econ2.charge = 0.0
    for _ in range(int(3.0 / DT)):
        st.resupply(HOME, econ2, DT)
    check("and the pack charges too",
          econ2.charge > CHARGE_RATE * 2.0, f"{econ2.charge:.2f} units")
    _report("3 s of charging", f"{econ2.charge:.2f}", " units")


def test_free_power_has_a_radius_and_it_is_small():
    """SUBMERGED 3.1's progression curve, as a distance. Everything
    interesting happens outside this circle."""
    st = Station(HOME)
    rows = []
    for d in (0.0, 100.0, 200.0, 299.0, 320.0, 600.0):
        rows.append((d, st.available_at((HOME[0] + d, HOME[1]))))
    check("power falls off with distance",
          all(b[1] <= a[1] for a, b in zip(rows, rows[1:])),
          str([(d, f"{p:.2f}") for d, p in rows]))
    check("and stops entirely outside its reach",
          rows[-2][1] == 0.0 and rows[-1][1] == 0.0,
          str(rows[-2:]))
    for d, p in rows:
        _report(f"{d:5.0f} m out", f"{p:5.2f} units/s")

    # And what that means for a machine: free at home, yours to solve away.
    econ = Economy()
    srcs = [Body(), st]
    home_air, away_air = [], []
    for pos, sink in (((HOME[0], HOME[1]), home_air),
                      ((HOME[0] + 600.0, HOME[1]), away_air)):
        e = Economy()
        for _ in range(int(4.0 / DT)):
            e.draw_energy(0.46, srcs, pos, DT)
        sink.append(e.air)
    check("a thruster costs nothing at home and costs air away from it",
          home_air[0] > away_air[0] + 5.0,
          f"air {home_air[0]:.1f} at home vs {away_air[0]:.1f} away")
    _report("4 s of thrusting at home", f"{home_air[0]:6.2f} air left")
    _report("4 s of thrusting 600 m out", f"{away_air[0]:6.2f} air left")


# --- 2. it is made of the same physics as everything else --------------------


def test_the_station_is_warm_and_that_has_consequences():
    med, st = warmed()
    row, col = med._cell(HOME[0], HOME[1] - 8.0)
    here = float(med.temp[row, col])
    far = float(med.temp[row, 4])
    check("the hull leaks heat into the water", here > far + 1.0,
          f"{here:.2f} C at the door vs {far:.2f} C far off")
    _report("at the door", f"{here:6.2f} C")
    _report("far away, same depth", f"{far:6.2f} C")

    # Which means it is findable by exactly the senses a creature uses.
    from . import creatures

    hunter = creatures.make("stalker", (HOME[0] + 150.0, HOME[1]))
    near = hunter.comfort(med, HOME[0] + 40.0, HOME[1])
    far_c = hunter.comfort(med, HOME[0] + 500.0, HOME[1])
    check("a heat-hunter prefers the water near the station",
          near > far_c, f"{near:.4f} near vs {far_c:.4f} far")
    _report("stalker comfort at the door", f"{near:.4f}")
    _report("stalker comfort 500 m out", f"{far_c:.4f}")


def test_there_is_a_permanent_updraft_over_the_door():
    """The inconvenient consequence, and the one that makes the station a
    place. Warm water rises, so home has weather."""
    med, st = warmed()
    u, v = med.flow_at(HOME[0], HOME[1] - 16.0)
    check("the water over the door is going up", v < -0.5, f"{v:+.3f} px/s")

    d = Diver((HOME[0], HOME[1] - 8.0))
    for _ in range(int(8.0 / DT)):
        d.step(DT, med)
    lifted = (HOME[1] - 8.0) - d.pos.y
    check("a diver who does nothing at the door gets carried off it",
          lifted > 20.0, f"moved {lifted:+.1f} px up in 8 s")
    check("far enough that they undock",
          not st.docked(d.pos), f"{st.distance_to(d.pos):.1f} px out")
    _report("8 s of holding still at the door", f"{lifted:+7.1f} px up")
    _report("dock radius", f"{DOCK_RADIUS:7.1f} px")


def test_cold_made_at_home_is_not_as_cold():
    """A refrigerator does not make a temperature, it makes a DIFFERENCE -- so
    what comes out of the port is ambient plus that difference, and ambient at
    home is warm.

    The first version of this test claimed the cooler would work *worse* near
    the station and it is worth recording that the physics said otherwise:
    warm water holds less gas, so the same dissolved gas reads as a higher
    saturation, so the compressor has MORE working fluid and the cycle is
    slightly stronger. The machine is fine. It is the water it is made of that
    is warm, and the absolute number is the one a player cares about.
    """
    med, st = warmed()
    kinds = ("INTAKE", "SQUEEZE", "COIL", "EXPAND", "PORT")
    at_home = Chain(kinds).evaluate(
        couple.ambient_from(med, HOME[0] + 20.0, HOME[1] - 8.0))
    away = Chain(kinds).evaluate(
        couple.ambient_from(med, HOME[0] + 560.0, HOME[1] - 8.0))
    check("the same rig makes genuinely colder water away from home",
          away.out_temp < at_home.out_temp - 0.5,
          f"{at_home.out_temp:.2f} C at home vs {away.out_temp:.2f} C out")
    check("even though the cycle itself is no worse",
          abs(at_home.delta_temp - away.delta_temp) < 0.5,
          f"{at_home.delta_temp:+.2f} vs {away.delta_temp:+.2f}")
    _report("cooler at the door",
            f"{at_home.out_temp:6.2f} C out ({at_home.delta_temp:+.2f})")
    _report("cooler 560 m away",
            f"{away.out_temp:6.2f} C out ({away.delta_temp:+.2f})")


def test_you_can_find_your_way_home():
    st = Station(HOME)
    for dx, dy in ((300.0, 0.0), (-300.0, 0.0), (0.0, 260.0), (-180.0, -240.0)):
        pos = (HOME[0] + dx, HOME[1] + dy)
        b = st.bearing_from(pos)
        to_home = (V(HOME) - V(pos))
        check(f"the bearing from {int(dx):+5d},{int(dy):+5d} points home",
              b.dot(to_home.normalize()) > 0.999,
              f"{b} vs {to_home.normalize()}")


def main():
    pygame.init()
    print("=" * 72)
    print("THE STATION -- a place, not a menu")
    print("=" * 72)
    print("\n[1] it gives, at a rate, and only close up")
    test_resupply_takes_time_and_proximity()
    test_free_power_has_a_radius_and_it_is_small()
    print("\n[2] and it is made of the same physics as everything else")
    test_the_station_is_warm_and_that_has_consequences()
    test_there_is_a_permanent_updraft_over_the_door()
    test_cold_made_at_home_is_not_as_cold()
    print("\n[3] finding it")
    test_you_can_find_your_way_home()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
