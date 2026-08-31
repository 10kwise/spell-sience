"""Stage 6 (§9): chirality. A clockwise-drawn loop and a counterclockwise
one must produce opposite-signed chi_b, and an open shape with no loop must
default to +1 everywhere (§2.8: chirality is a property of loops, so an
un-looped shape has no sign to read — but it still must not silence the
kinetic/thermal coupling that consumes this vector as a signed multiplier;
see the comment in cycles.compute_chirality for why 0.0 would be a bug).

Run with:

    python -m sigilwave.sim.selftest_chirality
"""

import pygame

from ..ink import DEFAULT_INK
from ..ink import Stroke
from .cycles import compute_chirality
from .filterbank import FilterBank
from .parser import parse_strokes


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def make_circle_points(center: pygame.Vector2, radius: float, n: int, clockwise: bool) -> list:
    sign = 1.0 if clockwise else -1.0  # screen space: +y is down, so this is the actual on-screen winding
    return [center + pygame.Vector2(radius, 0).rotate(sign * 360.0 * i / n) for i in range(n + 1)]


def test_cw_and_ccw_circles_have_opposite_chirality() -> None:
    dx = 4.0
    band_centers = FilterBank().centers

    cw_stroke = Stroke(points=make_circle_points(pygame.Vector2(400, 300), 80.0, 48, clockwise=True), ink_type=DEFAULT_INK)
    ccw_stroke = Stroke(points=make_circle_points(pygame.Vector2(400, 300), 80.0, 48, clockwise=False), ink_type=DEFAULT_INK)

    cw_graph = parse_strokes([cw_stroke], dx)
    ccw_graph = parse_strokes([ccw_stroke], dx)

    cw_chi = compute_chirality(cw_graph, band_centers, dx)
    ccw_chi = compute_chirality(ccw_graph, band_centers, dx)

    check(f"CW circle chirality is consistently one sign: {[round(c, 2) for c in cw_chi]}", all(c >= 0 for c in cw_chi) or all(c <= 0 for c in cw_chi))
    check(f"CCW circle chirality is the opposite sign of CW: {[round(c, 2) for c in ccw_chi]}", all(c1 * c2 <= 0 for c1, c2 in zip(cw_chi, ccw_chi) if c1 != 0 or c2 != 0))

    max_abs = max(abs(c) for c in cw_chi)
    check(f"chirality actually engages near the loop's resonant band (max |chi|={max_abs:.2f})", max_abs > 0.3)


def test_open_line_defaults_to_positive_chirality() -> None:
    """Not 0.0 — see the comment in cycles.compute_chirality. A literal zero
    here would silence kinetic push and thermal burn for every un-looped
    shape once coupling.py multiplies band energy by this vector, which
    would make stage 5's own straight-line 'something moves' demo go dead
    the moment stage 6's chirality wiring lands on top of it."""
    dx = 4.0
    band_centers = FilterBank().centers
    stroke = Stroke(points=[pygame.Vector2(100, 100), pygame.Vector2(500, 100)], ink_type=DEFAULT_INK)
    graph = parse_strokes([stroke], dx)

    chi = compute_chirality(graph, band_centers, dx)
    check(f"open line (no loop) defaults to +1 chirality everywhere: {chi}", all(c == 1.0 for c in chi))


def main() -> None:
    for test in [test_cw_and_ccw_circles_have_opposite_chirality, test_open_line_defaults_to_positive_chirality]:
        test()
    print("\n2 checks passed.")


if __name__ == "__main__":
    main()
