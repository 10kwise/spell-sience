"""The map.

Thirty-nine rooms in four regions, laid out on a coarse grid so that the
world map can be drawn without anybody hand-placing an icon, and connected
by a table of pairs so that a door can never exist on one side only — the
single most common and most miserable bug in a hand-authored metroidvania.

The gates deserve a note, because they are the whole progression design and
none of them is a key:

    FORCE     early, and trivial once you have any shove at all. It exists
              to teach that doors have conditions, using a condition you
              already meet.
    CAUSTIC   in the Cisterns, whose water is thick with sediment — so the
              region hands you the ingredient (silt) for the answer (rot =
              heat + sediment) and lets you work out that they go together.
              Behind it: the Harmonic.
    RISE      in the Lattice. Not locked at all: an open door at the top of
              a shaft. The gate is your own weight, and the answer is
              either a Mirror Sac or the realisation that what you are
              carrying is what is holding you down.
    GENTLE    the gate to the Sill. Needs a balanced charge, which needs a
              Harmonic or a very clever Sieve, and which is the exact
              opposite of everything twelve hours of combat has trained.
    COLD      optional, twice. Freezing is available to anyone who worked
              out that heavy unlit water takes heat away.

The ordering is deliberate: every gate teaches the tool the next gate
requires, and the last one asks you to unlearn.
"""

from ..humours import Charge
from .room import (
    LOCK_CAUSTIC, LOCK_COLD, LOCK_FORCE, LOCK_GENTLE, LOCK_RISE,
)

# ---------------------------------------------------------------- regions

REGIONS = {
    "nursery": {
        "name": "The Nursery",
        # Warm, organic, and rich — the water is practically food. This is
        # why the first hour is generous and why every build the player
        # makes here quietly assumes heat they will not have later.
        "water": [4.0, 11.0, 4.0, 2.0],
        "tint": (26, 40, 38),
        "tier": 0,
        "blurb": "warm. it has not finished being alive.",
    },
    "cisterns": {
        "name": "The Cisterns",
        # Thick. Sight is short here for reasons that have nothing to do
        # with your lamp, and every intake you own starts pulling sediment.
        "water": [6.0, 3.0, 12.0, 1.0],
        "tint": (30, 30, 26),
        "tier": 1,
        "blurb": "thick. the light stops about an arm out.",
    },
    "lattice": {
        "name": "The Lattice",
        # Still powered, after all this time. Spark-rich, which makes the
        # worst weapon in the game cheap and the water itself hostile.
        "water": [4.0, 4.0, 3.0, 11.0],
        "tint": (24, 28, 44),
        "tier": 2,
        "blurb": "it still has power. nobody has ever explained that.",
    },
    "sill": {
        "name": "The Sill",
        # Cold, dense, ancient. Brine-heavy: you sink here, your heat bleeds
        # away fast, and the builds that carried you down do not work.
        "water": [14.0, 2.0, 5.0, 2.0],
        "tint": (18, 24, 34),
        "tier": 3,
        "blurb": "cold, and old, and it goes down further than the building.",
    },
}


# ------------------------------------------------------------------- rooms
# (key, region, kind, map_x, map_y, name, extras)

