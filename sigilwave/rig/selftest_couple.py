"""What a rig does to real water. RIGS.md 6.1, 9.1, 10.

`selftest_conservation` proves the rig's books balance. This suite proves the
books are attached to something: that heat a ledger says went into the ocean
is in the ocean, that a gill straining gas actually empties the room, and that
the amplification at the boundary lands inside the band SUBMERGED 8.2 says
mirrors need.

The one that matters is [4]. SUBMERGED's first build of the stage drove
sound-speed contrast to 3085x and produced a region sound simply refused to
enter, with no readable reason. Any coupling constant that does that again has
destroyed the critical angle and with it the skill the whole medium exists to
teach, so it is checked here rather than trusted.

Run:  python -m sigilwave.rig.selftest_couple
"""

import numpy as np

from ..medium.field import Medium
from . import couple, library
from .chain import Chain

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


def _fresh(width=640, height=480):
    return Medium(width, height, cell_size=16.0)


def _cell_temp(med, x, y):
    return float(med.temp[med._cell(x, y)])


def _run(med, preset_or_chain, x, y, seconds, dt=1.0 / 60.0, coil_at=None):
    """Hold a rig at a spot for a while, re-reading ambient every step.

    Re-reading is the point rather than an implementation detail: a rig
    standing in its own warm wake must see the wake, which is what makes
    RIGS.md 6.1's couplings self-inflicted instead of theoretical.
    """
    chain = (preset_or_chain.build() if hasattr(preset_or_chain, "build")
             else preset_or_chain)
    applied = {"heat_c": 0.0, "gas": 0.0, "bubbles": 0.0}
    steps = int(seconds / dt)
    result = None
    for _ in range(steps):
        amb = couple.ambient_from(med, x, y)
        result = chain.evaluate(amb)
        got = couple.apply(result, med, x, y, dt, coil_at=coil_at)
        for k in applied:
            applied[k] += got.get(k, 0.0)
    return result, applied


# --- 1 ----------------------------------------------------------------------


def test_the_ledger_reaches_the_water():
    print("\n[1] heat the ledger says left the rig is in the ocean")
    med = _fresh()
    x, y = 320.0, 200.0
    before = _cell_temp(med, x, y)
    result, applied = _run(med, library.get("the heater"), x, y, 1.0)
    after = _cell_temp(med, x, y)

    check("a heater warms the cell it stands in", after > before + 0.5,
          f"{before:.2f} -> {after:.2f} C")
    check("and the rise matches what apply() reported",
          abs((after - before) - applied["heat_c"]) < 1e-6,
          f"cell {after - before:.4f} vs applied {applied['heat_c']:.4f}")
    _report("heater, one second", f"{before:.2f} -> {after:.2f} C "
                                  f"({after - before:+.2f})")


def test_the_coil_dumps_where_you_put_it():
    """RIGS.md 4.1: heat has to go somewhere and WHERE IS A DECISION.

    This is the check that the decision is real. A cooler run with its coil
    somewhere else makes a cold place in front of you and a warm place over
    there; run with the coil at your feet it heats the water you are standing
    in, which is how a player cooks themselves.
    """
    print("\n[2] a COIL dumps where you put it, not where you are")
    med = _fresh()
    port = (320.0, 200.0)
    coil = (480.0, 200.0)
    t_port0, t_coil0 = _cell_temp(med, *port), _cell_temp(med, *coil)
    _run(med, library.get("the cooler"), port[0], port[1], 1.5, coil_at=coil)
    t_port1, t_coil1 = _cell_temp(med, *port), _cell_temp(med, *coil)

    check("the coil's cell gets warmer", t_coil1 > t_coil0 + 0.1,
          f"{t_coil0:.3f} -> {t_coil1:.3f} C")
    check("the port's cell gets colder", t_port1 < t_port0 - 0.05,
          f"{t_port0:.3f} -> {t_port1:.3f} C")
    _report("cooler", f"port {t_port1 - t_port0:+.2f} C, "
                      f"coil {t_coil1 - t_coil0:+.2f} C")


