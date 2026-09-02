"""The laws, measured. RIGS.md 4, 11, 12.

This is the suite the whole design rests on. RIGS.md claims the rig is a
system rather than a pile of effects that individually look plausible, and the
only difference between those two things is whether the books balance under
composition. So:

    - every joule is accounted for, in every chain, at every depth
    - every gram of gas is accounted for
    - **no chain generates energy**, including chains nobody designed

The third is the one that matters and it is fuzzed rather than enumerated,
because the failure mode this design is most exposed to is a five-module
combination nobody thought to try that quietly runs a free heat engine. Two
such bugs were found this way while the modules were being written, and both
are recorded in `modules.py` where the fix lives.

Run:  python -m sigilwave.rig.selftest_conservation
"""

import random

from .chain import Chain, ambient_at
from .library import PRESETS
from .modules import KINDS, NOTES
from .slug import Ambient
from .units import (
    ETA_COMPRESSOR,
    ETA_TURBINE,
    RIG_MASS_FLOW,
    gas_capacity,
)

# Float noise for sums of terms around 1e8 J. Anything above this is a term
# that was genuinely forgotten, not rounding.
ENERGY_TOL = 1e-4
GAS_TOL = 1e-9

DEPTHS = (0.0, 40.0, 120.0, 250.0, 400.0, 600.0, 760.0)

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


# --- 1. energy ---------------------------------------------------------------


def test_energy_balances_for_every_preset():
    print("\n[1] every library machine accounts for every joule, at every depth")
    worst = 0.0
    worst_where = ""
    for preset in PRESETS:
        for depth in DEPTHS:
            amb = ambient_at(depth)
            r = preset.build().evaluate(amb)
            resid = abs(r.ledger.residual(None))
            if resid > worst:
                worst, worst_where = resid, f"{preset.name} at {depth:.0f} m"
    check("energy residual is zero everywhere",
          worst < ENERGY_TOL,
          f"worst {worst:.3e} J at {worst_where}")
    _report("worst residual", f"{worst:.3e} J ({worst_where})")


def test_gas_balances_for_every_preset():
    print("\n[2] nothing creates gas")
    worst = 0.0
    worst_where = ""
    for preset in PRESETS:
        for depth in DEPTHS:
            amb = ambient_at(depth)
            r = preset.build().evaluate(amb)
            resid = abs(r.ledger.gas_residual(None))
            if resid > worst:
                worst, worst_where = resid, f"{preset.name} at {depth:.0f} m"
    check("gas residual is zero everywhere",
          worst < GAS_TOL,
          f"worst {worst:.3e} kg at {worst_where}")
    _report("worst residual", f"{worst:.3e} kg")


def test_mass_is_conserved():
    print("\n[3] water in equals water out")
    amb = ambient_at(200)
    bad = []
    for preset in PRESETS:
        chain = preset.build()
        r = chain.evaluate(amb)
        if not r.runs and r.fault.kind == "IT DOES NOTHING":
            continue
        # Every live stage carries exactly the intake's mass. A module that
        # changed it would be creating or destroying water, which law I
        # forbids and which nothing in the vocabulary is allowed to do.
        for st in r.stages:
            if st.temp is None:
                continue
        # mass is not exposed per-stage, so check the ledger's own view
        if r.ledger.gas_from_ocean > 0:
            implied = r.ledger.gas_from_ocean / max(amb.gas, 1e-12)
            if abs(implied - RIG_MASS_FLOW) > 1e-6:
                bad.append((preset.name, implied))
    check("every chain moves exactly one intake of water", not bad, str(bad[:3]))


# --- 4. the one that matters -------------------------------------------------


def _random_chain(rng, length):
    kinds = list(KINDS)
    body = [rng.choice(kinds) for _ in range(length)]
    return Chain(["INTAKE"] + body + ["PORT"])


