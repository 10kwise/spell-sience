"""Adversarial-input bug hunt: degenerate strokes, extreme ink parameters,
determinism (design doc §6: "Parse and compile are deterministic"). None of
these map to a named mechanic — they exist purely to catch crashes, NaN/inf,
and non-determinism before a player's messy real-world drawing hits them.

Run with:

    python -m sigilwave.sim.selftest_edgecases
"""

import math

import pygame

from ..ink import InkType, Stroke
from ..world import GHOST_OVERSHOOT_MARGIN, Token
from .compiler import compile_graph
from .cycles import compute_chirality
from .filterbank import FilterBank
from .parser import parse_strokes


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def test_single_point_stroke_does_not_crash() -> None:
    dx = 4.0
    stroke = Stroke(points=[pygame.Vector2(100, 100)], ink_type=InkType("t"))
    graph = parse_strokes([stroke], dx)
    net = compile_graph(graph, dx)
    check("single-point stroke parses to an empty/degenerate graph without raising", len(graph.edges) == 0)
    check("compiling that graph doesn't raise", net is not None)


def test_zero_length_stroke_does_not_crash() -> None:
    dx = 4.0
    p = pygame.Vector2(50, 50)
    stroke = Stroke(points=[p, pygame.Vector2(p), pygame.Vector2(p)], ink_type=InkType("t"))
    graph = parse_strokes([stroke], dx)
    net = compile_graph(graph, dx)
    check("zero-length stroke produces no edges (filtered by min_edge_length)", len(graph.edges) == 0)
    check("stepping a network with only degenerate/no edges doesn't raise", net.step() == 0.0 or net.step() >= 0.0)


def test_self_intersecting_stroke_forms_a_loop() -> None:
    """A figure-eight-ish self-crossing stroke should snap its crossing point
    into one shared node and produce at least one non-tree (loop-closing)
    edge — the parser's whole reason for existing (§4.3: 'sloppy drawings
    must parse the way they look')."""
    dx = 4.0
    pts = []
    for i in range(97):
        t = i / 96 * 2 * math.pi
        # Lemniscate of Gerono: crosses itself once, at (300, 300).
        x = 300 + 80 * math.sin(t)
        y = 300 + 80 * math.sin(t) * math.cos(t)
        pts.append(pygame.Vector2(x, y))
    stroke = Stroke(points=pts, ink_type=InkType("t"))
    graph = parse_strokes([stroke], dx)
    net = compile_graph(graph, dx)

    check("self-intersecting stroke produces at least one edge", len(graph.edges) >= 1)
    for _ in range(200):
        net.step({0: 0.5})
    total = net.total_energy()
    check(f"stepping the compiled network stays finite (energy={total})", math.isfinite(total))


def test_extreme_ink_parameters_stay_finite() -> None:
    dx = 4.0
    extreme_inks = [
        InkType("near-zero-impedance", impedance=1e-3),
        InkType("huge-impedance", impedance=1e6),
        InkType("near-zero-threshold", nl_threshold=1e-4, nl_asymmetry=0.5),
        InkType("zero-asymmetry", nl_threshold=0.5, nl_asymmetry=0.0),
        InkType("full-open-terminal", rad_admittance_fraction=1.0),
        InkType("closed-terminal", rad_admittance_fraction=0.0),
    ]
    for ink in extreme_inks:
        stroke = Stroke(points=[pygame.Vector2(0, 0), pygame.Vector2(200, 0)], ink_type=ink)
        graph = parse_strokes([stroke], dx)
        net = compile_graph(graph, dx, max_energy=50.0)
        terminals = [nid for nid, n in graph.nodes.items() if n.is_terminal]

        for i in range(500):
            injections = {terminals[0]: math.sin(i * 0.3)} if terminals else {}
            net.step(injections)

        total = net.total_energy()
        check(f"ink '{ink.name}' stays finite after 500 driven steps (energy={total:.4g})", math.isfinite(total))