def test_heat_is_linear_in_the_ledger():
    print("\n[3] twice the heat in the ledger is twice the heat in the water")
    med = _fresh()
    one = Chain(("INTAKE", "SQUEEZE", "COIL", "PORT"))
    two = Chain(("INTAKE", "SQUEEZE", "COIL", "SQUEEZE", "COIL", "PORT"))
    amb = couple.ambient_from(med, 320.0, 200.0)
    r1, r2 = one.evaluate(amb), two.evaluate(amb)

    m1, m2 = _fresh(), _fresh()
    couple.apply(r1, m1, 320.0, 200.0, 1.0)
    couple.apply(r2, m2, 320.0, 200.0, 1.0)
    d1 = _cell_temp(m1, 320.0, 200.0) - amb.temp
    d2 = _cell_temp(m2, 320.0, 200.0) - amb.temp

    ledger_ratio = ((r2.ledger.heat_to_ocean + r2.ledger.heat_out)
                    / max(r1.ledger.heat_to_ocean + r1.ledger.heat_out, 1e-9))
    water_ratio = d2 / max(d1, 1e-9)
    check("the conversion is linear",
          abs(ledger_ratio - water_ratio) < 1e-6,
          f"ledger {ledger_ratio:.4f} vs water {water_ratio:.4f}")
    _report("one stage vs two", f"{d1:+.3f} C and {d2:+.3f} C "
                                f"({water_ratio:.2f}x)")


# --- 4: the hard design rule ------------------------------------------------


def test_contrast_stays_inside_the_usable_band():
    """SUBMERGED 8.2: contrast must stay in 1.05-1.5x.

    Past it every boundary is a perfect mirror at every angle, the critical
    angle stops existing, and 'a mirror only works if you ping shallow' -- the
    skill both the mirror and the sound channel teach -- evaporates.
    """
    print("\n[4] a running rig stays inside the band that keeps mirrors usable")
    med = _fresh()
    x, y = 320.0, 200.0
    base = float(med.c_field[med._cell(x, y)])

    peaks = []
    for seconds in (0.5, 1.0, 2.0, 4.0, 8.0):
        m = _fresh()
        chain = library.build("the heater")
        dt = 1.0 / 60.0
        for _ in range(int(seconds / dt)):
            amb = couple.ambient_from(m, x, y)
            couple.apply(chain.evaluate(amb), m, x, y, dt)
            m.step(dt)          # diffusion and buoyancy fight back
        c = float(m.c_field[m._cell(x, y)])
        b = float(m.c_field[m._cell(x, y)] / base)
        peaks.append((seconds, b))

    worst = max(b for _, b in peaks)
    reachable = [b for _, b in peaks if b >= 1.05]
    check("one second of holding reaches a usable contrast",
          any(b >= 1.05 for s, b in peaks if s <= 1.0),
          f"contrasts {[f'{s}s={b:.3f}' for s, b in peaks]}")
    check("and sustained holding never leaves the band", worst <= 1.5,
          f"worst {worst:.4f}x -- SUBMERGED 8.2 forbids > 1.5")
    for s, b in peaks:
        _report(f"{s:>4}s of heating", f"{b:.4f}x")


# --- 5 ----------------------------------------------------------------------


def test_a_gill_empties_the_room():
    """RIGS.md 6.1: emergent scarcity, with no rule for it.

    Take the gas out of the water and it is not there any more. The rig that
    did it then works worse, because `units.working_fraction` reads the same
    field -- so a player who parks and breathes has to move, and nobody wrote
    that down.
    """
    print("\n[5] a gill strips the water it stands in, and then works worse")
    med = _fresh()
    x, y = 320.0, 300.0
    row, col = med._cell(x, y)
    gas0 = float(med.gas[row, col])

    first, _ = _run(med, library.get("the gill"), x, y, 0.25)
    caught_first = first.ledger.tank_gas
    _run(med, library.get("the gill"), x, y, 6.0)
    gas1 = float(med.gas[row, col])

    amb = couple.ambient_from(med, x, y)
    later = library.build("the gill").evaluate(amb)
    caught_later = later.ledger.tank_gas

    check("the cell loses dissolved gas", gas1 < gas0 * 0.9,
          f"{gas0:.5f} -> {gas1:.5f}")
    check("and the same rig then catches less there",
          caught_later < caught_first * 0.9,
          f"{caught_first:.2f} kg/s -> {caught_later:.2f} kg/s")
    _report("gas in the cell", f"{gas0:.5f} -> {gas1:.5f} "
                               f"({(1 - gas1 / max(gas0, 1e-9)) * 100:.0f}% gone)")
    _report("gill yield", f"{caught_first:.1f} kg/s -> {caught_later:.1f} kg/s")


