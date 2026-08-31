"""A ring: sound, loose in the world.

The old build's attack was a stream of small projectiles, and that one
choice is responsible for most of what felt bad about it. A stream has no
moment - there is no frame where the hit happens, so there is nothing to
punctuate, nothing to freeze, nothing to shake the camera on. It also asks
the player to aim continuously at a thing that is dodging, which turns a
game about *what note* into a game about mouse tracking.

A ring is the opposite in every one of those respects:

* It has exactly one moment per target: the frame its edge crosses them.
  That frame is where the hitstop, the flash and the shatter live.
* It is omnidirectional, so the skill it asks for is **distance**, and
  distance is precisely what the note ladder encodes. You stop aiming and
  start standing in the right place.
* Its radius is legible before it resolves. A player can see a ring is going
  to fall short, which is a thought they can have *during* the swing.

And it cools as it goes. The high notes in a ring die within a body length
and the low ones cross the room, so one expanding ring shows the entire
range/pitch law happening, in one animation, without a word of text.
"""

import math

import pygame

from . import notes
from .bell import survived
from .notes import N_NOTES

# How fast a ring expands. Fast enough to read as a shockwave rather than a
# growing circle, slow enough that a player can watch it reach and know
# whether it will arrive. Tuned against the largest reach (560px): a BOURDON
# ring takes about a third of a second to run out, which is one beat of a
# fast bell and reads as a single event.
RING_SPEED = 1750.0
RING_THICKNESS = 30.0

# Shove is not damage; it is the other half of the game. Any energy at all
# moves things whether or not it is the right note, which is what makes a
# mistuned bell a tool instead of a punishment.
SHOVE_SCALE = 26.0

# What a matched strike is worth against a crack meter. One number, set from
# measurement (`python -m sigilwave.campanary.calibrate`) so that a settled
# on-beat strike from the right bell takes a third of its target: three good
# tolls and the thing goes. Everything else in the balance table is a cap,
# and every cap is expressed in those same units.
CRACK_SCALE = 0.00208


class Ring:
    """One expanding wavefront."""

    __slots__ = (
        "origin", "r", "prev_r", "bands", "max_r", "push", "hostile",
        "bias", "bias_strength", "spent", "hit", "born", "power", "note",
        "chorus", "on_beat", "source", "damage",
    )

    def __init__(self, origin, bands, push=1.0, hostile=False,
                 bias=None, bias_strength=0.0, chorus=1.0, on_beat=False,
                 source=None):
        self.origin = pygame.Vector2(origin)
        self.bands = list(bands)
        self.push = push
        self.hostile = hostile
        self.bias = pygame.Vector2(bias) if bias is not None else pygame.Vector2(0, 0)
        self.bias_strength = bias_strength
        self.chorus = chorus
        self.on_beat = on_beat
        self.source = source
        self.damage = 22.0
        self.r = 0.0
        self.prev_r = 0.0
        self.spent = False
        self.hit = set()
        self.born = 0.0
        self.power = sum(bands)
        self.note = notes.note_from_bands(bands)[0]
        self.max_r = _reach_of(bands)

    def update(self, dt: float) -> None:
        self.prev_r = self.r
        self.r += RING_SPEED * dt
        self.born += dt
        if self.r - RING_THICKNESS > self.max_r or self.power <= 1e-7:
            self.spent = True

    # ------------------------------------------------------------ geometry

    def crosses(self, pos, radius: float) -> bool:
        """True on the single frame this ring's edge sweeps a body.

        Tested as a swept annulus rather than a point sample, because at
        1750px/s a thin ring steps 29px per frame at 60fps and would tunnel
        straight through anything smaller than that - which is most things.
        """
        d = (pygame.Vector2(pos) - self.origin).length()
        near = self.prev_r - RING_THICKNESS * 0.5 - radius
        far = self.r + RING_THICKNESS * 0.5 + radius
        return near <= d <= far and d <= self.max_r + radius

    def directional(self, pos) -> float:
        """How hard this ring hits in a given direction.

        A symmetric bell hits evenly all round. A bell with an open end
        leans that way - so the shape you drew still decides the shape of
        your attack, but a bad drawing can no longer produce a bell that
        misses everything. The worst case is a ring that is merely even.
        """
        if self.bias_strength <= 1e-3 or self.bias.length_squared() < 1e-9:
            return 1.0
        to = pygame.Vector2(pos) - self.origin
        if to.length_squared() < 1e-9:
            return 1.0
        align = to.normalize().dot(self.bias)          # -1 .. 1
        return 1.0 + self.bias_strength * 0.55 * align

    def spectrum_at(self, pos) -> list:
        """What is left of this ring by the time it reaches `pos`."""
        d = (pygame.Vector2(pos) - self.origin).length()
        lean = self.directional(pos)
        return [b * lean for b in survived(self.bands, d)]

    def shove_at(self, pos) -> pygame.Vector2:
        """Force is radial, and its sign is the winding of the ring that made
        it: a bell wound one way blows outward, the same bell wound the other
        way drags inward. Nobody wrote that as a spell type.

        The chorus multiplies it, exactly as it multiplies crack. Without
        that, the beat only paid off in the resonance lane and the force lane
        stayed a flat, fiddly chore - measured, a Deadweight wave took the
        harness sixty seconds because a point-blank toll threw the thing at
        543px/s and a slam needs speed. Playing in time now throws things
        properly, so force is a skill rather than a slow patch of the game.
        """
        to = pygame.Vector2(pos) - self.origin
        if to.length_squared() < 1e-9:
            return pygame.Vector2(0, 0)
        arrived = sum(self.spectrum_at(pos))
        groove = 1.0 + (self.chorus - 1.0) * 0.6
        return to.normalize() * arrived * SHOVE_SCALE * self.push * groove

    def color_at(self, radius: float) -> tuple:
        left = survived(self.bands, radius)
        centre, total = notes.note_from_bands(left)
        return notes.note_color(centre if total > 1e-9 else self.note)


