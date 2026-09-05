"""Organs: the parts you are made of, and the grammar they form.

A chain is an ordered sequence of cells in your body:

    INTAKE  ->  transform  ->  transform  ->  ...  ->  VENT

The intake decides what enters. Each transform rewrites the humour vector
*in place*. The vent decides how what is left leaves you. Because every
transform acts on whatever the previous one produced, **order is the
design**, and it is the entire reason this system is worth building:

    SALT NODE -> KILN     doubles the brine, then burns the doubled brine.
                          a lance.
    KILN -> SALT NODE     burns the brine first, then doubles a brine that
                          is no longer there. a cough.

Same two organs. Different creature. Nothing in the code special-cases
either arrangement; it falls out of running the functions in the order the
player laid them.

Three rules were held to while writing this file, and breaking any of them
would make the system worse in a way that is hard to see and impossible to
undo later:

**No organ prints a number.** Not one. Organs carry a name, a shape, and a
line of prose about what somebody once saw them do. Everything else is
learned at the Assay bench by firing the thing and watching the vector
change. A system that tells you what it does is a system you read once; a
system that shows you what it did is one you think about in the shower.

**Every organ does exactly one thing.** If an organ needs two clauses to
describe, it is two organs. This is what makes a chain readable at a glance
after you know the pieces, and it is what makes a twelve-organ body
comprehensible rather than a soup.

**Downsides are consequences, never balance tax.** The Ember Gland does not
"have a drawback"; it makes heat, and heat is heat — it cooks its
neighbours in your body, it lights you up, and light is how you are found.
Nobody authored that as a cost. It is the same heat doing the same thing in
three places.
"""

from .humours import (
    BRINE, ICHOR, SILT, SPARK, N_HUMOURS, Charge, toward_balance,
)

INTAKE, TRANSFORM, VENT = "intake", "transform", "vent"


class ChainContext:
    """Mutable state threaded down a chain. Organs write to it to change
    how the *emission* happens rather than what is in it — spread, count,
    speed, re-entry — which is the second axis of the grammar."""

    __slots__ = (
        "body", "world", "pos", "aim", "count", "spread", "speed",
        "recursions", "aborted", "extra_heat", "viability_cost",
        "quiet", "trail", "delay", "log", "heat_scale", "dry",
    )

    def __init__(self, body=None, world=None, pos=None, aim=None):
        self.body = body
        self.world = world
        self.pos = pos
        self.aim = aim
        self.count = 1
        self.spread = 0.0
        self.speed = 1.0
        self.recursions = 0
        self.aborted = False
        self.extra_heat = 0.0
        self.viability_cost = 0.0
        self.heat_scale = 1.0
        # A standing chain is measured every half second to find out what
        # it is doing to you. Measuring it must not also drain the tank —
        # the draining is the upkeep, charged once, in body.update().
        self.dry = False
        self.quiet = 1.0        # multiplier on how loud the emission is
        self.trail = False
        self.delay = 0.0
        self.log = []           # (organ_name, charge_snapshot) for the Assay


class OrganType:
    """The immutable definition.

    Glyphs are deliberately plain ASCII. The first pass used typographic
    symbols (a delta for the Kiln, a lozenge for the Ember Gland) which
    looked far better in the source and rendered as identical empty boxes
    in the game, because pygame's bundled font has no coverage for that
    block — so the one thing a player most needs to read at a glance, which
    organ is in which socket, was unreadable in every socket at once.
 Instances (class Organ, below) carry the
    heat and wear that make one particular Kiln different from another."""

    __slots__ = (
        "key", "name", "role", "glyph", "heat", "tier", "blurb",
        "fn", "vent", "unique", "weight",
    )

    def __init__(self, key, name, role, glyph, heat, tier, blurb,
                 fn=None, vent=None, unique=False, weight=1.0):
        self.key = key
        self.name = name
        self.role = role
        self.glyph = glyph
        self.heat = heat          # heat added to THIS organ per activation
        self.tier = tier          # 0 common .. 3 deep
        self.blurb = blurb        # what you are told. never what it does.
        self.fn = fn              # (charge, ctx) -> charge
        self.vent = vent          # VentShape, for role == VENT
        self.unique = unique      # one per body
        self.weight = weight      # drop weighting

    def __repr__(self):
        return "<%s %s>" % (self.role, self.name)


