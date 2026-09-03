"""Nothing powers itself. RIGS.md 5.3, 12.4.

`selftest_conservation` proves the LEDGER cannot be cheated: inside one
evaluation, energy in equals energy out. That is necessary and it is not
sufficient, because a rig does not run for one evaluation -- it runs for
minutes, against a live ocean, and it **changes the water it is reading**.

So there is a second loop, and it does not go through the ledger at all:

    the rig dumps waste heat into a cell
        -> `couple.apply` writes it into the medium
        -> `couple.ambient_from` reads that cell back as the sink
        -> the THERMOPILE sees a gradient
        -> it generates

Every step of that is correct on its own. It is a perpetual motion machine
assembled out of four honest parts, and no test in this project could have
seen it, because each of the four is in a different file and all of them
balance. This suite closes it by running the loop.

THE ARGUMENT, BEFORE THE MEASUREMENTS
-------------------------------------
It turns out to be structurally impossible rather than merely unprofitable,
which is the strongest form the answer could take. A thermopile hands back

    w = q * (1 - Tc/Th) * ETA_PILE

of the heat `q` that crosses it. A gradient the rig made itself was paid for
at **at least one joule per joule** -- more, because the machines that make
heat are inefficient. So the loop returns `ETA_PILE * (1 - Tc/Th)` of what it
cost, and that is below 1 for every temperature this ocean can reach: it would
need a difference of 372 K to break even, and water boils at 100 and the rig
faults at `IT BOILS` long before.

That is Carnot, again, doing the only job it has. **The generators take power
OUT OF THE WATER, and the water has to have had it first.**

Run:  python -m sigilwave.rig.selftest_selfpower
"""

import pygame

from ..medium.field import Medium
from ..sources import AIR_MAX, Body, Economy, Vent
from . import couple
from .chain import Chain, ambient_at
from .units import ETA_PILE, K

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


# --- the closed loop ---------------------------------------------------------


# Where a vent lives, and where its heat actually is. Measured rather than
# assumed: 120 s of a vent at (600, 500) leaves 16.97 degC one cell ABOVE it
# against 5.19 degC of undisturbed water at the same depth 128 m away, because
# warm water rises and `Medium._buoyancy` has always known that.
#
# So the play pattern is not "stand on the vent" -- it is **stand off in the
# cold and run the line into the plume**, which is also what you would do if
# the water were real and you did not want to be cooked or lifted. The first
# version of this test put the rig and its coil in the same warm cell, found a
# gradient of 0.96 degC, and concluded generators were useless.
VENT_AT = (600.0, 500.0)
PLUME_AT = (600.0, 484.0)        # one cell up: where the heat goes
STANDOFF = 128.0                 # how far off to the side you stand


def run_loop(kinds, seconds=60.0, dt=1 / 15.0, coil_dx=16.0, coil_dy=0.0,
             vent=None, pos=(600.0, 400.0), warmup=0.0, coil_at=None):
    """Run a rig against a LIVE medium and let it read back what it wrote.

    `warmup` runs the vent alone first, because a vent in the world has been
    going for a long time and a test that starts one from cold is measuring
    the first two minutes of geology rather than the machine.

    Returns (net units banked, best instantaneous rate once settled, the
    gradient it ended up maintaining, the sink temperature).
    """
    med = Medium(1200, 800)
    if vent is not None and warmup > 0.0:
        for _ in range(int(warmup / dt)):
            vent.warm(med, dt)
            med.step(dt)
    x, y = pos
    coil = coil_at if coil_at is not None else (x + coil_dx, y + coil_dy)
    chain = Chain(kinds)
    banked = 0.0
    best_rate = -1e30
    steps = max(1, int(seconds / dt))
    for i in range(steps):
        if vent is not None:
            vent.warm(med, dt)
        amb = couple.ambient_from(med, x, y, coil_at=coil)
        r = chain.evaluate(amb)
        couple.apply(r, med, x, y, dt, coil_at=coil)
        banked += -r.cost * dt
        if i > steps * 0.75:      # only once the water has settled
            best_rate = max(best_rate, -r.cost)
        med.step(dt)
    row, col = med._cell(x, y)
    srow, scol = med._cell(*coil)
    here = float(med.temp[row, col])
    sink = float(med.temp[srow, scol])
    return banked, best_rate, sink - here, sink


def at_a_vent(kinds, seconds=60.0, warmup=90.0):
    """Stand off in the cold water and run the line into the plume."""
    return run_loop(kinds, seconds=seconds, warmup=warmup,
                    vent=Vent(VENT_AT),
                    pos=(VENT_AT[0] + STANDOFF, VENT_AT[1]),
                    coil_at=PLUME_AT)


# --- 1. the loop that had to be closed --------------------------------------


