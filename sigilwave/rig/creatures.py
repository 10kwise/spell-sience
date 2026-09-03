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

# How hard a creature casts about when the water tells it nothing, as a
# fraction of its own speed.
#
# Without this a creature in a flat field FREEZES: `step` only accelerates when
# the comfort gradient is non-zero, and drag takes the rest of its velocity
# within a second or so. That is the same failure `_band`'s softness was
# written to avoid, arriving through a different door -- and it is fatal to the
# cycle, because a channel under CHANNEL_FLOOR is exactly zero, so anything
# more than a plume's width from food would simply stop and wait to die.
#
# The gradient is normalised before this is added, so a real signal of any
# strength at all still dominates: 0.35 deflects a committed creature by about
# nineteen degrees and completely determines one that has nothing to go on.
# Only creatures that forage do this -- see the gate in `step`.
WANDER = 0.35

# How fast condition falls when a creature is not eating, per second, and how
# much one unit of food restores.
#
# CONDITION EXISTS TO CLOSE A FREE-ENERGY LEAK, and `selftest_cycle` found it
# rather than reasoning. Presence channels (`swarm`, `shoal`) are written by
# `signals` whether or not the creature ate, which is right -- a shoal is
# findable because it is there. But the hunter EATS `shoal` and turns it into
# `chum`, which is a substance, so an unconditional signal was a doorway from
# nothing into the substance chain: with no snow and no seeps at all, total
# channel mass rose from 60 to 722 units in five minutes. A food web that runs
# on itself is RIGS.md 12.5's perpetual motion machine wearing fins.
#
# Gating the signal on condition closes it: a creature only advertises while it
# is fed, and being fed traces back through the whole chain to snow and death.
# It also buys the behaviour 13.3 wanted from the other direction -- work a
# place hard enough and it goes quiet, because the things living there thin out
# rather than because a designer put a timer on it.
CONDITION_DECAY = 0.08
CONDITION_GAIN = 1.2

