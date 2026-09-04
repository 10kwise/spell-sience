"""Fragments, and the codex that remembers them.

Rules held to while writing this file:

**Never explain in the voice of the game.** Everything here is a document
somebody left, a mark somebody scratched, or a thing you half-remember. The
facility's own logs are clinical and incurious because it has been doing
this for a very long time and has stopped finding it remarkable. The marks
left by other candidates are short, because they were made by things with
no hands and not much time.

**Three depths, and the player controls how deep they go.** The first layer
is unavoidable: this is a facility, it is flooded, everything is dead. The
second is available to anyone who reads what they pick up: it grew
candidates and tested them, and every creature here is one. The third is
deliberately hard to assemble — it is spread across five documents in four
regions, one of them behind a lock most players will never open — and it
says that the test is not broken, it is *running*, and it has a pass
condition.

**The pass condition is stated exactly once**, in FRAG_PASS, and it is the
only place in the entire game where the ending is explained before it
happens. Everything else circles it. A player who finds it will recognise
the last room immediately; a player who does not will meet it cold, and
both of those are good outcomes, which is why it is placed where it is and
not anywhere easier.
"""

LOG, MARK, MEMORY = "log", "mark", "memory"


class Fragment:
    __slots__ = ("key", "kind", "title", "text", "region")

    def __init__(self, key, kind, title, text, region=""):
        self.key = key
        self.kind = kind
        self.title = title
        self.text = text.strip()
        self.region = region


FRAGMENTS = {}


def _f(key, kind, title, text, region=""):
    fr = Fragment(key, kind, title, text, region)
    FRAGMENTS[key] = fr
    return fr


# --------------------------------------------------------------- layer one
# It is a place. It is flooded. It was for something.

_f("caul", MEMORY, "before", """
you do not remember opening.

you remember being warm, and being held at every point at once, and a sound
that was not a sound so much as the absence of any reason to move.

then a pressure change. then cold at one edge of you. then the rest.
""", "nursery")

_f("intake_plate", LOG, "intake plate", """
CONSERVATION FACILITY — SUBSURFACE
STOCK INTAKE AND DIFFERENTIATION

all material entering beyond this point is undifferentiated and remains the
property of the project until it is not.

do not seal the lower doors. the lower doors are not for sealing.
""", "nursery")

_f("wet_notice", LOG, "notice, laminated", """
FLOODING IS NOT A FAULT CONDITION.

the lower volumes are designed to flood. the medium is the point. air-filled
storage fails in ninety years and water-filled storage fails in nine
thousand, and we did not build this for ninety years.

if you are reading this and you are dry, you are on the wrong level.
""", "nursery")

_f("mark_one", MARK, "scratched into the wall", """
i was here first

no
""", "nursery")

# --------------------------------------------------------------- layer two
# It grew things. It is still growing things. So are you.

_f("candidate_note", LOG, "differentiation note", """
we are not preserving humans. we tried that. a preserved human is a human
shaped for a world that no longer exists, and it dies of that.

we are preserving the part that had not decided yet.

the stock will be permitted to differentiate against conditions. we will
observe which forms persist. we will not intervene, because intervening is
how you get something that needs you.
""", "nursery")

_f("ledger_a", LOG, "ledger, water-damaged", """
CANDIDATE 4
persisted 11 days. respiratory. did not feed.

CANDIDATE 12
persisted 3 days. fed once, on CANDIDATE 11.

CANDIDATE 40
persisted 206 days. fed continuously. terminated at the sill, cause not
recorded, remains not recovered.

CANDIDATE 41
""", "cisterns")

_f("husbandry", LOG, "husbandry standing order", """
candidates are not to be named.

a named candidate is observed differently. the observer begins to want an
outcome, and an observer who wants an outcome is a variable we cannot
subtract afterward.

number them. record what they did. do not record what you thought of them.
""", "cisterns")

_f("mark_two", MARK, "gouged, deep, repeatedly", """
IT COUNTS

IT IS STILL COUNTING
""", "cisterns")

_f("organ_note", LOG, "on recovered tissue", """
candidates recovered from other candidates and installed the tissue in
themselves. this was not taught and was not anticipated.

it works. that is the difficult part. the recovered organ functions in the
new host at full efficiency, in any arrangement the host can plumb, which
means the stock is not merely undifferentiated — it is *interoperable*, and
we did not design that either.

they are all the same animal. they simply have not met.
""", "cisterns")

