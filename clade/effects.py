"""What a mixture *does* when it leaves your body.

This module is the game's single most important design constraint made
literal: **there is no effect table**. Nothing anywhere maps "fire organ ->
fire damage". An Effect is computed arithmetically from the humour vector,
so a mixture the designer never considered still behaves sensibly, and two
players who arrive at the same vector by completely different routes get
identical results.

That matters more than it sounds. It is the difference between a system
that can be *learned* — where a hypothesis about what a mixture will do can
be tested and confirmed — and a system that can only be *memorised*. The
whole game asks the player to be curious; it would be a lie to ask that and
then hide the answers in a dictionary.

The rules, in full, so they can be argued with:

  force      brine, signed. positive shoves outward, negative pulls in.
             the only humour that moves mass, because it is the only one
             with any.
  heat       ichor, positive. also the only source of light in the game.
  chill      brine at low ichor. cold water is dense water; a mixture that
             is heavy and unlit takes heat *out*, and enough of that
             freezes.
  murk       silt. blocks sight, dampens sound, and settles.
  jolt       spark. damage that ignores armour, arcs through charged water,
             and stuns.
  caustic    ichor x silt. the rot blend. damage over time to *tissue only*
             — this is what opens grown doors that force cannot.
  gentle     the inverse of divergence past a threshold. feeds, heals,
             quiets, and persuades living matter to open.

  loudness   magnitude x divergence. a big balanced charge is nearly
             silent; a small pure one is not. this single product is the
             entire stealth economy and it is not a coincidence that it is
             also the formula for "a weapon".
"""

import math

from . import config as C
from .humours import BRINE, ICHOR, SILT, SPARK, Charge, blend_of


