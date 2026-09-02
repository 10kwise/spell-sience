"""The five sentences of SUBMERGED §4, checked against the simulation that
has to keep them. Run with:

    python -m sigilwave.bench.selftest_bench

Each part gets one sentence and no exceptions (§9.1), and those five
sentences are the game's whole contract with the player. So this file is not
a regression net. It is the place where a sentence gets to be *wrong*, and a
sentence that is wrong is worth more than a suite that is green: it means the
part is mis-specified and the doc, not the test, is what has to move.

Two deliberate departures from `sigilwave/sim/selftest.py`, whose conventions
this otherwise follows. First, a failure does not raise — every check runs and
prints, because "which of the five is a lie" is the output and stopping at the
first one would hide the other four. Second, checks print measurements even
when they pass, because §4's sentences are quantitative claims ("half as
bright", "twice as fast") and a bare PASS does not say whether the number
underneath is 0.5 or 0.44.
"""

import math
import time

import numpy as np

from ..ink import InkType
from ..sim.network import raised_cosine_burst
from .parts import (
    DRAWABLE_RUNGS,
    DX,
    GAP_MAX,
    GATE_RUNG,
    JOIN_EPS,
    LOOP_LADDER,
    MIN_RUN_LENGTH,
    Assembly,
    snap_radius,
)
from .pulse import pulse_samples, pulse_samples_directed

FAILURES: list = []

LOSSLESS = InkType("lossless", broadband_gain_per_sample=1.0, lowpass_coef_per_sample=1.0)


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        FAILURES.append(name)