class VentShape:
    """How an emission is delivered. Kept separate from the effect itself:
    the *what* comes from the humour vector, the *where* comes from here,
    and neither knows about the other."""

    __slots__ = ("kind", "speed", "life", "radius", "spread", "count",
                 "range", "sticky")

    def __init__(self, kind, speed=0.0, life=1.0, radius=10.0,
                 spread=0.0, count=1, rng=0.0, sticky=False):
        self.kind = kind
        self.speed = speed
        self.life = life
        self.radius = radius
        self.spread = spread
        self.count = count
        self.range = rng
        self.sticky = sticky


class Organ:
    """A placed, owned, wearing-out instance."""

    __slots__ = ("type", "heat", "stored", "uses", "integrity", "seized")

    def __init__(self, otype: OrganType):
        self.type = otype
        self.heat = 0.0
        self.stored = None        # Charge, for accumulators
        self.uses = 0
        self.integrity = 1.0      # 1.0 fresh, 0.0 dead
        self.seized = False       # too hot to work; hysteresis in body.py

    @property
    def key(self):
        return self.type.key

    @property
    def name(self):
        return self.type.name

    @property
    def role(self):
        return self.type.role

    @property
    def glyph(self):
        return self.type.glyph

    # Heat per unit of humour an organ *adds*. This one constant is what
    # stops stacked amplifiers from being the answer to every question.
    #
    # Without it, two Salt Nodes multiply brine by 7.8 for a flat six heat,
    # which beat every other build in every region — the conversion losses
    # that were supposed to give the four regions their own character were
    # simply dwarfed by the amplifier stack, and where you were standing
    # stopped mattering. Charging for work done makes a big shot cost what
    # a big shot should cost, in the currency the game already uses to
    # punish greed: your own organs cooking, your own light giving you
    # away.
    WORK_HEAT = 1.0 / 6.0

    def apply(self, charge, ctx):
        self.uses += 1
        # A worn organ does its job badly rather than not at all. The
        # failure is a fade, not a cliff, so a body degrades legibly over a
        # long descent instead of dying at a threshold you cannot see.
        wear = 0.45 + 0.55 * self.integrity
        if self.type.fn is None:
            self.heat += self.type.heat
            return charge
        before = charge.copy()
        out = self.type.fn(charge, ctx)
        if wear < 0.999:
            for i in range(N_HUMOURS):
                out.v[i] = before[i] + (out.v[i] - before[i]) * wear
        grew = max(0.0, out.magnitude - before.magnitude)
        self.heat += self.type.heat * (1.0 + grew * Organ.WORK_HEAT) \
            * ctx.heat_scale
        ctx.log.append((self.name, out.copy()))
        return out

    def to_dict(self):
        return {"key": self.key, "integrity": round(self.integrity, 3),
                "uses": self.uses}


# ===========================================================================
# INTAKES — what enters the chain.
#
# An intake's job is to answer "how much, of what, and at what risk". They
# are the only organs that touch the world directly rather than the vector,
# and they are why the *place you are standing* changes what your body can
# do: the water in the Nursery is warm and organic, the Cisterns are half
# sediment, the Lattice is live, and the Sill is cold salt. The same body
# is a different animal in each.
# ===========================================================================

def _draw_reserve(ctx, amount, purify=False, floor_only=False):
    body = ctx.body
    if body is not None and ctx.dry:
        return body.peek_reserve(amount, purify=purify, floor_only=floor_only)
    if body is None:
        # Assay bench: no body, so hand back a neutral sample so the player
        # can still study the *transforms* in isolation. This is the only
        # place in the game where humour appears from nowhere, and it is
        # deliberately a laboratory.
        c = Charge(amount / 4, amount / 4, amount / 4, amount / 4)
        return c
    return body.tap_reserve(amount, purify=purify, floor_only=floor_only)