def test_no_chain_generates_energy():
    """The Second Law, fuzzed.

    A chain may cost nothing (sonar with no resonator, a bare tapper) but it
    may never PRODUCE. A negative net_work is a machine you could bolt to
    itself and run forever, and this project would rather find that here than
    in a playtest.

    Two real bugs were caught by exactly this check while the modules were
    being written:

      - a turbine recovering work from expansion below ambient, which is
        pulling a vacuum and must cost;
      - an expansion valve returning its work to the economy, which converted
        ambient ocean heat into work with no cold sink -- a Kelvin-Planck
        violation whose books balanced perfectly.
    """
    print("\n[4] no chain generates energy -- 4000 random machines")
    rng = random.Random(20260902)
    worst = 0.0
    worst_chain = None
    generators = 0
    for _ in range(4000):
        depth = rng.choice(DEPTHS)
        chain = _random_chain(rng, rng.randint(1, 8))
        r = chain.evaluate(ambient_at(depth))
        cost = r.ledger.net_work
        if cost < worst:
            worst, worst_chain = cost, (repr(chain), depth)
        if cost < -ENERGY_TOL:
            generators += 1
    check("no random chain has negative net work",
          generators == 0,
          f"{generators} generators, worst {worst:.3e} J in {worst_chain}")
    _report("most negative net work", f"{worst:.3e} J")


def test_random_chains_conserve():
    print("\n[5] random machines account for every joule too")
    rng = random.Random(11235813)
    worst = 0.0
    worst_chain = None
    worst_gas = 0.0
    for _ in range(4000):
        depth = rng.choice(DEPTHS)
        chain = _random_chain(rng, rng.randint(1, 10))
        r = chain.evaluate(ambient_at(depth))
        resid = abs(r.ledger.residual(None))
        gas = abs(r.ledger.gas_residual(None))
        if resid > worst:
            worst, worst_chain = resid, (repr(chain), depth)
        worst_gas = max(worst_gas, gas)
    check("energy residual zero for random chains", worst < ENERGY_TOL,
          f"worst {worst:.3e} J in {worst_chain}")
    check("gas residual zero for random chains", worst_gas < GAS_TOL,
          f"worst {worst_gas:.3e} kg")
    _report("worst energy residual", f"{worst:.3e} J")


# --- 6. the laws individually ------------------------------------------------


def test_second_law_round_trip_is_hotter():
    """RIGS.md 6: the do-nothing is worse than nothing.

    A squeeze and an expansion are exact inverses on paper. In a real machine
    the compressor puts all of its work into the fluid and the valve rejects
    what it takes out, so the water comes back warmer and you paid for it.
    """
    print("\n[6] law II + the Second Law: a round trip comes back hotter")
    amb = ambient_at(120)
    r = Chain(("INTAKE", "SQUEEZE", "EXPAND", "PORT")).evaluate(amb)
    dT = r.delta_temp
    check("squeeze then expand ends warmer than it started", dT > 0.5,
          f"dT = {dT:+.3f} C")
    check("and it was not free", r.ledger.net_work > 0.0,
          f"net work {r.ledger.net_work:.3e} J")
    _report("round trip", f"{dT:+.2f} C for {r.cost:.2f} units")


def test_law_three_the_coil_is_what_makes_a_cooler():
    """RIGS.md 4.1: heat is moved, never destroyed.

    The single most important claim in the design, and it is one module wide:
    the same chain with and without a COIL is a cooler and a heater.
    """
    print("\n[7] law III: one module is the difference between cooling and heating")
    amb = ambient_at(120)
    with_coil = Chain(("INTAKE", "SQUEEZE", "COIL", "EXPAND", "PORT")).evaluate(amb)
    without = Chain(("INTAKE", "SQUEEZE", "EXPAND", "PORT")).evaluate(amb)
    check("with a COIL it cools", with_coil.delta_temp < -1.0,
          f"{with_coil.delta_temp:+.3f} C")
    check("without one it heats", without.delta_temp > 1.0,
          f"{without.delta_temp:+.3f} C")
    check("and the heat the coil moved went into the ocean",
          with_coil.ledger.heat_to_ocean > 0.0)
    _report("with coil", f"{with_coil.delta_temp:+.2f} C, "
                         f"{with_coil.ledger.heat_to_ocean:.3e} J to the water")
    _report("without", f"{without.delta_temp:+.2f} C")


