"""Waves, and deliberately nothing else.

This used to be a roguelite: three acts, a reward screen between them, metals
unlocked as loot, an anvil on a twelve-second clock. That structure is not
what the game is for and it was absorbing effort that belongs in the two
things that actually carry it - shaping a bell, and fighting with it.

So it is now a list. Everything is unlocked from the first second, you carry
three bells, the budget never changes, and the Foundry is open between every
wave with no timer on it. The waves escalate by putting more and harder
things in the room, which is the cheapest structure that still produces a
difficulty curve, and none of it is precious: change a line in WAVES and the
game is different.

The only rule the ordering obeys is dependency - a wave may not introduce a
foe whose answer has not already been available. That is not level design, it
is just not teaching things in the wrong order.
"""

import json
import os

from .metals import ALL_METALS
from .starters import METAL_BUDGET, starting_bells

SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "save", "campanary.json")

# Each wave introduces at most one new thing and then stops.
WAVES = [
    {"name": "FIRST TOLL", "foes": {"husk": 2}},
    {"name": "DEAD METAL", "foes": {"husk": 2, "deadweight": 1}},
    {"name": "GLASS AIR", "foes": {"glasswing": 2, "husk": 1}},
    {"name": "THE PAIR", "foes": {"twin": 1, "husk": 2}},
    {"name": "WEIGHT AND WING", "foes": {"glasswing": 3, "deadweight": 1}},
    {"name": "THE OVERTONE", "foes": {"overtone": 1, "husk": 2}},
    {"name": "THE GREAT BELL", "foes": {"greatbell": 1, "husk": 2},
     "phrase": [1, 2, 1]},
    {"name": "FULL PEAL", "foes": {"husk": 3, "glasswing": 2}},
    {"name": "TWIN OVERTONE", "foes": {"twin": 1, "overtone": 1, "glasswing": 1}},
    {"name": "DEAD CHOIR", "foes": {"deadweight": 1, "twin": 1, "glasswing": 2}},
    {"name": "THE LAST BELL", "foes": {"greatbell": 1, "overtone": 1, "glasswing": 2},
     "phrase": [3, 1, 2, 3]},
]

# Deliberately not much bigger than the viewport. There is no aiming in this
# game, so what the player is choosing is *where to stand* - and a room they
# cannot see is a room they cannot choose a place in. At 1750x1180 against a
# 1280x800 window, foes spent most of the fight off the edge of the screen
# and the whole positioning layer became guesswork.
ARENA_W, ARENA_H = 1520, 980

# The notes a wave will actually ask for. The Foundry shows this, which is
# the whole reason drawing stopped being a guess: the tuner has a target, so
# shaping a bell is hill-climbing toward a number rather than scribbling.
FOE_NOTES = {
    "husk": 1, "glasswing": 3, "deadweight": -1, "twin": 1,
    "overtone": 4, "greatbell": 2,
}


def notes_in(spec) -> list:
    """Distinct notes this room will demand, low first. -1 means something in
    there has no note at all."""
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


def spec_for(index: int) -> dict:
    """Past the end of the list the waves keep coming, with more in them.
    Endless rather than a finale, because the game is not a run."""
    if index < len(WAVES):
        spec = dict(WAVES[index])
    else:
        depth = index - len(WAVES) + 1
        base = dict(WAVES[(index * 7) % len(WAVES)])
        base["foes"] = {k: v + (1 if depth > 1 and k != "greatbell" else 0)
                        for k, v in base["foes"].items()}
        base["name"] = f"PEAL {index + 1}"
        spec = base
    spec.setdefault("width", ARENA_W)
    spec.setdefault("height", ARENA_H)
    return spec


class Session:
    """One sitting. Holds the bells and where you are in the list."""

    PEGS = 3

    def __init__(self, codex=None):
        self.bells = starting_bells()
        while len(self.bells) < self.PEGS:
            from .starters import blank
            self.bells.append(blank())
        self.budget = METAL_BUDGET
        self.pegs = self.PEGS
        self.wave = 0
        self.hp = 100.0
        self.max_hp = 100.0
        self.shatters = 0
        self.codex = codex or Codex()

    @property
    def spec(self):
        return spec_for(self.wave)

    @property
    def label(self) -> str:
        return f"WAVE {self.wave + 1}"

    def target_notes(self) -> list:
        return notes_in(self.spec)

    def advance(self):
        self.wave += 1
        self.codex.record(self)

    def unlocked_metals(self) -> list:
        return list(ALL_METALS)


class Codex:
    """What survives a death. Deliberately thin: the thing that persists in
    this game is the player's understanding, not a stat."""

    def __init__(self):
        self.best = 0
        self.runs = 0
        self.shatters = 0
        self.bells = []          # bells kept between sittings

    def record(self, session):
        self.best = max(self.best, session.wave)

    def end(self, session):
        self.runs += 1
        self.best = max(self.best, session.wave)
        self.shatters += session.shatters
        self.bells = [b.to_dict() for b in session.bells if not b.is_empty][:3]
        self.save()

    def to_dict(self):
        return {"best": self.best, "runs": self.runs,
                "shatters": self.shatters, "bells": self.bells}

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
        c.best = data.get("best", 0)
        c.runs = data.get("runs", 0)
        c.shatters = data.get("shatters", 0)
        c.bells = data.get("bells", [])
        return c