# And the signal rates themselves are held BELOW the feed rate of the creature
# emitting them (0.05 against 0.12 for a drifter, 0.07 against 0.16 for a
# grazer). Gating a signal on condition is not enough on its own: condition is
# a stock, so a trickle of food holds it at 1.0 and the creature advertises at
# full rate forever. Measured, the first version turned 0.006 units/s of intake
# into 0.30 units/s of signal, and `selftest_cycle` [2] caught it as 60 units
# of channel becoming 722 with nothing feeding the world at all.
#
# `menace` is exempt and deliberately louder, because nothing eats it. A
# channel that is never consumed cannot leak into the substance chain, so it
# is free to be as loud as the behaviour needs.


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

    # --- the trophic cycle (RIGS.md 13.4) -----------------------------------
    #
    # `reads` is what this creature is drawn to and `emits` is what it leaves
    # behind, and the food web is nothing but those two strings lining up
    # around a circle: the scavenger reads what the dead leave and emits what
    # the decomposer reads, and so on until the hunter emits chum again
    # because a kill is what starts the cycle over.
    #
    # This is a CYCLE and not a chain on purpose. A chain -- predators seek
    # prey, prey flee predators -- has a head attracted to something that only
    # runs and a tail attracted to nothing, so it diverges: the prey end up
    # against the map edge and the player never sees either of them. A closed
    # loop of attraction has no head and no tail.
    reads: str | None = None
    read_gain: float = 0.0

    # How much of `reads` this creature takes out of the water per second.
    # Eating is not decoration here: it is the only thing preventing the
    # aggregation from collapsing onto one cell, because it flattens the peak
    # that drew the crowd in. See `Medium.consume`.
    feed_rate: float = 0.0

    # ((channel, units emitted per unit EATEN), ...). Emission is driven by
    # intake rather than produced from nothing, so the cycle is a transfer and
    # a creature that finds no food leaves no trail. A tuple because the
    # hunter writes two -- the scraps that feed the scavengers, and the fact
    # of itself.
    #
    # These sum to less than 1 on every species, so the loop LOSES around its
    # circuit and cannot run on itself. That is not a balance decision, it is
    # the same law as RIGS.md 12.5: the cycle needs an external input, which
    # is carcasses plus `snowfall`, exactly as a real one needs the surface.
    emits: tuple = ()

    # The other half of the flocking rule. `reads` is a wide slow channel and
    # says "the shoal is somewhere that way" from across a room; `flees` is a
    # tight fast-decaying one and says "it is right here". Long-range
    # attraction with short-range repulsion is what makes a dense knot with
    # panic churning inside it rather than either a smear or a single point.
    flees: str | None = None
    flee_gain: float = 0.0

    # ((channel, units per second), ...) written whether or not it ate.
    #
    # The distinction between this and `emits` is SUBSTANCE versus PRESENCE,
    # and getting it wrong is what made the hunters fail to aggregate. `chum`,
    # `nutrient` and `bloom` are things -- they are produced by working on
    # something else, so they belong in `emits` and they attenuate down the
    # pyramid the way real trophic transfer does. `swarm` and `shoal` are not
    # things, they are the fact that there are drifters or grazers here, and a
    # shoal is findable because it exists rather than because it has been
    # feeding. Routed through `emits` they inherited four levels of trophic
    # loss, arrived at the top at a fifth of the strength anything could read,
    # and the hunters ended up MORE dispersed than random placement.
    signals: tuple = ()

    pos: tuple = (0.0, 0.0)
    vel: tuple = (0.0, 0.0)
    speed: float = 40.0
    last_meal: float = 0.0
    wander_phase: float = 0.0

    # 1.0 is well fed, 0.0 is starving. Only creatures that eat have it mean
    # anything; RIGS.md 9's four species leave it at 1.0 forever, which keeps
    # their behaviour exactly as `selftest_creatures` measured it.
    condition: float = 1.0

    def __post_init__(self):
        # Seeded from where it starts, so a shoal does not cast about in
        # unison, and so a run is reproducible without an RNG anywhere in
        # this module.
        if self.wander_phase == 0.0:
            self.wander_phase = (self.pos[0] * 0.7 + self.pos[1] * 1.3) % 6.283185

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

        # The cycle uses a POWER law rather than the exponential above, and
        # that difference was measured rather than chosen.
        #
        # `exp(gain * min(6, v))` was the first version, by analogy with the
        # two terms above. It collapsed the entire ecosystem onto a single
        # point -- every species at a radius of gyration under 2 px, all five
        # sharing one centroid. The reason is the clamp: channels reach 10.3
        # where the creatures pile up, so the response saturates, and a
        # saturated region is FLAT. That is the same failure the comment above
        # describes for a clamped linear term, arriving from the other side,
        # and it takes the repulsion out with it -- a grazer sitting in
        # saturated `menace` cannot tell which way is away from the hunter.
        #
        # (1 + v)**gain is 1.0 at zero, monotone forever, never flat, and
        # cannot overflow at any value a channel can reach. No clamp, so no
        # flat spot, so the gradient survives everywhere.
        if self.reads:
            c *= (1.0 + medium.channel_at(self.reads, x, y)) ** self.read_gain
        if self.flees:
            c *= (1.0 + medium.channel_at(self.flees, x, y)) ** -self.flee_gain

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

        # Cast about, but only if this creature forages. A slow turn rather
        # than a jitter, because an animal searching sweeps and a random walk
        # vibrates.
        #
        # The gate on `reads` is the whole point and it was put there by a
        # failing test. RIGS.md 9's four species are defined by what the
        # PLAYER does to the water, and `selftest_creatures` requires that
        # they do not move when their comfort is flat -- otherwise "the heater
        # moved it" stops being an attributable claim and every measurement in
        # that suite is contaminated. Searching belongs to foraging, which is
        # 13.4's cycle, so a creature that eats searches and a creature that
        # only prefers does not.
        if self.reads:
            self.wander_phase += dt * 0.6
            vx += math.cos(self.wander_phase) * self.speed * dt * 4.0 * WANDER
            vy += math.sin(self.wander_phase) * self.speed * dt * 4.0 * WANDER

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

        # Eat, then leave what eating leaves, at the cell it actually ended up
        # in -- so the trail records where it went rather than where it set
        # off from, and a creature that found nothing leaves nothing.
        #
        # A standing constraint on adding species: nothing in the cycle may
        # read the channel it emits. Self-attraction is a positive feedback
        # with no opposing term, and a creature that can smell itself stops
        # where it is and calls that comfort.
        ate = 0.0
        if self.reads and self.feed_rate > 0.0:
            ate = medium.consume(self.reads, nx, ny, self.feed_rate * dt)
        self.last_meal = ate

        if self.feed_rate > 0.0:
            self.condition = min(1.0, max(
                0.0, self.condition - CONDITION_DECAY * dt + CONDITION_GAIN * ate))

        for channel, yield_per in self.emits:
            if yield_per > 0.0 and ate > 0.0:
                medium.deposit(channel, nx, ny, yield_per * ate)
        # Scaled by condition, so a starving shoal stops advertising. See
        # CONDITION_DECAY: without this the cycle is a perpetual motion machine.
        for channel, rate in self.signals:
            if rate > 0.0 and self.condition > 0.0:
                medium.deposit(channel, nx, ny, rate * self.condition * dt)


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


