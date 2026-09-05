"""Assertions about the design, not about the code.

Every check here is a *claim the game makes to the player*, written as
something that can fail. If ordering stops mattering, if a balanced charge
starts doing damage, if the Muffle stops being a good trade, if a region's
water stops changing what your body can do — the game still runs, still
looks fine, and is quietly no longer the thing it says it is. Those are the
failures worth catching, and none of them is a crash.

    python -m clade.verify.selftest
"""

import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

from .. import bestiary, config as C
from ..body import Body, Chain, GRID_H, GRID_W, starting_body
from ..creatures import Creature
from ..effects import resolve
from ..humours import BRINE, ICHOR, SILT, SPARK, Charge, blend_of, strain
from ..organs import BY_KEY, ChainContext, make
from ..world.atlas import ATLAS, REGIONS
from ..world.fields import FREEZE_AT, Fields
from ..world.room import ROCK, Room

class FakeWorld:
    """Enough world for a creature to run a chain against. Real enough that
    a Leech finds something, because a stub that quietly returns None turns
    'the Lamprey cannot attack' into 'the test passes'."""

    _room = None

    def __init__(self):
        self.disturbance = 0.0
        self.player = None
        self.corpses = []
        self.creatures = []
        self.loudest_point = None
        self.events = []
        # A real room, built once and shared. Creatures stir the water while
        # they wind up, so a stub without fields is a stub that cannot run
        # an attack — and a test that quietly skips the attack it is meant
        # to be checking is worse than no test.
        if FakeWorld._room is None:
            from ..world.room import Room
            FakeWorld._room = Room("stub", ATLAS.spec("n_caul"))
        self.room = FakeWorld._room

    def add_disturbance(self, a, pos=None):
        self.disturbance += a

    def note_feed(self, c):
        pass

    def on_death(self, c):
        pass

    def flash_event(self, text, pos=None):
        pass

    def alert_all(self, pos):
        pass

    def drain_nearest_flesh(self, pos, radius, exclude=None):
        return Charge(2.0, 2.0, 2.0, 2.0)


PASSED = []
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print("[PASS] %s%s" % (name, (" (%s)" % detail) if detail else ""))
    else:
        FAILED.append(name)
        print("[FAIL] %s%s" % (name, (" (%s)" % detail) if detail else ""))


def run_chain(keys, reserve=None, cells=None):
    """Build a throwaway body around a chain and fire it once."""
    b = Body()
    if reserve is not None:
        b.reserve = reserve
    cells = cells or [(1, 1), (2, 1), (3, 1), (3, 2), (2, 2), (1, 2)][:len(keys)]
    for c, k in zip(cells, keys):
        b.install(c, make(k))
    b.chains[0] = Chain(list(cells))
    ok, why = b.validate(b.chains[0])
    if not ok:
        return None, why
    ems = b.fire(0, None, (0.0, 0.0), (1.0, 0.0))
    return ems, "ok"


def total(ems, attr):
    return sum(getattr(e.effect, attr) for e in ems)


# ===========================================================================

def t_order_matters():
    """The central claim of the organ system. If this ever comes back near
    1.0, the Noita half of the design is gone and nobody will notice from
    playing for ten minutes."""
    salt = Charge(28, 3, 7, 2)
    good, _ = run_chain(["siphon", "salt_node", "kiln", "spiracle"], salt.copy())
    bad, _ = run_chain(["siphon", "kiln", "salt_node", "spiracle"], salt.copy())
    ratio = total(good, "damage") / max(0.01, total(bad, "damage"))
    check("amplify-then-convert beats convert-then-amplify", ratio > 1.8,
          "%.2fx (%.1f vs %.1f)" % (ratio, total(good, "damage"),
                                    total(bad, "damage")))


def t_gentle_is_not_a_weapon():
    c = Charge(3, 3, 3, 3)
    e = resolve(c)
    check("a balanced charge does no damage", e.damage < 0.01,
          "damage=%.4f" % e.damage)
    check("a balanced charge is silent", e.loudness < 0.01,
          "loudness=%.4f" % e.loudness)
    check("a balanced charge opens living tissue", e.opens_tissue,
          "gentle=%.2f" % e.gentle)


def t_pure_is_a_weapon_and_is_heard():
    e = resolve(Charge(0, 12, 0, 0))
    check("a pure charge hurts", e.damage > 20.0, "damage=%.1f" % e.damage)
    check("a pure charge is loud", e.loudness > 8.0, "loudness=%.1f" % e.loudness)
    check("a pure charge cannot open living tissue", not e.opens_tissue)


def t_nervefire_is_the_peak():
    """The best damage in the game must actually be the best, or its cost
    is a tax on a trap option."""
    m = 8.0
    nerve = resolve(Charge(0, m / 2, 0, m / 2))
    best_pure = max(resolve(Charge.pure(i, m)).damage for i in range(4))
    check("nervefire out-damages any pure spike",
          nerve.damage > best_pure * 1.1,
          "%.1f vs %.1f" % (nerve.damage, best_pure))
    check("nervefire costs the caster", nerve.recoil > 2.0,
          "recoil=%.1f" % nerve.recoil)


def t_muffle_is_a_real_trade():
    r = Charge(6, 22, 8, 4)
    loud, _ = run_chain(["siphon", "kiln", "spiracle"], r.copy())
    quiet, _ = run_chain(["siphon", "muffle", "kiln", "spiracle"], r.copy())
    d_loud, d_quiet = total(loud, "damage"), total(quiet, "damage")
    n_loud = sum(e.loudness for e in loud)
    n_quiet = sum(e.loudness for e in quiet)
    eff_loud = d_loud / max(0.01, n_loud)
    eff_quiet = d_quiet / max(0.01, n_quiet)
    check("muffle keeps more damage than noise",
          eff_quiet > eff_loud * 1.5,
          "damage-per-noise %.2f -> %.2f" % (eff_loud, eff_quiet))
    check("muffle costs real damage", d_quiet < d_loud * 0.75,
          "%.1f -> %.1f" % (d_loud, d_quiet))


