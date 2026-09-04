"""The roster.

One ecological rule runs underneath all of it, and it is the reason the
four regions play differently rather than merely looking different:

    **things are armoured against the water they live in.**

The Cisterns are thick with sediment and everything there shrugs off
sediment. The Lattice is live and everything there shrugs off nerve. The
Sill is cold brine and the old things in it are armoured against weight.
So in every region after the first, the humour the water hands you for free
is the one the locals are hardest to hurt with — and the answer is to pay
the conversion toll, or to arrive still carrying water from somewhere else.

That last option is the one worth noticing. Your reserve is a supply line.
A body that fills up on warm Nursery water and takes it down into the
Cisterns is carrying ammunition that cannot be bought locally, and running
out of it two regions from the nearest source is a specific and quiet kind
of trouble that no message ever warns you about.

The Nursery is deliberately exempt. It is where the obvious answer works,
because a tutorial that punishes the obvious answer is not a tutorial.

Every entry is a claim about what the player will learn from meeting it.
Where a species has a `codex` line, that line is written as somebody's
observation and never as a statistic, because the codex is diegetic: it is
the facility's own record, and the facility has been watching these things
kill each other for a very long time and has stopped being surprised.

Resistances are per humour and they are the whole of the "weakness" system.
A thing made of sediment shrugs off sediment. A thing that is mostly nerve
is barely there to hit. Four numbers, and the player can reason about all
four from what the creature looks like and what it does, which is the
difference between a puzzle and a bestiary lookup.
"""

from .creatures import Species

SPECIES = {}


def _s(*a, **kw):
    sp = Species(*a, **kw)
    SPECIES[sp.key] = sp
    return sp


# --------------------------------------------------------------- nursery

COELENTER = _s(
    "coelenter", "Coelenter", viability=18.0, radius=13.0, speed=26.0,
    organs=["siphon", "settling_sac"], chain=[], behaviour="drift",
    resist=[0.0, 0.0, 0.35, 0.0], senses=0.35, tier=0, glow=0.10,
    peaceful=True,
    codex="it drifts. it has drifted past you four times now and has not "
          "once altered course. there is nothing inside it that decides "
          "anything.",
    harvest_note="it did not resist. it did not appear to notice.",
)

ATTENDANT = _s(
    "attendant", "Attendant", viability=34.0, radius=15.0, speed=54.0,
    organs=["siphon", "harmonic", "pore_field"], chain=[], behaviour="attendant",
    resist=[0.1, 0.1, 0.1, 0.1], senses=1.4, tier=0, glow=0.30,
    peaceful=True,
    codex="it keeps station off your flank at about nine metres. when you "
          "stop, it stops. it has never come closer and it has never fallen "
          "behind. you do not know what it wants.",
    harvest_note="it did not move away.",
)

FRY = _s(
    "fry", "Gullet-fry", viability=9.0, radius=7.0, speed=104.0,
    organs=["gullet"], chain=[], behaviour="swarm",
    resist=[0.0, 0.0, 0.0, 0.2], senses=1.1, tier=0, glow=0.04,
    aggression=1.6,
    codex="too small to be a problem and there are never few of them. they "
          "do not want you dead. they want what you are carrying, which "
          "turns out to be worse.",
)

SOUNDER = _s(
    "sounder", "Sounder", viability=26.0, radius=16.0, speed=14.0,
    organs=["siphon", "swell", "pore_field"], chain=[], behaviour="sounder",
    resist=[0.0, 0.0, 0.0, 0.0], senses=2.1, tier=0, glow=0.22,
    codex="anchored, blind, and listening. it has no way to hurt you at all. "
          "it does not need one.",
    harvest_note="the room went quiet in a way you had forgotten about.",
)

NURSE = _s(
    "nurse", "Nursemaid", viability=52.0, radius=19.0, speed=62.0,
    organs=["siphon", "kiln", "salt_node", "spiracle"], chain=[0, 1, 2, 3],
    behaviour="stalk", resist=[0.25, 0.0, 0.0, 0.0], senses=1.0, tier=0,
    glow=0.18,
    codex="it was built to move the stock between chambers and it is still "
          "doing that. you are stock. the chamber it wants you in is not one "
          "you would choose.",
)

# --------------------------------------------------------------- cisterns

LAMPREY = _s(
    "lamprey", "Lamprey", viability=30.0, radius=10.0, speed=132.0,
    organs=["leech", "spine", "spiracle"], chain=[0, 1, 2], behaviour="stalk",
    resist=[0.25, 0.0, 0.45, 0.35], senses=1.3, tier=1, glow=0.05,
    aggression=1.7,
    codex="it does not hunt you so much as commute through you.",
)

OSSUARY = _s(
    "ossuary", "Ossuary", viability=140.0, radius=26.0, speed=38.0,
    organs=["gullet", "kiln", "ember_gland", "maw"], chain=[0, 1, 2, 3],
    behaviour="ossuary", resist=[0.55, 0.10, 0.50, 0.0], armour=0.55,
    senses=0.8, tier=1, glow=0.34,
    codex="plated all the way round, except where it has to let the heat "
          "out. everything down here that lasted this long solved the same "
          "problem the same way and left the same hole.",
    harvest_note="the plates came away in sheets. underneath it was very "
                 "small.",
)

CARRION = _s(
    "carrion", "Carrion Drift", viability=44.0, radius=17.0, speed=76.0,
    organs=["gullet", "settling_sac", "bloom", "caster"], chain=[0, 1, 2, 3],
    behaviour="carrion", resist=[0.35, 0.0, 0.60, 0.0], senses=1.6, tier=1,
    glow=0.02,
    codex="it arrives after. it has always arrived after. it is the reason "
          "you have started eating faster.",
)