# --- the cycle ---------------------------------------------------------------
#
# RIGS.md 13.4. Six links, closing on themselves:
#
#     carrion -> scavenger -> decomposer -> drifter -> grazer -> hunter -> carrion
#
# Every link is ATTRACTION. Nobody in here hunts anything; everybody arrives,
# and predation is a consequence of two species being drawn to the same place
# by different things. That is how a bait ball actually forms, and it is the
# only arrangement that does not diverge.
#
# The one avoidance term in the whole ecosystem is the grazer fleeing `menace`,
# and it is deliberately short-ranged (see MENACE below): from across a room a
# grazer is drawn to the aggregation, and inside it a grazer is trying to not
# be the one that gets eaten.

# Each channel is (diffusivity px^2/s, half-life s). Those two set the reach,
# because a continuously fed decaying field settles at a length of about
# sqrt(D / lambda) with lambda = ln2 / half_life. The comment on each line is
# that number, and it is the only thing about a channel worth arguing over.
CHANNELS = {
    "chum":     ( 45.0, 150.0),   # ~99 px across. Carrion lingers
    "nutrient": ( 35.0, 150.0),   # ~88 px: what the scavengers leave
    "bloom":    ( 30.0, 300.0),   # ~115 px, slowest. A bloom is a place
    "swarm":    ( 45.0, 110.0),   # ~85 px, a presence: made to be found
    "shoal":    ( 55.0,  90.0),   # ~85 px, a presence
    "menace":   (100.0,  12.0),   # ~41 px. See below
}

# THE NUMBER IN THE COMMENT IS THE PLUME WIDTH, NOT THE RANGE, and getting
# those two confused cost two measured runs.
#
# Diffusion sets how wide a plume is across the flow. It does NOT set how far
# away a thing can be smelled, because what actually carries a channel is
# `Medium._advect_channels` -- the current. Every one of these is at or below
# HEAT_DIFFUSIVITY (60), which RIGS.md 9.0 measured as reaching 140 px, because
# a channel smoother than heat has no gradient to climb anywhere: the mass is
# real but so thin that (1 + v)**gain sits at 1.001 and the ocean's own
# temperature structure decides everything. That was the second failed run.
#
# The first failed run had them tighter still, which is defensible as molecular
# diffusion and useless as a game: nothing could find anything. The resolution
# is that neither number was the problem. In water a smell is carried, not
# spread, and once it is carried the tide decides who can smell what -- which
# is the coupling 13.6 wanted and did not have to be written.