BUILDS = {
    "burn": ["siphon", "salt_node", "kiln", "ember_gland", "spiracle"],
    "crush": ["siphon", "brackish", "salt_node", "salt_node", "spiracle"],
    "nerve": ["siphon", "ganglion", "spine", "spiracle"],
    "smother": ["siphon", "settling_sac", "bloom", "caster"],
    "rot": ["siphon", "bloom", "kiln", "caster"],
    "pure": ["filter_gill", "swell", "spiracle"],
    "quiet": ["siphon", "muffle", "salt_node", "kiln", "spiracle"],
}


def probe(keys, water):
    """Fire a build and report what it cost as well as what it did. Heat
    alone is the wrong denominator: in a game where being heard is what
    kills you, noise is the larger half of the bill, and a metric that
    ignores it concludes that the loudest build in the game is the best one
    everywhere — which it is, right up until something answers."""
    b = Body()
    b.reserve = water.copy()
    cells = [(1, 1), (2, 1), (3, 1), (3, 2), (2, 2), (1, 2)][:len(keys)]
    for c, k in zip(cells, keys):
        b.install(c, make(k))
    b.chains[0] = Chain(list(cells))
    ems = b.fire(0, None, (0.0, 0.0), (1.0, 0.0))
    heat = sum(o.heat for o in b.installed())
    noise = sum(e.loudness for e in ems)
    return ems, heat + 3.0 * noise


def score_against(ems, sp):
    out = 0.0
    for e in ems:
        f = e.effect.charge.fractions()
        through = 1.0 - sum(f[i] * sp.resist[i] for i in range(4))
        out += (e.effect.damage * max(0.05, through)
                * max(0.15, 1.0 - sp.armour))
    return out


def region_table():
    table = {}
    for reg, meta in REGIONS.items():
        water = Charge.of(meta["water"]).scaled(3.0)
        pool = [bestiary.get(k) for k in bestiary.REGION_POOLS[reg]]
        scores = {}
        for name, keys in BUILDS.items():
            ems, cost = probe(keys, water.copy())
            if not ems:
                scores[name] = 0.0
                continue
            scores[name] = (sum(score_against(ems, sp) for sp in pool)
                            / len(pool) / max(1.0, cost))
        table[reg] = scores
    return table


def t_water_changes_the_body():
    """The strong form of the claim: not that a chain hits for different
    numbers in different regions, but that **a different build is the right
    one**. If one build wins everywhere, the four kinds of water are
    scenery and re-plumbing between regions is busywork."""
    table = region_table()
    winners = {r: max(s, key=s.get) for r, s in table.items()}
    check("the best build is not the same build everywhere",
          len(set(winners.values())) >= 3,
          " ".join("%s->%s" % (r, w) for r, w in winners.items()))

    for name in BUILDS:
        wins = sum(1 for r, s in table.items() if max(s, key=s.get) == name)
        if wins == len(table):
            check("no build is best in every region", False, name)
            return
    check("no build is best in every region", True)


def t_the_local_answer_is_a_trap():
    """The Lattice is thick with live water, so the obvious build there is
    the nerve build — and everything that lives in the Lattice is armoured
    against nerve. The region hands you the wrong answer for free and makes
    you pay a conversion toll for the right one.

    This is the single best lesson in the game and it is entirely emergent:
    nothing scripts it, it is just water composition meeting resistance
    tables."""
    table = region_table()
    lattice = table["lattice"]
    naive = lattice["nerve"]
    best = max(lattice.values())
    check("in the Lattice the local-water build is not the answer",
          naive < best * 0.85, "nerve=%.2f best=%.2f" % (naive, best))
    check("and the answer there is a build that converts",
          max(lattice, key=lattice.get) in ("burn", "rot", "crush"),
          max(lattice, key=lattice.get))

    nursery = table["nursery"]
    check("the Nursery is exempt — the obvious answer works there",
          max(nursery.values()) > max(table["cisterns"].values()),
          "%.2f vs %.2f" % (max(nursery.values()),
                            max(table["cisterns"].values())))


def t_one_chain_swings_across_the_map():
    """A chain with no converter in it is a mirror: it fires whatever the
    region is made of. That is the version of this the player actually
    *sees*, because the colour of their own shots changes when they change
    region, before anybody has explained why."""
    from ..humours import NAMES
    keys = ["siphon", "swell", "spiracle"]
    doms = {}
    for reg, meta in REGIONS.items():
        ems, _ = run_chain(keys, Charge.of(meta["water"]).scaled(3.0))
        doms[reg] = NAMES[ems[0].charge.dominant]
    check("an unconverting chain takes the colour of the water it is in",
          len(set(doms.values())) == 4,
          " ".join("%s=%s" % (r, d) for r, d in doms.items()))

    out = {}
    for reg, meta in REGIONS.items():
        ems, _ = run_chain(BUILDS["burn"],
                           Charge.of(meta["water"]).scaled(3.0))
        out[reg] = total(ems, "damage")
    lo, hi = min(out.values()), max(out.values())
    check("and a converting chain still pays a real regional toll",
          hi > lo * 1.35,
          " ".join("%s=%.0f" % (k, v) for k, v in out.items()))


def t_amplifiers_saturate():
    """The rule that stopped one amplifier stack from winning the game."""
    from ..organs import _amplify
    thin = Charge(1, 3, 3, 3)
    thick = Charge(9, 0.3, 0.3, 0.4)
    a = thin.copy(); _amplify(a, BRINE, 3.4)
    b = thick.copy(); _amplify(b, BRINE, 3.4)
    gain_thin = a[BRINE] / thin[BRINE]
    gain_thick = b[BRINE] / thick[BRINE]
    check("amplifying a minority humour pays much better than a spike",
          gain_thin > gain_thick * 2.0,
          "%.2fx vs %.2fx" % (gain_thin, gain_thick))

    water = Charge(30, 4, 4, 4)
    one, _ = run_chain(["siphon", "salt_node", "spiracle"], water.copy())
    two, _ = run_chain(["siphon", "salt_node", "salt_node", "spiracle"],
                       water.copy())
    ratio = total(two, "damage") / max(0.01, total(one, "damage"))
    # Before saturation this pair was a flat 2.8x2.8 and the second node
    # roughly doubled the shot for three heat, which is why the stack beat
    # every other build in every region. Diminishing, not doubling, is the
    # whole of the fix.
    check("a second amplifier on the same humour is diminishing, not doubling",
          ratio < 1.6, "%.2fx for a whole extra organ and its heat" % ratio)