def test_a_tearing_rig_leaves_bubbles():
    print("\n[6] a rig that tears the water leaves bubbles in it")
    med = _fresh()
    x, y = 320.0, 120.0
    row, col = med._cell(x, y)
    before = float(med.bubbles[row, col])
    result, applied = _run(med, library.get("the lamp"), x, y, 0.5)
    after = float(med.bubbles[row, col])
    check("the lamp tears at this depth", result.tore,
          f"min pressure {result.min_pressure:.3f} bar")
    check("and bubbles appear where it ran", after > before,
          f"{before:.5f} -> {after:.5f}")
    _report("bubbles", f"{before:.5f} -> {after:.5f}")


# --- 7 ----------------------------------------------------------------------


def test_thrust_is_momentum_flux():
    """RIGS.md 10: this is what retires SUBMERGED's named lie.

    `THRUST_PER_ENERGY` existed because acoustic radiation pressure genuinely
    cannot move a diver. A port ejecting water can, so the number is now just
    mass flow times exit velocity and there is nothing to name.
    """
    print("\n[7] thrust is mass flow times exit speed, and nothing else")
    from .units import RIG_MASS_FLOW

    med = _fresh()
    amb = couple.ambient_from(med, 320.0, 200.0)
    r = library.build("the thruster").evaluate(amb)
    t = couple.thrust_from(r)
    check("thrust equals mdot * v exactly",
          abs(t - RIG_MASS_FLOW * r.out_speed) < 1e-9,
          f"{t:.2f} vs {RIG_MASS_FLOW * r.out_speed:.2f}")
    check("a machine with no port speed makes no thrust",
          couple.thrust_from(library.build("the heater").evaluate(amb)) == 0.0)

    v = couple.thrust_vector(r, (1.0, 0.0))
    check("and the reaction points opposite the port", v[0] < 0.0,
          f"vector {v}")
    _report("thruster", f"{r.out_speed:.2f} m/s -> {t:.0f} N")

    # And it actually moves a diver, which is the point of retiring the lie.
    # SUBMERGED measured its own baseline over the same four seconds: a driven
    # machine 101-134 px, kicking 14 px, nothing 3.7 px. A rig-driven diver has
    # to land in that band or the honest number is not usable in the game the
    # dishonest one was tuned for.
    import pygame

    from ..diver import Diver

    moved = {}
    for name in ("the thruster", "the charge", "the heater"):
        rr = library.build(name).evaluate(amb)
        d = Diver((600.0, 200.0))
        acc = d.rig_thrust(rr, pygame.Vector2(1.0, 0.0))
        for _ in range(240):
            d.step(1.0 / 60.0, med, thrust=acc, bounds=(640, 480))
        moved[name] = (d.pos - pygame.Vector2(600.0, 200.0)).length()

    check("a jet moves the diver, in SUBMERGED's own measured band",
          60.0 < moved["the thruster"] < 200.0,
          f"{moved['the thruster']:.1f} px in 4 s")
    check("and a machine that makes no jet moves them not at all",
          moved["the heater"] < 1.0,
          f"{moved['the heater']:.1f} px")
    for name, px in moved.items():
        _report(name, f"{px:.1f} px in 4 s")


