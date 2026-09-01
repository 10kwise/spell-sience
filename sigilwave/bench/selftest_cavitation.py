"""Is the gate real? SUBMERGED.md 4.1.

`selftest_bench` measured the ungated gap and found no threshold at all --
0.227046 of what arrives crosses, at every drive across six decades. These
checks exist to prove the cavitation layer supplies what was missing, and
they fail loudly if it turns out to be another soft nonlinearity wearing a
threshold's name.

    python -m sigilwave.bench.selftest_cavitation
"""

import math

from ..sim.network import raised_cosine_burst
from .cavitation import (
    BLAKE_SURFACE,
    HOLD_STEPS,
    Cavitation,
    blake_threshold,
)
from .parts import Assembly

_passed = 0
_failed = 0


def check(ok, label):
    global _passed, _failed
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if ok:
        _passed += 1
    else:
        _failed += 1


def note(text):
    print(f"       {text}")


def _gapped_run(gap_px=10.0):
    """Two runs, ends placed a gap apart. Energy enters the left mouth and
    the only way onward is across the gap."""
    asm = Assembly()
    asm.add_run((100.0, 200.0), (400.0, 200.0))
    asm.add_run((400.0 + gap_px, 200.0), (700.0, 200.0))
    return asm


def _delivered(amplitude, depth_m=0.0, gated=True, steps=600, gap_px=10.0):
    """Energy that ends up past the gap, for one burst of this amplitude."""
    asm = _gapped_run(gap_px)
    net = asm.compile()
    if not net.couplers:
        raise AssertionError("test assembly produced no coupler")
    cav = Cavitation(net, depth_m) if gated else None
    burst = raised_cosine_burst(6, amplitude=amplitude)
    far = net.edges[1]
    peak = 0.0
    fires = 0
    for i in range(steps):
        if cav is not None:
            cav.step()
        net.step({0: burst[i]} if i < len(burst) else None)
        peak = max(peak, far.total_energy())
    if cav is not None:
        fires = cav.fired()
    return peak / max(amplitude * amplitude, 1e-12), fires


def main():
    print("--- the ungated gap, for comparison ---")
    lo, _ = _delivered(0.05, gated=False)
    hi, _ = _delivered(5.00, gated=False)
    note(f"linear coupler delivers {lo:.6f} at drive 0.05 and {hi:.6f} at 5.0")
    check(abs(lo - hi) / max(lo, 1e-12) < 0.01,
          "ungated: the gap is linear, exactly as measured before (no threshold)")

    print("\n--- the gate ---")
    weak, weak_fires = _delivered(0.5 * BLAKE_SURFACE)
    strong, strong_fires = _delivered(4.0 * BLAKE_SURFACE)
    note(f"below threshold: {weak:.6f} delivered, {weak_fires} collapses")
    note(f"above threshold: {strong:.6f} delivered, {strong_fires} collapses")
    check(weak_fires == 0, "a weak pulse does not tear the water open")
    check(strong_fires > 0, "a strong pulse does")
    check(strong > weak * 3.0,
          f"and markedly more crosses when it does ({strong / max(weak,1e-12):.1f}x)")

    print("\n--- how sharp is it? ---")
    ratios = []
    prev = None
    for mult in (0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.25):
        got, fires = _delivered(mult * BLAKE_SURFACE)
        note(f"  drive {mult:4.2f}x threshold -> {got:.6f} delivered,"
             f" {fires} collapses")
        if prev is not None:
            ratios.append(got / max(prev, 1e-12))
        prev = got
    check(max(ratios) > 2.0,
          f"the transition is a step, not a slope (biggest jump {max(ratios):.1f}x"
          f" between adjacent drives)")

    print("\n--- hysteresis: a trigger, not a comparator ---")
    asm = _gapped_run()
    net = asm.compile()
    cav = Cavitation(net)
    burst = raised_cosine_burst(6, amplitude=3.0 * BLAKE_SURFACE)
    opened_at = None
    still_open_after = 0
    for i in range(400):
        cav.step()
        net.step({0: burst[i]} if i < len(burst) else None)
        if cav.open_gates and opened_at is None:
            opened_at = i
        if opened_at is not None and cav.open_gates:
            still_open_after = i - opened_at
    note(f"opened at step {opened_at}, stayed open {still_open_after} steps"
         f" (hold is {HOLD_STEPS})")
    check(opened_at is not None, "the gate opens")
    check(still_open_after >= HOLD_STEPS - 1,
          "and latches open after the pulse that opened it has gone")

    print("\n--- depth: the same machine is harder to trip deeper ---")
    for depth in (0.0, 100.0, 400.0, 700.0):
        t = blake_threshold(depth)
        note(f"  {depth:5.0f} m -> threshold {t:.4f}"
             f"  ({t / BLAKE_SURFACE:.2f}x the surface)")
    surface_fires = _delivered(1.5 * BLAKE_SURFACE, depth_m=0.0)[1]
    deep_fires = _delivered(1.5 * BLAKE_SURFACE, depth_m=700.0)[1]
    note(f"the same drive fires {surface_fires} times at the surface"
         f" and {deep_fires} at 700 m")
    check(blake_threshold(700.0) > blake_threshold(0.0) * 2.0,
          "the Blake threshold rises with ambient pressure")
    check(surface_fires > 0 and deep_fires == 0,
          "a machine tuned at the station simply refuses to trip at depth")

    print("\n--- LOOP + GAP: the timer 6 struck out ---")
    # A loop fed continuously charges; when the circulating amplitude passes
    # the threshold the gate fires, dumps, and the loop charges again.
    asm = Assembly()
    asm.add_loop((400.0, 300.0), 50.9)                 # hum: 80-sample lap
    asm.add_run((100.0, 300.0), (349.0, 300.0))        # feed, joined to the ring
    asm.add_run((461.0, 300.0), (700.0, 300.0))        # pickup, gapped off it
    net = asm.compile()
    if net.couplers:
        cav = Cavitation(net)
        drive = 0.30 * BLAKE_SURFACE                   # far too weak alone
        single, single_fires = _delivered(drive)
        for i in range(3000):
            cav.step()
            net.step({0: drive})
        note(f"a single {drive:.3f} pulse fires {single_fires} times;"
             f" the same drive into a loop fires {cav.fired()}")
        gaps_between = [b[0] - a[0] for a, b in zip(cav.collapses, cav.collapses[1:])]
        if gaps_between:
            mean = sum(gaps_between) / len(gaps_between)
            spread = max(gaps_between) - min(gaps_between)
            note(f"interval between collapses: mean {mean:.1f} steps,"
                 f" spread {spread} (loop lap is 80)")
        check(cav.fired() > 1,
              "a loop charges past a threshold a single pulse cannot reach")
        check(len(gaps_between) >= 2 and (max(gaps_between) - min(gaps_between)) <= mean,
              "and it fires at a regular interval - that is a clock")
    else:
        check(False, "LOOP + GAP: the test assembly produced no coupler")

    print(f"\n{_passed} passed, {_failed} failed.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