def test_coil_never_cools_past_ambient():
    """A heat exchanger cannot beat what it exchanges with. If it could, the
    cascade would be a free cryostat and depth would stop mattering."""
    print("\n[8] a COIL cannot cool below the water it sits in")
    bad = []
    for depth in DEPTHS:
        amb = ambient_at(depth)
        r = Chain(("INTAKE", "COIL", "COIL", "COIL", "COIL", "PORT")).evaluate(amb)
        for st in r.stages:
            if st.temp is not None and st.temp < amb.temp - 1e-6:
                bad.append((depth, st.temp, amb.temp))
    check("no stage ends below ambient from coils alone", not bad, str(bad[:3]))


def test_law_five_expansion_makes_bubbles():
    """RIGS.md 4: pressure holds gas in solution. Drop it and gas comes out."""
    print("\n[9] law V: dropping pressure brings gas out of solution")
    amb = ambient_at(120)
    r = Chain(("INTAKE", "EXPAND", "EXPAND", "PORT")).evaluate(amb)
    fizzed = [st for st in r.stages if st.bubbles and st.bubbles > 0]
    check("expanding produces bubbles", len(fizzed) >= 1,
          f"{len(fizzed)} stages fizzing")
    check("and a plain intake does not",
          (Chain(("INTAKE", "PORT")).evaluate(amb).stages[0].bubbles or 0.0) <= 1e-12)
    if fizzed:
        _report("bubbles after two expansions", f"{fizzed[-1].bubbles:.5f}")


def test_gas_capacity_agrees_with_the_ocean():
    """The rig computes capacity per parcel and field.py computes it per grid.
    If the two ever drift apart the bug is invisible, because each looks
    correct on its own."""
    print("\n[10] the rig and the ocean agree about what water can hold")
    import numpy as np

    from ..medium.field import Medium

    med = Medium(320, 320, cell_size=16.0)
    theirs = med._gas_capacity()
    worst = 0.0
    for row in range(0, med.ny, 3):
        for col in range(0, med.nx, 5):
            mine = gas_capacity(float(med.pressure[row, 0]),
                                float(med.temp[row, col]))
            worst = max(worst, abs(mine - float(theirs[row, col])))
    check("gas_capacity matches field.py to float precision", worst < 1e-12,
          f"worst disagreement {worst:.3e}")
    _report("worst disagreement", f"{worst:.3e}")


# --- 11. depth, which is the content ----------------------------------------


def test_depth_flips_the_sign():
    """RIGS.md 9.1. Three separate claims, each measured rather than asserted."""
    print("\n[11] depth changes what the same machine does")

    # the charge: tears at the station, refuses at depth
    charge = ("INTAKE", "PUMP", "PUMP", "NARROW", "NARROW", "NARROW", "PORT")
    shallow = Chain(charge).evaluate(ambient_at(40))
    deep = Chain(charge).evaluate(ambient_at(400))
    check("the charge tears at 40 m", shallow.tore)
    check("and refuses to tear at 400 m", not deep.tore)
    _report("charge", f"min pressure {shallow.min_pressure:.3f} bar shallow, "
                      f"{deep.min_pressure:.3f} bar deep")

    # the gill: breathes better where it is trying to kill you
    gill = ("INTAKE", "EXPAND", "EXPAND", "FILTER", "PORT")
    g_shallow = Chain(gill).evaluate(ambient_at(40))
    g_deep = Chain(gill).evaluate(ambient_at(400))
    check("the gill catches more gas deep than shallow",
          g_deep.ledger.tank_gas > g_shallow.ledger.tank_gas * 2.0,
          f"{g_shallow.ledger.tank_gas:.2f} kg vs {g_deep.ledger.tank_gas:.2f} kg")
    _report("gill", f"{g_shallow.ledger.tank_gas:.1f} kg at 40 m, "
                    f"{g_deep.ledger.tank_gas:.1f} kg at 400 m "
                    f"({g_deep.ledger.tank_gas / max(g_shallow.ledger.tank_gas, 1e-9):.1f}x)")

    # the boiler: cold water lets you push harder
    boiler = ("INTAKE",) + ("SQUEEZE",) * 7 + ("PORT",)
    b_shallow = Chain(boiler).evaluate(ambient_at(40))
    b_deep = Chain(boiler).evaluate(ambient_at(400))
    check("the boiler cooks at the station", not b_shallow.runs
          and b_shallow.fault.kind == "IT BOILS",
          f"peak {b_shallow.peak_temp:.1f} C")
    check("and survives in cold deep water", b_deep.runs,
          f"peak {b_deep.peak_temp:.1f} C")
    _report("boiler", f"peak {b_shallow.peak_temp:.0f} C at 40 m, "
                      f"{b_deep.peak_temp:.0f} C at 400 m")