_f("cistern_depth", LOG, "sounding record", """
the volume below is larger than the volume we excavated.

this has been re-measured four times.
""", "cisterns")

# ------------------------------------------------------------- layer three
# The test is not broken. It is running. And it wants something specific.

_f("escalation", LOG, "conditions schedule", """
no candidate has persisted to criterion.

recommendation: the conditions are insufficiently adverse. a population that
is merely surviving is not differentiating; it has found a local answer and
stopped.

approved. escalation to proceed on the standing schedule and to continue
without review until criterion is met.

note that nobody is going to be here to review it.
""", "lattice")

_f("mark_three", MARK, "small, careful, at eye level", """
i stopped eating them

i got weaker

i am still here
""", "lattice")

_f("attendant_note", LOG, "observation, unfiled", """
one of them does not feed.

it follows the others at a fixed distance and it does not close and it does
not leave. we assumed a malformed hunting behaviour and scheduled it for
recovery.

it has now followed nine consecutive candidates. all nine recovered it.

we are no longer sure it is hunting.
""", "lattice")

_f("pass", LOG, "criterion — sealed copy", """
the project is often described as preserving humanity. it is not. we could
not agree on what that would mean, and the argument took four years we did
not have.

what we agreed on was smaller.

we will keep the capacity to become something, and we will let it become
something, and we will hold it here until it becomes something worth
letting out. and we wrote down what that is, exactly once, so that nobody
could soften it later:

CRITERION: a candidate that encounters another candidate and does not
consume it.

that is all. it is not intelligence. it is not strength. we have had both
of those, repeatedly, and they ate each other, repeatedly, and we let them,
because a thing that would eat the last one of its kind is not a thing we
are going to open the doors for.

the doors are on the criterion. they are on nothing else.
""", "lattice")

_f("sill_lip", LOG, "at the sill", """
beyond this point the facility ends and the ocean begins, and there is no
door between them that we built.

we did not need one. nothing has ever got this far.
""", "sill")

_f("mark_four", MARK, "worn almost smooth", """
i am number one

nobody came
""", "sill")

_f("last_log", LOG, "final entry", """
we are leaving. there is nothing left to do here that being here improves.

the systems are autonomic and the medium is water and the schedule will run
whether or not there is anyone to read the output, which was the design
requirement, and which is now, standing in this room, the worst sentence
any of us has ever written.

if it works, it will work a very long time after the last of us is
irrelevant to it.

if it works, whatever comes up out of the sill will not know what we were
and will not owe us anything.

good.
""", "sill")

_f("your_number", MEMORY, "a number", """
there is a number on you.

it is not written anywhere. you have looked. it is more like a place where
counting happened and left a shape.

it is very large.
""", "sill")


# ---------------------------------------------------------------------------
# The codex: what you have seen, in the order you saw it.
# ---------------------------------------------------------------------------

class Codex:
    """Knowledge, tracked by observation rather than by unlock flags.

    Organs record what you have actually *done* with them, which is why the
    entry for a Kiln you have never fired says nothing at all. That is the
    whole discovery loop in one data structure: the game does not withhold
    information, it simply has not watched you find any out yet."""

    def __init__(self):
        self.fragments = []          # keys, in the order found
        self.organ_uses = {}         # key -> count
        self.organ_seen = set()
        self.species_seen = {}       # key -> count
        self.species_killed = {}
        self.blends_seen = set()
        self.notes = []              # (title, text) discovered observations

    def find_fragment(self, key):
        if key in FRAGMENTS and key not in self.fragments:
            self.fragments.append(key)
            return FRAGMENTS[key]
        return None

    def see_organ(self, key):
        self.organ_seen.add(key)

    def use_organ(self, key, n=1):
        self.organ_uses[key] = self.organ_uses.get(key, 0) + n
        self.organ_seen.add(key)

    def see_species(self, key):
        self.species_seen[key] = self.species_seen.get(key, 0) + 1

    def kill_species(self, key):
        self.species_killed[key] = self.species_killed.get(key, 0) + 1

    def see_blend(self, name):
        if name and name not in self.blends_seen:
            self.blends_seen.add(name)
            return True
        return False

    def organ_confidence(self, key):
        """0..3. Drives how much the codex is willing to say about an
        organ, which is a proxy for how much the player has bothered to
        find out."""
        n = self.organ_uses.get(key, 0)
        if n >= 40:
            return 3
        if n >= 12:
            return 2
        if n >= 1:
            return 1
        return 0

    @property
    def depth(self):
        """How much of the third layer has been assembled. Read by the
        ending to decide how much it is willing to say out loud."""
        deep = ("escalation", "pass", "attendant_note", "last_log",
                "your_number", "mark_three")
        return sum(1 for k in deep if k in self.fragments)

    def to_dict(self):
        return {
            "fragments": self.fragments,
            "organ_uses": self.organ_uses,
            "organ_seen": sorted(self.organ_seen),
            "species_seen": self.species_seen,
            "species_killed": self.species_killed,
            "blends_seen": sorted(self.blends_seen),
        }

    @staticmethod
    def from_dict(d):
        c = Codex()
        c.fragments = list(d.get("fragments", []))
        c.organ_uses = dict(d.get("organ_uses", {}))
        c.organ_seen = set(d.get("organ_seen", []))
        c.species_seen = dict(d.get("species_seen", {}))
        c.species_killed = dict(d.get("species_killed", {}))
        c.blends_seen = set(d.get("blends_seen", []))
        return c


