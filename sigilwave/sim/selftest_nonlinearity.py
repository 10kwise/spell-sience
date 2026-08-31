"""Stage 8 (§9), last and riskiest of the physical-model stages (§2.6, §8).
Checks: driving hard produces both even and odd harmonics, removing the
asymmetry (d=0) suppresses the even one specifically (the whole reason d
exists), and the exact stress case §8 names by name — many nested loops,
max drive, lowest threshold ink — staying bounded instead of diverging.

Note: "stays linear at low amplitude" turned out not to be a clean thing to
assert here. A closed loop driven at its own resonance builds amplitude far
past the injected level (that's the intended "repeated tapping" mechanic,
§4.3) — so a "gentle" injection can still reach a meaningfully distorted
steady state, and harmonic *ratios* don't move monotonically with drive
amplitude in a resonant nonlinear system (mode competition between the
directly-driven fundamental and the nonlinearity feeding the ring's own
2nd-harmonic resonant mode). That's real emergent behavior, not a bug —
matches the doc's own "deepest well... last thing to tune" framing — so the
checks below stick to the specific, unambiguous claims §2.6 actually makes.

Run with:

    python -m sigilwave.sim.selftest_nonlinearity
"""

import math

import numpy as np
import pygame

from ..ink import InkType, Stroke
from .compiler import compile_graph
from .network import Network
from .parser import parse_strokes


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def make_circle_points(center: pygame.Vector2, radius: float, n: int) -> list:
    return [center + pygame.Vector2(radius, 0).rotate(360.0 * i / n) for i in range(n + 1)]


def _drive_circle_and_record(ink: InkType, drive_amplitude: float, n_record: int = 4000):
    """A short broadband burst would excite *every* integer harmonic of the
    ring's own resonance regardless of nonlinearity (a closed loop is a
    resonator at every multiple of f0, not just f0) — verified directly:
    even with nonlinearity switched off, a burst alone leaves substantial
    energy at 2*f0. So this drives a sustained *narrowband* tone at exactly
    f0 instead (matching the doc's own 'a held tap is a narrowband tone',
    §4.3): in the linear case that stays concentrated at f0, so anything
    that shows up at 2*f0/3*f0 afterward is unambiguously the nonlinearity's
    doing.
    """
    dx = 4.0
    stroke = Stroke(points=make_circle_points(pygame.Vector2(400, 300), 80.0, 48), ink_type=ink)
    graph = parse_strokes([stroke], dx)
    net = compile_graph(graph, dx, max_energy=1e6)  # ceiling disabled for the harmonic-content checks

    edge = next(iter(net.edges.values()))
    node_id = edge.node_a
    fundamental = 1.0 / edge.forward.length

    drive_steps = 2000
    for i in range(drive_steps):
        attack = min(1.0, i / 200.0)
        net.step({node_id: drive_amplitude * attack * math.sin(2 * math.pi * fundamental * i)})

    signal = np.empty(n_record)
    for i in range(n_record):
        net.step()
        signal[i] = edge.forward.read_tail()

    return signal, fundamental


def _band_energy(signal: np.ndarray, freq: float, bandwidth: float = 0.001) -> float:
    n = len(signal)
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, d=1.0)
    mask = np.abs(freqs - freq) < bandwidth
    return float(np.sum(spectrum[mask] ** 2))


def test_hard_drive_generates_even_and_odd_harmonics() -> None:
    ink = InkType("test", nl_threshold=0.3, nl_asymmetry=0.4)
    signal, f0 = _drive_circle_and_record(ink, drive_amplitude=3.0)

    fundamental_energy = _band_energy(signal, f0)
    second = _band_energy(signal, 2 * f0)
    third = _band_energy(signal, 3 * f0)

    check(f"hard drive produces a 2nd (even) harmonic (energy ratio {second/fundamental_energy:.2e})", second > 1e-4 * fundamental_energy)
    check(f"hard drive produces a 3rd (odd) harmonic too (energy ratio {third/fundamental_energy:.2e})", third > 1e-4 * fundamental_energy)


