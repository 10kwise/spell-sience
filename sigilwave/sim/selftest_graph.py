"""Stage 2 kill criterion (design doc §9): verify a plain circle, drawn as a
stroke and pushed through the real parser + compiler, rings at f0 = c/L.
Run with:

    python -m sigilwave.sim.selftest_graph
"""

import math

import numpy as np
import pygame

from ..ink import InkType, Stroke
from .compiler import compile_graph
from .parser import parse_strokes


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def make_circle_points(center: pygame.Vector2, radius: float, n: int) -> list:
    return [
        center + pygame.Vector2(radius, 0).rotate(360.0 * i / n)
        for i in range(n + 1)  # +1 to close the loop back near the start
    ]


def test_circle_parses_to_single_self_loop() -> None:
    dx = 4.0
    stroke = Stroke(points=make_circle_points(pygame.Vector2(400, 300), 80.0, 48), ink_type=InkType("test"))

    graph = parse_strokes([stroke], dx, snap_eps=8.0)

    check("circle parses to exactly one node", len(graph.nodes) == 1)
    check("circle parses to exactly one edge", len(graph.edges) == 1)
    edge = graph.edges[0]
    check("that edge is a self-loop", edge.node_a == edge.node_b)


def test_circle_rings_at_c_over_l() -> None:
    dx = 4.0
    radius = 80.0
    stroke = Stroke(points=make_circle_points(pygame.Vector2(400, 300), radius, 48), ink_type=InkType("test"))

    graph = parse_strokes([stroke], dx, snap_eps=8.0)
    net = compile_graph(graph, dx)

    edge = next(iter(net.edges.values()))
    node_id = edge.node_a
    length_samples = edge.forward.length
    expected_freq = 1.0 / length_samples  # cycles per sample; f0 = c/L in real units

    # Broadband tap so the resonance shows up clearly against everything else.
    burst_len = 6
    for i in range(burst_len):
        t = i / burst_len
        window = 0.5 * (1 - math.cos(2 * math.pi * t))
        net.step({node_id: window})

    n_record = 4000
    signal = np.empty(n_record)
    for i in range(n_record):
        net.step()
        signal[i] = edge.forward.read_tail()

    spectrum = np.abs(np.fft.rfft(signal * np.hanning(n_record)))
    freqs = np.fft.rfftfreq(n_record, d=1.0)  # cycles per sample
    peak_freq = freqs[np.argmax(spectrum[1:]) + 1]  # skip DC bin

    relative_error = abs(peak_freq - expected_freq) / expected_freq
    check(
        f"circle (L={length_samples} samples) rings at f0=1/L={expected_freq:.5f} "
        f"cyc/sample (measured {peak_freq:.5f}, error {relative_error:.1%})",
        relative_error < 0.05,
    )


def main() -> None:
    for test in [test_circle_parses_to_single_self_loop, test_circle_rings_at_c_over_l]:
        test()
    print("\n2 checks passed.")


if __name__ == "__main__":
    main()
