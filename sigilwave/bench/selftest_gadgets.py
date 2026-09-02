"""Do gadgets react to what they are fed? SUBMERGED.md 8.

A gadget's contract is two sentences -- what it wants, what it does -- and
these checks exist to prove the first sentence is true. If a gadget runs on
anything, the band is decoration and the drawing stops mattering again.

    python -m sigilwave.bench.selftest_gadgets
"""

import math

from ..sim.network import raised_cosine_burst
from .gadgets import COUPLING_RANGE, KINDS, ORDER, Rack, drill, gill, lamp, propeller
from .mouths import Emitter
from .parts import Assembly

_p = _f = 0


def check(ok, label):
    global _p, _f
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if ok:
        _p += 1
    else:
        _f += 1


def note(t):
    print(f"       {t}")


def main():
    global _p, _f
    print("--- every gadget wants one thing, and refuses the rest ---")
    for name in ORDER:
        g = KINDS[name]()
        lo, hi = g.band
        mid = math.sqrt(lo * hi)
        inside = g.tuned(mid)
        below = g.tuned(lo * 0.2)
        above = g.tuned(hi * 5.0)
        note(f"  {name:10s} wants {lo:6.0f}-{hi:6.0f} Hz:"
             f" in band {inside:.2f}, far below {below:.2f}, far above {above:.2f}")
        check(inside > 0.99, f"a {name} runs on the note it wants")
        check(below == 0.0 and above == 0.0,
              f"and not at all on a note far outside its band")

    print("")
    print("--- the threshold is a wall, not a slope (9.5) ---")
    g = gill()
    lo, hi = g.band
    mid = math.sqrt(lo * hi)
    got_under = g.drive(g.threshold * 0.95, mid, 1 / 60.0)
    got_over = g.drive(g.threshold * 1.60, mid, 1 / 60.0)
    note(f"gill at 95% of threshold produced {got_under:.5f};"
         f" at 160% it produced {got_over:.5f}")
    check(got_under == 0.0, "under the threshold a gadget does nothing at all")
    check(got_over > 0.0, "over it, it runs")

    print("")
    print("--- the same drive cannot run everything ---")
    # A chirp that runs a gill must NOT also run a propeller, or there is no
    # reason to ever build a second machine.
    chirp = 1900.0
    low = 160.0
    rows = []
    for name in ORDER:
        gg = KINDS[name]()
        a = gg.threshold * 3.0
        on_chirp = gg.drive(a, chirp, 1 / 60.0) > 0.0
        gg2 = KINDS[name]()
        on_low = gg2.drive(a, low, 1 / 60.0) > 0.0
        rows.append((name, on_chirp, on_low))
        note(f"  {name:10s} on a chirp: {'yes' if on_chirp else 'no ':3s}"
             f"   on a low note: {'yes' if on_low else 'no'}")
    chirp_set = {n for n, c, _ in rows if c}
    low_set = {n for n, _, l in rows if l}
    check(chirp_set != low_set,
          "a chirp and a low note drive different gadgets - so what you tune"
          " for is a decision")
    check("gill" in chirp_set and "gill" not in low_set,
          "a gill runs on a chirp and not on a low note")
    check("propeller" in low_set and "propeller" not in chirp_set,
          "a propeller is the other way round")

    print("")
    print("--- a lamp is the greedy one ---")
    thresholds = [(n, KINDS[n]().threshold) for n in ORDER]
    for n, t in sorted(thresholds, key=lambda kv: kv[1]):
        note(f"  {n:10s} needs {t:.3f}")
    check(max(thresholds, key=lambda kv: kv[1])[0] == "lamp",
          "the lamp costs the most to run - it is tearing water open")

    print("")
    print("--- placement matters: a mouth feeds the water OR a gadget ---")
    asm = Assembly()
    asm.add_run((60.0, 300.0), (300.0, 300.0))
    net = asm.compile()
    em = Emitter(asm, net)
    aperture = max(em.groups, key=lambda g: g.centre.x).centre

    near = Rack()
    near.add("propeller", (aperture.x + 20.0, aperture.y))
    far = Rack()
    far.add("propeller", (aperture.x + COUPLING_RANGE * 2.5, aperture.y))

    # Driven with a NOTE, not a single burst. A gadget asks what note it is
    # being fed, and a lone raised-cosine burst has almost no zero crossings,
    # so the aperture honestly reports "no pitch" and every gadget correctly
    # refuses it. That is the right behaviour and the wrong test.
    from .mouths import WATER_FREQ_RATIO
    from .parts import SIM_DT
    hz = 300.0                                  # inside the propeller's band
    period = max(3.0, 1.0 / ((hz / WATER_FREQ_RATIO) * SIM_DT))
    feed = min(nid for nid, _ in asm.mouth_nodes())
    near_total = far_total = 0.0
    for i in range(1400):
        net.step({feed: 0.8 * math.sin(2.0 * math.pi * i / period)})
        em.step()
        near_total += sum(near.step(em, 1 / 60.0).values())
        far_total += sum(far.step(em, 1 / 60.0).values())
    note(f"a propeller 20 px from the mouth got {near_total:.5f};"
         f" one {COUPLING_RANGE*2.5:.0f} px away got {far_total:.5f}")
    check(near_total > 0.0, "a gadget near a mouth is driven")
    check(far_total == 0.0, "a gadget out of reach is not")

    print("")
    print("--- a gadget stops when the machine does ---")
    r = Rack()
    gg = r.add("propeller", (0.0, 0.0))
    gg.drive(gg.threshold * 4.0, 180.0, 1 / 60.0)
    was = gg.output
    for _ in range(60):
        gg.idle(1 / 60.0)
    note(f"driven to {was:.4f}, then left alone for a second: {gg.output:.6f}")
    check(was > 0.0 and gg.output < was * 0.05,
          "it spins down instead of latching on forever")

    print("")
    print("--- the chain a player actually has to solve ---")
    g = gill()
    lo, hi = g.band
    from .mouths import wavelength_px
    wl = wavelength_px(math.sqrt(lo * hi))
    note(f"a gill wants {lo:.0f}-{hi:.0f} Hz")
    note(f"that note's wavelength is {wl:.0f} bench px, so the loop that makes"
         f" it is about that circumference")
    note(f"and to aim it the mouth must be about {2*wl:.0f} px wide")
    check(50.0 < wl < 400.0,
          "the note a gill wants is made by a loop a hand can actually draw")
    check(2 * wl < 340.0,
          "and aimed by a mouth that fits on the bench")

    print("")
    print(f"{_p} passed, {_f} failed.")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
