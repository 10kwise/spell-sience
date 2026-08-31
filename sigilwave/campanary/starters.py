"""The two bells you begin with.

These matter more than any other content in the game. The largest risk in a
systems game is handing a new player a blank canvas: they draw a scribble,
nothing happens, and they conclude the game is broken rather than that their
scribble was. So a run does not start with a blank canvas. It starts with two
working instruments, and the first hour is spent *editing* them, which is a
far easier act than inventing.

The two are chosen so the first comparison a player makes is the one the
whole game rests on:

    THE TOLL is four times the size of THE HAND, and it reaches four times
    as far.

Nothing else differs. Same metal, same shape, same winding. One is big and
one is small, and the difference is immediately visible in the drawing, in
the colour, in the pitch, and in the circle on the floor. A player who
notices that has learned the entire system, and every later idea - the
octave, the beat, the winding - is a refinement of it.
"""

import pygame

from sigilwave.ink import Stroke

from .bell import Bell
from .metals import BRONZE
from .notes import NOTE_RADIUS
from .shapes import ring

CANVAS = 460.0              # the drawable square, centred on the origin
CANVAS_HALF = CANVAS / 2
METAL_BUDGET = 700.0        # in cost-weighted pixels


def _stroke(points, metal=BRONZE) -> Stroke:
    return Stroke(points=[pygame.Vector2(p) for p in points], ink_type=metal)


def toll() -> Bell:
    """TENOR. The working bell: reaches 400px, tolls every 0.8s, and is what
    the first room is tuned to - so somebody who has understood nothing can
    still win, and then wonder why the second room does not work."""
    return Bell("The Toll", [_stroke(ring((0, 0), NOTE_RADIUS[1]))])


def hand() -> Bell:
    """CHIME. A quarter of the size, so an octave and a half up, so it dies
    at 185px. Its whole job in the first act is to be visibly worse until the
    moment it is the only thing that works."""
    return Bell("The Hand", [_stroke(ring((0, 0), NOTE_RADIUS[3]))])


def starting_bells() -> list:
    return [toll(), hand()]


def blank() -> Bell:
    return Bell("new bell", [])
