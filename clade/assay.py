"""Measuring an organ, instead of describing one.

"I cannot tell what things do" was the fairest complaint made about this
game, and the design was the cause: organs carried a name, a mood and a
line of prose, and the only way to find out what one actually did was to
run it and squint at four coloured bars.

The instinct to protect discovery was right and the execution was wrong.
There is a real difference between the things a player *could* find out in
four seconds at a free, safe, unlimited test bench — that a Salt Node
multiplies brine — and the things that take a hundred hours of play to
notice — that it therefore belongs before the Kiln and not after. Being
coy about the first kind is not mystery, it is friction, and it stops
anybody ever reaching the second kind.

So: every line this module produces is *measured*, by running the organ on
a standard sample and reading what came out. Nothing here is authored, and
nothing here can drift out of step with the simulation, because it is the
simulation. If somebody retunes the Kiln tomorrow, this says the new thing.
"""

from .effects import resolve
from .humours import BRINE, ICHOR, N_HUMOURS, NAMES, SILT, SPARK, Charge
from .organs import INTAKE, Organ, TRANSFORM, VENT, ChainContext

# Probe samples, tried in order until one reveals the organ.
#
# A perfectly balanced sample looks fair and is useless for half the
# roster: a Sieve levels the largest humour down to the second largest, so
# on (2,2,2,2) it does *nothing*, and the readout said so. A Valve only
# reveals itself on a charge too small to pass. So: probe with a lopsided
# mixture first, fall back to a thin one, and take the first answer that
# actually says something.
SPIKED = (1.5, 5.0, 2.5, 1.0)
THIN = (0.4, 0.9, 0.5, 0.3)
EVEN = (2.0, 2.0, 2.0, 2.0)
PROBES = (SPIKED, THIN, EVEN)
STANDARD = EVEN

# The few organs whose behaviour genuinely does not live in their own
# transform, and therefore cannot be measured at a bench. Each is a real
# conditional on world state, so stating it is not spoiling anything a
# player could have measured — it is telling them what the bench cannot.
CANNOT_MEASURE = {
    "leech": "takes from whatever living thing you are touching, not from "
             "your own reserve. useless with nothing in reach.",
    "root": "reaches into the floor. it draws far less if you are not near "
            "the bottom, and what it brings up is mostly sediment.",
    "mouth": "takes a share of everything you are carrying, so it is "
             "enormous when you are full and nothing when you are empty.",
    "bladder": "holds everything it is given and passes nothing, until it "
               "is full, and then it hands the whole of it onward at once.",
}


def _run(otype, sample=None):
    ctx = ChainContext(None, None, (0.0, 0.0), (1.0, 0.0))
    organ = Organ(otype)
    before = Charge.of(sample or STANDARD)
    if otype.role == INTAKE:
        before = Charge()
    after = organ.apply(before.copy(), ctx)
    return before, after, ctx


def measure(otype, sample=None):
    """(before, after, ctx) for one organ on a sample."""
    return _run(otype, sample)


def _describe(otype, sample):
    """One probe. Returns None when this sample revealed nothing."""
    before, after, ctx = _run(otype, sample)

    # 1. Flags first. An organ that splits, repeats, blocks or costs you is
    #    telling you something the humour vector cannot.
    flags = []
    if ctx.count > 1:
        flags.append("splits it into %d, spread apart" % ctx.count)
    if ctx.recursions:
        flags.append("runs everything before it a second time — including "
                     "the heat")
    if ctx.aborted:
        flags.append("blocks anything too small to be worth firing")
    if ctx.trail:
        flags.append("lays a trail behind whatever leaves you")
    if ctx.speed > 1.1:
        flags.append("sends it %.0f%% faster" % ((ctx.speed - 1) * 100))
    if ctx.viability_cost > 0:
        flags.append("costs you %.1f of yourself" % ctx.viability_cost)
    if ctx.quiet < 0.8:
        flags.append("and it is much quieter")
    elif ctx.quiet > 1.2:
        flags.append("and it is louder")

    d = [after[i] - before[i] for i in range(N_HUMOURS)]
    up = [i for i in range(N_HUMOURS) if d[i] > 0.08]
    down = [i for i in range(N_HUMOURS) if d[i] < -0.08]
    bm, am = before.magnitude, after.magnitude
    body = None

    # 2. A sign flip is the Mirror Sac, and it is the only one.
    flipped = [i for i in range(N_HUMOURS)
               if before[i] * after[i] < 0 and abs(before[i]) > 0.05]
    if flipped:
        body = ("reverses %s, so it pulls where it used to push — and "
                "pointed at yourself, that is lift" % NAMES[flipped[0]])
    # 3. One down, one up: a converter.
    elif len(down) == 1 and len(up) == 1:
        moved = -d[down[0]]
        body = "%s becomes %s, with %.0f%% of it surviving the trip" % (
            NAMES[down[0]], NAMES[up[0]], d[up[0]] / max(1e-6, moved) * 100)
    # 4. Up with nothing down: an amplifier.
    elif len(up) == 1 and not down:
        factor = after[up[0]] / max(1e-6, before[up[0]])
        body = ("multiplies %s by about %.1f — less the more of it you "
                "already have" % (NAMES[up[0]], factor))
    # 5. Everything down, one up: the universal converter.
    elif len(down) >= 2 and len(up) == 1:
        body = "turns most of everything else into %s, wastefully" % \
            NAMES[up[0]]
    else:
        db, da = before.divergence, after.divergence
        if da < db - 0.04:
            how = ("by cutting the largest part down to the size of the "
                   "next largest" if down and not up else "")
            body = ("flattens the mixture toward even in all four" +
                    (" " + how if how else ""))
        elif da > db + 0.04:
            body = "makes the mixture more lopsided than it was"
        elif am < bm * 0.8:
            body = "shrinks the whole mixture to %.0f%%" % (am / bm * 100)
        elif am > bm * 1.15:
            body = "makes the whole mixture %.0f%% of what it was" % (
                am / bm * 100)

    if body and flags:
        return body + "; " + "; ".join(flags)
    if body:
        return body
    if flags:
        return "; ".join(flags)
    return None


