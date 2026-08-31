"""Stroke generators for authored sigils — starters, enemies, drops.

These exist because a sigil's *geometry* is its statistics: circumference
sets the band, winding sets the chirality sign, gap width sets the tunnel.
Anything the game wants to author has to be authored as a shape, and then
it goes through exactly the same parser and compiler a hand-drawn stroke
does. There is no second path for "designed" sigils.

`ring_with_tail` is the workhorse and is deliberately dense. The project's
own experiment harness has a generator whose loop-closure detection is
fragile outside a narrow radius range at its default vertex count, which is
a fine limitation for a bench script and a terrible one for content that
ships: a boss whose ring silently fails to close loses its resonance, its
chirality and its whole identity with no visible symptom. Here the point
count scales with the arc length and the ring is explicitly closed back
onto its own first point, so the parser snaps it every time.
"""

import math

import pygame

from .sigil import DX


def _dense(n_hint: float, minimum: int = 12) -> int:
    """Enough vertices that resampling at DX never skips a feature."""
    return max(minimum, int(n_hint / max(1.0, DX * 0.5)))


def ring_points(center, radius: float, clockwise: bool = True, closed: bool = True) -> list:
    cx, cy = center
    circumference = 2 * math.pi * radius
    n = _dense(circumference)
    direction = 1.0 if clockwise else -1.0
    pts = []
    span = n + 1 if closed else n
    for i in range(span):
        a = direction * 2 * math.pi * (i / n)
        pts.append(pygame.Vector2(cx + radius * math.cos(a), cy + radius * math.sin(a)))
    if closed:
        # Land exactly on the start so the parser cannot miss the closure.
        pts[-1] = pygame.Vector2(pts[0])
    return pts


def ring_with_tail(center, radius: float, tail_length: float, attach_deg: float = 0.0,
                   clockwise: bool = True) -> list:
    """A closed loop that resonates, plus an open end that can actually
    radiate. A bare ring has no terminal, so it stores energy beautifully
    and emits none of it — the first thing every new player builds, and the
    first thing that teaches them what a terminal is for.

    The tail leaves *radially outward* from where it attaches. Sending it in
    an arbitrary direction sounds harmless and is not: any other angle drags
    the tail back across the ring's own interior, the parser correctly snaps
    the crossings into extra junctions, and the single clean resonator
    becomes two short arcs that ring at the wrong frequency. The symptom is
    an enemy or a starter sigil quietly emitting in the wrong band.
    """
    cx, cy = center
    a = math.radians(attach_deg)
    outward = pygame.Vector2(math.cos(a), math.sin(a))
    attach = pygame.Vector2(cx, cy) + outward * radius

    # Start the ring at the attachment point so the loop closes exactly
    # where the tail leaves, giving one clean degree-3 junction.
    circumference = 2 * math.pi * radius
    n = _dense(circumference)
    direction = 1.0 if clockwise else -1.0
    pts = []
    for i in range(n + 1):
        theta = a + direction * 2 * math.pi * (i / n)
        pts.append(pygame.Vector2(cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
    pts[-1] = pygame.Vector2(attach)

    m = _dense(tail_length, 6)
    for i in range(1, m + 1):
        pts.append(attach + outward * (tail_length * i / m))
    return pts


def line_points(p0, p1) -> list:
    a, b = pygame.Vector2(p0), pygame.Vector2(p1)
    n = _dense((b - a).length(), 6)
    return [a.lerp(b, i / n) for i in range(n + 1)]


def arc_points(center, radius: float, a0_deg: float, a1_deg: float) -> list:
    cx, cy = center
    span = abs(a1_deg - a0_deg)
    n = _dense(2 * math.pi * radius * span / 360.0, 8)
    pts = []
    for i in range(n + 1):
        a = math.radians(a0_deg + (a1_deg - a0_deg) * i / n)
        pts.append(pygame.Vector2(cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return pts


def radius_for_band_px(loop_px: float) -> float:
    """Circumference to radius. Bands are specified as a circumference in
    the band table because that is the quantity physics cares about; every
    drawing tool wants a radius."""
    return loop_px / (2 * math.pi)


def bounds_of(strokes) -> pygame.Rect:
    xs, ys = [], []
    for s in strokes:
        for p in s.points:
            xs.append(p.x)
            ys.append(p.y)
    if not xs:
        return pygame.Rect(0, 0, 0, 0)
    return pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