class Effect:
    """The resolved consequence of a charge. Plain data — the world applies
    it, the renderer draws it, and neither needs to know what organs made
    it."""

    __slots__ = (
        "charge", "magnitude", "divergence", "blend", "blend_amount",
        "force", "heat", "murk", "jolt", "caustic", "gentle",
        "damage", "loudness", "light", "lift", "recoil", "color",
    )

    def __init__(self, charge: Charge):
        self.charge = charge
        m = charge.magnitude
        d = charge.divergence
        self.magnitude = m
        self.divergence = d
        self.blend, self.blend_amount = blend_of(charge)

        f = charge.fractions()
        b, i, s, k = f[BRINE], f[ICHOR], f[SILT], f[SPARK]
        scale = m * C.EFFECT_SCALE

        # --- gentleness first, because it gates everything else.
        #
        # A balanced mixture is not a weak weapon, it is a *different kind
        # of thing*. Diffuse energy has nowhere to concentrate: it warms
        # without burning, presses without shoving, and the body it touches
        # reads it as tissue rather than as an attack. So gentleness does
        # not merely add a channel, it *suppresses* the aggressive ones —
        # otherwise a perfectly balanced charge would still arrive carrying
        # a quarter of every hostile effect, which both reads wrong and
        # quietly makes the hardest build in the game into a free weapon.
        if d <= C.GENTLE_BELOW:
            t = 1.0 - (d / C.GENTLE_BELOW)
            # t**1.5, not t**2. The squared form put a second cliff on top
            # of the one `opens_tissue` already provides, so a mixture that
            # had been dragged down to a genuinely even 0.13 divergence —
            # which takes three organs and most of your reserve — still
            # came out too weak to turn anything, and the only working key
            # in the game was a single rare organ.
            soft = t ** 1.5
        else:
            soft = 0.0
        self.gentle = soft * scale
        sharp = 1.0 - soft

        # --- force. carries the sign of the brine component, which is the
        # only place in the game a negative humour survives all the way to
        # the world. that is what a Mirror Sac is for: negative brine is
        # not "less push", it is suction, and pointed at yourself it is
        # lift.
        brine_sign = 1.0 if charge[BRINE] >= 0.0 else -1.0
        self.force = b * scale * C.FORCE_PER_MAGNITUDE * brine_sign * sharp

        # --- heat and its opposite. ichor heats. brine *without* ichor
        # chills, because dense unlit water is cold water. the crossover is
        # the reason a pure-brine chain is a freezing tool nobody had to
        # design as one.
        self.heat = (i - 0.55 * b * max(0.0, 1.0 - i * 3.0)) * scale * C.HEAT_PER_MAGNITUDE * sharp

        self.murk = s * scale * C.SILT_PER_MAGNITUDE * sharp
        self.jolt = k * scale * C.SPARK_PER_MAGNITUDE * sharp

        # --- caustic. the product, not the sum: it needs *both*, so it is
        # unreachable by accident and obvious once found.
        self.caustic = 4.0 * i * s * scale * sharp

        # --- damage. concentration is what hurts. a perfectly balanced
        # charge of enormous magnitude is a warm bath.
        conc = max(0.0, (d - C.DIVERGENCE_DAMAGE_FLOOR)) / (1.0 - C.DIVERGENCE_DAMAGE_FLOOR)
        conc = max(0.0, min(1.0, conc))
        # nervefire (ichor+spark) is the one blend that beats pure anything,
        # and it has to actually beat it or nobody will ever pay for it.
        # The coefficient is set so a clean 50/50 lands about a fifth above
        # the best pure spike; the price is `recoil` below, which is the
        # only damage in the game you do to yourself on purpose.
        nerve = 6.0 * i * k
        self.damage = scale * C.DAMAGE_PER_MAGNITUDE * conc * (1.0 + nerve)
        self.recoil = nerve * scale * 0.42 * sharp

        # --- loudness. the product that runs the horror.
        self.loudness = m * d

        # --- light. ichor is the only thing that shines. silt eats it.
        self.light = max(0.0, i - 0.5 * s) * scale

        # --- lift. what this does to buoyancy if applied to a body.
        self.lift = -charge[BRINE] * C.BUOYANCY_GAIN

        self.color = charge.color()

    # ------------------------------------------------------------ helpers

    @property
    def opens_tissue(self) -> bool:
        """Grown doors answer to gentleness or to rot, and to nothing else.
        Two routes on purpose: the patient one and the ugly one."""
        return self.gentle > 1.2 or self.caustic > 2.4

    @property
    def freezes(self) -> bool:
        return self.heat < -1.6

    def describe(self) -> str:
        """One line, in the game's own voice, for the Assay bench. Written
        as observation rather than statistics because the codex's whole
        conceit is that you know what you have seen."""
        bits = []
        if self.gentle > 0.6:
            bits.append("it is gentle")
            if self.opens_tissue:
                bits.append("living things would open to it")
        if self.damage > 3.0:
            bits.append("it would hurt")
        if self.freezes:
            bits.append("it takes heat away")
        elif self.heat > 1.6:
            bits.append("it burns and it shines")
        if self.murk > 1.6:
            bits.append("it clouds the water")
        if self.jolt > 1.6:
            bits.append("it carries a shock")
        if self.caustic > 1.6:
            bits.append("it rots what it touches")
        if abs(self.force) > 220.0:
            bits.append("it pulls" if self.force < 0 else "it shoves")
        if not bits:
            bits.append("it does almost nothing")
        loud = ("silent", "quiet", "loud", "very loud")[
            min(3, int(self.loudness / 3.0))
        ]
        return ", ".join(bits) + ". " + loud + "."


def resolve(charge: Charge) -> Effect:
    return Effect(charge)


# ---------------------------------------------------------------------------
# Composition strain — what it costs a body to *be* a mixture rather than
# to fire one. Kept here rather than in body.py because it is the same
# family of rule: consequences derived from a vector.
# ---------------------------------------------------------------------------

def body_modifiers(comp: Charge) -> dict:
    """How a body's own standing composition changes it.

    You are always becoming what you eat. Every one of these is a real
    trade with a real upside, because a system where drifting is purely bad
    is just a second health bar wearing a hat.
    """
    f = comp.fractions()
    b, i, s, k = f[BRINE], f[ICHOR], f[SILT], f[SPARK]
    return {
        # heavy: sinks, hits harder, cannot climb.
        "weight": 0.55 + b * 1.5,
        "force_out": 0.75 + b * 0.9,
        # hot: bright (so visible), fast to act, cooks itself.
        "glow": i,
        "sight": C.BASE_SIGHT + i * comp.magnitude * C.SIGHT_PER_ICHOR,
        "heat_load": i * 1.4,
        # thick: hard to see, hard to see *with*, slow, and durable.
        "opacity": s,
        "speed": 1.18 - s * 0.5 - b * 0.22,
        "toughness": 0.8 + s * 0.7,
        # quick: everything faster, everything hurts more.
        "cycle": 1.0 - k * 0.45,      # multiplier on chain recharge time
        "fragility": 1.0 + k * 0.85,  # multiplier on damage taken
    }