def test_a_rig_cannot_tap_the_gradient_it_made():
    """The whole point of this file. Every one of these dumps heat into the
    cell its own thermopile is reading, which is the obvious thing to try."""
    cases = [
        (("INTAKE", "SQUEEZE", "COIL", "THERMOPILE", "PORT"),
         "one squeeze into the coil, then tap it"),
        (("INTAKE", "THERMOPILE", "SQUEEZE", "COIL", "PORT"),
         "tap first, heat afterwards"),
        (("INTAKE",) + ("SQUEEZE",) * 4 + ("COIL", "THERMOPILE", "PORT"),
         "four squeezes -- a bigger gradient to tap"),
        (("INTAKE", "SQUEEZE", "COIL", "THERMOPILE", "THERMOPILE",
          "THERMOPILE", "PORT"),
         "three piles on one gradient"),
        (("INTAKE", "EXPAND", "EXPAND", "COIL", "THERMOPILE", "PORT"),
         "make a COLD cell instead, and tap that"),
    ]
    rows = []
    for kinds, label in cases:
        banked, rate, grad, _ = run_loop(kinds)
        rows.append((label, banked, rate, grad))
    check("no self-heating loop ever banks energy",
          all(b < 0.0 for _, b, _, _ in rows),
          str([(l, f"{b:.1f}") for l, b, _, _ in rows if b >= 0.0]))
    check("and none of them is even briefly profitable once settled",
          all(r < 0.0 for _, _, r, _ in rows),
          str([(l, f"{r:.3f}") for l, _, r, _ in rows if r >= 0.0]))
    for label, banked, rate, grad in rows:
        _report(label, f"{banked:9.1f} units net, {rate:8.3f} u/s settled, "
                       f"{grad:+5.2f} C gradient")


def test_a_bigger_self_made_gradient_loses_MORE():
    """The signature of a Carnot-bounded loop rather than a tuned one. If this
    ever inverts, something has stopped being a heat engine."""
    rows = []
    for n in (1, 2, 4, 8):
        kinds = ("INTAKE",) + ("SQUEEZE",) * n + ("COIL", "THERMOPILE", "PORT")
        banked, rate, grad, _ = run_loop(kinds)
        rows.append((n, banked, grad))
    check("more heat poured in means a worse deal, not a better one",
          all(b[1] < a[1] for a, b in zip(rows, rows[1:])),
          str([(n, f"{b:.0f}") for n, b, _ in rows]))
    check("even though the gradient really is growing",
          all(b[2] > a[2] for a, b in zip(rows, rows[1:])),
          str([(n, f"{g:.2f}") for n, _, g in rows]))
    for n, banked, grad in rows:
        _report(f"{n} x SQUEEZE", f"{banked:9.1f} units, {grad:+6.2f} C built")


def test_the_break_even_gradient_is_out_of_reach():
    """Why it is structural and not a balance decision. The loop returns
    ETA_PILE * (1 - Tc/Th) of what it cost, so break-even needs a difference
    the water cannot survive."""
    cold = K(4.0)
    need = None
    for dt_k in range(1, 2000):
        hot = cold + dt_k
        if ETA_PILE * (1.0 - cold / hot) >= 1.0:
            need = dt_k
            break
    check("break-even would need a difference no water survives",
          need is None or need > 300,
          f"{need} K")
    at_100 = ETA_PILE * (1.0 - cold / K(100.0))
    check("and at boiling the loop still returns a fraction of its cost",
          at_100 < 0.3, f"{at_100:.3f} back per joule spent")
    _report("returned per joule at a 96 C self-made gradient",
            f"{at_100:.4f}")
    _report("difference needed to break even",
            "none exists" if need is None else f"{need} K")


# --- 2. what generators are actually for ------------------------------------


