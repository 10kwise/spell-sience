"""The four humours, and the arithmetic of what a mixture *is*.

Everything that flows through your body is one of these vectors. Organs
transform them. Vents spend them. Creatures are made of them. The water you
swim in has a composition, and so, uncomfortably, do you.

    BRINE   ~   salt, density, pressure      mass. force. sinking.
    ICHOR   *   metabolic fuel, hot blood    heat. light. appetite.
    SILT    .   sediment, particulate        obscurity. decay. weight
                                             without energy.
    SPARK   !   nerve, potential             speed. precision. pain.

There are four and not six because four is the largest number of
independent axes a player can hold in their head while also aiming. Every
mixture is legible as "mostly this, a bit of that", and the pairwise blends
(there are exactly six) are few enough to be *discovered* rather than
memorised from a table.

The one non-obvious quantity here is **divergence**, and it is the spine of
the whole design. It measures how far a mixture is from equal parts. A
weapon is a spike: one humour, nearly pure, divergence near 1. Living
tissue is a smear: all four in rough balance, divergence near 0. The game
rewards spikes with power and punishes them with noise, and the only way
through a living door is to make something gentle — which is the hardest
thing to build, because every instinct the combat teaches you is to
concentrate.
"""

import math

BRINE, ICHOR, SILT, SPARK = 0, 1, 2, 3
N_HUMOURS = 4

NAMES = ("brine", "ichor", "silt", "spark")
GLYPHS = ("~", "*", ".", "!")

# Blue-white cold, ember, dun, violet-white. Chosen so the four are still
# distinguishable at 30% brightness on a near-black field, which is where
# they will spend most of their life.
COLORS = (
    (108, 168, 214),
    (232, 138,  74),
    (150, 132, 104),
    (188, 148, 236),
)

# What each reads as, for the codex. Deliberately physical rather than
# elemental: the player should end up thinking "this water is thick" and
# not "this is the earth element".
FEEL = (
    "heavy. it wants to fall and to push.",
    "hot. it burns and it shines, and shining is being seen.",
    "thick. it hides things and it eats them slowly.",
    "quick. it goes where it likes and it hurts on the way.",
)


class Charge:
    """A quantity of mixed humour. Mutable on purpose — an organ chain is a
    pipeline that rewrites one of these in place as it passes down the
    chain, and allocating a new tuple per organ per shot per creature was
    measurably the hottest thing in the frame."""

    __slots__ = ("v",)

    def __init__(self, brine=0.0, ichor=0.0, silt=0.0, spark=0.0):
        self.v = [float(brine), float(ichor), float(silt), float(spark)]

    # ------------------------------------------------------------ basics

    @staticmethod
    def zero() -> "Charge":
        return Charge()

    @staticmethod
    def of(seq) -> "Charge":
        c = Charge()
        c.v = [float(x) for x in seq]
        return c

    @staticmethod
    def pure(index: int, amount: float = 1.0) -> "Charge":
        c = Charge()
        c.v[index] = float(amount)
        return c

    def copy(self) -> "Charge":
        c = Charge.__new__(Charge)
        c.v = list(self.v)
        return c

    def __getitem__(self, i):
        return self.v[i]

    def __setitem__(self, i, x):
        self.v[i] = float(x)

    def __iter__(self):
        return iter(self.v)

    def __repr__(self):
        return "<" + " ".join(
            "%s%.1f" % (GLYPHS[i], self.v[i]) for i in range(N_HUMOURS)
        ) + ">"

    # --------------------------------------------------------- arithmetic

    def add(self, other) -> "Charge":
        for i in range(N_HUMOURS):
            self.v[i] += other[i]
        return self

    def scaled(self, k: float) -> "Charge":
        c = Charge.__new__(Charge)
        c.v = [x * k for x in self.v]
        return c

    def scale_in_place(self, k: float) -> "Charge":
        for i in range(N_HUMOURS):
            self.v[i] *= k
        return self

    def clamp_nonneg(self) -> "Charge":
        """Negative humour is meaningful in exactly one place — a Mirror Sac
        inverting brine to make something rise — and the sign is carried by
        the *effect*, not by the reserve. Anything that stores a Charge
        clamps first, or a clever loop mints free energy out of a negative
        component."""
        for i in range(N_HUMOURS):
            if self.v[i] < 0.0:
                self.v[i] = 0.0
        return self

    # --------------------------------------------------------- measures

    @property
    def magnitude(self) -> float:
        """Total humour present. This is 'how much', and it maps almost
        directly onto how much the world notices."""
        return sum(abs(x) for x in self.v)

    @property
    def signed_total(self) -> float:
        return sum(self.v)

    def fractions(self) -> list:
        m = self.magnitude
        if m < 1e-9:
            return [0.25, 0.25, 0.25, 0.25]
        return [abs(x) / m for x in self.v]

    @property
    def divergence(self) -> float:
        """0 = equal parts, 1 = a single humour.

        L1 distance from the balanced point, normalised by its own maximum
        (0.75 + 3*0.25 = 1.5). Chosen over entropy or variance because it is
        *linear* — halving the excess of one humour halves the divergence,
        which means the player's mental model ("take some of the spike off")
        maps onto the number in the obvious way. Entropy does not behave
        like that near the balanced point and the difference is felt."""
        f = self.fractions()
        return min(1.0, sum(abs(x - 0.25) for x in f) / 1.5)

    @property
    def dominant(self) -> int:
        best, bi = -1.0, BRINE
        for i in range(N_HUMOURS):
            a = abs(self.v[i])
            if a > best:
                best, bi = a, i
        return bi

    def ranked(self) -> list:
        """Humour indices, largest first."""
        return sorted(range(N_HUMOURS), key=lambda i: -abs(self.v[i]))

    @property
    def is_gentle(self) -> bool:
        from .config import GENTLE_BELOW
        return self.magnitude > 1e-6 and self.divergence <= GENTLE_BELOW

    def color(self) -> tuple:
        """Blend the humour colours by proportion. A balanced charge comes
        out a pale, sickly, almost-white — which is exactly right: gentle
        things in this game should look like flesh, not like a spell."""
        f = self.fractions()
        r = g = b = 0.0
        for i in range(N_HUMOURS):
            r += COLORS[i][0] * f[i]
            g += COLORS[i][1] * f[i]
            b += COLORS[i][2] * f[i]
        return (int(r), int(g), int(b))


