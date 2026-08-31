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
