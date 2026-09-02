"""Everything alive obeys the same six laws. RIGS.md 4.2, 9.

There is one rule in this module and it is the whole module:

    **Everything alive swims toward where it is more comfortable.**

A creature is not a state machine, has no behaviour tree, and contains no code
for herding, luring, hunting, hiding or taking cover. It is a set of
preferences over the quantities `field.py` already tracks, plus a body that
climbs the gradient of its own comfort. All five of those behaviours are
things a PLAYER does to a creature by changing the field, and
`selftest_creatures` measures that each of them emerges rather than trusting
that it does.

WHY THIS IS THE WHOLE DESIGN AND NOT A CONVENIENCE
--------------------------------------------------
RIGS.md 9 asks for creatures that react to temperature and pressure
consistently, so that knowing the world is what lets you act on it. The
temptation is to write `if player_is_hot: flee()`, and that fails for the same
reason a glyph system fails (2.1): the meaning is authored, so nothing emerges
from combining and the player is learning a lookup table rather than a world.

Reading the field instead buys the thing the design is actually for. **If
creatures read fields, so does whatever is hunting you** -- so the same rig
that finds prey advertises you to a predator, and defence and offence become
the same verb aimed differently. That property is what makes this a sandbox
worth living in rather than a toolbox worth clearing, and it costs one rule.

WHAT MEASURING CHANGED
----------------------
**Comfort had to be multiplicative, not additive.** With a sum, a creature
sitting in lethally hot water would still climb toward it if the depth term
was good enough, because one large term drowned the other. Multiplying means
any single intolerable condition zeroes the whole reading, which is what
"intolerable" means, and it is what makes a warm barrier an actual barrier
rather than a toll.

**The gradient must be sampled at a distance the creature can act on.** At one
pixel the sound-speed field is smooth enough that a cold-lover took hundreds
of steps to notice a barrier it was swimming into. Sampling at a cell width
matches the scale the medium actually varies on and costs nothing.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from ..medium.field import METRES_PER_PIXEL
from .modules import NOTES

# How far apart the comfort probes sit, in world pixels. One cell, because
# that is the scale field.py varies on -- probing finer reads numerical noise
# and probing coarser walks the creature past what it is avoiding.
PROBE = 16.0

# A creature is a body in water, so it gets the same quadratic drag the diver
# does. Without it, gradient climbing is teleportation with extra steps.
DRAG = 0.02
MAX_SPEED = 90.0


def _band(value, low, high, softness):
    """1.0 inside the band, falling off smoothly outside it.

    Smooth rather than a cliff on purpose. A hard window has zero gradient
    everywhere outside it, so a creature that is already uncomfortable has no
    information about which way is better and simply sits there -- which looks
    exactly like a broken AI and is the most common way a preference system
    fails silently.
    """
    if low <= value <= high:
        return 1.0
    d = (low - value) if value < low else (value - high)
    return math.exp(-(d / max(softness, 1e-6)) ** 2)


@dataclass
class Creature:
    """A set of preferences, and a body that climbs its own comfort.

    Every field here is a preference over something `field.py` already
    tracks. There is deliberately no `state`, no `target`, and no `mode`.
    """

    name: str
    wants: str = ""
    does: str = ""

    temp_band: tuple = (4.0, 18.0)
    temp_softness: float = 3.0

    depth_band: tuple = (0.0, 800.0)      # metres
    depth_softness: float = 120.0

    # What bubbles do. Negative flees them, positive seeks them, zero cannot
    # tell they are there -- which is what makes a curtain cover from some
    # things and not others.
    bubble_response: float = 0.0

    # Notes it approaches, notes it flees, and everything else it cannot hear.
    likes_note: float | None = None
    fears_note: float | None = None
    hearing: float = 0.35                 # fractional bandwidth it responds in

    # A hunter's comfort includes being near a warm anomaly. This is the one
    # preference that is about something the PLAYER made rather than about the
    # ocean, and it is still just a term in the same sum.
    heat_hunter: float = 0.0

    pos: tuple = (0.0, 0.0)
    vel: tuple = (0.0, 0.0)
    speed: float = 40.0

    # --- the one rule -------------------------------------------------------

    def comfort(self, medium, x: float, y: float, sounds=()) -> float:
        """How much this creature wants to be here. The only preference code.

        Multiplicative, so any single intolerable condition zeroes the whole
        reading. See the module docstring for why an additive version let
        creatures swim happily into water that would kill them.
        """
        row, col = medium._cell(x, y)
        if medium.solid[row, col]:
            return 0.0

        temp = float(medium.temp[row, col])
        depth = float(y * METRES_PER_PIXEL)
        bubbles = float(medium.bubbles[row, col])

        c = _band(temp, self.temp_band[0], self.temp_band[1], self.temp_softness)
        c *= _band(depth, self.depth_band[0], self.depth_band[1],
                   self.depth_softness)

        # Bubbles and heat both enter as EXPONENTIALS rather than as clamped
        # linear multipliers, and that shape is load-bearing.
        #
        # A linear term goes negative when the quantity does, which inverts
        # every other preference in the product -- comfort of -1.16 was a real
        # bug here. Clamping fixes the sign and introduces a worse problem: a
        # clamped region is FLAT, so a creature sitting in one has no gradient
        # to read and simply stops. The stalker went blind at 140 px from a
        # wake it should have been able to follow.
        #
        # exp() is positive everywhere, monotone everywhere, and never flat, so
        # the sign is safe and the gradient survives at any distance where the
        # field is varying at all.
        if self.bubble_response:
            c *= math.exp(self.bubble_response * bubbles)

        if self.heat_hunter:
            a = self._anomaly(medium, row, col)
            c *= math.exp(self.heat_hunter * max(-6.0, min(6.0, a)))

        for sx, sy, freq, loudness in sounds:
            d = math.hypot(x - sx, y - sy)
            heard = loudness / (1.0 + (d / 120.0) ** 2)
            if self.likes_note and self._in_hearing(freq, self.likes_note):
                c *= 1.0 + heard
            if self.fears_note and self._in_hearing(freq, self.fears_note):
                c *= 1.0 / (1.0 + heard)
        return c

    def _in_hearing(self, freq, centre) -> bool:
        if freq <= 0.0 or centre <= 0.0:
            return False
        return abs(freq - centre) <= centre * self.hearing

    @staticmethod
    def _anomaly(medium, row, col) -> float:
        """How much warmer this cell is than the rest of the water at its depth.

        SUBMERGED 7.5 had to learn this the hard way: comparing against a
        snapshot conflates heat the player added with the background gradient
        being stirred by convection. A cell is warm when it is warmer than its
        own row.
        """
        return float(medium.temp[row, col] - medium.temp[row, :].mean())

    # --- the body -----------------------------------------------------------

    def step(self, dt: float, medium, sounds=()) -> None:
        """Climb the gradient of comfort. That is the entire behaviour."""
        x, y = self.pos
        here = self.comfort(medium, x, y, sounds)
        gx = (self.comfort(medium, x + PROBE, y, sounds)
              - self.comfort(medium, x - PROBE, y, sounds))
        gy = (self.comfort(medium, x, y + PROBE, sounds)
              - self.comfort(medium, x, y - PROBE, sounds))

        n = math.hypot(gx, gy)
        vx, vy = self.vel
        if n > 1e-9:
            # Normalised: a creature swims at its own speed toward better
            # water, rather than faster where the gradient happens to be
            # steeper. How keen it is is a property of the creature, not of
            # how sharply the player drew the boundary.
            vx += (gx / n) * self.speed * dt * 4.0
            vy += (gy / n) * self.speed * dt * 4.0

        sp = math.hypot(vx, vy)
        if sp > 1e-9:
            drag = DRAG * sp
            vx -= vx / sp * min(sp, drag * sp * dt + sp * 0.9 * dt)
            vy -= vy / sp * min(sp, drag * sp * dt + sp * 0.9 * dt)
        sp = math.hypot(vx, vy)
        if sp > MAX_SPEED:
            vx, vy = vx / sp * MAX_SPEED, vy / sp * MAX_SPEED

        nx, ny = x + vx * dt, y + vy * dt
        nx = min(max(nx, 1.0), medium.width - 1.0)
        ny = min(max(ny, 1.0), medium.height - 1.0)
        # Nothing tunnels through rock. Not a behaviour, a wall.
        if medium.is_solid(nx, ny):
            nx, ny = x, y
            vx, vy = 0.0, 0.0
        self.pos = (nx, ny)
        self.vel = (vx, vy)
        self.last_comfort = here


# --- the species -------------------------------------------------------------
#
# Each is two sentences: what it wants, and what that makes it do. Nothing
# below adds a rule; every one of them is the same `comfort` with different
# numbers, which is the claim RIGS.md 9 is making.


def lantern(pos=(0.0, 0.0)) -> Creature:
    """Wants cold, deep, quiet water. So a warm patch is a wall to it, and a
    cold pocket is bait -- which makes it the creature the whole thermal
    vocabulary is aimed at."""
    return Creature(
        name="lantern",
        wants="cold water, deep, and quiet",
        does="refuses to cross warm water, and comes to a cold pocket",
        temp_band=(2.0, 8.0), temp_softness=2.0,
        depth_band=(300.0, 760.0), depth_softness=140.0,
        fears_note=NOTES["chirp"],
        pos=pos, speed=46.0,
    )


def shoalfish(pos=(0.0, 0.0)) -> Creature:
    """Wants warm shallow water and comes to a low note. So it is the easy
    one -- the creature you learn the system on, and the one a heater gathers
    for you without your having to understand why yet."""
    return Creature(
        name="shoalfish",
        wants="warm shallow water, and a low note",
        does="gathers where you put heat, and comes when you call",
        temp_band=(12.0, 20.0), temp_softness=3.0,
        depth_band=(0.0, 220.0), depth_softness=90.0,
        likes_note=NOTES["groan"],
        bubble_response=-1.2,
        pos=pos, speed=52.0,
    )


def stalker(pos=(0.0, 0.0)) -> Creature:
    """Wants whatever is warmer than the water around it. So it hunts your
    waste heat, and the only way to lose it is to stop being warmer than the
    ocean -- which means your rig's efficiency is also your camouflage."""
    return Creature(
        name="stalker",
        wants="anything warmer than the water it is in",
        does="follows your wake, and loses you when you match ambient",
        temp_band=(0.0, 30.0), temp_softness=14.0,
        depth_band=(0.0, 760.0), depth_softness=400.0,
        heat_hunter=2.2,
        pos=pos, speed=58.0,
    )


def siftling(pos=(0.0, 0.0)) -> Creature:
    """Wants bubbles, and cannot hear anything at all. So a curtain laid as
    cover from a sonar-hunter is an invitation to this one, and the same
    action is concealment and advertisement depending on who is looking."""
    return Creature(
        name="siftling",
        wants="bubbles, and it is deaf",
        does="comes to a curtain that hides you from everything else",
        temp_band=(3.0, 16.0), temp_softness=6.0,
        depth_band=(0.0, 760.0), depth_softness=300.0,
        bubble_response=4.0,
        pos=pos, speed=40.0,
    )


SPECIES = {
    "lantern": lantern,
    "shoalfish": shoalfish,
    "stalker": stalker,
    "siftling": siftling,
}
ORDER = ("lantern", "shoalfish", "stalker", "siftling")


def make(kind, pos=(0.0, 0.0)) -> Creature:
    return SPECIES[kind](pos)


def describe(c: Creature) -> str:
    return f"{c.name}: wants {c.wants}; {c.does}."