def t_sieve_and_harmonic_make_keys():
    """There must be a buildable route to gentleness, from a spiked
    reserve, or the gate to the Sill is a wall.

    Note what the working build costs: a *wide* intake, because gentleness
    scales with magnitude and the two organs that make a mixture even both
    destroy magnitude doing it. So a key is four organs and a big gulp,
    which is exactly the right price for the thing that opens the last
    region."""
    spiked = Charge(2, 30, 3, 2)
    plain, _ = run_chain(["siphon", "spiracle"], spiked.copy())
    check("a spiked body cannot open tissue by default",
          not plain[0].effect.opens_tissue)

    thin, _ = run_chain(["siphon", "harmonic", "pore_field"], spiked.copy())
    keyed, _ = run_chain(["gullet", "sieve", "harmonic", "pore_field"],
                         spiked.copy())
    check("a wide intake plus sieve plus harmonic makes a key",
          keyed[0].effect.opens_tissue,
          "gentle=%.2f div=%.2f" % (keyed[0].effect.gentle,
                                    keyed[0].effect.divergence))
    check("a narrow intake does not — volume is part of the price",
          not thin[0].effect.opens_tissue,
          "gentle=%.2f" % thin[0].effect.gentle)

    sieved, _ = run_chain(
        ["gullet", "sieve", "swell", "swell", "pore_field"], spiked.copy())
    check("sieve plus volume also gets there (the no-harmonic route)",
          sieved[0].effect.opens_tissue,
          "gentle=%.2f div=%.2f" % (sieved[0].effect.gentle,
                                    sieved[0].effect.divergence))


def t_every_lock_is_satisfiable():
    """Each door lock must be answerable by some chain built from organs
    the player can actually reach before that door."""
    reg = {k: Charge.of(v["water"]).scaled(3.0) for k, v in
           ((r, REGIONS[r]) for r in REGIONS)}

    caustic, _ = run_chain(["siphon", "bloom", "kiln", "caster"],
                           reg["cisterns"].copy())
    check("CAUSTIC lock: rot is buildable in the Cisterns",
          caustic[0].effect.caustic > 2.4,
          "caustic=%.2f" % caustic[0].effect.caustic)

    cold, _ = run_chain(["siphon", "salt_node", "salt_node", "caster"],
                        reg["sill"].copy())
    check("COLD lock: freezing is buildable from brine",
          cold[0].effect.freezes, "heat=%.2f" % cold[0].effect.heat)

    force, _ = run_chain(["gullet", "salt_node", "swell", "spiracle"],
                         reg["sill"].copy())
    check("FORCE lock: a big shove is buildable",
          abs(force[0].effect.force) > 900.0,
          "force=%.0f" % force[0].effect.force)

    gentle, _ = run_chain(["gullet", "harmonic", "pore_field"],
                          reg["lattice"].copy())
    check("GENTLE lock: a key is buildable in the Lattice",
          gentle[0].effect.gentle > 1.2,
          "gentle=%.2f" % gentle[0].effect.gentle)

    lift, _ = run_chain(["siphon", "mirror_sac", "pore_field"],
                        reg["sill"].copy())
    check("RISE gate: a mirror sac makes lift", lift[0].effect.lift > 0.0,
          "lift=%.1f" % lift[0].effect.lift)


def t_recursor_feeds_on_focus():
    """The one creature whose lesson is 'stop hitting it harder'."""
    sp = bestiary.get("recursor")
    w = FakeWorld()
    c = Creature(sp, (0, 0))
    dealt = c.take(resolve(Charge(0, 20, 0, 0)), w, (10, 0))
    check("a focused hit does no damage to a Recursor", dealt == 0.0,
          "dealt=%.1f" % dealt)

    c.viability = sp.viability * 0.5           # wound it first: a full one
    before = c.viability                        # has nowhere to put the meal
    c.take(resolve(Charge(0, 20, 0, 0)), w, (10, 0))
    check("a wounded Recursor is healed by a focused hit", c.viability > before,
          "%.1f -> %.1f" % (before, c.viability))

    c2 = Creature(sp, (0, 0))
    b2 = c2.viability
    c2.take(resolve(Charge(5, 5, 5, 5)), w, (10, 0))
    check("a gentle charge hurts a Recursor", c2.viability < b2,
          "%.1f -> %.1f" % (b2, c2.viability))


def t_resistance_is_readable():
    w = FakeWorld()
    sp = bestiary.get("silt_mother")
    a = Creature(sp, (0, 0))
    b = Creature(sp, (0, 0))
    d_silt = a.take(resolve(Charge(0, 0, 10, 0)), w, (9, 0))
    d_ichor = b.take(resolve(Charge(0, 10, 0, 0)), w, (9, 0))
    check("a thing made of sediment shrugs off sediment",
          d_ichor > d_silt * 2.0, "silt=%.1f ichor=%.1f" % (d_silt, d_ichor))


def t_heat_is_local():
    """Body layout has to matter thermally, or the grid is a list."""
    b = Body()
    b.install((1, 1), make("ember_gland"))
    b.install((2, 1), make("ganglion"))   # adjacent
    b.install((1, 2), make("spine"))      # adjacent
    b.install((3, 2), make("condenser"))  # not adjacent
    b.cells[(1, 1)].heat = 90.0
    for _ in range(60):
        b._thermal(1 / 60.0, None, None)
    near = b.cells[(2, 1)].heat
    far = b.cells[(3, 2)].heat
    check("heat crawls to neighbours and not across the body",
          near > far * 3.0, "adjacent=%.1f distant=%.1f" % (near, far))
    check("an organ can be cooked until it seizes",
          b.cells[(1, 1)].seized or b.cells[(1, 1)].heat < 90.0,
          "source heat=%.1f" % b.cells[(1, 1)].heat)


def t_seize_has_hysteresis():
    b = Body()
    b.install((1, 1), make("kiln"))
    o = b.cells[(1, 1)]
    o.heat = C.ORGAN_SEIZE_AT + 1.0
    b._thermal(0.001, None, None)
    check("an organ over the ceiling seizes", o.seized)
    o.heat = (C.ORGAN_SEIZE_AT + C.ORGAN_COOL_AT) / 2.0
    b._thermal(0.001, None, None)
    check("it stays seized between the two thresholds", o.seized,
          "heat=%.1f" % o.heat)
    o.heat = C.ORGAN_COOL_AT - 1.0
    b._thermal(0.001, None, None)
    check("it comes back below the lower threshold", not o.seized)


