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
    # A loop only charges if it is coupled WEAKLY. Joined to its feed it is
    # an open port and the energy leaves the way it came; gapped, the same
    # drive builds until it tears the water open, dumps, and builds again.
    # That contrast is the lesson, so it is the check.
    def _loop_rig(feed_gap):
        asm = Assembly()
        asm.add_loop((400.0, 300.0), 50.9)                    # hum: 80-sample lap
        asm.add_run((100.0, 300.0), (349.1 - feed_gap, 300.0))
        asm.add_run((461.0, 300.0), (700.0, 300.0))
        return asm

    results = {}
    for feed_gap, label in ((0.0, "joined"), (10.0, "gapped")):
        net = _loop_rig(feed_gap).compile()
        cav = Cavitation(net)
        peak = 0.0
        for i in range(6000):
            cav.step()
            net.step({0: 0.10 * math.sin(2.0 * math.pi * i / 80.0)})
            if i > 200:
                peak = max(peak, max(
                    abs(e.forward.peek(j))
                    for e in net.edges.values()
                    for j in range(0, e.length_samples, 5)))
        results[label] = (peak, cav.fired(), cav.collapses)
        note(f"feed {label}: peak in the wires {peak:.4f}"
             f" (threshold {BLAKE_SURFACE:.2f}), gate fired {cav.fired()}")

    joined_peak, joined_fires, _ = results["joined"]
    gapped_peak, gapped_fires, collapses = results["gapped"]
    check(joined_fires == 0,
          "a loop JOINED to its feed never charges - the feed is an open port"
          " and the energy leaves the way it came")
    check(gapped_fires > 1 and gapped_peak > joined_peak * 5.0,
          f"a loop GAPPED off its feed charges"
          f" {gapped_peak / max(joined_peak, 1e-12):.0f}x higher and fires -"
          f" weak coupling is what makes a resonator")
    check(gapped_peak > BLAKE_SURFACE,
          f"and past a threshold the drive alone cannot reach (drive 0.10,"
          f" threshold {BLAKE_SURFACE:.2f}, reached {gapped_peak:.2f})")

    gaps_between = [b[0] - a[0] for a, b in zip(collapses, collapses[1:])]
    if gaps_between:
        mean = sum(gaps_between) / len(gaps_between)
        note(f"interval between collapses: mean {mean:.1f} steps,"
             f" min {min(gaps_between)}, max {max(gaps_between)}")
        # NOT claimed: that this is a metronome. It fires repeatedly, which
        # makes it an oscillator and a usable trigger, but the interval is
        # set by where the drive happens to cross the threshold rather than
        # by the loop's own charge time, so the spread is wide and the rate
        # is not monotone in loop size (measured: groan 66.9, hum 37.8, ping
        # 54.8 steps). Turning a repeating trigger into a readable clock is
        # an open problem, and asserting regularity here would only hide it.
        check(len(gaps_between) >= 5,
              f"it fires again and again - a repeating trigger, though not yet"
              f" a metronome (interval spread {min(gaps_between)}-{max(gaps_between)})")
    else:
        check(False, "the gated loop never fired twice, so there is no interval")


    print(f"\n{_passed} passed, {_failed} failed.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