_ROOMS = [
    # --- nursery -----------------------------------------------------
    ("n_caul", "nursery", "chamber", 0, 0, "the caul", dict(
        quiet=True, frag="caul",
        seeps=[[1, 9, 1, 0]])),
    ("n_crib", "nursery", "cavern", 1, 0, "crib row", dict(
        frag="intake_plate", spawns=[("coelenter", 3)])),
    ("n_ward", "nursery", "hall", 2, 0, "the ward", dict(
        spawns=[("coelenter", 2), ("attendant", 1)], nerve=True)),
    ("n_font", "nursery", "chamber", 3, 0, "the font", dict(
        frag="candidate_note", organ="filter_gill",
        seeps=[[0, 16, 0, 0]], spawns=[("fry", 4)])),
    ("n_run", "nursery", "corridor", 1, 1, "the run", dict(
        frag="wet_notice", spawns=[("fry", 5)])),
    ("n_gallery", "nursery", "cavern", 2, 1, "the gallery", dict(
        frag="mark_one", organ="valve",
        spawns=[("sounder", 1), ("coelenter", 2)])),
    ("n_vault", "nursery", "chamber", 3, 1, "sealed store", dict(
        organ="muffle", spawns=[("fry", 3)])),
    ("n_creche", "nursery", "warren", 0, 1, "the creche", dict(
        organ="fork", spawns=[("nurse", 1), ("fry", 3)])),
    ("n_quiet", "nursery", "chamber", 0, 2, "a still corner", dict(
        quiet=True)),
    ("n_stair", "nursery", "shaft", 1, 2, "the descent", dict(
        spawns=[("nurse", 1), ("coelenter", 2)])),

    # --- cisterns ----------------------------------------------------
    ("c_mouth", "cisterns", "hall", 1, 3, "cistern mouth", dict(
        nerve=True, organ="bladder",
        spawns=[("lamprey", 2), ("carrion", 1)])),
    ("c_sink", "cisterns", "cavern", 0, 3, "the sink", dict(
        frag="ledger_a", organ="brackish",
        spawns=[("lamprey", 2), ("fry", 4)])),
    ("c_span", "cisterns", "hall", 2, 3, "the span", dict(
        frag="husbandry", spawns=[("carrion", 2), ("lamprey", 1)])),
    ("c_shelf", "cisterns", "cavern", 3, 3, "the shelf", dict(
        organ="bloom", seeps=[[3, 0, 14, 0]], spawns=[("ossuary", 1)])),
    ("c_bloom", "cisterns", "warren", 0, 4, "bloom warren", dict(
        organ="root", spawns=[("silt_mother", 1), ("fry", 4)])),
    ("c_still", "cisterns", "chamber", 1, 4, "the stilling basin", dict(
        quiet=True, organ="swell")),
    ("c_bone", "cisterns", "cavern", 2, 4, "the bone shelf", dict(
        frag="mark_two", organ="seed",
        spawns=[("ossuary", 1), ("carrion", 2)])),
    ("c_seal", "cisterns", "chamber", 3, 4, "sealed ward", dict(
        frag="organ_note", organ="harmonic", spawns=[("carrion", 1)])),
    ("c_deep", "cisterns", "hall", 1, 5, "the deep basin", dict(
        frag="cistern_depth", nerve=True,
        spawns=[("lamprey", 3), ("ossuary", 1)])),
    ("c_gate", "cisterns", "cavern", 0, 5, "the scald", dict(
        organ="condenser", seeps=[[0, 20, 0, 0]])),
    ("c_drop", "cisterns", "shaft", 2, 5, "the drop", dict(
        spawns=[("carrion", 1), ("lamprey", 2)])),

    # --- lattice -----------------------------------------------------
    ("l_rack", "lattice", "hall", 2, 6, "the rack", dict(
        nerve=True, organ="harmonic", spawns=[("circuit", 2)])),
    ("l_conduit", "lattice", "corridor", 1, 6, "conduit run", dict(
        frag="escalation", organ="spine", spawns=[("circuit", 2)])),
    ("l_spool", "lattice", "chamber", 3, 6, "the spool", dict(
        organ="mirror_sac", spawns=[("hollow", 1)])),
    ("l_cell", "lattice", "cavern", 1, 7, "holding cell", dict(
        frag="attendant_note", organ="spinneret",
        spawns=[("recursor", 1), ("circuit", 1)])),
    ("l_switch", "lattice", "hall", 2, 7, "the switch floor", dict(
        nerve=True, organ="proboscis",
        spawns=[("circuit", 2), ("hollow", 1)])),
    ("l_hush", "lattice", "chamber", 0, 7, "dead conduit", dict(
        quiet=True, frag="mark_three", organ="sieve")),
    ("l_climb", "lattice", "shaft", 3, 7, "the climb", dict(
        frag="pass", organ="knot", spawns=[("circuit", 1)])),
    ("l_core", "lattice", "hall", 2, 8, "the core floor", dict(
        organ="tendril", spawns=[("the_circuit", 1), ("hollow", 1)])),
    ("l_vein", "lattice", "warren", 1, 8, "the vein", dict(
        organ="ganglion", spawns=[("recursor", 1), ("circuit", 2)])),
    ("l_gate", "lattice", "chamber", 3, 8, "the lower door", dict(
        spawns=[("hollow", 1)])),

    # --- sill --------------------------------------------------------
    ("s_lip", "sill", "hall", 3, 9, "the lip", dict(
        frag="sill_lip", spawns=[("hollow", 1), ("carrion", 2)])),
    ("s_cold", "sill", "cavern", 2, 9, "the cold shelf", dict(
        organ="condenser", spawns=[("recursor", 1), ("hollow", 1)])),
    ("s_hush", "sill", "chamber", 1, 9, "under the shelf", dict(
        quiet=True, frag="last_log", organ="harmonic")),
    ("s_long", "sill", "hall", 2, 10, "the long floor", dict(
        nerve=True, spawns=[("hollow", 2), ("recursor", 1)])),
    ("s_ossuary", "sill", "warren", 1, 10, "the ossuary", dict(
        frag="mark_four", organ="tithe", spawns=[("carrion", 3)])),
    ("s_first", "sill", "chamber", 3, 10, "where it waited", dict(
        nerve=True, spawns=[("first", 1)])),
    ("s_deep", "sill", "cavern", 2, 11, "the last shelf", dict(
        frag="your_number", spawns=[("hollow", 1)])),
    ("s_axis", "sill", "chamber", 3, 11, "the sill", dict(
        ending=True, spawns=[("conspecific", 1)])),
]