# MENACE is the short-range half of the flocking rule and its reach is the
# number that decides whether this looks like life. At 40 px it is about two
# and a half cells: a grazer inside the knot is uncomfortable and a grazer at
# the edge of it is not, so the shoal churns and thins around a hunter instead
# of either ignoring it or evaporating. Widen it and the grazers scatter and
# the cycle breaks; narrow it and nothing reacts to being hunted.

# Marine snow: the external input the cycle cannot run without.
#
# Every species passes on less than it eats, so the loop loses about 96% of
# whatever goes round it once. That is deliberate and it is the same law as
# RIGS.md 12.5 -- nothing powers itself, ecosystems included. A real one is
# driven by the surface, and this is that: aggregate falling out of the light
# and feeding the dark.
#
# It falls as SPECKS rather than as a uniform drizzle, and that detail is
# load-bearing. A uniform field has no gradient anywhere, so a decomposer in
# one has nothing to climb and the bottom of the food web goes blind. Snow is
# actually particulate; making it particulate here is both truer and the only
# version that works.
# THE BALANCE RULE, which four measured runs arrived at from four directions:
#
#     supply into a channel must not exceed what its eaters can take out.
#
# Overfeed a channel and it stops being patchy -- the stock builds until the
# whole ocean is above the level that matters, (1 + v)**gain is large
# everywhere, and there is nowhere better to be, which is the same "no
# aggregation" symptom as having no food at all. Underfeed it and the level
# below starves. Total supply here is about 1.45 units/s of nutrient against a
# decomposer capacity of 1.5, and every level below is deliberately a little
# hungry, because a food-limited predator is one that has to go where the food
# is. That is what makes a hunter follow a shoal without any code for hunting.
SNOW_SPECKS_PER_MEGAPIXEL = 0.45  # per second
SNOW_SPECK = 4.0                  # units of nutrient in one

# Those two numbers were balanced against the feed rates below rather than
# chosen, and the first attempt at both was wrong in opposite directions.
# Fifty creatures eating at 1 unit/s against a world fed 1.4 units/s strips
# every channel to about 0.001, where (1 + v)**gain is 1.001 and the cycle
# is invisible underneath the temperature and depth bands. The budget has to
# close: supply, standing stock and grazing pressure are one number each and
# they are only meaningful against each other.


def snowfall(medium, dt: float, rng) -> int:
    """Rain nutrient onto random cells. Returns how many specks landed."""
    area = (medium.width * medium.height) / 1.0e6
    expected = SNOW_SPECKS_PER_MEGAPIXEL * area * dt
    n = int(rng.poisson(expected)) if expected > 0.0 else 0
    for _ in range(n):
        x = float(rng.uniform(0.0, medium.width))
        y = float(rng.uniform(0.0, medium.height))
        medium.deposit("nutrient", x, y, SNOW_SPECK)
    return n


class Seep:
    """A place that makes food out of nothing but chemistry. RIGS.md 13.3.

    THIS CLASS IS THE ANSWER TO WHY ANYTHING CLUSTERS, and it was added
    because measuring said it had to be. With the cycle fed only by snow
    falling at uniform random over the whole ocean, nothing aggregated at
    all -- three separate tunings, and the radius of gyration never went
    below its random starting value. The reason is embarrassingly simple in
    hindsight: **uniformly distributed food cannot produce an aggregation.**
    There is nowhere better to be.

    So the base of the food web is a PLACE, which is the same correction
    13.3 had to make to the player's economy, arriving independently from
    the ecosystem's side. And it is what a real one does: a vent community
    is chemosynthetic, built on the chemistry of the water coming out of the
    ground rather than on light, which is why the richest thing in the deep
    ocean is a hole in the floor.

    The consequence is the one the whole design has been circling. The best
    generator site (13.3), the most attractive place to a heat-hunter, and
    the base of the food web are the same coordinate -- and nobody had to
    make that true, it is three systems reading the same hole.
    """

    def __init__(self, pos, rate: float = 0.35, channel: str = "nutrient"):
        self.pos = (float(pos[0]), float(pos[1]))
        self.rate = float(rate)
        self.channel = channel

    def step(self, dt: float, medium) -> None:
        medium.deposit(self.channel, self.pos[0], self.pos[1], self.rate * dt)


