"""Prebuilt sigils — a library of working spells you can load and pull apart.

The point of this file is not convenience. It is that **inventing from a
blank canvas is a much harder act than modifying**, and a systems game that
only offers the blank canvas loses most of its players in the first ten
minutes to a scribble that does nothing.

So there is a shelf of finished instruments. Every one of them is a legal
drawing the player could have made — no privileged construction, no hidden
parameters — and every one demonstrates exactly one idea in the cleanest
form it takes. Load one, fire it, then start cutting bits off it and see what
changes. That is how the system actually gets learned, and it is the reason
each entry carries a `teaches` line rather than a stat block.

They are also deliberately not optimal. Each has an obvious flaw a player
will eventually notice — a terminal that leaks, a ring a little off band, a
body that would carry further in a better ink — because a library of perfect
answers ends the game and a library of good starting points begins it.
"""

import math

import pygame

from sigilwave.ink import Stroke

from .bands import BAND_LOOP_PX
from .inks import BONEWHITE, CHALK, EMBERGLASS, QUICKSILVER, SLATE, VOIDGLASS
from .shapes import arc_points, line_points, radius_for_band_px, ring_points, ring_with_tail
from .sigil import Sigil


def _s(points, ink=CHALK):
    return Stroke(points=[pygame.Vector2(p) for p in points], ink_type=ink)


def _r(band):
    return radius_for_band_px(BAND_LOOP_PX[band])


# --------------------------------------------------------------------------
# Emitters — they have terminals, so they throw things.


def lance():
    """Band 2, long body, wide-open tip. The workhorse ranged attack."""
    r = _r(2)
    return Sigil("Lance", [
        _s(ring_with_tail((-40, 0), r, 26.0), SLATE),
        _s(line_points((-40 + r + 26, 0), (-40 + r + 26 + 78, 0)), QUICKSILVER),
    ])


def fork():
    """One resonator, three ways out.

    The firing pattern is not a property of the spell, it is a property of
    where the ink stops. Three terminals at three angles is a spread shot,
    and nobody had to implement a spread shot."""
    r = _r(2)
    strokes = [_s(ring_points((0, 0), r, closed=True), CHALK)]
    for ang in (-38, 0, 38):
        a = math.radians(ang)
        start = pygame.Vector2(math.cos(a), math.sin(a)) * r
        strokes.append(_s(line_points(start, start + pygame.Vector2(math.cos(a), math.sin(a)) * 76),
                          QUICKSILVER))
    return Sigil("Fork", strokes)


def needle():
    """Band 4, tiny ring, long conducting body.

    Heat cannot travel, so this one is a knife: it does enormous work at
    contact range and nothing at all across a room. Learning where to stand
    is the entire skill of using it."""
    r = _r(4)
    return Sigil("Needle", [
        _s(ring_with_tail((-30, 0), r, 22.0), CHALK),
        _s(line_points((-30 + r + 22, 0), (-30 + r + 22 + 62, 0)), QUICKSILVER),
    ])


# --------------------------------------------------------------------------
# Capacitors — no terminal, so nothing leaves until you let it.


def cask():
    """A sealed low-band ring. Charge it, then release it as a shockwave.

    It has no way out, which is the entire point: everything you pour in
    stays in until you say otherwise. Watch the char meter, because the ink
    is what fails first."""
    return Sigil("Cask", [_s(ring_points((0, 0), _r(1), closed=True), BONEWHITE)])


def pyre():
    """A sealed small ring. Small means hot, so the release is a firestorm.

    Note the ink. The obvious choice here is Emberglass — it folds early, it
    makes harmonics, it is *the* fire material — and it is the wrong one, for
    exactly that reason: a junction that saturates at 0.85 clips every crest
    off the wave, so nothing accumulates and the thing chars to nothing while
    still nearly empty. Measured, an Emberglass capacitor tops out around 10%
    charge at any ring size.
    
    Storage wants an ink that stays linear while you fill it. Emberglass is
    for throwing, not for holding — see Kiln."""
    return Sigil("Pyre", [_s(ring_points((0, 0), _r(3), closed=True), CHALK)])


def kiln():
    """A mid ring in ink that folds early, with a way out.

    This is what Emberglass is actually for. The ring is band 2 and the
    output is not: driving the junction past its threshold folds the wave and
    the fold throws harmonics upward, so the spectrum that leaves is hotter
    than the geometry that made it. It is the only way to reach the top of
    the band range at all, because no ring small enough to ring there will
    survive the parser."""
    r = _r(2)
    return Sigil("Kiln", [
        _s(ring_with_tail((-30, 0), r, 24.0), EMBERGLASS),
        _s(line_points((-30 + r + 24, 0), (-30 + r + 24 + 66, 0)), QUICKSILVER),
    ])