def note(text: str) -> None:
    print(f"       {text}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) < tol


# --------------------------------------------------------------- utilities


def _first_arrival(net, node_id: int, max_steps: int, threshold: float = 1e-12) -> int | None:
    """The step at which anything at all reaches a node. Leading edge, not
    peak: the per-edge lowpass smears the top of a pulse by an amount that
    depends on edge length, so peak time would measure the filter and the
    leading edge measures the delay line."""
    for step in range(1, max_steps + 1):
        net.step()
        if abs(net.nodes[node_id].last_emitted) > threshold:
            return step
    return None


def _inject(net, node_id: int, amplitude: float = 1.0, width: int = 8) -> float:
    """Fire one burst in and hand back the energy that ended up on the wires.
    §3.2 counts energy from the moment it is on the drawing; what a source
    spends putting it there is §3.1's business, not this file's."""
    for sample in raised_cosine_burst(width, amplitude):
        net.step({node_id: sample})
    return net.total_energy()


def _outgoing(net_edge, node_id: int) -> float:
    """The sample this node just pushed into this edge."""
    if net_edge.node_a == node_id:
        line = net_edge.forward
    else:
        line = net_edge.backward
    return float(line.buffer[(line.ptr - 1) % line.length])


def _make_incident(net_edge, node_id: int, value: float) -> None:
    """Put a sample where this node will read it as incident on the next
    step, without it having to travel and be filtered on the way."""
    line = net_edge.forward if net_edge.node_b == node_id else net_edge.backward
    line.buffer[line.ptr] = value


def _peak_amplitude(net_edge) -> float:
    return max(
        float(np.max(np.abs(net_edge.forward.buffer))),
        float(np.max(np.abs(net_edge.backward.buffer))),
    )


def _two_runs(separation: float, ink=None) -> Assembly:
    a = Assembly(ink=ink) if ink else Assembly()
    a.add_run((100.0, 100.0), (300.0, 100.0))
    a.add_run((300.0 + separation, 100.0), (500.0 + separation, 100.0))
    return a


def _fork_assembly(ink=None, arm: float = 200.0) -> Assembly:
    a = Assembly(ink=ink) if ink else Assembly()
    centre = (400.0, 400.0)
    for angle in (180.0, -60.0, 60.0):
        rad = math.radians(angle)
        a.add_run(centre, (centre[0] + arm * math.cos(rad), centre[1] + arm * math.sin(rad)))
    return a


# ------------------------------------------------------------------- tests


def test_run_takes_time_to_cross() -> None:
    """RUN, section 4: *a signal takes time to cross. Longer is later.*"""
    results = []
    for length in (200.0, 400.0):
        a = Assembly()
        a.add_run((100.0, 100.0), (100.0 + length, 100.0))
        net = a.compile(max_energy=None)
        src = a.node_at((100.0, 100.0))
        dst = a.node_at((100.0 + length, 100.0))
        net.step({src: 1.0})
        arrival = _first_arrival(net, dst, max_steps=400)
        results.append((length, arrival, length / DX))
        note(f"{length:.0f} px run: crossed in {arrival} steps, geometry says {length / DX:.0f}")

    (l0, t0, e0), (l1, t1, e1) = results
    check("RUN: a pulse crosses in length/dx steps", t0 == round(e0) and t1 == round(e1))
    ratio = t1 / t0
    note(f"twice the run, {ratio:.3f}x the crossing time ({t1} vs {t0} steps)")
    check("RUN: longer is later, in proportion", close(ratio, l1 / l0, tol=0.02))


def test_loop_laps_forever_at_its_note() -> None:
    """LOOP, section 4: *a signal caught in a loop laps forever. Its lap time
    is its note.* The ladder is the reason that sentence can be said at all — an
    unquantised radius has a lap time but not a note (§2.1)."""
    measured = {}
    for rung in LOOP_LADDER:
        a = Assembly()
        a.add_loop((600.0, 600.0), rung.radius, rung=rung)
        net = a.compile(max_energy=None)
        graph = a.to_graph()
        if not graph.edges:
            note(f"{rung.name}: does not compile at all")
            continue
        node_id = next(iter(graph.nodes))
        drawn = graph.edges[0].length
        net.step({node_id: 0.1})
        lap = _first_arrival(net, node_id, max_steps=1000, threshold=1e-6)
        measured[rung.name] = lap
        err = 100.0 * (lap / rung.lap_samples - 1.0)
        note(
            f"{rung.name:<8} r={rung.radius:6.2f}  nominal {rung.lap_samples:5.1f} samples/lap"
            f"  drawn {drawn / DX:6.2f}  measured {lap:4d}  ({err:+5.1f}%)"
            f"{'' if rung.drawable else '   <- gate rung, not placeable'}"
        )

    exact = [r.name for r in DRAWABLE_RUNGS if measured.get(r.name) == round(r.lap_samples)]
    check(
        f"LOOP: lap time is circumference/c, exactly, on every placeable rung"
        f" ({len(exact)}/{len(DRAWABLE_RUNGS)})",
        len(exact) == len(DRAWABLE_RUNGS),
    )
    check(
        "LOOP: and the rung below the bottom of the ladder is the one that misses,"
        " which is why it is not placeable",
        measured.get(GATE_RUNG.name) != round(GATE_RUNG.lap_samples)
        and snap_radius(GATE_RUNG.radius) is not GATE_RUNG,
    )

    a = Assembly()
    a.add_loop((600.0, 600.0), LOOP_LADDER[2].radius)
    net = a.compile(max_energy=None)
    node_id = next(iter(a.to_graph().nodes))
    net.step({node_id: 0.1})
    for _ in range(20 * int(LOOP_LADDER[2].lap_samples)):
        net.step()
    still_going = net.total_energy()
    note(f"hum loop after 20 laps still holds {still_going:.3e} (injected onto the wire, then untouched)")
    check("LOOP: it laps forever - energy is still circulating after 20 laps", still_going > 0.0)

    half = measured.get("chirp")
    full = measured.get("ping")
    if half and full:
        note(f"a loop half the size laps {full / half:.3f}x as fast ({full} vs {half} steps)")
        check("LOOP: half the size laps twice as fast", close(full / half, 2.0, tol=1e-9))
    else:
        check("LOOP: half the size laps twice as fast", False)


def test_fork_goes_both_ways() -> None:
    """FORK, section 4: *a signal that hits a split goes both ways, half as
    bright each.* Junction scattering is by admittance (§2.3), and the general
    formula for N equal ports is (2-N)/N reflected and 2/N transmitted. At a
    fork, N is 3."""
    a = _fork_assembly(ink=LOSSLESS)
    net = a.compile(max_energy=None)
    graph = a.to_graph()
    fork = next(nid for nid, n in graph.nodes.items() if n.degree >= 3)
    incident = [eid for eid, e in net.edges.items() if fork in (e.node_a, e.node_b)]
    source, branches = incident[0], incident[1:]

    _make_incident(net.edges[source], fork, 1.0)
    net.step()

    r = _outgoing(net.edges[source], fork)
    t = [_outgoing(net.edges[b], fork) for b in branches]
    u_in = t[0] - r  # t is u_j; r is u_j - u_in

    amp = [x / u_in for x in t]
    back = r / u_in
    energy = [x * x for x in amp]
    note(f"3-way fork: amplitude {amp[0]:.4f} and {amp[1]:.4f} out, {back:+.4f} back")
    note(f"            energy    {energy[0]:.4f} and {energy[1]:.4f} out, {back * back:.4f} back")
    note(f"            accounted: {energy[0] + energy[1] + back * back:.6f} of 1")

    check("FORK: it goes both ways, evenly", close(amp[0], amp[1], tol=1e-12))
    check("FORK: nothing is created at the junction", close(sum(energy) + back * back, 1.0, tol=1e-12))
    # 4's original sentence said "half as bright each" and was wrong. The
    # corrected sentence -- "shares itself out between the ways on, and a
    # little bounces back" -- is what is asserted now, so this check tests
    # the design as written rather than as first guessed. See 4.0.
    check(
        f"FORK: it shares out between the ways on - {energy[0]:.4f} each of three,"
        f" not the 0.5 the first draft claimed",
        close(energy[0], 2.0 / 9.0 * 2.0, tol=0.01),
    )
    check(
        f"FORK: and a little bounces back - {back * back:.4f} returns the way it came,"
        f" which the first draft did not mention at all",
        back * back > 0.05,
    )
    note("the sentence is true only for a 4-way junction, where 2/N is exactly 1/2:")
    for n in (3, 4, 5):
        note(f"  N={n}: amplitude {2 / n:.4f} per branch, energy {(2 / n) ** 2:.4f}, reflected {((2 - n) / n) ** 2:.4f}")


def test_gap_jumps_only_if_strong_enough() -> None:
    """GAP, section 4: *a signal jumps a gap only if it is strong enough.* It is
    emphatic about why: "GAP is a gate, not a leak. In the old build a coupler
    was a leaky wire - a matter of degree, therefore invisible, therefore
    indistinguishable from a direct join. As a threshold it is categorical."
    """
    ratios = []
    for amplitude in (1e-3, 1e-2, 1e-1, 1.0, 1e1, 1e2, 1e3):
        a = _two_runs(12.0)
        net = a.compile(max_energy=None)
        src = a.node_at((100.0, 100.0))
        _inject(net, src, amplitude)
        far = net.edges[1]
        peak = 0.0
        for _ in range(600):
            net.step()
            peak = max(peak, _peak_amplitude(far))
        ratios.append(peak / amplitude)
        note(f"drive {amplitude:<8g} -> {peak / amplitude:.6f} of it crosses a 12 px gap")

    spread = max(ratios) / min(ratios)
    note(f"crossing fraction over six decades of drive: spread {spread:.6f}x (a gate would be thousands)")
    # The bare coupler has no threshold and this check now asserts that,
    # because it is the measured truth and the reason `cavitation.py` exists.
    # The gate lives there, on top of this; `selftest_cavitation` proves it.
    check(
        "GAP: the bare coupler is linear - no threshold anywhere in six decades"
        " (the gate is cavitation, see selftest_cavitation)",
        spread < 1.01,
    )

    joined = _two_runs(4.0)
    net = joined.compile(max_energy=None)
    src = joined.node_at((100.0, 100.0))
    e_in = _inject(net, src, 1.0)
    far_join = 0.0
    for _ in range(600):
        net.step()
        far_join = max(far_join, net.edges[1].total_energy())
    note(f"a join (ends {4.0} px apart, so snapped) delivers {far_join / e_in:.4f} of the energy across")

    crossings = []
    for gap in (JOIN_EPS, 12.0, 20.0, GAP_MAX - 0.5):
        a = _two_runs(gap)
        net = a.compile(max_energy=None)
        src = a.node_at((100.0, 100.0))
        e_in = _inject(net, src, 1.0)
        far = 0.0
        for _ in range(600):
            net.step()
            far = max(far, net.edges[1].total_energy())
        note(f"a {gap:>4.1f} px gap delivers {far / e_in:.6f} - {far_join / max(far, 1e-30):.0f}x less than the join")
        crossings.append(far / e_in)
    check(
        "GAP: it is never mistakable for a join (the widest coupling is still an order down)",
        max(crossings) * 4.0 < far_join / e_in,
    )

    # There is exactly one amplitude-dependent element in the whole network -
    # the saturating junction sited on loop-closing edges (§2.6) - so if any
    # threshold behaviour exists anywhere, a gap hanging off a driven loop is
    # where it would show. It shows the opposite.
    ratios = []
    for amplitude in (0.01, 30.0):
        a = Assembly()
        rung = snap_radius(51.0)
        a.add_loop((400.0, 400.0), rung.radius)
        a.add_run((400.0 + rung.radius, 400.0), (700.0, 400.0))
        a.add_run((712.0, 400.0), (860.0, 400.0))
        net = a.compile(max_energy=None)
        graph = a.to_graph()
        stub = next(
            eid
            for eid, e in enumerate(graph.edges)
            if graph.nodes[e.node_a].is_terminal and graph.nodes[e.node_b].is_terminal
        )
        loop_node = next(
            nid for nid, n in graph.nodes.items() if n.degree >= 3
        )
        _inject(net, loop_node, amplitude)
        peak = 0.0
        for _ in range(1200):
            net.step()
            peak = max(peak, _peak_amplitude(net.edges[stub]))
        ratios.append(peak / amplitude)
        note(f"loop driven at {amplitude:<6g} -> {peak / amplitude:.6f} of it crosses the gap past it")
    note(
        f"driving the loop {30.0 / 0.01:.0f}x harder changes the crossing fraction by"
        f" {ratios[1] / ratios[0]:.3f}x - saturation makes a gap harder to jump, not easier"
    )
    check(
        "GAP: and saturation cannot supply one - driving a loop harder makes"
        " LESS cross, not more, so the gate could not have come from the sim",
        ratios[1] < ratios[0],
    )


def test_mouth_is_the_only_part_that_touches_the_water() -> None:
    """MOUTH, section 4: *the only part that touches the water* - and section
    9.5, *failure must be visible*. A scribble that reaches no mouth must do
    nothing at all, not a little."""
    a = Assembly()
    a.add_run((100.0, 100.0), (400.0, 100.0))
    net = a.compile(max_energy=None)
    src = a.node_at((100.0, 100.0))
    e_in = _inject(net, src, 1.0)
    radiated = sum(net.step() for _ in range(4000))
    note(f"open run: {radiated / e_in:.4f} of the energy on the wire left through its two mouths")
    check("MOUTH: a free end radiates", radiated > 0.0)

    a = Assembly()
    a.add_loop((600.0, 600.0), LOOP_LADDER[2].radius)
    net = a.compile(max_energy=None)
    node_id = next(iter(a.to_graph().nodes))
    e_in = _inject(net, node_id, 1.0)
    radiated_closed = sum(net.step() for _ in range(4000))
    note(f"closed ring: {radiated_closed:.3e} radiated from {e_in:.4f} on the wire, over 4000 steps")
    check("MOUTH: a closed assembly with no free end radiates nothing", radiated_closed == 0.0)
    check("MOUTH: and the energy is still in there, going round", net.total_energy() > 0.0)


def test_the_three_emergent_parts_emerge() -> None:
    """EMERGENCE: three of the five parts are never placed. They are what an
    arrangement *is*."""
    a = _fork_assembly()
    note(f"three runs to one point: {a.describe()}")
    check("EMERGENCE: three run ends at a point make exactly one fork", len(a.forks()) == 1)
    check("EMERGENCE: and exactly three mouths", len(a.mouths()) == 3)
    check("EMERGENCE: and no gap and no loop", not a.gaps() and not a.loops())

    a = _two_runs(12.0)
    note(f"two runs 12 px apart: {a.describe()}")
    check("EMERGENCE: two runs placed near but not touching make one gap", len(a.gaps()) == 1)
    check("EMERGENCE: and four mouths", len(a.mouths()) == 4)
    check("EMERGENCE: and no fork", not a.forks())

    a = Assembly()
    a.add_loop((600.0, 600.0), 51.0)
    note(f"one ring: {a.describe()}")
    check("EMERGENCE: a ring is one loop", len(a.loops()) == 1)
    check("EMERGENCE: with no mouth and no fork", not a.mouths() and not a.forks())


def test_snapping_is_never_ambiguous() -> None:
    """SNAPPING, section 9.2: *nothing ambiguous in the middle.* Ends are joined
    or gapped. Sweep the distance and confirm every single one of them is
    exactly one of the two, and that the boundary is where it is claimed."""
    both, neither = [], []
    joined_max, gap_min, gap_max_seen = 0.0, None, 0.0
    d = 0.0
    while d <= 40.0:
        a = _two_runs(d)
        graph = a.to_graph()
        n_gaps = len(a.gaps())
        # A join is a topological fact: the two runs became one component
        # through a shared node, so there are 3 nodes and 2 mouths, not 4.
        is_join = len(graph.nodes) == 3 and len(a.mouths()) == 2
        is_gap = n_gaps == 1
        is_unrelated = not is_join and not is_gap
        if is_join and is_gap:
            both.append(d)
        if is_unrelated and d < GAP_MAX:
            neither.append(d)
        if is_join:
            joined_max = max(joined_max, d)
        if is_gap:
            gap_min = d if gap_min is None else min(gap_min, d)
            gap_max_seen = max(gap_max_seen, d)
        d = round(d + 0.25, 4)

    note(f"joined out to {joined_max:.2f} px; gapped from {gap_min:.2f} to {gap_max_seen:.2f} px; nothing past that")
    note(f"JOIN_EPS={JOIN_EPS} GAP_MAX={GAP_MAX} - the bands touch, so the boundary has no width")
    check("SNAP: no separation is both a join and a gap", not both)
    check("SNAP: no separation under GAP_MAX is neither", not neither)
    check("SNAP: the join band ends where the gap band begins", joined_max < JOIN_EPS <= gap_min)

    # The boundary has to be visible, not just decidable. A join snaps the
    # placed geometry, so either side of it the drawing itself jumps by the
    # whole of JOIN_EPS - which is the answer to "there must be no distance at
    # which the player cannot tell which they made".
    tight = _two_runs(JOIN_EPS - 0.25)
    drawn_when_joined = (tight.parts[1].p0 - tight.parts[0].p1).length()
    loose = _two_runs(JOIN_EPS + 0.25)
    drawn_when_gapped = (loose.parts[1].p0 - loose.parts[0].p1).length()
    note(
        f"placed 0.25 px inside the boundary the ends draw {drawn_when_joined:.2f} px apart;"
        f" 0.25 px outside it they draw {drawn_when_gapped:.2f} px apart"
    )
    check(
        "SNAP: a join moves the geometry, so the boundary is a jump and not a hair",
        drawn_when_joined == 0.0 and drawn_when_gapped >= JOIN_EPS,
    )


def test_you_can_name_what_you_drew() -> None:
    """NAMING, section 9.6: *you must be able to name what you drew.* "If the only
    description is 'a squiggle', the system has already failed." """
    cases = []

    a = Assembly()
    cases.append(("nothing placed at all", a, "nothing placed"))

    a = Assembly()
    a.add_run((100.0, 100.0), (100.0 + MIN_RUN_LENGTH / 2.0, 100.0))
    cases.append(("one run under the minimum length", a, "too short"))

    a = Assembly()
    a.add_run((100.0, 100.0), (400.0, 100.0))
    cases.append(("one run", a, "run"))

    a = Assembly()
    a.add_loop((600.0, 600.0), 51.0)
    cases.append(("one ring, touching nothing", a, "loop"))

    a = _fork_assembly()
    cases.append(("three runs to a point", a, "fork"))

    a = _two_runs(12.0)
    cases.append(("two runs, gapped", a, "gapped"))

    a = Assembly()
    rung = snap_radius(51.0)
    a.add_loop((400.0, 400.0), rung.radius)
    a.add_run((400.0 + rung.radius, 400.0), (700.0, 400.0))
    a.add_run((712.0, 400.0), (760.0, 400.0))
    cases.append(("the sentence from section 9.6 itself", a, "fork into"))

    a = Assembly()
    a.add_run((100.0, 600.0), (300.0, 600.0))
    a.add_run((300.0, 600.0), (200.0, 700.0))
    a.add_run((200.0, 700.0), (100.0, 600.0))
    cases.append(("three runs closed into a ring", a, "loop"))

    a = Assembly()
    for i in range(7):
        a.add_run((100.0 + 90 * i, 700.0), (150.0 + 90 * i, 800.0))
        a.add_loop((120.0 + 90 * i, 900.0), 12.7)
    cases.append(("fourteen parts scattered about", a, "too much to name"))

    for label, assembly, expected in cases:
        sentence = assembly.describe()
        note(f"{label:<34} -> \"{sentence}\"")
        check(f"NAME: {label} is nameable", expected in sentence and "squiggle" not in sentence)


def test_energy_is_never_created() -> None:
    """ENERGY, section 3.2: *nothing else happens to it.*

    One injection halves at every fork, dims along every run, loses a little
    per lap in a loop, and leaves at a mouth. The point of the rule is that
    "why did that not work" becomes answerable by counting."""
    a = _fork_assembly(ink=LOSSLESS)
    net = a.compile(max_energy=None)
    src = a.mouth_nodes()[0][0]
    e_in = _inject(net, src, 1.0)
    radiated = sum(net.step() for _ in range(6000))
    remaining = net.total_energy()
    note(f"lossless fork: on the wire {e_in:.9f} -> radiated {radiated:.9f} + left {remaining:.3e}")
    check(
        "ENERGY: with lossless ink, every unit that goes in comes out of a mouth",
        close(radiated + remaining, e_in, tol=1e-9),
    )

    a = _fork_assembly()
    net = a.compile(max_energy=None)
    src = a.mouth_nodes()[0][0]
    e_in = _inject(net, src, 1.0)
    radiated = sum(net.step() for _ in range(6000))
    remaining = net.total_energy()
    absorbed = e_in - radiated - remaining
    note(
        f"real ink, 3 runs of 200 px and one fork - of {e_in:.4f} on the wire:"
        f" {100 * radiated / e_in:5.1f}% left at mouths,"
        f" {100 * absorbed / e_in:5.1f}% dimmed along the runs,"
        f" {100 * remaining / e_in:5.1f}% still in flight"
    )
    check("ENERGY: nothing is created (radiated + left + absorbed accounts for all of it)", absorbed >= -1e-12)
    check("ENERGY: and every bucket is somewhere it is allowed to be", radiated >= 0.0 and remaining >= 0.0)


def test_pulse_render_is_a_travelling_blob() -> None:
    """PULSE, section 9.4: *render a discrete travelling blob, not a glow.* It is
    the delay-line contents laid on the polyline, so this checks that the blob
    is in the right place at the right time and going the right way."""
    a = Assembly()
    a.add_run((100.0, 100.0), (500.0, 100.0))
    net = a.compile(max_energy=None)
    src = a.node_at((100.0, 100.0))
    net.step({src: 1.0})

    positions = []
    for _ in range(4):
        for _ in range(20):
            net.step()
        pts = pulse_samples(net, a, max_points_per_edge=100)
        peak = max(pts, key=lambda p: abs(p[2]))
        positions.append(peak[0])
    note(f"blob x every 20 steps (80 px of travel each): {[round(x, 1) for x in positions]}")
    check("PULSE: the blob moves along the run at one sample per step", all(
        abs((positions[i + 1] - positions[i]) - 80.0) < 8.0 for i in range(len(positions) - 1)
    ))
    check("PULSE: and it moves away from the end it was injected into", positions[0] > 100.0)

    directed = pulse_samples_directed(net, a, max_points_per_edge=100)
    outbound = [p for p in directed if p[3] > 0 and abs(p[2]) > 1e-6]
    check("PULSE: both directions are reported separately for the renderer", bool(outbound))

    for _ in range(300):
        net.step()
    returning = [p for p in pulse_samples_directed(net, a, 100) if p[3] < 0 and abs(p[2]) > 1e-6]
    check("PULSE: a reflection comes back down the other line", bool(returning))


def test_performance_against_the_frame_budget() -> None:
    """The bench runs this alongside the front propagator, so the number that
    matters is what fraction of 16.67 ms one step costs."""
    a = Assembly()
    for i in range(6):
        a.add_run((100.0 + 120 * i, 200.0), (160.0 + 120 * i, 320.0))
    a.add_loop((300.0, 500.0), 51.0)
    a.add_loop((520.0, 500.0), 25.5)
    a.add_run((300.0 + 50.93, 500.0), (480.0, 500.0))
    a.add_run((100.0, 700.0), (600.0, 700.0))

    t0 = time.perf_counter()
    net = a.compile()
    compile_ms = 1000.0 * (time.perf_counter() - t0)
    graph = a.to_graph()

    src = a.mouth_nodes()[0][0]
    _inject(net, src, 1.0)

    steps = 2000
    t0 = time.perf_counter()
    for _ in range(steps):
        net.step()
    step_ms = 1000.0 * (time.perf_counter() - t0) / steps

    t0 = time.perf_counter()
    for _ in range(200):
        pulse_samples(net, a, max_points_per_edge=64)
    render_ms = 1000.0 * (time.perf_counter() - t0) / 200.0

    note(
        f"{len(a.parts)} parts -> {len(graph.nodes)} nodes, {len(graph.edges)} edges,"
        f" {len(net.couplers)} couplers; compile {compile_ms:.1f} ms"
    )
    note(f"{step_ms * 1000:.1f} us/step = {100 * step_ms / 16.67:.2f}% of a 60 Hz frame at 1 step/frame")
    note(f"pulse_samples costs {render_ms:.3f} ms, {100 * render_ms / 16.67:.1f}% of a frame")
    note(f"headroom: {int(16.67 / (step_ms + render_ms))} sim steps per frame including the render")
    check("PERF: one step plus one render fits inside a 60 Hz frame", step_ms + render_ms < 16.67)


def main() -> None:
    tests = [
        test_run_takes_time_to_cross,
        test_loop_laps_forever_at_its_note,
        test_fork_goes_both_ways,
        test_gap_jumps_only_if_strong_enough,
        test_mouth_is_the_only_part_that_touches_the_water,
        test_the_three_emergent_parts_emerge,
        test_snapping_is_never_ambiguous,
        test_you_can_name_what_you_drew,
        test_energy_is_never_created,
        test_pulse_render_is_a_travelling_blob,
        test_performance_against_the_frame_budget,
    ]
    for test in tests:
        print(f"\n--- {test.__doc__.splitlines()[0].strip()}")
        test()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for name in FAILURES:
            print(f"  - {name}")
        raise SystemExit(1)
    print("all checks passed.")


if __name__ == "__main__":
    main()