CARCASS_YIELD = 200.0    # total units of chum a body is worth
CARCASS_SECONDS = 300.0  # over which it gives them up, and then it is gone

# 0.67 units/s from a single cell, against a whole world receiving about 6
# from the snow. Locally a body outweighs everything else by a wide margin,
# which is what makes death an event rather than a contribution.


def install_channels(medium) -> None:
    """Declare the cycle's channels on a medium. Idempotent.

    A medium with no ecosystem in it costs nothing at all, so this is opt-in
    rather than something `Medium.__init__` does -- `selftest_field` and the
    rig suites should not have to know the food web exists.
    """
    for name, (diffusivity, half_life) in CHANNELS.items():
        medium.add_channel(name, diffusivity, half_life)


@dataclass
class Carcass:
    """A dead thing, which is the only source the cycle has.

    It is not a creature and it has no comfort: it sinks and it gives off
    chum. RIGS.md 13.4's claim that "death is a resource that propagates"
    is this class plus the fact that a hunter also emits chum -- the cycle
    is fed continuously by predation and in pulses by whatever dies.
    """

    pos: tuple = (0.0, 0.0)
    yield_left: float = CARCASS_YIELD
    rate: float = CARCASS_YIELD / CARCASS_SECONDS

    # A body is denser than water and it goes down. This is the mechanism by
    # which the shallows feed the deep, and it means a kill made up top is a
    # gift to something you will meet later.
    #
    # 2.5 px/s, not 9: at 9 a carcass dropped in midwater is on the seabed
    # inside ninety seconds, which is long before anything has arrived and
    # means the plume is only ever seen lying on the floor. A body should take
    # about five minutes to fall through the column it was killed in, so that
    # the thing it attracts arrives while it is still falling.
    sink_speed: float = 2.5

    @property
    def spent(self) -> bool:
        return self.yield_left <= 0.0

    def step(self, dt: float, medium) -> None:
        if self.spent:
            return
        x, y = self.pos
        y = min(y + self.sink_speed * dt, medium.height - 2.0)
        if medium.is_solid(x, y):
            y = self.pos[1]
        self.pos = (x, y)

        give = min(self.yield_left, self.rate * dt)
        self.yield_left -= give
        medium.deposit("chum", x, y, give)


def scavenger(pos=(0.0, 0.0)) -> Creature:
    """Comes to the dead, from further away than anything else can. So it is
    the first thing that arrives anywhere, and watching where the scavengers
    are going is how you learn something died."""
    return Creature(
        name="scavenger",
        wants="carrion, and it can smell it across a room",
        does="arrives first, and leads everything else in",
        temp_band=(1.0, 22.0), temp_softness=9.0,
        depth_band=(0.0, 790.0), depth_softness=300.0,
        reads="chum", read_gain=1.6, feed_rate=0.18,
        emits=(("nutrient", 0.55),),
        pos=pos, speed=62.0,
    )


def decomposer(pos=(0.0, 0.0)) -> Creature:
    """Works over what the scavengers left. Slow, and it stays after they have
    gone -- so a place that has been busy stays productive long after the thing
    that made it busy is finished."""
    return Creature(
        name="decomposer",
        wants="what the scavengers leave behind",
        does="stays long after the crowd has moved on",
        temp_band=(1.0, 16.0), temp_softness=7.0,
        depth_band=(120.0, 790.0), depth_softness=260.0,
        reads="nutrient", read_gain=1.4, feed_rate=0.15,
        emits=(("bloom", 0.60),),
        pos=pos, speed=26.0,
    )