def test_symmetric_saturation_skips_even_harmonics() -> None:
    """Sanity check on the sanity check: zero asymmetry (d=0) should behave
    like a plain symmetric tanh and suppress the even harmonic relative to
    the asymmetric case — this is the exact property §2.6 says the offset
    d exists to fix."""
    asymmetric_ink = InkType("asym", nl_threshold=0.3, nl_asymmetry=0.4)
    symmetric_ink = InkType("sym", nl_threshold=0.3, nl_asymmetry=0.0)

    asym_signal, f0 = _drive_circle_and_record(asymmetric_ink, drive_amplitude=3.0)
    sym_signal, _ = _drive_circle_and_record(symmetric_ink, drive_amplitude=3.0)

    # Normalized by each case's own fundamental energy — the two cases build
    # up to different overall amplitudes, so comparing raw 2nd-harmonic
    # energy would partly just be comparing "which one is louder overall."
    asym_ratio = _band_energy(asym_signal, 2 * f0) / _band_energy(asym_signal, f0)
    sym_ratio = _band_energy(sym_signal, 2 * f0) / _band_energy(sym_signal, f0)

    check(
        f"symmetric saturation (d=0) puts much less energy into the 2nd harmonic, relatively, "
        f"than asymmetric does (sym ratio={sym_ratio:.2e}, asym ratio={asym_ratio:.2e})",
        asym_ratio > 10 * sym_ratio,
    )


def test_pathological_sigil_stays_bounded() -> None:
    """§8's own named regression case: many nested loops, maximum drive,
    lowest-threshold ink. Should never blow up to inf/NaN thanks to the
    hard per-network energy ceiling."""
    dx = 4.0
    hot_ink = InkType("pathological", nl_threshold=0.05, nl_asymmetry=0.5, impedance=50.0)

    strokes = []
    for k in range(5):
        radius = 40.0 + 15.0 * k
        strokes.append(Stroke(points=make_circle_points(pygame.Vector2(400, 300), radius, 48), ink_type=hot_ink))

    graph = parse_strokes(strokes, dx)
    net = compile_graph(graph, dx, max_energy=50.0)

    terminals = [nid for nid, n in graph.nodes.items() if n.is_terminal]
    ignition_targets = terminals if terminals else list(graph.nodes.keys())

    max_energy_seen = 0.0
    for step in range(6000):
        injections = {nid: 10.0 * math.sin(2 * math.pi * 0.05 * step) for nid in ignition_targets}
        net.step(injections)
        e = net.total_energy()
        if not math.isfinite(e):
            check("pathological sigil stays finite (no NaN/inf) under sustained max drive", False)
            return
        max_energy_seen = max(max_energy_seen, e)

    check(
        f"pathological sigil stays finite and under the energy ceiling (peak energy {max_energy_seen:.2f}, ceiling 50.0)",
        math.isfinite(max_energy_seen),
    )
    check(
        f"energy ceiling actually held (peak {max_energy_seen:.2f} not wildly over cap)",
        max_energy_seen < 50.0 * 1.5,
    )


def test_energy_ceiling_clamps_directly() -> None:
    """The pathological-sigil test above never actually exercises the
    clamp — the nonlinearity's own saturation turned out to bound things on
    its own well before the ceiling mattered. Test the ceiling itself in
    isolation (linear network, no nonlinearity involved) so it's still
    verified as an independent safety net for whatever future feature
    doesn't have that built-in self-limiting property.
    """
    net = Network()
    net.add_node(0)
    net.add_node(1)
    net.add_edge(0, 1, length_samples=20, impedance=50.0)
    net.max_energy = 5.0

    edge = next(iter(net.edges.values()))
    edge.forward.buffer[:] = 100.0  # inject a huge amount of energy directly, bypassing normal physics
    edge.backward.buffer[:] = 100.0

    check(f"energy is huge before any step ({net.total_energy():.1f})", net.total_energy() > 1000)

    net.step()

    check(
        f"one step clamps total energy at or under the ceiling (after={net.total_energy():.3f}, ceiling=5.0)",
        net.total_energy() <= 5.0 + 1e-6,
    )


def main() -> None:
    tests = [
        test_hard_drive_generates_even_and_odd_harmonics,
        test_symmetric_saturation_skips_even_harmonics,
        test_pathological_sigil_stays_bounded,
        test_energy_ceiling_clamps_directly,
    ]
    for test in tests:
        test()
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