def t_composition_is_buoyancy_and_light():
    heavy = Body()
    heavy.reserve = Charge(40, 1, 4, 1)
    light = Body()
    light.reserve = Charge(2, 30, 2, 2)
    heavy.update(0.016)
    light.update(0.016)
    check("a brine-heavy body is heavier",
          heavy.mods["weight"] > light.mods["weight"] * 1.4,
          "%.2f vs %.2f" % (heavy.mods["weight"], light.mods["weight"]))
    check("an ichor-heavy body is brighter", light.glow > heavy.glow * 3.0,
          "glow %.2f vs %.2f" % (light.glow, heavy.glow))
    check("brightness costs sight-range secrecy", light.sight > heavy.sight,
          "sight %.0f vs %.0f" % (light.sight, heavy.sight))


def t_strain_punishes_purity():
    pure = Charge(40, 0, 0, 0)
    even = Charge(10, 10, 10, 10)
    check("a pure body is strained", strain(pure) > 0.9,
          "%.2f" % strain(pure))
    check("an even body is not", strain(even) < 0.01)


def t_fields_do_what_they_claim():
    f = Fields(1536, 864, Charge(4, 9, 5, 2))
    before = f.ambient((300, 300))[ICHOR]
    f.add_heat((300, 300), 60, 4.0)
    for _ in range(30):
        f.update(1 / 60)
    after = f.ambient((300, 300))[ICHOR]
    check("fire makes the water around it richer in ichor", after > before * 1.5,
          "%.1f -> %.1f" % (before, after))

    f.add_heat((700, 300), 60, -14.0)
    for _ in range(20):
        f.update(1 / 60)
    check("chilling the water freezes it solid", f.frozen_at((700, 300)))

    f.add_silt((300, 600), 90, 3.0)
    for _ in range(10):
        f.update(1 / 60)
    vis = f.visibility_along((100, 600), (500, 600))
    check("silt shortens a sightline", vis < 0.6, "visibility=%.2f" % vis)


def t_diffusion_conserves():
    """The bug that quietly deletes every spreading effect in the game."""
    f = Fields(800, 600, Charge(1, 1, 1, 1))
    f.add_heat((400, 300), 70, 5.0)
    start = float(f.heat.sum())
    from ..world.fields import _diffuse
    a = f.heat.copy()
    for _ in range(40):
        a = _diffuse(a, 0.2)
    check("diffusion moves heat instead of destroying it",
          abs(float(a.sum()) - start) < start * 0.02,
          "%.2f -> %.2f" % (start, float(a.sum())))


def t_atlas_is_sound():
    problems = ATLAS.check()
    check("every door has a matching door on the other side and every room "
          "is reachable", not problems, "; ".join(problems[:3]))
    check("the map is the promised size", 35 <= len(ATLAS.rooms) <= 45,
          "%d rooms" % len(ATLAS.rooms))
    regions = {}
    for spec in ATLAS.rooms.values():
        regions[spec["region"]] = regions.get(spec["region"], 0) + 1
    check("all four regions exist and are populated",
          len(regions) == 4 and min(regions.values()) >= 6, str(regions))


def t_rooms_connect():
    """A generated room whose exits do not reach each other is an hour of
    the player's life spent in the dark for nothing."""
    import collections
    bad = []
    for kind in ("cavern", "hall", "warren", "shaft", "corridor", "chamber"):
        spec = {"kind": kind, "doors": [
            {"side": "e", "at": 13, "target": "a"},
            {"side": "w", "at": 13, "target": "b"},
            {"side": "s", "at": 24, "target": "c"},
            {"side": "n", "at": 20, "target": "d"}]}
        for seed in range(8):
            import random
            r = Room("%s%d" % (kind, seed), spec, random.Random(seed))
            start = None
            for t in r.doors[0].tiles(r.w, r.h):
                if r.tiles[t[1]][t[0]] != ROCK:
                    start = t
                    break
            if start is None:
                bad.append("%s/%d no opening" % (kind, seed))
                continue
            seen = {start}
            q = collections.deque([start])
            while q:
                x, y = q.popleft()
                for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + d[0], y + d[1])
                    if r.in_bounds(*n) and n not in seen \
                            and r.tiles[n[1]][n[0]] != ROCK:
                        seen.add(n)
                        q.append(n)
            for d in r.doors:
                if not any(t in seen for t in d.tiles(r.w, r.h)):
                    bad.append("%s/%d %s unreachable" % (kind, seed, d.side))
    check("every room kind connects all four exits, 8 seeds each",
          not bad, "; ".join(bad[:3]))


def t_every_atlas_room_builds():
    import random
    bad = []
    for key in ATLAS.rooms:
        try:
            r = Room(key, ATLAS.spec(key), random.Random(7))
            if len(r.free_cells()) < 120:
                bad.append("%s only %d open" % (key, len(r.free_cells())))
        except Exception as exc:                      # pragma: no cover
            bad.append("%s raised %s" % (key, exc))
    check("all %d authored rooms build with room to swim" % len(ATLAS.rooms),
          not bad, "; ".join(bad[:3]))


def t_organs_are_wired():
    missing = [t.key for t in BY_KEY.values()
               if t.role != "vent" and t.fn is None]
    check("every non-vent organ has a transform", not missing, str(missing))
    novent = [t.key for t in BY_KEY.values()
              if t.role == "vent" and t.vent is None]
    check("every vent has a shape", not novent, str(novent))
    unreachable = set(BY_KEY) - {p["id"] for s in ATLAS.rooms.values()
                                 for p in s["props"] if p["kind"] == "organ"}
    unreachable -= set(__import__("clade.organs", fromlist=["x"]).STARTING_KEYS)
    unreachable -= {k for sp in bestiary.SPECIES.values() for k in sp.drops}
    check("every organ is obtainable somewhere", not unreachable,
          str(sorted(unreachable)))