def hearth():
    """A sealed mid ring in the most char-resistant ink there is.

    Nothing leaves, so all of it goes into the ground around you: this is a
    standing fire you carry. It is the one spell here that is better held
    than released."""
    return Sigil("Hearth", [_s(ring_points((0, 0), _r(3), closed=True), SLATE)])


def rime():
    """Hearth, wound the other way.

    The same ring, the same ink, the same size — and it freezes instead of
    burning, because chirality decides the sign of the coupling and nothing
    else about this drawing changed. It is the counter to a room on fire:
    frozen ground will not light."""
    return Sigil("Rime", [_s(ring_points((0, 0), _r(3), clockwise=False, closed=True), SLATE)])


def maw():
    """A sealed low ring wound counter-clockwise: it pulls.

    Wind blows inward instead of out, which gathers a crowd into one place.
    Pair it with something that punishes a crowd."""
    return Sigil("Maw", [_s(ring_points((0, 0), _r(1), clockwise=False, closed=True), BONEWHITE)])


# --------------------------------------------------------------------------
# Barriers and oddities.


def aegis():
    """A dense arc across your front, and a small ring to keep it alive.

    Bonewhite has an impedance far above open ground, so incoming energy
    reflects off it. That is the whole shield: an ink with the wrong
    impedance, drawn in the way of something."""
    return Sigil("Aegis", [
        _s(arc_points((0, 0), 96.0, -62, 62), BONEWHITE),
        _s(ring_with_tail((-70, 0), _r(2), 24.0, attach_deg=180.0), CHALK),
    ])


def lantern():
    """Two rings that never touch.

    The gap is narrow enough for energy to cross it without a join, so the
    second ring rings although nothing connects it to the first. Widen the
    gap and it goes quiet; that distance is the mechanic."""
    r = _r(3)
    gap = 22.0
    return Sigil("Lantern", [
        _s(ring_with_tail((-r - gap / 2 - 18, 0), r, 20.0, attach_deg=180.0), VOIDGLASS),
        _s(ring_points((r + gap / 2 + 18, 0), r, closed=True), VOIDGLASS),
    ])


def chord():
    """Two rings of slightly different size, joined.

    They disagree, and the disagreement is audible as a slow swell in the
    output — the beat runs at the difference of the two fundamentals. Useful
    because the peaks hit far harder than either ring alone."""
    r = _r(2)
    small = r * 0.82
    bridge_a = pygame.Vector2(-46 + r, 0)
    bridge_b = pygame.Vector2(46 - small, 0)
    # Both rings, bridged — and then an open end off the far side, because a
    # bridge between two sealed loops seals them both. Without this tail the
    # whole thing is a two-loop capacitor and emits nothing at all, which is
    # the single easiest mistake to make when drawing a composite.
    tip = pygame.Vector2(46 + small, 0)
    return Sigil("Chord", [
        _s(ring_points((-46, 0), r, closed=True), CHALK),
        _s(ring_points((46, 0), small, closed=True), CHALK),
        _s(line_points(bridge_a, bridge_b), CHALK),
        _s(line_points(tip, tip + pygame.Vector2(74, 0)), QUICKSILVER),
    ])


LIBRARY = [
    ("Lance", lance, "emitter", "long-range band 2 - a slate body that carries, a quicksilver tip that lets go"),
    ("Fork", fork, "emitter", "three terminals, three directions - the drawing IS the firing pattern"),
    ("Needle", needle, "emitter", "band 4 knife - devastating at contact, useless at range"),
    ("Cask", cask, "capacitor", "sealed low ring - charge it, release it, shockwave"),
    ("Pyre", pyre, "capacitor", "sealed small ring - charge it, release a firestorm"),
    ("Kiln", kiln, "emitter", "early-folding ink - harmonics push the output hotter than the ring"),
    ("Hearth", hearth, "aura", "sealed mid ring - a standing fire you carry. hold, do not release"),
    ("Rime", rime, "aura", "Hearth wound backwards - freezes, and frozen ground will not light"),
    ("Maw", maw, "aura", "counter-clockwise low ring - wind blows inward, gathers a crowd"),
    ("Aegis", aegis, "barrier", "a dense arc reflects incoming energy - impedance is the shield"),
    ("Lantern", lantern, "conduit", "two rings that never touch - energy crosses the gap anyway"),
    ("Chord", chord, "emitter", "two detuned rings beat against each other - the peaks hit hard"),
]

BY_NAME = {name: fn for name, fn, _k, _d in LIBRARY}


def build(name):
    fn = BY_NAME.get(name)
    return fn() if fn else None


def all_entries():
    return LIBRARY