def _siphon(charge, ctx):
    return _draw_reserve(ctx, 3.2)


def _gullet(charge, ctx):
    ctx.quiet *= 1.9     # a big mouth is a loud mouth
    return _draw_reserve(ctx, 9.0)


def _filter_gill(charge, ctx):
    # Draws only the humour you already have most of. A purity engine: it
    # makes weapons out of whatever the room is full of, and it makes keys
    # impossible.
    return _draw_reserve(ctx, 4.4, purify=True)


def _leech(charge, ctx):
    body = ctx.body
    if body is None:
        return Charge(1.2, 1.2, 1.2, 1.2)
    got = body.tap_nearby_flesh(ctx.world, ctx.pos, 5.5)
    if got is None:
        ctx.aborted = True
        return Charge()
    return got


def _root(charge, ctx):
    return _draw_reserve(ctx, 6.0, floor_only=True)


def _mouth(charge, ctx):
    body = ctx.body
    if body is None:
        return Charge(2, 2, 2, 2)
    # Scales with how full you are: rich bodies fire enormous shots and
    # empty ones fire nothing. Feast or famine, made literal.
    frac = body.reserve.magnitude / max(1.0, body.reserve_cap)
    return body.tap_reserve(2.0 + 11.0 * frac * frac)


# ===========================================================================
# TRANSFORMS — the grammar.
# ===========================================================================

def _convert(charge, src, dst, rate, loss=0.30):
    """Move humour from one axis to another.

    The loss is the most important single number in this file, and it was
    wrong for a while at 0.15. Cheap conversion means a chain of two
    converters can turn *any* water into *any* humour for almost nothing,
    which quietly deletes the entire point of having four regions with four
    different kinds of water: the same amplifier stack won everywhere, and
    where you were standing stopped mattering.

    At 0.30 a single conversion is a real decision and a double conversion
    costs you half of everything. Working *with* the water you are standing
    in beats working against it — unless the things that live there are
    armoured against exactly what the water gives you, which is the case in
    the Lattice, and which is the best lesson in the game."""
    moved = charge[src] * rate
    charge.v[src] -= moved
    charge.v[dst] += moved * (1.0 - loss)
    return charge


def _kiln(charge, ctx):
    return _convert(charge, BRINE, ICHOR, 0.85)


def _condenser(charge, ctx):
    return _convert(charge, ICHOR, BRINE, 0.85)


def _settling_sac(charge, ctx):
    # Everything decays toward sediment. The only conversion that accepts
    # any input at all, and it pays for that generality: it is the lossiest
    # organ in the game, so "turn it all to silt" is always available and
    # never efficient.
    for src in (BRINE, ICHOR, SPARK):
        _convert(charge, src, SILT, 0.5, loss=0.40)
    return charge


def _ganglion(charge, ctx):
    ctx.viability_cost += 1.4    # thinking hurts
    return _convert(charge, ICHOR, SPARK, 0.8, loss=0.10)


def _brackish(charge, ctx):
    return _convert(charge, SILT, BRINE, 0.7)


def _amplify(charge, index, gain):
    """Multiply one humour — but with saturation.

    A flat multiplier is a trap disguised as an organ. Two Salt Nodes at a
    flat 2.8 is 7.8x brine for six heat, and because the damage rules
    reward *concentration* as well as magnitude, purity gets paid twice:
    once for being big and once for being pure. Measured, that single
    interaction made one amplifier stack the best build in all four
    regions regardless of what lived there, which collapsed the ecology,
    the four kinds of water and most of the reason to own other organs.

    So the gain falls off as the humour approaches purity: you cannot
    concentrate what is already concentrated. Amplifying a minority humour
    is efficient and amplifying a spike is nearly pointless, which puts the
    optimum somewhere in the middle of the range instead of at the end of
    it — and a design whose optimum is an interior point is a design with
    something to think about in it."""
    m = charge.magnitude
    if m < 1e-9:
        return charge
    frac = abs(charge[index]) / m
    effective = 1.0 + (gain - 1.0) * (1.0 - frac)
    charge.v[index] *= effective
    return charge


