"""Run structure: what you meet, in what order, and why that order.

Every room introduces exactly one idea and then stops. The ordering is not
difficulty-first, it is dependency-first — a room is only allowed to appear
once every idea it relies on has already been survived somewhere earlier.

    1  aim and fire                      (nothing)
    2  bands are a gate, not a bonus     (needs 1)
    3  incoming energy is the same stuff (needs 1)
    4  two sources interfere             (needs 3)
    5  the top band needs overdrive      (needs 2, 3)

Rooms 6+ recombine without introducing anything new, which is where a run
stops teaching and starts testing. That boundary is deliberate: a roguelite
that keeps introducing mechanics forever never lets the player feel
competent, and competence is the reward this particular game is selling.
"""

import random

ROOMS = [
    {
        "name": "First Light",
        "banner": "Left-click to strike. Hold to sustain.",
        "teaches": "A big ring rings slow. Slow travels far and shoves hard.",
        "enemies": {"cinder": 3},
        "width": 1500, "height": 1050,
    },
    {
        "name": "The Mirror",
        "banner": "Your opener will bounce. Something else won't.",
        "teaches": "A Ward reflects the low bands. Heat is a smaller ring - and it dies in the air, so walk in.",
        "enemies": {"cinder": 2, "ward": 1},
        "width": 1600, "height": 1120,
    },
    {
        "name": "Crossfire",
        "banner": "They radiate too. Energy is energy.",
        "teaches": "Drone motes cancel against opposite chirality. A pull sigil parries a push.",
        "enemies": {"cinder": 2, "drone": 1},
        "width": 1750, "height": 1200,
    },
    {
        "name": "The Pair",
        "banner": "Two sources. One envelope.",
        "teaches": "A bonded Choir beats at the difference of its two rings. Break the pair to kill the beat.",
        "enemies": {"choir": 1, "cinder": 2},
        "width": 1750, "height": 1200,
    },
    {
        "name": "The Anchor",
        "banner": "It will not take a hit until it stops being solid.",
        "teaches": "Hold to overdrive. Saturation makes harmonics, harmonics reach the top band, the top band decoheres.",
        "enemies": {"anchor": 1, "drone": 1},
        "width": 1900, "height": 1300,
    },
]

LATE_POOL = [
    {"name": "Choral Ward", "enemies": {"choir": 1, "ward": 2}},
    {"name": "Hunting Party", "enemies": {"cinder": 4, "drone": 2}},
    {"name": "Two Anchors", "enemies": {"anchor": 2, "cinder": 3}},
    {"name": "Mirror Hall", "enemies": {"ward": 3, "drone": 1}},
    {"name": "Full Choir", "enemies": {"choir": 2, "anchor": 1}},
]


def room_spec(index: int, rng=None):
    rng = rng or random.Random(index * 7919)
    if index < len(ROOMS):
        return dict(ROOMS[index])

    base = dict(rng.choice(LATE_POOL))
    depth = index - len(ROOMS)
    scaled = {}
    for kind, n in base["enemies"].items():
        scaled[kind] = n + (1 if depth >= 2 and kind in ("cinder", "drone") else 0)
    base["enemies"] = scaled
    base["banner"] = f"Depth {index + 1}"
    base["teaches"] = ""
    base["width"] = 1900
    base["height"] = 1300
    return base


# ---------------------------------------------------------------------------
# Rewards. Kept small and legible: a reward that needs explaining competes
# with the system for the player's attention budget, and the system needs all
# of it.

REWARD_KINDS = [
    ("ink", "New ink family", "A new material. Different tradeoff, same physics."),
    ("budget", "+180 ink budget", "Bigger sigils, on every focus."),
    ("heal", "Restore health", "Back to full."),
    ("slot", "+1 focus slot", "Carry another instrument."),
]


def rewards_for(index: int, run, rng=None):
    """Two choices, never more. Three is a menu; two is a decision."""
    rng = rng or random.Random(index * 104729 + 17)
    pool = []
    if run.locked_inks:
        pool.append("ink")
    pool.append("budget")
    if run.player_hp_fraction < 0.85:
        pool.append("heal")
    if len(run.foci) < run.max_foci:
        pool.append("slot")

    rng.shuffle(pool)
    chosen = pool[:2]
    if len(chosen) < 2:
        chosen = (chosen + ["budget", "heal"])[:2]
    lookup = {k: (k, label, desc) for k, label, desc in REWARD_KINDS}
    return [lookup[k] for k in chosen]