# --------------------------------------------------------------- edges
# (a, b, lock). Side is derived from the map coordinates, and both halves
# of every door are generated from this one entry.

_EDGES = [
    ("n_caul", "n_crib", None),
    ("n_crib", "n_ward", None),
    ("n_crib", "n_run", None),
    ("n_ward", "n_font", None),
    ("n_ward", "n_gallery", None),
    ("n_run", "n_gallery", None),
    ("n_run", "n_creche", None),
    ("n_gallery", "n_vault", LOCK_FORCE),
    ("n_creche", "n_quiet", None),
    ("n_quiet", "n_stair", None),
    ("n_stair", "c_mouth", None),

    ("c_mouth", "c_sink", None),
    ("c_mouth", "c_span", None),
    ("c_mouth", "c_still", None),
    ("c_span", "c_shelf", None),
    ("c_span", "c_bone", None),
    ("c_bone", "c_seal", LOCK_CAUSTIC),
    ("c_sink", "c_bloom", None),
    ("c_still", "c_bloom", None),
    ("c_still", "c_deep", None),
    ("c_deep", "c_gate", LOCK_COLD),
    ("c_deep", "c_drop", None),
    ("c_drop", "l_rack", None),

    ("l_rack", "l_conduit", None),
    ("l_rack", "l_spool", None),
    ("l_rack", "l_switch", None),
    ("l_conduit", "l_cell", None),
    ("l_cell", "l_switch", None),
    ("l_cell", "l_hush", None),
    ("l_switch", "l_climb", LOCK_RISE),
    ("l_switch", "l_core", None),
    ("l_core", "l_vein", None),
    ("l_core", "l_gate", LOCK_GENTLE),
    ("l_gate", "s_lip", None),

    ("s_lip", "s_cold", None),
    ("s_cold", "s_hush", None),
    ("s_cold", "s_long", None),
    ("s_long", "s_ossuary", None),
    ("s_long", "s_first", None),
    ("s_long", "s_deep", None),
    ("s_deep", "s_axis", None),
]