def _salt_node(charge, ctx):
    return _amplify(charge, BRINE, 3.4)


def _ember_gland(charge, ctx):
    return _amplify(charge, ICHOR, 3.4)


def _spine(charge, ctx):
    ctx.speed *= 1.45
    return _amplify(charge, SPARK, 3.2)


def _bloom(charge, ctx):
    return _amplify(charge, SILT, 3.6)


def _muffle(charge, ctx):
    # Halves the shot and more than halves the noise. The correct answer
    # far more often than it looks, which is a lesson the game would rather
    # you learn late and painfully.
    charge.scale_in_place(0.52)
    ctx.quiet *= 0.30
    return charge


def _swell(charge, ctx):
    charge.scale_in_place(1.55)
    return charge


def _sieve(charge, ctx):
    """Cuts the largest humour down to the size of the next largest.

    The obvious implementation — delete the spike outright — is worse than
    it looks. It does not move a mixture toward balance, it moves the
    *spike somewhere else*: knock 90% off the top humour and whatever was
    second is now a spike of its own, so two Sieves in a row leave you as
    divergent as you started, pointing a different way. Levelling to the
    runner-up converges instead, which makes a Sieve chain a real (slow,
    lossy, magnitude-destroying) alternative to owning a Harmonic — and
    the game should not have exactly one answer to its own last gate."""
    order = charge.ranked()
    top, second = order[0], order[1]
    target = abs(charge[second])
    if abs(charge[top]) > target:
        sign = 1.0 if charge[top] >= 0 else -1.0
        charge.v[top] = sign * target
    return charge


def _harmonic(charge, ctx):
    # The only organ that pulls toward balance. It is rare, it is deep, and
    # it is the difference between a body that can open things and one that
    # can only break them.
    return toward_balance(charge, 0.85)


def _mirror_sac(charge, ctx):
    # Inverts the dominant humour's sign. On brine that is lift; the game's
    # traversal upgrade is a *negative number*, which nobody had to build a
    # jump button for.
    d = charge.dominant
    charge.v[d] = -charge.v[d]
    return charge


def _fork(charge, ctx):
    # Multicast. Two of everything downstream, at a cost that is less than
    # half — so forking is a real gain in total output and a real loss in
    # concentration, which is exactly the trade the divergence rules
    # already punish and reward.
    ctx.count *= 2
    ctx.spread += 13.0
    charge.scale_in_place(0.62)
    return charge


def _knot(charge, ctx):
    # Re-entry: everything upstream of the vent runs again on its own
    # output. Doubles the heat, doubles the transformation, and can turn a
    # mild converter into something that empties your reserve into a single
    # unrecognisable shot. Capped at two extra passes because three is a
    # crash and the player would never see why.
    if ctx.recursions < 2:
        ctx.recursions += 1
    return charge


def _valve(charge, ctx):
    # Passes only a charge worth passing. Pointless alone; transformative
    # with a Bladder in front of it, which is a two-organ discovery the
    # game never mentions.
    if charge.magnitude < 6.0:
        ctx.aborted = True
    return charge


def _bladder(charge, ctx):
    # Accumulates across firings and dumps when full. State lives on the
    # instance, so two Bladders in one body fill independently.
    org = ctx.log and None
    return charge  # real behaviour is in Body._run_chain (needs the instance)


def _proboscis(charge, ctx):
    ctx.delay += 0.0
    ctx.speed *= 1.9
    return charge


def _spinneret(charge, ctx):
    ctx.trail = True
    charge.scale_in_place(0.78)
    return charge


def _tithe(charge, ctx):
    # Pays viability for magnitude. An honest, terrible bargain, and the
    # only organ in the game that says out loud what all the others imply.
    ctx.viability_cost += 3.0
    charge.scale_in_place(1.75)
    return charge


# ===========================================================================
# THE ROSTER
# ===========================================================================

_T = []