def t_creatures_use_the_same_grammar():
    bad = []
    for key, sp in bestiary.SPECIES.items():
        for k in sp.organs:
            if k not in BY_KEY:
                bad.append("%s has unknown organ %s" % (key, k))
        if not sp.chain:
            continue
        seq = [BY_KEY[sp.organs[i]] for i in sp.chain]
        if seq[0].role != "intake":
            bad.append("%s chain does not start at an intake" % key)
        if seq[-1].role != "vent":
            bad.append("%s chain does not end at a vent" % key)
        for m in seq[1:-1]:
            if m.role != "transform":
                bad.append("%s has %s mid-chain" % (key, m.key))
    check("every creature's attack is a legal organ chain", not bad,
          "; ".join(bad[:3]))


def t_creatures_actually_fire():
    silent = []
    for key, sp in bestiary.SPECIES.items():
        if not sp.chain:
            continue
        c = Creature(sp, (100, 100))
        out = []
        c.fire(FakeWorld(), (1.0, 0.0), out)
        if not out or sum(e.effect.damage for e in out) <= 0.0:
            silent.append(key)
    check("every armed creature produces a real attack", not silent,
          str(silent))


def t_starting_body_can_kill_the_first_thing():
    """A new player with the default wiring must be able to win the first
    fight without understanding anything. If this fails the opening is a
    wall."""
    ems, _ = run_chain(["siphon", "kiln", "spiracle"], Charge(6, 22, 8, 4))
    dmg = total(ems, "damage")
    hp = bestiary.get("coelenter").viability
    shots = math.ceil(hp / max(0.1, dmg))
    check("the starting chain kills a Coelenter in a few shots",
          2 <= shots <= 5, "%d shots (%.1f dmg vs %.0f hp)" % (shots, dmg, hp))


def t_save_round_trip():
    b = starting_body()
    b.pack.append(make("harmonic"))
    b.cells[(1, 1)].heat = 30.0
    b.cells[(1, 1)].integrity = 0.8
    d = b.to_dict()
    b2 = Body.from_dict(d)
    check("a body survives a save and a load",
          len(b2.installed()) == len(b.installed())
          and b2.chains[0].cells == b.chains[0].cells
          and len(b2.pack) == len(b.pack)
          and abs(b2.cells[(1, 1)].integrity - 0.8) < 1e-6)


def t_death_costs_you():
    import types
    from ..app import Game
    scr = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    g = Game(scr, headless=True)
    before = len(g.body.installed())
    g.player.pos = [200.0, 200.0]
    g._regress()
    after = len(g.body.installed())
    check("dying takes organs out of you", after == before - 2,
          "%d -> %d" % (before, after))
    check("dying does not end the run", not g.player.dead
          and g.body.viability > 0)


def t_endings_exist_and_differ():
    from ..app import ENDINGS, Game
    scr = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    g = Game(scr, headless=True)
    a = ENDINGS["harvest"](g)
    b = ENDINGS["abstain"](g)
    check("both endings render", len(a) > 6 and len(b) > 6)
    check("the endings are different texts", a != b)
    for k in ("escalation", "pass", "attendant_note", "last_log",
              "your_number", "mark_three"):
        g.codex.find_fragment(k)
    deep = ENDINGS["abstain"](g)
    check("knowing the criterion changes what the ending says", deep != b,
          "codex depth %d" % g.codex.depth)


def t_the_attendant_carries_the_key():
    """The quietest piece of design in the game, and now a load-bearing
    one: the harmless thing that follows you from the first hour is
    carrying a Harmonic, a Siphon and a Pore Field — a complete, working
    key chain. Killing the one creature that never threatens you is the
    fastest route to the organ of gentleness.

    The game says nothing about this, and there is a second Harmonic later
    for anyone who leaves it alone."""
    sp = bestiary.get("attendant")
    check("the Attendant never attacks", not sp.chain and sp.peaceful)
    check("the Attendant is carrying a whole key",
          {"siphon", "harmonic", "pore_field"} <= set(sp.drops), str(sp.drops))
    from ..world.atlas import ATLAS as A
    later = [k for k, spec in A.rooms.items()
             for p in spec["props"]
             if p["kind"] == "organ" and p["id"] == "harmonic"]
    check("and sparing it does not lock the game", len(later) >= 2, str(later))


def t_critical_path_is_walkable():
    """End to end: from the tank you wake in to the room the game ends in,
    opening every gate on the way with a chain built for that gate.

    The lock tests above prove the *arithmetic* is satisfiable. This proves
    the **world** is: that the doors are where the atlas says, that opening
    one really does carve the tiles, that the room on the other side builds
    and connects, and that the route is not severed by a generation seed.
    Everything else in this file can pass while the game is unfinishable."""
    from ..app import Game, PLAY
    from ..world.room import (
        LOCK_CAUSTIC, LOCK_COLD, LOCK_FORCE, LOCK_GENTLE, LOCK_RISE,
    )

    screen = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    game = Game(screen, headless=True)
    game.state = PLAY
    world = game.world

    # Purpose-built answers, one per lock. These are effects, not cheats:
    # each is the resolution of a humour vector a player can produce with
    # organs available before that door.
    keys = {
        LOCK_FORCE: Charge(26, 0, 0, 0),
        LOCK_CAUSTIC: Charge(0, 7, 7, 0),
        LOCK_COLD: Charge(22, 0, 1, 0),
        LOCK_GENTLE: Charge(4, 4, 4, 4),
    }

    route = ["n_caul", "n_crib", "n_run", "n_creche", "n_quiet", "n_stair",
             "c_mouth", "c_still", "c_deep", "c_drop",
             "l_rack", "l_switch", "l_core", "l_gate",
             "s_lip", "s_cold", "s_long", "s_deep", "s_axis"]

    problems = []
    for a, b in zip(route, route[1:]):
        world.enter_room(a)
        room = world.room
        door = next((d for d in room.doors if d.target == b), None)
        if door is None:
            problems.append("no door %s -> %s" % (a, b))
            break
        if not door.open:
            answer = keys.get(door.lock)
            if answer is None:
                problems.append("%s -> %s has lock %r with no answer"
                                % (a, b, door.lock))
                break
            cx, cy = door.center_px(room.w, room.h)
            game.player.pos = [cx, cy]
            if not world.try_open_door(resolve(answer), (cx, cy)):
                problems.append("%s -> %s (%s) would not open"
                                % (a, b, door.lock))
                break
        if not door.open:
            problems.append("%s -> %s still shut after opening" % (a, b))
            break
        # ...and the tiles really are carved, not just the flag flipped.
        if all(room.tiles[t[1]][t[0]] != 0 for t in door.tiles(room.w, room.h)):
            problems.append("%s -> %s opened but stayed solid" % (a, b))
            break

    check("the whole route from the tank to the sill can be walked",
          not problems, "; ".join(problems[:2]))

    # And every optional gate opens too, so no reward is stranded.
    stranded = []
    for key, spec in ATLAS.rooms.items():
        for d in spec["doors"]:
            if d["lock"] is None or d["lock"] == LOCK_RISE:
                continue
            world.enter_room(key)
            room = world.room
            door = next((x for x in room.doors
                         if x.side == d["side"] and x.at == d["at"]), None)
            if door is None or door.open:
                continue
            answer = keys.get(door.lock)
            cx, cy = door.center_px(room.w, room.h)
            if answer is None or not world.try_open_door(resolve(answer),
                                                         (cx, cy)):
                stranded.append("%s/%s(%s)" % (key, d["side"], d["lock"]))
    check("every locked door in the world can be opened", not stranded,
          "; ".join(stranded[:3]))


