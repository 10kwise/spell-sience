"""The Shelf: prebuilt chains that work.

Every entry is a real chain built from real organs, and loading one routes
it exactly the way a player would have. They exist for three reasons and
the third is the important one:

1. **Testing.** You can put a known-good build in a body in two keypresses
   and go and find out whether the game around it is any good.
2. **Teaching by contrast.** LANCE and FIZZLE are the same four organs in a
   different order. Loading both and assaying them is the single fastest
   way to understand what this whole system is.
3. **A floor under being stuck.** The three standing chains at the bottom
   are the answers to the three region hazards. A player who cannot work
   out why the Sill is killing them can load FURNACE and *then* work out
   why it helps, which is a much better failure mode than quitting.

Nothing here is optimal. They are honest, legible, mid-tier builds — the
kind a player arrives at in their second hour — so that beating them
remains the point.
"""

FIRED, STANDING = "fired", "standing"


class Preset:
    __slots__ = ("key", "name", "kind", "organs", "note", "teaches")

    def __init__(self, key, name, kind, organs, note, teaches=""):
        self.key = key
        self.name = name
        self.kind = kind
        self.organs = organs
        self.note = note
        self.teaches = teaches


SHELF = [
    # ---------------------------------------------------------- the basics
    Preset("sting", "Sting", FIRED,
           ["siphon", "kiln", "spiracle"],
           "what you woke up with. takes a little, warms it, throws it.",
           "the shape of a chain: intake, transform, vent."),
    Preset("lance", "Lance", FIRED,
           ["siphon", "salt_node", "kiln", "ember_gland", "spiracle"],
           "double the weight, burn the doubled weight, then double the "
           "heat. hot, loud, and it cooks you.",
           "amplify BEFORE the thing that spends what you amplified."),
    Preset("fizzle", "Fizzle", FIRED,
           ["siphon", "ember_gland", "kiln", "salt_node", "spiracle"],
           "the same five organs as the Lance, in the worst order there "
           "is. it doubles a heat it has not made yet, converts that heat "
           "away, and then doubles a weight it has already spent.",
           "load this and the Lance and assay both. same parts, a third of "
           "the damage. that is the whole game."),

    # ------------------------------------------------------------- shaping
    Preset("whisper", "Whisper", FIRED,
           ["siphon", "muffle", "kiln", "spiracle"],
           "half the shot for a fifth of the noise.",
           "the trade is not even, and it is in your favour."),
    Preset("scatter", "Scatter", FIRED,
           ["gullet", "fork", "maw", ],
           "a wide mouthful, split in two, thrown as a cone. for crowds.",
           "fork multiplies the shots and divides the concentration."),
    Preset("burst", "Burst", FIRED,
           ["gullet", "bladder", "valve", "swell", "caster"],
           "does nothing at all for three or four presses, then hands over "
           "everything it has been holding.",
           "the Bladder fills; the Valve refuses to pass anything small."),

    # ------------------------------------------------------------- unusual
    Preset("key", "Key", FIRED,
           ["gullet", "sieve", "harmonic", "pore_field"],
           "a wide gulp, flattened, evened out, and breathed over "
           "everything near you. it does no damage whatsoever.",
           "grown doors open to this. nothing else opens them."),
    Preset("rot", "Rot", FIRED,
           ["siphon", "bloom", "kiln", "caster"],
           "heat and sediment together. it does not kill things, it unmakes "
           "them — doors included.",
           "the ugly way through a grown door."),
    Preset("nervefire", "Nervefire", FIRED,
           ["siphon", "ganglion", "spine", "spiracle"],
           "the most damage available anywhere, and it takes a piece of you "
           "every time you fire it.",
           "heat into nerve. both at once is the worst thing you can make."),
    Preset("decoy", "Decoy", FIRED,
           ["siphon", "swell", "seed"],
           "you leave it somewhere. it remembers you later, loudly, "
           "somewhere you are not.",
           "noise is a resource. it can be spent on purpose."),
    Preset("frost", "Frost", FIRED,
           ["siphon", "salt_node", "salt_node", "caster"],
           "cold, dense water. it freezes what it lands in — including the "
           "water itself, which stops being something you can swim through.",
           "heavy unlit water takes heat away. that is all ice is."),

    # ------------------------------------------------------------ standing
    Preset("furnace", "Furnace", STANDING,
           ["siphon", "kiln", "ember_gland"],
           "you burn, continuously. the cold stops taking you apart and "
           "everything in the room can see you.",
           "THE SILL. its water has no heat in it, so you convert."),
    Preset("shroud", "Shroud", STANDING,
           ["siphon", "settling_sac", "bloom"],
           "you trail sediment. it hides you, and it earths the current "
           "that is otherwise running through you.",
           "THE LATTICE."),
    Preset("mend", "Mend", STANDING,
           ["siphon", "sieve", "harmonic"],
           "you keep yourself even, and evenness tends you. slow, real "
           "healing, and your intakes stay clear.",
           "THE CISTERNS."),
    Preset("ascent", "Ascent", STANDING,
           ["siphon", "mirror_sac", "salt_node"],
           "weight, pointed the other way. you rise.",
           "the shaft in the Lattice. there is no jump button."),
    Preset("quicken", "Quicken", STANDING,
           ["siphon", "ganglion", "spine"],
           "everything about you cycles faster, and everything that touches "
           "you hurts more.",
           "speed is bought with fragility."),
]

BY_KEY = {p.key: p for p in SHELF}


def missing_for(preset, body):
    """Which organs a body cannot supply for this preset.

    Counts the pack plus anything installed that no chain is currently
    routed through, because a player should not have to manually strip
    their own spare parts before the Shelf will talk to them."""
    import collections
    have = collections.Counter(o.key for o in body.pack)
    used = set()
    for ch in list(body.chains) + list(body.standing):
        used.update(ch.cells)
    for cell, o in body.cells.items():
        if o is not None and cell not in used:
            have[o.key] += 1
    need = collections.Counter(preset.organs)
    short = []
    for key, n in need.items():
        if have[key] < n:
            short.extend([key] * (n - have[key]))
    return short
