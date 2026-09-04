"""The three sigils you start with.

These matter more than any other content in the game. The single largest
risk in a systems game this deep is that a new player is handed a blank
canvas, draws a scribble, watches nothing happen, and concludes the game is
broken rather than that their scribble was. So the run does not begin with a
blank canvas. It begins with three working instruments, and the first hour
is spent *editing* them — which is a far easier act than inventing, and
which teaches by contrast.

The three are deliberately chosen so that the first comparison a player
makes is the most important one in the system:

    Shove and Draw are the same ring wound the opposite way.

Nothing else differs. Same size, same ink, same tail, same everything. One
pushes and one pulls. A player who notices that has learned chirality
without being told it exists, and — more importantly — has learned that the
*direction you drew a line* is a physical quantity the game reads. Every
later discovery is downstream of believing that.

Spark is the odd one out on purpose: a small ring, so it rings hot, so its
output dies in the air within a couple of body lengths. The lesson is
delivered as an inconvenience rather than a sentence.
"""

import pygame

from sigilwave.ink import Stroke

from .bands import BAND_LOOP_PX
from .inks import CHALK, QUICKSILVER
from .shapes import line_points, radius_for_band_px, ring_with_tail
from .sigil import Sigil

FOCUS_CANVAS = 440.0        # the drawable square, centred on the origin
FOCUS_HALF = FOCUS_CANVAS / 2
FOCUS_INK_BUDGET = 900.0    # in cost-weighted pixels


def _stroke(points, ink=CHALK) -> Stroke:
    return Stroke(points=[pygame.Vector2(p) for p in points], ink_type=ink)


def shove() -> Sigil:
    """Band 1, wound clockwise. Push. Long reach, because low bands survive
    the air. The reliable opener and the ruler for everything else."""
    r = radius_for_band_px(BAND_LOOP_PX[1])
    return Sigil("Shove", [_stroke(ring_with_tail((-30, 0), r, 78.0, attach_deg=0.0, clockwise=True))])


def draw_in() -> Sigil:
    """The same ring, wound counter-clockwise. Pull.

    Identical in every measurable respect except the sign of its enclosed
    area, and that one sign flips the direction of every impulse it emits.
    Put these two side by side in the codex and the whole idea of chirality
    arrives on its own."""
    r = radius_for_band_px(BAND_LOOP_PX[1])
    return Sigil("Draw", [_stroke(ring_with_tail((-30, 0), r, 78.0, attach_deg=0.0, clockwise=False))])


def spark() -> Sigil:
    """A small ring rings hot. Hot dies in the air. So this one only works
    if you walk into trouble, which is the range/element tradeoff arriving
    as a tactical fact instead of a tooltip.

    The ring is Chalk (it has to survive being driven) and the tail is
    Quicksilver (it has to actually let go). That split is the composite
    lesson, pre-solved once so the player has seen it work before they are
    asked to invent it."""
    r = radius_for_band_px(BAND_LOOP_PX[4])
    ring = ring_with_tail((-8, 0), r, 26.0, attach_deg=0.0, clockwise=True)
    tip_start = pygame.Vector2(-8 + r + 26.0, 0)
    tail = line_points(tip_start, tip_start + pygame.Vector2(58, 0))
    return Sigil("Spark", [_stroke(ring, CHALK), _stroke(tail, QUICKSILVER)])


def starting_loadout() -> list:
    return [shove(), draw_in(), spark()]


def blank() -> Sigil:
    return Sigil("new sigil", [])