def _add(*args, **kw):
    t = OrganType(*args, **kw)
    _T.append(t)
    return t


# --- intakes -------------------------------------------------------------

SIPHON = _add("siphon", "Siphon", INTAKE, "o", 1.0, 0,
              "a soft ring of muscle. it opens and closes on its own, slowly, "
              "like something asleep.", _siphon)
GULLET = _add("gullet", "Gullet", INTAKE, "O", 4.0, 0,
              "it was built to swallow more than it needs. you can hear it "
              "work from the next room.", _gullet)
FILTER_GILL = _add("filter_gill", "Filter Gill", INTAKE, "=", 2.0, 1,
                   "a stack of fine plates. whatever passes through comes out "
                   "the same as itself, only more so.", _filter_gill)
LEECH = _add("leech", "Leech", INTAKE, "c", 2.5, 1,
             "it does not care for water. it wants to be against something.",
             _leech)
ROOT = _add("root", "Root", INTAKE, "Y", 2.0, 1,
            "it reaches down. what it brings up is mostly floor.", _root)
MOUTH = _add("mouth", "Mouth", INTAKE, "U", 5.0, 2,
             "it takes what you have. all of it, if you have a lot.", _mouth)

# --- converters ----------------------------------------------------------

KILN = _add("kiln", "Kiln", TRANSFORM, "^", 7.0, 0,
            "a small hard chamber, scorched inside. heavy things go in.", _kiln)
CONDENSER = _add("condenser", "Condenser", TRANSFORM, "v", 2.0, 1,
                 "cold to the touch, always, even here. it drinks warmth and "
                 "gives back weight.", _condenser)
SETTLING_SAC = _add("settling_sac", "Settling Sac", TRANSFORM, ".", 1.5, 0,
                    "everything ends up in it eventually. that seems to be the "
                    "point.", _settling_sac)
GANGLION = _add("ganglion", "Ganglion", TRANSFORM, "%", 5.0, 2,
                "a knot of grey thread. holding it makes your own edges ache.",
                _ganglion)
BRACKISH = _add("brackish", "Brackish Node", TRANSFORM, "~", 2.5, 1,
                "silt goes in. something denser comes out. it smells of the "
                "bottom.", _brackish)

# --- amplifiers ----------------------------------------------------------

SALT_NODE = _add("salt_node", "Salt Node", TRANSFORM, "#", 3.0, 0,
                 "a crust of white crystal around a hollow. it grows back if "
                 "you break it.", _salt_node)
EMBER_GLAND = _add("ember_gland", "Ember Gland", TRANSFORM, "&", 12.0, 1,
                   "warm. it is warm even now, even out here, even after all "
                   "this time.", _ember_gland)
SPINE = _add("spine", "Spine", TRANSFORM, "!", 6.0, 1,
             "it twitches when you are not looking at it.", _spine)
BLOOM = _add("bloom", "Silt Bloom", TRANSFORM, ":", 2.0, 1,
             "a dry grey flower. it sheds constantly and never gets smaller.",
             _bloom)
SWELL = _add("swell", "Swell", TRANSFORM, "@", 5.0, 1,
             "whatever goes through arrives bigger. nothing else about it is "
             "remarkable.", _swell)

# --- shapers -------------------------------------------------------------

MUFFLE = _add("muffle", "Muffle", TRANSFORM, "_", 0.5, 0,
              "dense wet wadding. the room gets further away when you use it.",
              _muffle)
SIEVE = _add("sieve", "Sieve", TRANSFORM, "/", 1.0, 1,
             "it takes the largest thing and will not say where it went.",
             _sieve)
HARMONIC = _add("harmonic", "Harmonic", TRANSFORM, "+", 3.0, 3,
                "it is the only thing down here that is the same all the way "
                "through.", _harmonic, unique=False, weight=0.35)
MIRROR_SAC = _add("mirror_sac", "Mirror Sac", TRANSFORM, "M", 4.0, 2,
                  "hold it up and the water above looks like the water below.",
                  _mirror_sac)