def test_sound_leaves_through_the_port():
    print("\n[8] acoustic output becomes a front the medium can propagate")
    med = _fresh()
    amb = couple.ambient_from(med, 320.0, 200.0)

    r = library.build("sonar").evaluate(amb)
    front = couple.emit_front(r, med, (320.0, 200.0), (1.0, 0.0))
    check("sonar emits a front", front is not None)
    if front is not None:
        check("carrying the ledger's acoustic energy",
              abs(front.energy0 - r.out_acoustic) < 1e-6,
              f"{front.energy0:.1f} vs {r.out_acoustic:.1f} J")
        check("at the note the resonator was set to",
              abs(front.freq - r.out_note) < 1e-9,
              f"{front.freq} vs {r.out_note} Hz")
        front.step(med, 0.01)
        check("and it propagates without dying immediately",
              not front.is_dead())
        _report("sonar front", f"{front.energy0:.0f} J at {front.freq:.0f} Hz, "
                               f"arc {front.arc_length():.1f} m")

    quiet = couple.emit_front(library.build("the heater").evaluate(amb),
                              med, (320.0, 200.0), (1.0, 0.0))
    check("a silent machine emits nothing", quiet is None)


def test_widen_and_narrow_shape_the_front():
    """RIGS.md 5.3: the aperture physics survives, driven by a token count."""
    print("\n[9] WIDEN and NARROW decide the shape the sound is born as")
    med = _fresh()
    amb = couple.ambient_from(med, 320.0, 200.0)
    wide = Chain(("INTAKE", "RESONATOR", "WIDEN", "WIDEN", "PORT")).evaluate(amb)
    tight = Chain(("INTAKE", "RESONATOR", "NARROW", "NARROW", "PORT")).evaluate(amb)
    fw = couple.emit_front(wide, med, (320.0, 200.0), (1.0, 0.0))
    ft = couple.emit_front(tight, med, (320.0, 200.0), (1.0, 0.0))
    check("a widened port is born broader than a narrowed one",
          fw.arc_length() > ft.arc_length() * 3.0,
          f"{fw.arc_length():.2f} m vs {ft.arc_length():.2f} m")
    check("and softer per unit of front",
          float(np.max(fw.intensity())) < float(np.max(ft.intensity())),
          f"{float(np.max(fw.intensity())):.1f} vs "
          f"{float(np.max(ft.intensity())):.1f}")
    _report("aperture", f"wide {fw.arc_length():.1f} m, "
                        f"narrow {ft.arc_length():.1f} m")


def test_the_ocean_is_read_not_assumed():
    print("\n[10] a rig reads the water it is actually in")
    med = _fresh()
    x, y = 320.0, 200.0
    cold = couple.ambient_from(med, x, y)
    for _ in range(40):
        med.add_heat(x, y, 0.25)
    warm = couple.ambient_from(med, x, y)
    check("heating the cell changes what the rig reads",
          warm.temp > cold.temp + 5.0,
          f"{cold.temp:.2f} -> {warm.temp:.2f} C")

    r_cold = library.build("the cooler").evaluate(cold)
    r_warm = library.build("the cooler").evaluate(warm)
    check("and the same rig behaves differently in it",
          abs(r_warm.delta_temp - r_cold.delta_temp) > 1e-3,
          f"{r_cold.delta_temp:+.3f} vs {r_warm.delta_temp:+.3f} C")
    _report("cooler in its own wake",
            f"{r_cold.delta_temp:+.2f} C cold water, "
            f"{r_warm.delta_temp:+.2f} C warm water")


def main():
    print("=" * 72)
    print("RIGS -- the rig against real water")
    print("=" * 72)
    test_the_ledger_reaches_the_water()
    test_the_coil_dumps_where_you_put_it()
    test_heat_is_linear_in_the_ledger()
    test_contrast_stays_inside_the_usable_band()
    test_a_gill_empties_the_room()
    test_a_tearing_rig_leaves_bubbles()
    test_thrust_is_momentum_flux()
    test_sound_leaves_through_the_port()
    test_widen_and_narrow_shape_the_front()
    test_the_ocean_is_read_not_assumed()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