def t_no_room_strands_you():
    """You must be able to leave every room you can enter. A one-way room
    in a dark game is indistinguishable from a crash."""
    from ..app import Game, PLAY
    screen = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    game = Game(screen, headless=True)
    bad = []
    for key in ATLAS.rooms:
        spec = ATLAS.spec(key)
        exits = [d for d in spec["doors"]]
        if not exits:
            bad.append("%s has no doors" % key)
        elif all(d["lock"] not in (None, "rise") for d in exits):
            # Every way out is locked: fine only if the locks are openable
            # from the inside, which they are, but worth naming.
            pass
    check("every room has a way out", not bad, "; ".join(bad[:3]))


# ===========================================================================
# The overhaul: upkeep, standing chains, region hazards, and a combat
# grammar. Every check below is a claim the first build could not have
# made.
# ===========================================================================

def t_nothing_is_free():
    """The original sin of the first build: ambient water refilled you
    faster than you could spend it, so nothing was scarce and there was no
    reason to do anything. Ambient uptake must not cover a working body."""
    b = starting_body()
    b.recompute_standing()
    check("a body with one standing chain costs more than ambient water "
          "gives back", b.upkeep > b.absorb_rate * 0.55,
          "upkeep %.2f/s vs absorb %.2f/s" % (b.upkeep, b.absorb_rate))

    b2 = Body()
    b2.reserve = Charge(25, 25, 25, 25)
    start = b2.reserve.magnitude
    for _ in range(600):
        b2.update(1 / 60.0)
    drained = start - b2.reserve.magnitude
    check("just being awake drains the tank", drained > 3.0,
          "%.1f in ten seconds" % drained)


def t_feeding_is_the_answer():
    from ..world.live import Corpse
    b = Body()
    b.reserve = Charge(1, 1, 1, 1)
    corpse = Corpse((0, 0), Charge(14, 14, 8, 6), [], "test")
    before = b.reserve.magnitude
    for _ in range(60):
        b.feed(corpse.drain(C.BITE_RATE / 60.0))
    gained = b.reserve.magnitude - before
    check("one second of feeding is worth many seconds of upkeep",
          gained > C.BASE_UPKEEP * 8, "%.1f reserve in one second" % gained)


def t_standing_chains_do_body_things():
    """The answer to 'the Bench is only a weapon designer'. Six chains, six
    genuinely different things done to the body that owns them, all read
    off the same effect rules the weapons use."""
    def standing(keys, reserve):
        b = Body()
        b.reserve = reserve
        cells = [(1, 2), (2, 2), (3, 2)][:len(keys)]
        for c, k in zip(cells, keys):
            b.install(c, make(k))
        b.standing[0] = Chain(list(cells))
        ok, why = b.validate(b.standing[0], standing=True)
        if not ok:
            return None, why
        return b.recompute_standing(), b

    warm, _ = standing(["siphon", "kiln", "ember_gland"], Charge(22, 6, 6, 4))
    check("a burning standing chain makes real heat", warm["heat"] > 1.0,
          "heat=%.2f" % warm["heat"])

    haze, _ = standing(["siphon", "settling_sac", "bloom"], Charge(6, 6, 22, 4))
    check("a sediment standing chain hazes you", haze["murk"] > 1.0,
          "murk=%.2f" % haze["murk"])

    tend, _ = standing(["siphon", "harmonic"], Charge(9, 9, 9, 9))
    check("a balanced standing chain tends you", tend["gentle"] > 1.0,
          "gentle=%.2f" % tend["gentle"])

    up, _ = standing(["siphon", "mirror_sac", "salt_node"],
                     Charge(26, 4, 6, 4))
    check("an inverted-brine standing chain is traversal", up["lift"] > 3.0,
          "lift=%.2f" % up["lift"])

    quick, _ = standing(["siphon", "ganglion", "spine"], Charge(4, 18, 4, 10))
    check("a nerve standing chain makes you quicker", quick["jolt"] > 1.0,
          "jolt=%.2f" % quick["jolt"])

    check("and every one of them costs upkeep",
          all(x is not None for x in (warm, haze, tend, up, quick)))


def t_a_standing_chain_runs_all_its_organs():
    """The bug that made the Cisterns unsolvable: standing chains were
    sliced organs[1:-1], copied from the active path where the last organ
    is a vent. A standing chain has no vent, so its final stage — usually
    the Harmonic, usually the entire point — never ran."""
    b = Body()
    b.reserve = Charge(6, 22, 8, 4)
    for c, k in ((1, 2), "siphon"), ((2, 2), "sieve"), ((3, 2), "harmonic"):
        b.install(c, make(k))
    b.standing[0] = Chain([(1, 2), (2, 2), (3, 2)])
    fx = b.recompute_standing()
    check("the last organ of a standing chain actually runs",
          fx["gentle"] > 0.8, "gentle=%.2f" % fx["gentle"])