# Observed-behaviour lines for organs. Keyed by confidence, so an organ you
# have used twice tells you less than one you have leaned on for an hour.
ORGAN_OBSERVED = {
    "kiln": ["", "heavy water goes in warm water comes out.",
             "it converts weight into heat, and it keeps some of the "
             "difference.",
             "whatever weight it is given, it burns most of. give it more "
             "weight first and it burns more."],
    "salt_node": ["", "things come out of it heavier.",
                  "it multiplies weight, and only weight.",
                  "it multiplies what is already there. it cannot make "
                  "weight out of nothing, which is why it belongs before "
                  "the thing that spends weight and not after."],
    "ember_gland": ["", "it comes out hot. much hotter.",
                    "it multiplies heat. the heat does not all leave.",
                    "it multiplies heat and it keeps a share of it inside "
                    "you, and the share is not small, and the things beside "
                    "it in your body pay it."],
    "muffle": ["", "quieter. weaker.",
               "it takes about half the force and nearly all of the noise.",
               "the trade is not even. half the shot for a fifth of the "
               "noise is a bargain in almost every room you are actually "
               "frightened in."],
    "sieve": ["", "something is missing afterward.",
              "it removes whatever there was most of.",
              "it removes the largest part. run it on a spike and what is "
              "left is nearly even, which is the only route to anything "
              "gentle that does not need a Harmonic."],
    "harmonic": ["", "it comes out even.",
                 "it pulls everything toward the middle.",
                 "it makes a mixture that is all four things equally, which "
                 "does nothing to anything that is not alive, and everything "
                 "to anything that is."],
    "mirror_sac": ["", "it came back wrong.",
                   "it reverses the largest part.",
                   "reversed weight is not less weight. it is weight "
                   "pointing the other way, and pointed at yourself it is "
                   "the only way up."],
    "knot": ["", "it went round again.",
             "everything before it runs twice.",
             "everything before it runs twice, including the heat, which is "
             "why the things that have one are always burning."],
    "fork": ["", "two of them.",
             "it splits the shot in two and spreads them.",
             "two shots at rather more than half each. more total, less "
             "concentrated — which is better against a crowd and worse "
             "against anything armoured."],
    "bladder": ["", "nothing happened.",
                "it fills up and then it lets go all at once.",
                "it holds until it is full and then hands the whole of it "
                "onward in one piece, which is what a Valve is waiting for."],
    "valve": ["", "sometimes nothing happens.",
              "it will not pass a small charge.",
              "it refuses anything under a threshold and costs nothing when "
              "it refuses, which makes it free to put in front of anything "
              "you only want to fire when it matters."],
    "ganglion": ["", "that hurt.",
                 "it turns heat into nerve, and it takes some of you.",
                 "heat into nerve, at a price paid in yourself. nerve and "
                 "heat together is the worst thing you can make, and this "
                 "is how you make both at once."],
    "filter_gill": ["", "it came out pure.",
                    "it takes only whatever you have most of.",
                    "it draws one thing, purely, which is the most damage "
                    "and the most noise available anywhere, and it leaves "
                    "the rest of you unbalanced in the opposite direction."],
    "tithe": ["", "it took something.",
              "it costs you and gives back more.",
              "it costs you and gives back more, and it does not care how "
              "much you have left."],
}


def organ_line(key, confidence):
    lines = ORGAN_OBSERVED.get(key)
    if not lines:
        return ""
    return lines[min(confidence, len(lines) - 1)]