# ---------------------------------------------------------------------------
# Blends. Six pairs, and each one is a thing the player can find out by
# trying it once. They are named here because naming them is the codex's
# job, but nothing in the simulation branches on the name — the effect
# resolver (clade/effects.py) computes consequences from the vector itself,
# so a mixture that is 60/40 gets 60/40 of the behaviour rather than
# snapping to whichever label won.
# ---------------------------------------------------------------------------

BLEND_NAMES = {
    (BRINE, ICHOR): "boil",
    (BRINE, SILT): "slurry",
    (BRINE, SPARK): "conduction",
    (ICHOR, SILT): "rot",
    (ICHOR, SPARK): "nervefire",
    (SILT, SPARK): "static",
}

BLEND_NOTES = {
    "boil": "water torn into bubbles that collapse. bright, violent, heard everywhere.",
    "slurry": "sediment made heavy. it falls, it smothers, it puts things out.",
    "conduction": "the water itself carries it. wide, indiscriminate, no aim required.",
    "rot": "slow. it does not kill things, it unmakes them. doors included.",
    "nervefire": "the worst thing you can make. it costs you to make it.",
    "static": "charged grit. it hangs in the water and it tells you what it touches.",
}


def blend_of(charge: Charge):
    """The named pair for a mixture, plus how strongly it reads as that pair
    (0..1). A near-pure charge has no blend."""
    order = charge.ranked()
    a, b = order[0], order[1]
    m = charge.magnitude
    if m < 1e-9:
        return None, 0.0
    second = abs(charge[b]) / m
    if second < 0.12:
        return None, 0.0
    key = (a, b) if a < b else (b, a)
    name = BLEND_NAMES.get(key)
    # 0.5 of the total in the second humour is a perfect 50/50 blend.
    return name, min(1.0, second / 0.5)


def mix(*charges) -> Charge:
    out = Charge()
    for c in charges:
        out.add(c)
    return out


def lerp(a: Charge, b: Charge, t: float) -> Charge:
    c = Charge()
    for i in range(N_HUMOURS):
        c.v[i] = a[i] + (b[i] - a[i]) * t
    return c


def toward_balance(charge: Charge, t: float) -> Charge:
    """Pull a mixture toward equal parts while preserving its magnitude.
    This is what a Harmonic organ does and it is the rarest verb in the
    game, because it is the only way to make a key."""
    m = charge.magnitude
    if m < 1e-9:
        return charge
    even = m / N_HUMOURS
    for i in range(N_HUMOURS):
        charge.v[i] += (even - charge.v[i]) * t
    return charge


def strain(charge: Charge) -> float:
    """How much it costs a *body* to hold this composition, 0..1.

    Bodies are made of balanced tissue. Carrying a spiked composition is
    survivable and useful — a brine-heavy body sinks fast and hits hard —
    but it is a strain, and the strain is what stops the optimal play from
    being 'become entirely one thing'. Squared so that mild specialisation
    is nearly free and total specialisation is ruinous."""
    d = charge.divergence
    return d * d