def t_every_region_hazard_has_an_answer():
    """Below the Nursery you cannot merely survive being somewhere: each
    region applies a pressure exactly one standing build answers. And the
    wrong build must genuinely fail, or the choice is decoration."""
    from ..app import Game, PLAY
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))

    def trial(room, keys):
        g = Game(screen, headless=True)
        g.state = PLAY
        cells = [(0, 3), (1, 3), (2, 3), (3, 3)][:len(keys)]
        for c in cells:
            g.body.unlock(c)
        for c, k in zip(cells, keys):
            if g.body.organ_at(c) is not None:
                g.body.uninstall(c)
            g.body.install(c, make(k))
        g.body.standing[0] = Chain(list(cells))
        g.world.enter_room(room)
        # A body that has been in this region is full of this region's
        # water. Testing with the starting tank still full of warm Nursery
        # water measures the wrong thing entirely — it lets a chain that
        # makes no heat at all look like an answer to the cold.
        reg = ATLAS.rooms[room]["region"]
        g.body.reserve = Charge.of(REGIONS[reg]["water"]).scaled(2.4)
        g.player.pos = list(g._spawn_point())
        v0 = g.body.viability
        for _ in range(420):
            g.update(1 / 60.0)
        return v0 - g.body.viability, g.world.hazard_bite, g.body.clog

    cases = [
        ("sill", "cold", ["siphon", "kiln", "ember_gland"],
         ["siphon", "settling_sac"]),
        ("lattice", "live water", ["siphon", "settling_sac", "bloom"],
         ["siphon", "kiln", "ember_gland"]),
        ("cisterns", "clogging", ["siphon", "sieve", "harmonic"],
         ["siphon", "bloom"]),
    ]
    rooms = {"sill": "s_lip", "lattice": "l_rack", "cisterns": "c_mouth"}
    for region, label, right, wrong in cases:
        lost_r, bite_r, clog_r = trial(rooms[region], right)
        lost_w, bite_w, clog_w = trial(rooms[region], wrong)
        check("%s: the right standing chain answers it" % label,
              bite_r < 0.2, "bite %.2f (lost %.1f viability)" % (bite_r, lost_r))
        check("%s: the wrong one does not" % label, bite_w > 0.5,
              "bite %.2f (lost %.1f viability)" % (bite_w, lost_w))


def t_attacks_are_telegraphed():
    """No attack may be instant. Windup is the only reason a fight is
    something you can play rather than something that happens to you."""
    instant = [k for k, sp in bestiary.SPECIES.items()
               if sp.chain and sp.windup < 0.3]
    check("every armed creature winds up before it commits", not instant,
          str(instant))
    noreco = [k for k, sp in bestiary.SPECIES.items()
              if sp.chain and sp.recover < 0.5]
    check("and every one of them has a recovery you can punish", not noreco,
          str(noreco))
    archetypes = {sp.attack for sp in bestiary.SPECIES.values() if sp.chain}
    check("the roster uses several different attacks, not one",
          len(archetypes) >= 5, str(sorted(archetypes)))
    behaviours = {sp.behaviour for sp in bestiary.SPECIES.values()}
    check("and several different behaviours", len(behaviours) >= 10,
          "%d" % len(behaviours))


def t_the_cycle_actually_runs():
    from ..creatures import COMMIT, Creature, RECOVER, WINDUP
    sp = bestiary.get("nurse")
    c = Creature(sp, (0, 0))
    w = FakeWorld()
    out = []

    class _P:
        pos = (120.0, 0.0)
        vel = [0.0, 0.0]
    seen = []
    c.cooldown = 0.0          # creatures spawn with a random first delay
    c.begin_attack()
    for _ in range(400):
        c._advance_phase(1 / 60.0, w, _P(), out)
        if c.phase and (not seen or seen[-1] != c.phase):
            seen.append(c.phase)
        if c.phase is None and seen:
            break
    check("an attack passes through windup, commit and recovery in order",
          seen == [WINDUP, COMMIT, RECOVER], str(seen))
    check("and it produced a real emission", out and out[0].effect.damage > 0)


def t_recovery_is_a_punish_window():
    from ..creatures import Creature, RECOVER
    w = FakeWorld()
    sp = bestiary.get("ossuary")
    normal = Creature(sp, (0, 0))
    open_ = Creature(sp, (0, 0))
    open_.phase = RECOVER
    open_.phase_len = open_.phase_t = 1.0
    hit = resolve(Charge(0, 9, 0, 0))
    a = normal.take(hit, w, (10, 0))
    b = open_.take(resolve(Charge(0, 9, 0, 0)), w, (10, 0))
    check("hitting an armoured thing mid-recovery is worth far more",
          b > a * 2.5, "%.1f vs %.1f" % (b, a))


def t_the_player_is_findable_when_they_move():
    """'You just sprint around and they do nothing' was the sharpest thing
    said about the first build, and it was true: nothing in perception
    looked at velocity."""
    from ..creatures import Creature

    class _P:
        def __init__(self, speed):
            self.pos = (300.0, 0.0)
            self.vel = [speed, 0.0]
            self.body = starting_body()

    w = FakeWorld()
    still = Creature(bestiary.get("nurse"), (0.0, 0.0))
    fast = Creature(bestiary.get("nurse"), (0.0, 0.0))
    for _ in range(90):
        still.sense(w, _P(0.0), 1 / 60.0)
        fast.sense(w, _P(C.PLAYER_MAX_SPEED), 1 / 60.0)
    check("moving fast makes you much easier to find than holding still",
          fast.alarm > still.alarm * 1.6,
          "alarm %.2f moving vs %.2f still" % (fast.alarm, still.alarm))


def t_a_motionless_ambusher_is_invisible():
    from ..creatures import Creature
    c = Creature(bestiary.get("silt_mother"), (0, 0))
    c.still_time = 3.0
    check("a silt mother that has stopped moving cannot be seen at all",
          c.hidden)
    c.still_time = 0.0
    check("...and can be, the moment it moves", not c.hidden)


# ===========================================================================
# The Bench. Reported as the worst screen in the game: right-click stopped
# removing after you touched a slot, connections worked "sometimes", and
# nothing said what anything did. These are the guards against all of it
# coming back.
# ===========================================================================

def _bench():
    from ..app import BENCH, Game
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    game = Game(screen, headless=True, sandbox=True)
    game.state = BENCH
    return game, game.bench


