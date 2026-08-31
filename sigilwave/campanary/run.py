"""A run: what you meet, in what order, and why that order.

Every wave introduces exactly one idea and then stops. The ordering is
dependency-first rather than difficulty-first - a wave is only allowed to
appear once every idea it leans on has already been survived somewhere
earlier:

    1  strike, and the beat                (nothing)
    2  force moves what resonance cannot   (needs 1)
    3  a high note has no reach            (needs 1)
    B  answer a phrase in its own note     (needs 1, 3)
    4  break a bond before you ring it     (needs 2)
    5  swell until the bell climbs         (needs 3)

An act is three waves and a boss, about five minutes. Not an endless
corridor: a roguelite that keeps introducing mechanics forever never lets
the player feel competent, and competence is the thing this game is selling.

Between every wave is **the anvil** - twelve seconds to reshape a bell,
under a clock, with the next room's notes shown. That is the fix for the old
build's worst structural problem: the authoring layer used to sit minutes
away from the consequence of using it, so it read as homework. Twelve
seconds after being unable to touch something is when a player actually
wants to change their tool.
"""

import json
import os
import random

from . import notes
from .metals import UNLOCK_ORDER
from .starters import METAL_BUDGET, starting_bells

SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "save", "campanary.json")

ACTS = [
    {
        "name": "THE NAVE",
        "waves": [
            {"name": "First Toll", "foes": {"husk": 3},
             "width": 1550, "height": 1050},
            {"name": "Dead Metal", "foes": {"husk": 2, "deadweight": 1},
             "width": 1650, "height": 1100},
            {"name": "Glass Air", "foes": {"glasswing": 2, "husk": 1},
             "width": 1850, "height": 1250},
            {"name": "THE GREAT BELL", "foes": {"greatbell": 1, "husk": 2},
             "phrase": [1, 2, 1], "width": 1800, "height": 1220, "boss": True},
        ],
    },
    {
        "name": "THE CRYPT",
        "waves": [
            {"name": "The Pair", "foes": {"twin": 1, "husk": 2},
             "width": 1850, "height": 1250},
            {"name": "Weight and Wing", "foes": {"glasswing": 2, "deadweight": 1},
             "width": 1850, "height": 1250},
            {"name": "The Overtone", "foes": {"overtone": 1, "husk": 2},
             "width": 1800, "height": 1220},
            {"name": "THE SECOND BELL", "foes": {"greatbell": 1, "glasswing": 2},
             "phrase": [2, 3, 1, 2], "width": 1900, "height": 1280, "boss": True},
        ],
    },
    {
        "name": "THE TOWER",
        "waves": [
            {"name": "Full Peal", "foes": {"husk": 3, "glasswing": 2, "deadweight": 1},
             "width": 1850, "height": 1250},
            {"name": "Twin Overtone", "foes": {"twin": 1, "overtone": 1},
             "width": 1850, "height": 1250},
            {"name": "Dead Choir", "foes": {"deadweight": 2, "twin": 1, "glasswing": 2},
             "width": 1850, "height": 1250},
            {"name": "THE LAST BELL", "foes": {"greatbell": 1, "overtone": 1, "husk": 2},
             "phrase": [3, 1, 2, 3], "width": 1950, "height": 1320, "boss": True},
        ],
    },
]

# The notes a wave will actually ask for. The anvil shows this, which is the
# whole reason drawing stopped being a guess: the Forge now has a stated
# target, so shaping a bell is hill-climbing toward a number instead of
# scribbling and hoping.
FOE_NOTES = {
    "husk": 1, "glasswing": 3, "deadweight": -1, "twin": 1,
    "overtone": 4, "greatbell": 2,
}


def notes_in(spec) -> list:
    """Distinct notes the player will have to produce in this room, low
    first. -1 means 'something in here has no note at all'."""
    out = []
    for kind in spec.get("foes", {}):
        n = FOE_NOTES.get(kind, 1)
        if n not in out:
            out.append(n)
        if kind == "twin" and 2 not in out:
            out.append(2)
        if kind == "greatbell":
            for p in spec.get("phrase", []):
                if p not in out:
                    out.append(p)
    return sorted(out)


REWARDS = [
    ("metal", "A NEW METAL", "Another way for a bell to behave."),
    ("budget", "+260 METAL", "Bigger bells, on every peg."),
    ("mend", "MEND", "Back to full."),
    ("peg", "+1 BELL PEG", "Carry another bell."),
]