def test_a_vent_is_a_different_thing_entirely():
    """The contrast that says what the modules are for. The SAME rig that
    cannot pay for itself off its own waste heat pays for itself easily off a
    gradient something else is maintaining."""
    tap = ("INTAKE", "THERMOPILE", "PORT")
    own, _, own_grad, _ = run_loop(tap, vent=None)
    fed, _, fed_grad, _ = at_a_vent(tap)
    check("with nothing maintaining a gradient it makes exactly nothing",
          abs(own) < 1e-9, f"{own:.6f} units")
    check("with a vent maintaining one it generates",
          fed > 1.0, f"{fed:.3f} units")
    _report("no vent", f"{own:8.3f} units, {own_grad:+.2f} C")
    _report("line run into a plume", f"{fed:8.3f} units, {fed_grad:+.2f} C")

    # And what the power is worth, which is the whole balance of the thing:
    # a vent pays for propulsion and sound forever and never pays for heavy
    # thermal work, so it is worth walking to and does not end the economy.
    rows = []
    for label, kinds in (
        ("a thruster", ("INTAKE", "THERMOPILE", "PUMP", "PUMP", "NARROW", "PORT")),
        ("sonar", ("INTAKE", "THERMOPILE", "RESONATOR", "WIDEN", "WIDEN", "PORT")),
        ("a refrigerator", ("INTAKE", "THERMOPILE", "SQUEEZE", "COIL",
                            "EXPAND", "PORT")),
    ):
        banked, _, _, _ = at_a_vent(kinds)
        rows.append((label, banked))
    paid = dict(rows)
    check("a vent pays for propulsion and for sound",
          paid["a thruster"] > 0.0 and paid["sonar"] > 0.0,
          str([(l, f"{b:.2f}") for l, b in rows]))
    check("and never for heavy thermal work",
          paid["a refrigerator"] < 0.0, f"{paid['a refrigerator']:.2f} units")
    for label, banked in rows:
        _report(f"{label} run off the vent", f"{banked:9.3f} units net")


def test_tapping_a_vent_cools_it():
    """Taking power OUT OF THE WATER means the water has less. Nobody wrote a
    depletion rule; `couple.apply` writes `heat_from_ocean` back as cooling
    and always did."""
    def sink_after(kinds):
        return at_a_vent(kinds)[3]

    untapped = sink_after(("INTAKE", "PORT"))
    tapped = sink_after(("INTAKE", "THERMOPILE", "PORT"))
    check("a vent someone is tapping is colder than one nobody is",
          tapped < untapped - 0.05,
          f"{untapped:.3f} C untapped vs {tapped:.3f} C tapped")
    _report("vent left alone", f"{untapped:7.3f} C")
    _report("vent with a pile on it", f"{tapped:7.3f} C")
    _report("taken out of the water", f"{untapped - tapped:7.3f} C")


# --- 3. the economy itself ---------------------------------------------------


def test_the_pack_cannot_be_laundered():
    """Banking and spending must be one-for-one. A store that gives back more
    than it took would be a generator hiding in the accounting."""
    e = Economy()
    srcs = [Body()]
    dt = 1 / 60.0
    for _ in range(6000):
        e.draw_energy(-2.0, srcs, (0.0, 0.0), dt)
    banked = e.charge
    check("the pack fills and stops at its limit",
          0.0 < banked <= 40.0 + 1e-9, f"{banked:.4f} units")

    spent = 0.0
    for _ in range(60000):
        if e.charge <= 0.0:
            break
        before = e.charge
        e.draw_energy(1.0, srcs, (0.0, 0.0), dt)
        spent += before - e.charge
    check("and gives back exactly what it held, never more",
          abs(spent - banked) < 1e-6,
          f"held {banked:.6f}, returned {spent:.6f}")

    # Idling on a full pack must not create air either.
    e2 = Economy()
    e2.air = 50.0
    for _ in range(600):
        e2.draw_energy(-5.0, srcs, (0.0, 0.0), dt)
    check("and generating never refills your lungs",
          e2.air <= 50.0, f"air went {50.0} -> {e2.air:.3f}")
    _report("air after 10 s of generating", f"{e2.air:.3f} of {AIR_MAX:.0f}")


def test_a_rig_with_no_water_to_take_from_takes_nothing():
    """The degenerate case, stated because it is the sentence the whole design
    rests on: a generator is a PLACE, not a machine."""
    worst = None
    for depth in (0.0, 40.0, 200.0, 400.0, 760.0):
        for kinds in (("INTAKE", "THERMOPILE", "PORT"),
                      ("INTAKE", "TURBINE", "THERMOPILE", "PORT"),
                      ("INTAKE",) + ("THERMOPILE",) * 6 + ("PORT",)):
            r = Chain(kinds).evaluate(ambient_at(depth))
            if r.ledger.work_out != 0.0:
                worst = (depth, kinds, r.ledger.work_out)
    check("in water that is all one temperature, every generator makes zero",
          worst is None, str(worst))


def main():
    pygame.init()
    print("=" * 72)
    print("RIGS -- nothing powers itself")
    print("=" * 72)
    print("\n[1] the loop through the ocean, which the ledger cannot see")
    test_a_rig_cannot_tap_the_gradient_it_made()
    test_a_bigger_self_made_gradient_loses_MORE()
    test_the_break_even_gradient_is_out_of_reach()
    print("\n[2] what generators are for: taking power OUT OF the water")
    test_a_vent_is_a_different_thing_entirely()
    test_tapping_a_vent_cools_it()
    print("\n[3] the economy")
    test_the_pack_cannot_be_laundered()
    test_a_rig_with_no_water_to_take_from_takes_nothing()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