SILT_MOTHER = _s(
    "silt_mother", "Silt Mother", viability=115.0, radius=24.0, speed=70.0,
    organs=["root", "bloom", "settling_sac", "fork", "caster"],
    chain=[0, 1, 2, 3, 4], behaviour="ambush",
    resist=[0.40, 0.0, 0.75, 0.0], senses=1.9, tier=1, glow=0.0,
    codex="you have never seen it. you have seen the place where the water "
          "stops telling you anything, and you have watched that place "
          "move.",
)

# ---------------------------------------------------------------- lattice

RECURSOR = _s(
    "recursor", "Recursor", viability=95.0, radius=21.0, speed=88.0,
    organs=["siphon", "knot", "ganglion", "spine", "spiracle"],
    chain=[0, 2, 3, 4], behaviour="recursor",
    resist=[0.25, 0.05, 0.20, 0.50], senses=1.2, tier=2, glow=0.55,
    aggression=1.4,
    codex="hit it harder and it gets brighter. you have tested this more "
          "times than you would like to write down. it is burning itself to "
          "death the entire time and it does not appear to mind.",
    harvest_note="the knot came out whole. you still cannot find the end of "
                 "it.",
)

CIRCUIT = _s(
    "circuit", "Circuit", viability=72.0, radius=14.0, speed=175.0,
    organs=["filter_gill", "ganglion", "spine", "fork", "spiracle"],
    chain=[0, 1, 2, 3, 4], behaviour="stalk",
    resist=[0.10, 0.05, 0.10, 0.70], senses=1.5, tier=2, glow=0.42,
    aggression=1.9,
    codex="it runs the corridors on a schedule. it has been running them on "
          "a schedule since before there was anything down here to run from.",
)

HOLLOW = _s(
    "hollow", "Hollow", viability=185.0, radius=28.0, speed=46.0,
    organs=["mouth", "condenser", "salt_node", "swell", "maw"],
    chain=[0, 1, 2, 3, 4], behaviour="stalk",
    resist=[0.60, 0.0, 0.20, 0.45], armour=0.35, senses=1.0, tier=2,
    glow=0.08,
    codex="it is a candidate that got everything right except one thing, and "
          "it has been down here long enough that nobody remembers which "
          "thing.",
)

# ------------------------------------------------------------------- sill

FIRST = _s(
    "first", "First Candidate", viability=520.0, radius=40.0, speed=96.0,
    organs=["mouth", "harmonic", "knot", "ember_gland", "fork", "maw"],
    chain=[0, 2, 3, 4, 5], behaviour="apex",
    # Armoured against the cold weight it has been sitting in for ten
    # thousand years. Heat is the gap, and the Sill has no heat in it.
    resist=[0.60, 0.05, 0.35, 0.35], armour=0.40, senses=1.8, tier=3,
    glow=0.75,
    codex="the number on it is one. it is still here. it has been here the "
          "entire time, and it passed nothing, and nobody came to tell it "
          "so.",
)

# ------------------------------------------------------------------ apexes

MIDWIFE = _s(
    "midwife", "The Midwife", viability=380.0, radius=38.0, speed=118.0,
    organs=["mouth", "kiln", "salt_node", "swell", "maw"],
    chain=[0, 1, 2, 3, 4], behaviour="apex",
    resist=[0.35, 0.15, 0.15, 0.15], armour=0.30, senses=2.2, tier=1,
    glow=0.28,
    codex="it does not eat you. it takes you somewhere. the difference has "
          "stopped being important.",
)

LONG_QUIET = _s(
    "long_quiet", "The Long Quiet", viability=460.0, radius=52.0, speed=104.0,
    organs=["mouth", "settling_sac", "bloom", "swell", "fork", "caster"],
    chain=[0, 1, 2, 3, 4, 5], behaviour="apex",
    resist=[0.20, 0.20, 0.65, 0.20], armour=0.35, senses=2.0, tier=2,
    glow=0.0,
    codex="you have seen a flank of it, once, at the edge of your light, "
          "moving the wrong way for how long it took to pass.",
)

THE_CIRCUIT = _s(
    "the_circuit", "Breaker", viability=420.0, radius=34.0, speed=190.0,
    organs=["filter_gill", "ganglion", "spine", "knot", "fork", "spiracle"],
    chain=[0, 1, 2, 4, 5], behaviour="apex",
    resist=[0.15, 0.15, 0.15, 0.70], armour=0.25, senses=2.4, tier=2,
    glow=0.66,
    codex="whatever it was for, the building still has power for it, and it "
          "still has somewhere to be.",
)

# ---------------------------------------------------------------- the end

CONSPECIFIC = _s(
    "conspecific", "—", viability=90.0, radius=17.0, speed=58.0,
    organs=["siphon", "harmonic", "kiln", "salt_node", "spiracle"],
    chain=[], behaviour="conspecific",
    resist=[0.0, 0.0, 0.0, 0.0], senses=1.0, tier=3, glow=0.45,
    peaceful=True,
    codex="",
    harvest_note="",
)


REGION_POOLS = {
    "nursery": ["coelenter", "fry", "sounder", "nurse"],
    "cisterns": ["lamprey", "carrion", "ossuary", "fry", "silt_mother"],
    "lattice": ["circuit", "recursor", "hollow", "lamprey"],
    "sill": ["hollow", "recursor", "carrion", "first"],
}

REGION_APEX = {
    "nursery": "midwife",
    "cisterns": "long_quiet",
    "lattice": "the_circuit",
    "sill": "first",
}


def get(key) -> Species:
    return SPECIES[key]
