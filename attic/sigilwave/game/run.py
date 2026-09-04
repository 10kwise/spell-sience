"""Run state — what survives a room, and what survives a death.

The split matters. Inside a run, progression is materials and capacity: more
ink families, a bigger budget, another focus slot. Across runs, progression
is *the codex* — the sigils you drew and named.

That is the deliberate choice here. A roguelite normally makes you re-earn
your power every time, which is fine when power is a list of items and
miserable when power is an idea you had. Making the player redraw a circuit
they already understand is not difficulty, it is typing. So the meta-layer
is a library, the run layer is materials, and the thing that actually gets
stronger between runs is the player.
"""

import json
import os

from .inks import STARTER_INKS, UNLOCK_ORDER
from .starters import FOCUS_INK_BUDGET, starting_loadout

SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "save")
CODEX_PATH = os.path.join(SAVE_DIR, "codex.json")


class Run:
    def __init__(self, codex=None):
        self.foci = starting_loadout()
        self.inks = list(STARTER_INKS)
        self.locked_inks = list(UNLOCK_ORDER)
        self.ink_budget = FOCUS_INK_BUDGET
        self.max_foci = 4
        self.room_index = 0
        self.player_hp = 100.0
        self.player_max_hp = 100.0
        self.codex = codex if codex is not None else Codex()
        self.deepest = 0
        self.kills = 0

    @property
    def player_hp_fraction(self):
        return self.player_hp / max(1.0, self.player_max_hp)

    def apply_reward(self, kind):
        if kind == "ink" and self.locked_inks:
            ink = self.locked_inks.pop(0)
            self.inks.append(ink)
            return f"{ink.name} unlocked - {ink.blurb}"
        if kind == "budget":
            self.ink_budget += 180
            return f"ink budget now {self.ink_budget:.0f}"
        if kind == "heal":
            self.player_hp = self.player_max_hp
            return "restored to full"
        if kind == "slot" and len(self.foci) < self.max_foci:
            from .starters import blank

            self.foci.append(blank())
            return f"focus slot {len(self.foci)} added - it is empty, go draw in it"
        self.ink_budget += 120
        return f"ink budget now {self.ink_budget:.0f}"

    def add_drop(self, sigil):
        """A defeated caster's ink, readable and keepable. Free content, in
        the strict sense: the enemy was already running a real sigil, so its
        corpse is a real sigil, and no separate loot system had to exist."""
        self.codex.add(sigil)
        if len(self.foci) < self.max_foci:
            self.foci.append(sigil.clone())
            return True
        return False


class Codex:
    """Named sigils, persisted across runs. Naming is the act that converts
    an accident into an owned tool, so it is the only thing the game keeps."""

    def __init__(self):
        self.entries = []

    def add(self, sigil):
        data = sigil.to_dict()
        if any(e.get("strokes") == data.get("strokes") for e in self.entries):
            return False
        self.entries.append(data)
        return True

    def save(self, path=CODEX_PATH):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"entries": self.entries}, fh, indent=1)
            return True
        except OSError:
            return False

    @staticmethod
    def load(path=CODEX_PATH):
        codex = Codex()
        try:
            with open(path, encoding="utf-8") as fh:
                codex.entries = json.load(fh).get("entries", [])
        except (OSError, ValueError):
            pass
        return codex

    def sigils(self):
        from .sigil import Sigil

        out = []
        for e in self.entries:
            try:
                out.append(Sigil.from_dict(e))
            except Exception:
                continue
        return out


def share_string(sigil) -> str:
    """A sigil is strokes and ink names, so it serialises to a short string
    and travels for free. A community without a server."""
    import base64
    import zlib

    raw = json.dumps(sigil.to_dict(), separators=(",", ":")).encode("utf-8")
    return "SW1:" + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def from_share_string(text: str):
    import base64
    import zlib

    from .sigil import Sigil

    if not text.startswith("SW1:"):
        raise ValueError("not a sigil string")
    raw = zlib.decompress(base64.urlsafe_b64decode(text[4:].encode("ascii")))
    return Sigil.from_dict(json.loads(raw.decode("utf-8")))