FORK = _add("fork", "Fork", TRANSFORM, "<", 3.0, 1,
            "it has two of everything and no opinion about which.", _fork)
KNOT = _add("knot", "Knot", TRANSFORM, "8", 9.0, 2,
            "you cannot find the end of it. you have tried.", _knot)
VALVE = _add("valve", "Valve", TRANSFORM, "T", 1.0, 1,
             "shut. it stays shut until it does not.", _valve)
BLADDER = _add("bladder", "Bladder", TRANSFORM, "0", 1.5, 1,
               "it fills. you can watch it fill. it does not do anything while "
               "it fills.", _bladder)
TITHE = _add("tithe", "Tithe", TRANSFORM, "$", 4.0, 3,
             "it asks. if you let it, it takes, and it gives back more than it "
             "took from somewhere that is not here.", _tithe, weight=0.4)
SPINNERET = _add("spinneret", "Spinneret", TRANSFORM, ";", 3.0, 2,
                 "it lays a line behind whatever leaves you.", _spinneret)
PROBOSCIS = _add("proboscis", "Proboscis", TRANSFORM, "-", 2.0, 2,
                 "long. much longer than it looks when it is coiled.",
                 _proboscis)

# --- vents ---------------------------------------------------------------

SPIRACLE = _add("spiracle", "Spiracle", VENT, ">", 2.0, 0,
                "a hard little nozzle. it points where you point.", None,
                VentShape("bolt", speed=430.0, life=1.5, radius=6.0))
MAW = _add("maw", "Maw", VENT, "D", 4.0, 0,
           "it opens much wider than the body it is in.", None,
           VentShape("cone", speed=250.0, life=0.34, radius=17.0, spread=46.0,
                     count=5))
PORE_FIELD = _add("pore_field", "Pore Field", VENT, "*", 3.0, 1,
                  "thousands of them. you cannot feel any single one.", None,
                  VentShape("aura", radius=112.0, life=0.5))
CASTER = _add("caster", "Caster", VENT, "C", 3.0, 1,
              "it throws. it is not accurate and it does not need to be.", None,
              VentShape("lob", speed=290.0, life=1.15, radius=13.0))
TENDRIL = _add("tendril", "Tendril", VENT, "|", 3.5, 2,
               "it goes out and it stays out for as long as you can stand it.",
               None, VentShape("beam", speed=690.0, life=0.14, radius=8.0,
                               rng=300.0))
SEED = _add("seed", "Seed", VENT, "S", 2.0, 2,
            "you leave it somewhere. it remembers you later.", None,
            VentShape("seed", speed=200.0, life=5.0, radius=15.0, sticky=True))

ALL = list(_T)
BY_KEY = {t.key: t for t in ALL}

INTAKES = [t for t in ALL if t.role == INTAKE]
TRANSFORMS = [t for t in ALL if t.role == TRANSFORM]
VENTS = [t for t in ALL if t.role == VENT]

# What you wake up with. Deliberately a *working* body and a boring one:
# a quiet intake, one converter, one amplifier, one nozzle. It can kill the
# first thing you meet and it can do nothing clever at all, which is the
# correct first hour.
STARTING_KEYS = ["siphon", "kiln", "salt_node", "spiracle", "settling_sac"]


def make(key: str) -> Organ:
    return Organ(BY_KEY[key])


def drops_for_tier(max_tier: int, rng, n: int = 1) -> list:
    """Weighted pick, capped at a tier. Depth gates complexity: you cannot
    find a Harmonic in the Nursery, so the key-making problem cannot be
    solved before the game has taught you why you would want to."""
    pool = [t for t in ALL if t.tier <= max_tier]
    weights = [t.weight * (1.0 if t.tier == max_tier else 1.4) for t in pool]
    out = []
    for _ in range(n):
        total = sum(weights)
        r = rng.random() * total
        acc = 0.0
        for t, w in zip(pool, weights):
            acc += w
            if r <= acc:
                out.append(Organ(t))
                break
        else:
            out.append(Organ(pool[-1]))
    return out