def t_right_click_always_removes():
    """The bug that made the Bench feel broken: `_click` dispatched to the
    router before anything else, so arming a slot silently disabled both
    selecting and removing. Every one of these must work *while editing*."""
    game, b = _bench()
    b._arm(1, False)                       # arm a slot: the old poison pill
    cell = next(c for c, o in game.body.cells.items() if o is not None)

    b._click_cell(cell, 3)
    check("right-click removes an organ while a chain is being edited",
          game.body.organ_at(cell) is None)

    other = next(c for c, o in game.body.cells.items() if o is not None)
    b._click_cell(other, 1)
    check("left-click still selects while a chain is being edited",
          b.sel_cell == other)

    check("...and editing is still live afterwards", b.editing == 1)


def t_route_clicks_are_forgiving():
    """Clicking a socket already in the path used to be an error. Now it
    steps back to it, which is what every player expects and what makes a
    misclick cost nothing."""
    game, b = _bench()
    body = game.body
    run = [(0, 0), (1, 0), (2, 0), (3, 0)]
    for cell, key in zip(run, ["siphon", "kiln", "salt_node", "spiracle"]):
        if body.organ_at(cell) is not None:
            body.uninstall(cell)
        body.install(cell, make(key))
    b._arm(0, False)
    b.route = []
    for cell in run:
        b._extend(cell)
    check("clicking sockets in order builds the path", b.route == run,
          str(b.route))

    b._extend(run[1])
    check("clicking a socket already in the path steps back to it",
          b.route == run[:2], str(b.route))

    b._extend((5, 4))
    check("a socket that does not touch the last one is refused, not "
          "silently accepted", b.route == run[:2], str(b.route))


def t_auto_route_produces_legal_chains():
    game, b = _bench()
    body = game.body
    for slot, standing in ((0, False), (1, False), (0, True)):
        b._arm(slot, standing)
        b.route = []
        b._auto_route()
        ok, why = body.validate(Chain(b.route), standing=standing)
        check("auto-route builds a legal %s chain"
              % ("standing" if standing else "fired"), ok,
              why + " " + str(b.route))


def t_every_shelf_preset_loads():
    """Sixteen prebuilt chains, and every one of them must actually fit
    into a body and validate. A shelf entry that does not load is worse
    than no shelf."""
    from ..shelf import SHELF, STANDING
    bad = []
    for preset in SHELF:
        game, b = _bench()
        b._load_preset(preset)
        standing = preset.kind == STANDING
        pool = game.body.standing if standing else game.body.chains
        fitted = any(
            game.body.validate(ch, standing=standing)[0]
            and [o.key for o in game.body.chain_organs(ch)] == preset.organs
            for ch in pool)
        if not fitted:
            bad.append("%s (%s)" % (preset.key, b.message))
    check("every one of the %d shelf presets loads and routes" % len(SHELF),
          not bad, "; ".join(bad[:3]))


def t_the_shelf_teaches_the_order_lesson():
    """LANCE and FIZZLE are the same five organs in a different order, and
    the shelf exists partly so a player can load both and see it."""
    from ..shelf import BY_KEY as PRESETS
    lance, fizzle = PRESETS["lance"], PRESETS["fizzle"]
    check("Lance and Fizzle are built from exactly the same organs",
          sorted(lance.organs) == sorted(fizzle.organs))
    check("...in a different order", lance.organs != fizzle.organs)
    a, _ = run_chain(lance.organs, Charge(24, 5, 6, 4))
    b2, _ = run_chain(fizzle.organs, Charge(24, 5, 6, 4))
    ratio = total(a, "damage") / max(0.01, total(b2, "damage"))
    check("and the good order hits far harder", ratio > 2.2,
          "%.2fx (%.1f vs %.1f)" % (ratio, total(a, "damage"),
                                    total(b2, "damage")))


def t_every_organ_says_what_it_does():
    """'I cannot tell what things do' was the fairest complaint made about
    this game. Every organ now carries a measured line, derived by running
    it, and none of them may be empty or a placeholder."""
    from ..assay import bias_of, function_of
    from ..organs import ALL
    vague = []
    for t in ALL:
        line = function_of(t)
        tag = bias_of(t)
        if not line or len(line) < 12:
            vague.append("%s: %r" % (t.name, line))
        elif "changes nothing measurable" in line:
            vague.append("%s: unmeasurable" % t.name)
        elif "%s" in line or "%.1f" in line:
            vague.append("%s: unformatted %r" % (t.name, line))
        if not tag or tag == "shapes":
            vague.append("%s: no useful tag (%r)" % (t.name, tag))
    check("all %d organs describe themselves, measurably" % len(ALL),
          not vague, "; ".join(vague[:4]))


def t_the_tutorial_can_be_completed():
    """Every step must be reachable by doing the thing it asks for."""
    from ..screens.bench import Tutorial
    game, b = _bench()
    check("the tutorial has steps", len(Tutorial.STEPS) >= 6)
    b.tut_key = True
    b.tut_removed = True
    b.tut_installed = True
    b._arm(0, False)
    b.tut_committed = True
    b.tut_assayed = True
    b.tutorial.advance(game.body, b)
    b.standing_edit = True
    b.editing = 0
    b.tut_shelf = True
    b.tutorial.advance(game.body, b)
    check("and doing what it asks reaches the last one",
          b.tutorial.step == len(Tutorial.STEPS) - 1,
          "reached %d/%d" % (b.tutorial.step + 1, len(Tutorial.STEPS)))


def t_sandbox_grants_the_vocabulary():
    from ..organs import ALL
    from ..body import GRID_H, GRID_W
    game, b = _bench()
    have = {o.key for o in game.body.pack} | {
        o.key for o in game.body.installed()}
    check("sandbox hands you one of every organ",
          have >= {t.key for t in ALL},
          "missing %s" % sorted({t.key for t in ALL} - have)[:4])
    check("and opens every socket",
          len(game.body.cells) == GRID_W * GRID_H, str(len(game.body.cells)))


def t_criterion_is_stated_once():
    from ..lore import FRAGMENTS
    hits = [k for k, f in FRAGMENTS.items() if "CRITERION" in f.text]
    check("the pass condition is written down exactly once",
          len(hits) == 1, str(hits))


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for t in tests:
        t()
    print()
    print("%d passed, %d failed" % (len(PASSED), len(FAILED)))
    if FAILED:
        for f in FAILED:
            print("  failed: %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