def function_of(otype) -> str:
    """One plain line saying what this organ does to a mixture.

    Derived by running it, never written down — so it cannot drift out of
    step with the simulation, because it *is* the simulation."""
    if otype.key in CANNOT_MEASURE:
        return CANNOT_MEASURE[otype.key]

    if otype.role == VENT:
        v = otype.vent
        shapes = {
            "bolt": "one fast bolt, aimed",
            "cone": "a short wide cone, several at once",
            "aura": "a field around you — it catches you too",
            "lob": "a thrown blob that arcs and bursts where it lands",
            "beam": "a continuous line for as long as you hold it",
            "seed": "left where you put it, and it goes off later",
        }
        return shapes.get(v.kind, v.kind)

    if otype.role == INTAKE:
        before, after, ctx = _run(otype)
        bits = ["draws %.1f a shot" % after.magnitude]
        if after.divergence > 0.9:
            bits.append("of one humour only, purely")
        if ctx.quiet > 1.2:
            bits.append("and it is loud")
        elif ctx.quiet < 0.8:
            bits.append("and it is quiet")
        return ", ".join(bits)

    for sample in PROBES:
        line = _describe(otype, sample)
        if line:
            return line
    return "changes nothing measurable at a bench"


def bias_of(otype) -> str:
    """The one-word tag shown on the socket itself."""
    if otype.role == VENT:
        return {"bolt": "bolt", "cone": "cone", "aura": "aura", "lob": "lob",
                "beam": "beam", "seed": "trap"}.get(otype.vent.kind, "vent")
    if otype.role == INTAKE:
        return "draws"
    if otype.key == "bladder":
        return "holds"
    before, after, ctx = _run(otype, SPIKED)
    d = [after[i] - before[i] for i in range(N_HUMOURS)]
    up = [i for i in range(N_HUMOURS) if d[i] > 0.08]
    down = [i for i in range(N_HUMOURS) if d[i] < -0.08]
    if ctx.count > 1:
        return "splits"
    if ctx.recursions:
        return "repeats"
    if any(before[i] * after[i] < 0 for i in range(N_HUMOURS)):
        return "inverts"
    if len(up) == 1 and not down:
        return "+" + NAMES[up[0]]
    if len(up) == 1 and down:
        return NAMES[down[0]][0] + ">" + NAMES[up[0]]
    if after.divergence < before.divergence - 0.04:
        return "evens"
    if ctx.trail:
        return "trails"
    if ctx.speed > 1.1:
        return "hastens"
    if after.magnitude < before.magnitude * 0.8:
        return "shrinks"
    if after.magnitude > before.magnitude * 1.15:
        return "swells"
    _, _, thin = _run(otype, THIN)
    if thin.aborted:
        return "gates"
    return "shapes"


def effect_summary(charge: Charge):
    """Labelled magnitudes for a resolved charge, for the Assay's readout.
    Returned as (label, value, 0..1 bar, colour) so the screen does not
    have to know the effect rules."""
    e = resolve(charge)
    rows = [
        ("damage", e.damage, min(1.0, e.damage / 45.0), (226, 132, 112)),
        ("noise", e.loudness, min(1.0, e.loudness / 14.0), (216, 176, 96)),
        ("gentleness", e.gentle, min(1.0, e.gentle / 6.0), (140, 206, 172)),
        ("heat", e.heat, min(1.0, abs(e.heat) / 8.0),
         (226, 138, 74) if e.heat >= 0 else (108, 168, 214)),
        ("shove", abs(e.force), min(1.0, abs(e.force) / 1600.0),
         (150, 168, 190)),
        ("murk", e.murk, min(1.0, e.murk / 6.0), (150, 132, 104)),
        ("shock", e.jolt, min(1.0, e.jolt / 8.0), (188, 148, 236)),
        ("rot", e.caustic, min(1.0, e.caustic / 8.0), (168, 186, 96)),
    ]
    return e, [r for r in rows if r[1] > 0.05]