class Run:
    MAX_PEGS = 3

    def __init__(self, codex=None):
        self.bells = starting_bells()
        self.budget = METAL_BUDGET
        self.pegs = 2
        self.metals_locked = list(UNLOCK_ORDER)
        self.act = 0
        self.wave = 0
        self.hp = 100.0
        self.max_hp = 100.0
        self.shatters = 0
        self.slams = 0
        self.codex = codex or Codex()
        self.deepest = 0

    # --------------------------------------------------------------- state

    @property
    def finished(self) -> bool:
        return self.act >= len(ACTS)

    @property
    def spec(self):
        if self.finished:
            return None
        return ACTS[self.act]["waves"][self.wave]

    @property
    def act_name(self) -> str:
        return ACTS[self.act]["name"] if not self.finished else "DONE"

    @property
    def label(self) -> str:
        if self.finished:
            return "the tower is quiet"
        return f"{self.act_name}  {self.wave + 1}/{len(ACTS[self.act]['waves'])}"

    def target_notes(self) -> list:
        s = self.spec
        return notes_in(s) if s else []

    def advance(self) -> str:
        """Returns what happens next: 'anvil', 'reward' or 'done'."""
        self.deepest = max(self.deepest, self.act * 10 + self.wave + 1)
        self.wave += 1
        if self.wave >= len(ACTS[self.act]["waves"]):
            self.wave = 0
            self.act += 1
            self.codex.record(self)
            return "done" if self.finished else "reward"
        return "anvil"

    # -------------------------------------------------------------- rewards

    def offers(self, rng=None) -> list:
        """Two choices, never more. Three is a menu; two is a decision."""
        rng = rng or random.Random(self.act * 104729 + 17)
        pool = []
        if self.metals_locked:
            pool.append("metal")
        pool.append("budget")
        if self.hp < self.max_hp * 0.85:
            pool.append("mend")
        if self.pegs < self.MAX_PEGS:
            pool.append("peg")
        rng.shuffle(pool)
        chosen = (pool + ["budget", "mend"])[:2]
        table = {k: (k, a, b) for k, a, b in REWARDS}
        return [table[k] for k in chosen]

    def take(self, kind) -> str:
        if kind == "metal" and self.metals_locked:
            m = self.metals_locked.pop(0)
            self.codex.metals.add(m.name)
            return f"{m.name.upper()} - {m.blurb}"
        if kind == "budget":
            self.budget += 260.0
            return f"metal budget is now {int(self.budget)}"
        if kind == "mend":
            self.hp = self.max_hp
            return "mended"
        if kind == "peg":
            from .starters import blank
            self.pegs += 1
            self.bells.append(blank())
            return "a third peg - draw something for it"
        return ""

    def unlocked_metals(self) -> list:
        from .metals import ALL_METALS
        locked = {m.name for m in self.metals_locked}
        return [m for m in ALL_METALS if m.name not in locked]


class Codex:
    """What survives a death. Deliberately thin: the thing that persists in
    this game is supposed to be the player's understanding, not a stat."""

    def __init__(self):
        self.metals = set()
        self.best = 0
        self.runs = 0
        self.shatters = 0
        self.kept = []          # bells saved off a finished run

    def record(self, run):
        self.best = max(self.best, run.deepest)
        self.shatters += run.shatters

    def end_run(self, run):
        self.runs += 1
        self.best = max(self.best, run.deepest)
        self.shatters += run.shatters
        self.save()

    def to_dict(self):
        return {"metals": sorted(self.metals), "best": self.best,
                "runs": self.runs, "shatters": self.shatters,
                "kept": [b.to_dict() for b in self.kept[:12]]}

    def save(self):
        try:
            os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
            with open(SAVE_PATH, "w") as fh:
                json.dump(self.to_dict(), fh, indent=1)
        except OSError:
            pass

    @staticmethod
    def load() -> "Codex":
        c = Codex()
        try:
            with open(SAVE_PATH) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return c
        c.metals = set(data.get("metals", []))
        c.best = data.get("best", 0)
        c.runs = data.get("runs", 0)
        c.shatters = data.get("shatters", 0)
        from .bell import Bell
        for d in data.get("kept", []):
            try:
                c.kept.append(Bell.from_dict(d))
            except Exception:
                pass
        return c