def drifter(pos=(0.0, 0.0)) -> Creature:
    """A filter feeder in the bloom. Barely swims, and it is the slowest thing
    in the cycle -- which is what makes the bloom a place rather than an
    event, and gives the grazers somewhere to be."""
    return Creature(
        name="drifter",
        wants="the bloom, and it is in no hurry",
        does="turns a slow chemical patch into somewhere worth eating",
        temp_band=(2.0, 18.0), temp_softness=8.0,
        depth_band=(40.0, 640.0), depth_softness=280.0,
        bubble_response=0.6,
        reads="bloom", read_gain=1.3, feed_rate=0.12,
        signals=(("swarm", 0.05),),
        pos=pos, speed=18.0,
    )


def grazer(pos=(0.0, 0.0)) -> Creature:
    """Eats the drifters, and is the only thing in the cycle that is afraid.
    Drawn to the swarm from across a room and repelled by a hunter within
    forty pixels, which is the whole flocking rule and the reason the
    aggregation churns instead of either dispersing or collapsing."""
    return Creature(
        name="grazer",
        wants="the swarm, and it does not want to be eaten",
        does="balls up around the food and thins where a hunter is",
        temp_band=(2.0, 20.0), temp_softness=7.0,
        depth_band=(0.0, 700.0), depth_softness=260.0,
        reads="swarm", read_gain=1.5, feed_rate=0.16,
        flees="menace", flee_gain=2.0,
        signals=(("shoal", 0.07),),
        pos=pos, speed=68.0,
    )


def hunter(pos=(0.0, 0.0)) -> Creature:
    """Comes to the shoal, and closes the loop by feeding on it -- the scraps
    are chum, which is what the scavengers came for in the first place. It
    also announces itself, because a thing this size cannot not."""
    return Creature(
        name="hunter",
        wants="the shoal",
        does="closes the cycle, and everything nearby knows it is there",
        temp_band=(1.0, 20.0), temp_softness=8.0,
        depth_band=(0.0, 760.0), depth_softness=320.0,
        reads="shoal", read_gain=1.4, feed_rate=0.18,
        emits=(("chum", 0.35),),
        signals=(("menace", 0.5),),
        pos=pos, speed=74.0,
    )


CYCLE_SPECIES = {
    "scavenger": scavenger,
    "decomposer": decomposer,
    "drifter": drifter,
    "grazer": grazer,
    "hunter": hunter,
}

# The order is the loop, and reading it top to bottom is reading the food web.
CYCLE_ORDER = ("scavenger", "decomposer", "drifter", "grazer", "hunter")

SPECIES.update(CYCLE_SPECIES)


def make_cycle(kind, pos=(0.0, 0.0)) -> Creature:
    return CYCLE_SPECIES[kind](pos)


def cycle_table() -> str:
    """The food web as it actually is in the data, rather than as documented.

    Written to be printed, because the one thing that must never drift is the
    claim that this is a closed loop: if a `reads` stops matching somebody
    else's `emits`, this prints a chain and the chain has a visible end.
    """
    rows = ["snowfall       ->  nutrient",
            "carrion        ->  chum"]
    carried = 1.0
    for kind in CYCLE_ORDER:
        c = CYCLE_SPECIES[kind]()
        out = ", ".join(f"{ch} x{y:.2f}" for ch, y in c.emits)
        sig = ", ".join(f"{ch} (presence)" for ch, _ in c.signals)
        out = "  ".join(x for x in (out, sig) if x) or "-"
        flee = f"  flees {c.flees}" if c.flees else ""
        if c.emits:
            carried *= sum(y for _, y in c.emits)
        rows.append(f"{c.name:<14} {c.reads:<9} ->  {out}{flee}")
    rows.append("")
    rows.append(f"substance carried once round the loop: {carried * 100:.1f}% of what "
                f"it started with,")
    rows.append("so the cycle cannot run on itself and needs snow and death.")
    return "\n".join(rows)