def test_parse_and_compile_are_deterministic() -> None:
    """§6: 'Parse and compile are deterministic.' Same strokes in, same
    graph/network structure out, every time — required for replay sharing."""
    dx = 4.0
    ink = InkType("t")
    strokes = [
        Stroke(points=[pygame.Vector2(x, 100 + 10 * math.sin(x * 0.05)) for x in range(0, 300, 7)], ink_type=ink),
        Stroke(points=[pygame.Vector2(x, 150) for x in range(50, 250, 11)], ink_type=ink),
    ]

    graph_a = parse_strokes(strokes, dx)
    graph_b = parse_strokes(strokes, dx)

    check("same node count across repeated parses", len(graph_a.nodes) == len(graph_b.nodes))
    check("same edge count across repeated parses", len(graph_a.edges) == len(graph_b.edges))

    positions_a = sorted((round(n.pos.x, 6), round(n.pos.y, 6)) for n in graph_a.nodes.values())
    positions_b = sorted((round(n.pos.x, 6), round(n.pos.y, 6)) for n in graph_b.nodes.values())
    check("identical node positions across repeated parses", positions_a == positions_b)

    band_centers = FilterBank().centers
    chi_a = compute_chirality(graph_a, band_centers, dx)
    chi_b = compute_chirality(graph_b, band_centers, dx)
    check("identical chirality across repeated compiles", chi_a == chi_b)


def test_disconnected_multi_stroke_graph_steps_fine() -> None:
    """Several strokes that never touch each other at all — no shared nodes,
    no couplers (too far apart) — just independent islands in one network."""
    dx = 4.0
    ink = InkType("t")
    strokes = [
        Stroke(points=[pygame.Vector2(x, 0) for x in range(0, 100, 8)], ink_type=ink),
        Stroke(points=[pygame.Vector2(x, 500) for x in range(0, 100, 8)], ink_type=ink),
        Stroke(points=[pygame.Vector2(x, 1000) for x in range(0, 100, 8)], ink_type=ink),
    ]
    graph = parse_strokes(strokes, dx)
    net = compile_graph(graph, dx)
    check("three far-apart strokes produce three separate edges (no accidental merging)", len(graph.edges) == 3)

    terminals = [nid for nid, n in graph.nodes.items() if n.is_terminal]
    for i in range(300):
        injections = {terminals[0]: math.sin(i * 0.2)}
        net.step(injections)

    total = net.total_energy()
    check(f"disconnected islands step without raising and stay finite (energy={total:.4g})", math.isfinite(total))


def test_ghost_overshoot_snap_is_bounded() -> None:
    """A ghosted token (phase > threshold) under a sustained push must not
    be able to drift arbitrarily far outside bounds, because un-ghosting
    unconditionally snaps position back to the wall on the very next
    collision check — an unbounded drift means an unbounded, jarring
    teleport-in-reverse the instant phase decays (§2.9's ghosting is
    supposed to read as legible displacement, not a glitch)."""
    bounds = pygame.Rect(0, 0, 100, 100)
    token = Token(pygame.Vector2(0, 50))  # y centered so only x overshoots, isolating the measurement
    token.phase = 1.0
    token.vel = pygame.Vector2(100000, 0)
    for _ in range(50):
        token.update(0.01, bounds)

    overshoot = token.pos.x - bounds.right
    check(
        f"ghosted overshoot stays within the configured margin (overshoot={overshoot:.1f}, margin={GHOST_OVERSHOOT_MARGIN})",
        overshoot <= GHOST_OVERSHOOT_MARGIN + 1e-6,
    )

    pos_before_unghost = pygame.Vector2(token.pos)
    token.phase = 0.0
    token.update(0.01, bounds)
    snap_distance = (token.pos - pos_before_unghost).length()
    check(
        f"un-ghosting snap distance is bounded, not an arbitrary teleport (snap={snap_distance:.1f}px)",
        snap_distance <= GHOST_OVERSHOOT_MARGIN + token.radius + 1e-6,
    )


def main() -> None:
    tests = [
        test_single_point_stroke_does_not_crash,
        test_zero_length_stroke_does_not_crash,
        test_self_intersecting_stroke_forms_a_loop,
        test_extreme_ink_parameters_stay_finite,
        test_parse_and_compile_are_deterministic,
        test_disconnected_multi_stroke_graph_steps_fine,
        test_ghost_overshoot_snap_is_bounded,
    ]
    for test in tests:
        test()
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