def _reach_of(bands, floor: float = 0.06) -> float:
    total = sum(bands)
    if total <= 1e-12:
        return notes.NOTE_REACH[-1]
    far = notes.NOTE_REACH[-1]
    for i, e in enumerate(bands):
        if e / total >= floor:
            far = max(far, notes.NOTE_REACH[i])
    return far


def cancel(friendly: list, hostile: list, answered: list | None = None) -> list:
    """Two rings meeting.

    Where their spectra agree and their windings oppose, they annihilate -
    which is the simulation's own antiphase cancellation, promoted into a
    defensive verb. Answering a toll with the same note deletes it; answering
    with the wrong note does nothing at all; answering with the same note
    wound the *same* way feeds it, because that is what superposition does.

    Only friendly-against-hostile is tested. Same-team interference would be
    physically consistent and reads on screen as your own attacks eating each
    other, which is noise rather than depth.
    """
    events = []
    if not friendly or not hostile:
        return events
    for f in friendly:
        if f.spent:
            continue
        for h in hostile:
            if h.spent:
                continue
            gap = (f.origin - h.origin).length()
            # Two expanding fronts touch where their radii sum to the
            # distance between their centres.
            if abs(f.r + h.r - gap) > RING_THICKNESS * 1.6:
                continue
            opposed = f.push * h.push < 0
            removed = 0.0
            for i in range(N_NOTES):
                fb, hb = f.bands[i], h.bands[i]
                if fb <= 0.0 or hb <= 0.0:
                    continue
                if opposed:
                    overlap = min(fb, hb)
                    f.bands[i] = fb - overlap
                    h.bands[i] = hb - overlap
                    removed += overlap * 2.0
                else:
                    transfer = min(fb, hb) * 0.5
                    f.bands[i] = fb - transfer
                    h.bands[i] = hb + transfer
            f.power, h.power = sum(f.bands), sum(h.bands)
            if f.power < 1e-7:
                f.spent = True
            if h.power < 1e-7:
                h.spent = True
            if removed > 1e-6:
                mid = f.origin + (h.origin - f.origin) * (
                    f.r / max(1e-6, f.r + h.r))
                events.append((mid, removed, opposed))
                if opposed and answered is not None and h.source is not None \
                        and h.source not in answered:
                    answered.append(h.source)
    return events