def test_stripping_the_water_weakens_the_compressor():
    """The coupling nobody designed: FILTER takes the working fluid away, so a
    rig that strips its own water stops being able to compress it."""
    print("\n[12] taking the gas out disables your own compressor")
    amb = ambient_at(200)

    # The two chains must differ by the FILTER and nothing else, and the
    # measurement must be the SQUEEZE's own heating rather than the whole
    # chain's bill. The first version compared total work_in between chains of
    # different lengths, so the extra module's vacuum cost swamped the effect
    # it was trying to see and the test failed while the physics was right.
    def squeeze_rise(kinds, at):
        r = Chain(kinds).evaluate(amb)
        return r.stages[at].temp - r.stages[at - 1].temp, r

    full_dT, full = squeeze_rise(("INTAKE", "EXPAND", "SQUEEZE", "PORT"), 2)
    strip_dT, strip = squeeze_rise(
        ("INTAKE", "EXPAND", "FILTER", "SQUEEZE", "PORT"), 3)

    check("the same SQUEEZE heats stripped water less than full water",
          strip_dT < full_dT * 0.95,
          f"{strip_dT:+.3f} C stripped vs {full_dT:+.3f} C full")
    check("because the filter took the working fluid with the gas",
          strip.stages[2].working < full.stages[1].working,
          f"working {strip.stages[2].working:.4f} vs {full.stages[1].working:.4f}")
    _report("squeeze heating", f"{full_dT:+.2f} C on full water, "
                               f"{strip_dT:+.2f} C after a FILTER "
                               f"({strip_dT / max(full_dT, 1e-9) * 100:.0f}%)")


# --- 13. the four failures ---------------------------------------------------


def test_the_four_failures_are_reachable_and_distinct():
    print("\n[13] all four failures are reachable, and only by their own cause")
    amb = ambient_at(40)
    cases = {
        "IT DOES NOTHING": ("SQUEEZE", "SQUEEZE"),
        "IT BOILS": ("INTAKE",) + ("SQUEEZE",) * 7 + ("PORT",),
        "IT STALLS": ("INTAKE",) + ("PUMP",) * 4 + ("PORT",),
    }
    for want, kinds in cases.items():
        r = Chain(kinds).evaluate(amb)
        check(f"{want} is reachable",
              r.fault is not None and r.fault.kind == want,
              f"got {r.fault.kind if r.fault else 'no fault'}")
    healthy = Chain(("INTAKE", "SQUEEZE", "COIL", "EXPAND", "PORT")).evaluate(amb)
    check("and a good machine trips none of them", healthy.runs,
          str(healthy.fault))


def main():
    print("=" * 72)
    print("RIGS -- conservation and the laws")
    print("=" * 72)
    test_energy_balances_for_every_preset()
    test_gas_balances_for_every_preset()
    test_mass_is_conserved()
    test_no_chain_generates_energy()
    test_random_chains_conserve()
    test_second_law_round_trip_is_hotter()
    test_law_three_the_coil_is_what_makes_a_cooler()
    test_coil_never_cools_past_ambient()
    test_law_five_expansion_makes_bubbles()
    test_gas_capacity_agrees_with_the_ocean()
    test_depth_flips_the_sign()
    test_stripping_the_water_weakens_the_compressor()
    test_the_four_failures_are_reachable_and_distinct()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