class Atlas:
    def __init__(self):
        self.rooms = {}
        self.order = []
        self.start = "n_caul"
        self._build()

    def _build(self):
        from .. import config as C
        meta = {}
        for key, region, kind, mx, my, name, extra in _ROOMS:
            meta[key] = (region, kind, mx, my, name, extra)
            self.order.append(key)

        doors = {k: [] for k in meta}
        used = {k: {} for k in meta}

        for a, b, lock in _EDGES:
            if a not in meta or b not in meta:
                raise KeyError("edge references unknown room: %s -> %s" % (a, b))
            _, _, ax, ay, _, _ = meta[a]
            _, _, bx, by, _, _ = meta[b]
            if bx > ax:
                sa, sb = "e", "w"
            elif bx < ax:
                sa, sb = "w", "e"
            elif by > ay:
                sa, sb = "s", "n"
            else:
                sa, sb = "n", "s"
            doors[a].append(dict(side=sa, at=_slot(used[a], sa), target=b,
                                 lock=lock))
            doors[b].append(dict(side=sb, at=_slot(used[b], sb), target=a,
                                 lock=lock))

        for key, (region, kind, mx, my, name, extra) in meta.items():
            reg = REGIONS[region]
            props = []
            if extra.get("frag"):
                props.append({"kind": "fragment", "id": extra["frag"],
                              "hidden": True})
            if extra.get("organ"):
                props.append({"kind": "organ", "id": extra["organ"],
                              "hidden": True})
            if extra.get("nerve"):
                props.append({"kind": "nerve", "id": "nerve_" + key,
                              "hidden": True})
            if extra.get("quiet"):
                props.append({"kind": "quiet", "id": "quiet_" + key})
            if extra.get("ending"):
                props.append({"kind": "ending", "id": "ending"})

            spawns = [{"kind": k, "n": n} for k, n in extra.get("spawns", [])]
            seeps = [{"water": w, "radius": 175.0}
                     for w in extra.get("seeps", [])]

            self.rooms[key] = {
                "region": region,
                "kind": kind,
                "name": name,
                "map": (mx, my),
                "w": C.ROOM_W,
                "h": C.ROOM_H,
                "water": reg["water"],
                "doors": doors[key],
                "spawns": spawns,
                "seeps": seeps,
                "props": props,
                "quiet": bool(extra.get("quiet")),
                "ending": bool(extra.get("ending")),
            }

    def spec(self, key):
        return self.rooms[key]

    def region_of(self, key):
        return self.rooms[key]["region"]

    def neighbours(self, key):
        return [d["target"] for d in self.rooms[key]["doors"]]

    def check(self):
        """Structural assertions. Run by the verification suite and cheap
        enough to run at startup — a world with a one-way door or an
        unreachable region is not a bug you want to find in the dark."""
        problems = []
        for key, spec in self.rooms.items():
            for d in spec["doors"]:
                t = d["target"]
                if t not in self.rooms:
                    problems.append("%s -> missing room %s" % (key, t))
                    continue
                back = [e for e in self.rooms[t]["doors"] if e["target"] == key]
                if not back:
                    problems.append("%s -> %s has no return door" % (key, t))
                elif back[0]["lock"] != d["lock"]:
                    problems.append("%s <-> %s lock mismatch" % (key, t))

        seen = {self.start}
        stack = [self.start]
        while stack:
            k = stack.pop()
            for n in self.neighbours(k):
                if n in self.rooms and n not in seen:
                    seen.add(n)
                    stack.append(n)
        missing = set(self.rooms) - seen
        if missing:
            problems.append("unreachable: %s" % ", ".join(sorted(missing)))
        return problems


def _slot(used, side):
    """Spread multiple doors along the same wall instead of stacking them
    on top of each other, which would silently merge two exits into one."""
    from .. import config as C
    n = used.get(side, 0)
    used[side] = n + 1
    span = C.ROOM_H if side in ("e", "w") else C.ROOM_W
    offsets = [0.5, 0.28, 0.72, 0.14, 0.86]
    return int(span * offsets[n % len(offsets)])


ATLAS = Atlas()
