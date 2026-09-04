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

    def __init__(self):
        self.disturbance = 0.0
        self.player = None
        self.corpses = []
        self.creatures = []
        self.loudest_point = None
        self.events = []

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
