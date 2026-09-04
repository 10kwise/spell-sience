"""Stage 7 (§9): evanescent coupling / tunneling. Checks the specific
consequences claimed in §2.7: a coupler never creates energy, a wider gap
(smaller kappa) transmits less, and — for a fixed gap — long wavelengths
tunnel further than short ones (the frequency-dependent lowpass in the
cross path).

Run with:

    python -m sigilwave.sim.selftest_couplers
"""

import math

import numpy as np
import pygame

from ..ink import DEFAULT_INK, Stroke
from .compiler import compile_graph
from .network import Network, raised_cosine_burst
from .parser import parse_strokes

LOW_FREQ = 0.01
HIGH_FREQ = 0.2


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def measure_tunneled_energy(kappa: float, lowpass_coef: float, freq: float, length: int = 60) -> float:
    """Two otherwise-disconnected edges, coupled only via a Coupler at their
    midpoints. Inject a tone into edge A; measure what a matched terminal on
    edge B actually absorbs."""
    net = Network()
    net.add_node(0)  # edge A: free end, injection
    net.add_node(1)  # edge A: free end
    y_rad = 1.0 / 50.0
    net.add_node(2, rad_admittance=y_rad)  # edge B: matched, absorbs + lets us measure
    net.add_node(3)  # edge B: free end

    net.add_edge(0, 1, length, impedance=50.0)
    net.add_edge(2, 3, length, impedance=50.0)
    net.add_coupler(0, length // 2, 1, length // 2, kappa, lowpass_coef)

    warmup = length + 300
    total = warmup + 2000
    radiated = np.empty(total)
    for i in range(total):
        radiated[i] = net.step({0: math.sin(2 * math.pi * freq * i)})

    mean_u_j_sq = float(np.mean(radiated[warmup:])) / y_rad
    return math.sqrt(max(0.0, mean_u_j_sq))


def test_coupler_never_creates_energy() -> None:
    net = Network()
    net.add_node(0)
    net.add_node(1)
    net.add_node(2)
    net.add_node(3)
    net.add_edge(0, 1, 40, impedance=50.0)
    net.add_edge(2, 3, 40, impedance=50.0)
    net.add_coupler(0, 20, 1, 20, kappa=0.7, lowpass_coef=0.3)

    for i in range(20):
        net.step({0: math.sin(2 * math.pi * 0.1 * i), 2: math.cos(2 * math.pi * 0.13 * i)})

    energy_after_injection = net.total_energy()
    max_drift = 0.0
    for _ in range(2000):
        net.step()
        max_drift = max(max_drift, net.total_energy() - energy_after_injection)

    check(
        f"coupled network never gains energy over 2000 steps (max increase {max_drift:.2e})",
        max_drift < 1e-9,
    )


def test_wider_gap_transmits_less() -> None:
    # Smaller kappa stands in for a wider gap (§2.7's gap->kappa mapping).
    close = measure_tunneled_energy(kappa=0.6, lowpass_coef=0.5, freq=LOW_FREQ)
    far = measure_tunneled_energy(kappa=0.15, lowpass_coef=0.5, freq=LOW_FREQ)
    check(
        f"a tighter coupling (larger kappa) transmits more than a looser one (close={close:.4f}, far={far:.4f})",
        close > far * 2,
    )


def test_long_wavelength_tunnels_further() -> None:
    # A coupler's filter only fires once per step (unlike edge damping, which
    # compounds over every sample the wave travels), so it takes a more
    # aggressive coefficient to show clean separation over just one hop.
    low = measure_tunneled_energy(kappa=0.4, lowpass_coef=0.03, freq=LOW_FREQ)
    high = measure_tunneled_energy(kappa=0.4, lowpass_coef=0.03, freq=HIGH_FREQ)
    check(
        f"for the same gap, low frequency tunnels through better than high (low={low:.4f}, high={high:.4f})",
        low > 3 * high,
    )


def test_full_pipeline_detects_coupler_between_nearby_strokes() -> None:
    """Two separate strokes, drawn close but never touching, should compile
    to a network with a real Coupler joining them — no manual wiring."""
    dx = 4.0
    stroke_a = Stroke(points=[pygame.Vector2(0, 0), pygame.Vector2(300, 0)], ink_type=DEFAULT_INK)
    stroke_b = Stroke(points=[pygame.Vector2(0, 15), pygame.Vector2(300, 15)], ink_type=DEFAULT_INK)

    graph = parse_strokes([stroke_a, stroke_b], dx)
    check("two nearby-but-separate strokes stay two edges (not merged into one)", len(graph.edges) == 2)

    net = compile_graph(graph, dx)
    check(f"compiling detected a coupler between them ({len(net.couplers)} found)", len(net.couplers) == 1)

    terminals = [nid for nid, n in graph.nodes.items() if n.is_terminal]
    stroke_a_terminals = [t for t in terminals if graph.nodes[t].pos.y < 5]
    stroke_b_terminals = [t for t in terminals if graph.nodes[t].pos.y > 5]
    inject_id = stroke_a_terminals[0]
    y_rad = 1.0 / DEFAULT_INK.impedance
    listen_candidates = [t for t in stroke_b_terminals]
    listen_id = listen_candidates[0]
    net.nodes[listen_id].rad_admittance = y_rad  # matched, so we can measure what tunnels across cleanly

    burst = raised_cosine_burst(24, amplitude=1.0)
    total_radiated = 0.0
    for i in range(3000):
        injections = {inject_id: burst[i]} if i < len(burst) else {}
        total_radiated += net.step(injections)

    check(f"energy actually tunneled from stroke A to stroke B (total={total_radiated:.6f})", total_radiated > 1e-6)


def main() -> None:
    tests = [
        test_coupler_never_creates_energy,
        test_wider_gap_transmits_less,
        test_long_wavelength_tunnels_further,
        test_full_pipeline_detects_coupler_between_nearby_strokes,
    ]
    for test in tests:
        test()
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
