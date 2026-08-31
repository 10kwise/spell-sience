"""Stroke generators for authored bells - starters, foes, drops.

Anything the game authors goes through exactly the same parser and compiler
a hand-drawn stroke does. There is no second path for designed content, which
is why a foe's ring is a thing the player can measure by eye and then draw.
"""

import math

import pygame

from .notes import DX, NOTE_RADIUS


def _dense(arc: float, minimum: int = 12) -> int:
    """Enough vertices that resampling at DX never skips a feature."""
    return max(minimum, int(arc / max(1.0, DX * 0.5)))


def ring(center, radius: float, clockwise: bool = True) -> list:
    """A closed loop. This is a whole working bell on its own - the body
    radiates, so nothing has to be drawn open before it makes a sound."""
    cx, cy = center
    n = _dense(2 * math.pi * radius)
    d = 1.0 if clockwise else -1.0
    pts = [
        pygame.Vector2(cx + radius * math.cos(d * 2 * math.pi * i / n),
                       cy + radius * math.sin(d * 2 * math.pi * i / n))
        for i in range(n + 1)
    ]
    pts[-1] = pygame.Vector2(pts[0])   # land exactly on the start
    return pts


def ring_with_horn(center, radius: float, horn: float, attach_deg: float = 0.0,
                   clockwise: bool = True) -> list:
    """A ring with one open end, which biases its output that way.

    The horn leaves *radially outward*. Any other angle drags it back across
    the ring's own interior, the parser correctly snaps the crossings into
    extra junctions, and one clean resonator silently becomes two short arcs
    ringing at the wrong note.
    """
    cx, cy = center
    a = math.radians(attach_deg)
    outward = pygame.Vector2(math.cos(a), math.sin(a))
    attach = pygame.Vector2(cx, cy) + outward * radius

    n = _dense(2 * math.pi * radius)
    d = 1.0 if clockwise else -1.0
    pts = [
        pygame.Vector2(cx + radius * math.cos(a + d * 2 * math.pi * i / n),
                       cy + radius * math.sin(a + d * 2 * math.pi * i / n))
        for i in range(n + 1)
    ]
    pts[-1] = pygame.Vector2(attach)
    m = _dense(horn, 6)
    pts += [attach + outward * (horn * i / m) for i in range(1, m + 1)]
    return pts


def line(p0, p1) -> list:
    a, b = pygame.Vector2(p0), pygame.Vector2(p1)
    n = _dense((b - a).length(), 6)
    return [a.lerp(b, i / n) for i in range(n + 1)]


def ring_for_note(note: int, center=(0, 0), clockwise: bool = True) -> list:
    return ring(center, NOTE_RADIUS[max(0, min(len(NOTE_RADIUS) - 1, note))], clockwise)


def bounds_of(strokes) -> pygame.Rect:
    xs, ys = [], []
    for s in strokes:
        for p in s.points:
            xs.append(p.x)
            ys.append(p.y)
    if not xs:
        return pygame.Rect(0, 0, 0, 0)
    return pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def arc(center, radius: float, start_deg: float, sweep_deg: float) -> list:
    """A partial ring. Sweeping past 360 closes it into a whole one, which is
    what makes the sweep gesture in the Foundry work: keep going round and
    the thing you are drawing becomes a bell."""
    cx, cy = center
    sweep = max(-720.0, min(720.0, sweep_deg))
    n = _dense(2 * math.pi * radius * abs(sweep) / 360.0, 8)
    pts = []
    for i in range(n + 1):
        a = math.radians(start_deg + sweep * i / n)
        pts.append(pygame.Vector2(cx + radius * math.cos(a), cy + radius * math.sin(a)))
    if abs(sweep) >= 359.0:
        pts[-1] = pygame.Vector2(pts[0])     # land exactly, so the parser snaps
    return pts


def nearest_note_radius(radius: float, tolerance: float = 9.0):
    """Snap a radius to the note ladder. Returns (radius, snapped_index|None).

    This is the single change that makes the Foundry usable with a mouse.
    Freehand circles are hard and eyeballing 51px is harder; the ladder is
    already drawn on the canvas, so letting the cursor stick to it costs
    nothing and turns "draw a TENOR" from a test of hand steadiness into one
    gesture. Deliberate detuning is still available - you just have to mean
    it, which is the right way round.
    """
    best, bi = radius, None
    for i, r in enumerate(NOTE_RADIUS):
        if abs(radius - r) < tolerance and abs(radius - r) < abs(best - radius) + 1e9:
            best, bi = r, i
            break
    return best, bi


def stroke_distance(points, q) -> float:
    """Closest approach from a point to a polyline, for hover-picking."""
    best = 1e18
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        ab = b - a
        L2 = ab.length_squared()
        if L2 < 1e-9:
            d = (q - a).length()
        else:
            t = max(0.0, min(1.0, (q - a).dot(ab) / L2))
            d = (q - (a + ab * t)).length()
        if d < best:
            best = d
    return best


def circle_fit(points):
    """(centre, radius) of the best circle through a polyline, or None.

    Used to tell whether an existing stroke is a ring - which decides whether
    the wheel can retune it. Algebraic (Kasa) fit: cheap, and exact for the
    rings this editor produces.
    """
    n = len(points)
    if n < 8:
        return None
    sx = sy = sxx = syy = sxy = sxz = syz = sz = 0.0
    for p in points:
        x, y = float(p.x), float(p.y)
        z = x * x + y * y
        sx += x; sy += y; sz += z
        sxx += x * x; syy += y * y; sxy += x * y
        sxz += x * z; syz += y * z
    a11 = 2 * (sxx - sx * sx / n)
    a12 = 2 * (sxy - sx * sy / n)
    a22 = 2 * (syy - sy * sy / n)
    b1 = sxz - sx * sz / n
    b2 = syz - sy * sz / n
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-9:
        return None
    cx = (b1 * a22 - b2 * a12) / det
    cy = (a11 * b2 - a12 * b1) / det
    r = sum(((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5 for p in points) / n
    # Reject anything that is not actually round.
    spread = max(abs(((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5 - r) for p in points)
    if spread > max(6.0, r * 0.18):
        return None
    return pygame.Vector2(cx, cy), r


def winding(points) -> float:
    """+1 clockwise, -1 counter-clockwise, by signed area."""
    area = 0.0
    for i in range(len(points) - 1):
        area += points[i].x * points[i + 1].y - points[i + 1].x * points[i].y
    return -1.0 if area > 0 else 1.0
