"""Does the ecosystem aggregate on its own? RIGS.md 13.4, 13.8 test 1.

This is a go/no-go and it was allowed to fail. RIGS.md 13.8 states the bar:

    Run 13.4 with no player for ten minutes and measure clustering. If a
    closed attraction loop does not form a travelling knot, everything above
    it is decoration.

It failed four times before it passed, and every failure was a different
wrong idea about the same system. They are worth more than the passing
version, so all four are recorded here and three of them are still tested
for, because each one is a state the tuning can silently fall back into.

FOUR MEASURED FAILURES
----------------------
**1. Total collapse.** Comfort used `exp(gain * min(6, v))`, by analogy with
the bubble and heat terms. Channels reach 10 where creatures pile up, so the
response saturated, and a saturated region is FLAT. Every species ended at a
radius of gyration under 2 px, all five sharing one centroid, and the grazers
could not tell which way was away from a hunter because `menace` was clamped
too. `(1 + v)**gain` is monotone forever and never flat. Test [1].

**2. Nothing to eat.** Fifty creatures feeding at 1 unit/s against a world fed
1.4 units/s strips every channel to about 0.001, where `(1 + v)**gain` is
1.001 and the ocean's own temperature structure decides everything.

**3. Nothing to smell.** Correcting (2) by making channels tighter than heat
gave a detection range of about 200 px -- beyond that the field is under
CHANNEL_FLOOR, the gradient is exactly zero, and a creature FREEZES, because
`step` only accelerates on a gradient and drag takes the rest. A decomposer
300 px from a fed patch never arrived. Two things were wrong: a smell in water
is carried rather than spread (`Medium._advect_channels`), and an animal with
nothing to go on searches rather than stopping (`WANDER`).

**4. Nowhere better to be.** With the cycle fed by snow falling at uniform
random over the whole ocean, nothing clustered in three separate tunings.
The reason is embarrassing in hindsight: **evenly distributed food cannot
produce an aggregation.** The base of a food web has to be a PLACE, which is
the correction RIGS.md 13.3 had already made to the player's economy, arriving
again from the ecosystem's side. `Seep` is that, test [8] is the control that
proves it is what does the work, and the consequence is the one the design has
been circling: the best generator site, the most attractive place to a
heat-hunter, and the base of the food web are one coordinate.

**5. A signal that pays for nothing.** Presence channels are written whether
or not a creature ate, which is right -- a shoal is findable because it is
there. But a hunter EATS `shoal` and turns it into `chum`, which is a
substance, so an unpaid signal was a doorway from nothing into the substance
chain. With no snow and no seeps at all, total channel mass rose from 60 units
to 722 in five minutes: a food web running on itself, which is RIGS.md 12.5's
perpetual motion machine with fins. It took two fixes -- `condition`, so a
starving creature stops advertising, and holding every signal rate below the
feed rate of whatever emits it. Test [2] is the one that caught it.

AND ONE THING THE OCEAN DID BY ITSELF
--------------------------------------
Test [8] cannot be run as written, because **uniform food is not achievable in
water that moves.** The same mass added to every cell is carried by the tide
and piled up wherever the flow converges, so a perfectly even snowfall is a
patchy field two minutes later and the decomposers gather on the patches at
twice chance. Convergence zones concentrate food -- which is why a front is
worth something in a real ocean -- and it arrived here out of a flux term
written for an entirely different reason.

AND ONE MEASUREMENT MISTAKE, WHICH COST A WHOLE TUNING PASS
------------------------------------------------------------
Clustering was first measured as a radius of gyration, which is the spread
about a single centre. With food at three seeps, perfect aggregation still
reads as a large number, so a working ecosystem was scored as a failure and
"fixed" twice. Everything here is measured as a mean nearest-neighbour
distance against a random-placement control instead, which does not assume
there is only one place worth being.

    python -m sigilwave.rig.selftest_cycle
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np

from ..medium.field import CHANNEL_FLOOR, Medium
from . import creatures

W, H = 900, 700
DT = 1.0 / 30.0

# The pyramid that actually ships, rather than a second one invented here.
# The suite used to carry its own counts and they drifted out of step with
# `creatures.PYRAMID` -- so this was measuring a configuration nobody runs,
# which is the least useful kind of green.
COUNTS = dict(creatures.PYRAMID)
SEEPS = ((190.0, 540.0), (700.0, 400.0), (470.0, 200.0))

_passed = 0
_failed = []

# [7] measures these and [8] compares against them.
_with_seeps = {}


def check(name, condition, detail=""):
    global _passed
    if condition:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed.append((name, detail))
        print(f"  FAIL {name}   {detail}")


def _report(name, value, unit=""):
    print(f"       {name}: {value}{unit}")


# --- measurement --------------------------------------------------------------


def nnd(points):
    """Mean nearest-neighbour distance. Falls when a group clumps, and unlike
    a radius of gyration it does not assume there is only one place to be."""
    if len(points) < 2:
        return 0.0
    pts = np.asarray(points, dtype=float)
    d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    np.fill_diagonal(d, np.inf)
    return float(d.min(axis=1).mean())


def spread_x(points):
    """Horizontal spread only.

    The ocean structures creatures vertically all by itself -- every species
    has a temperature band and the column is stratified, so they settle at a
    preferred depth whether or not there is any food anywhere. That is correct
    and it is not aggregation. Measuring across the current instead isolates
    the part that food is responsible for, which is what test [8] is asking
    about."""
    if len(points) < 2:
        return 0.0
    return float(np.std([p[0] for p in points]))


def to_nearest(points, sites):
    if not len(sites):
        return 0.0
    return float(np.mean([min(math.dist(p, s) for s in sites) for p in points]))


def random_control(n, sites, seed=11, trials=160):
    """The same two numbers for creatures scattered at random. Nothing below
    means anything except as a ratio against this."""
    rng = np.random.default_rng(seed)
    a, b = [], []
    for _ in range(trials):
        pts = [(float(rng.uniform(40, W - 40)), float(rng.uniform(40, H - 40)))
               for _ in range(n)]
        a.append(nnd(pts))
        b.append(to_nearest(pts, sites))
    return float(np.mean(a)), float(np.mean(b))


def world(seeps=SEEPS, seed=3, counts=None, settle=200):
    med = Medium(W, H)
    creatures.install_channels(med)
    for _ in range(settle):
        med.step(1 / 15.0)
    rng = np.random.default_rng(seed)
    packs = {}
    for kind in creatures.CYCLE_ORDER:
        n = (counts or COUNTS)[kind]
        packs[kind] = [
            creatures.make_cycle(kind, (float(rng.uniform(40, W - 40)),
                                        float(rng.uniform(40, H - 40))))
            for _ in range(n)
        ]
    return med, packs, [creatures.Seep(p) for p in seeps], rng


def run(med, packs, seeps, rng, seconds, bodies=()):
    for _ in range(int(seconds / DT)):
        creatures.snowfall(med, DT, rng)
        for s in seeps:
            s.step(DT, med)
        for b in bodies:
            b.step(DT, med)
        for kind in creatures.CYCLE_ORDER:
            for c in packs[kind]:
                c.step(DT, med)
        med.step(DT)
    return med, packs


def positions(pack):
    return [c.pos for c in pack]


# --- the structure ------------------------------------------------------------


def test_the_loop_closes():
    """A chain has an end. A cycle does not, and that is the whole design."""
    print("\n[1] the food web is a closed loop, not a chain")
    produced = {"chum"}          # carrion and hunters both write it
    for kind in creatures.CYCLE_ORDER:
        c = creatures.CYCLE_SPECIES[kind]()
        for ch, _ in c.emits:
            produced.add(ch)
        for ch, _ in c.signals:
            produced.add(ch)

    orphans = []
    for kind in creatures.CYCLE_ORDER:
        c = creatures.CYCLE_SPECIES[kind]()
        if c.reads and c.reads not in produced:
            orphans.append((kind, c.reads))
        if c.flees and c.flees not in produced:
            orphans.append((kind, c.flees))
    check("every creature reads something something else makes", not orphans,
          str(orphans))

    # Walk it: start at the scavenger and follow reads -> emitter, and the
    # walk has to come back rather than run out.
    emitter = {}
    for kind in creatures.CYCLE_ORDER:
        c = creatures.CYCLE_SPECIES[kind]()
        for ch, _ in tuple(c.emits) + tuple(c.signals):
            emitter.setdefault(ch, kind)
    seen, node, closed = [], "scavenger", False
    for _ in range(len(creatures.CYCLE_ORDER) + 2):
        if node in seen:
            closed = True
            break
        seen.append(node)
        reads = creatures.CYCLE_SPECIES[node]().reads
        node = emitter.get(reads)
        if node is None:
            break
    check("following who-eats-whom returns to where it started", closed,
          f"walk was {' -> '.join(seen)}")
    _report("the web", "\n" + creatures.cycle_table())

    # Nothing may read what it emits: that is a positive feedback with no
    # opposing term, and a creature that can smell itself stops moving.
    selfish = []
    for kind in creatures.CYCLE_ORDER:
        c = creatures.CYCLE_SPECIES[kind]()
        mine = {ch for ch, _ in tuple(c.emits) + tuple(c.signals)}
        if c.reads in mine:
            selfish.append(kind)
    check("nothing is attracted to its own trail", not selfish, str(selfish))


def test_the_cycle_cannot_run_on_itself():
    """RIGS.md 12.5, applied to the food web instead of to a rig."""
    print("\n[2] the loop loses, so it needs snow and death")
    carried = 1.0
    for kind in creatures.CYCLE_ORDER:
        c = creatures.CYCLE_SPECIES[kind]()
        if c.emits:
            carried *= sum(y for _, y in c.emits)
    check("substance is lost around one circuit", carried < 1.0,
          f"carries {carried:.4f}")

    # The other half of "it cannot run on itself", and the one that was
    # actually leaking. Holding condition at 1.0 costs condition_decay /
    # CONDITION_GAIN units of food a second, so a creature emitting a signal
    # at rate S is an amplifier whenever S * GAIN / decay >= 1. The grazer was
    # at 1.05 and nothing caught it, because every run measured had it
    # starving rather than emitting. `menace` is exempt: nothing consumes it,
    # so it cannot reach the substance chain at all.
    amps = []
    for kind in creatures.CYCLE_ORDER:
        c = creatures.CYCLE_SPECIES[kind]()
        for channel, rate in c.signals:
            if channel == "menace":
                continue
            amp = rate * creatures.CONDITION_GAIN / c.condition_decay
            amps.append((kind, channel, amp))
            _report(f"{kind} -> {channel}", f"x{amp:.2f} of the food that pays for it")
    check("no presence signal emits more than its food pays for",
          all(a < 1.0 for _, _, a in amps),
          str([(k, ch, round(a, 2)) for k, ch, a in amps if a >= 1.0]))
    _report("one circuit carries", f"{carried * 100:.1f}%")

    # And measured, not just asserted: with nothing feeding it, it runs down.
    med, packs, seeps, rng = world(seeps=())
    med.deposit("nutrient", 450.0, 350.0, 60.0)
    before = sum(float(med.channels[c].sum()) for c in creatures.CHANNELS)

    def no_snow(*_a, **_k):
        return 0
    real_snow, creatures.snowfall = creatures.snowfall, no_snow
    try:
        run(med, packs, (), rng, 300.0)
    finally:
        creatures.snowfall = real_snow
    after = sum(float(med.channels[c].sum()) for c in creatures.CHANNELS)
    check("with no input at all, the ecosystem runs down", after < before * 0.5,
          f"{before:.1f} -> {after:.1f}")
    _report("after 300 s with no snow and no seeps", f"{after:.2f} units left")


# --- the medium ---------------------------------------------------------------


def test_advection_moves_without_creating():
    print("\n[3] the current carries a channel without inventing any of it")
    med = Medium(W, H)
    creatures.install_channels(med)
    for _ in range(120):
        med.step(1 / 15.0)
    med.deposit("chum", 300.0, 300.0, 50.0)
    start = float(med.channels["chum"].sum())

    # Advection alone: no decay, no diffusion, no eaters.
    total = start
    worst = 0.0
    for _ in range(600):
        med._advect_channels(1 / 15.0)
        now = float(med.channels["chum"].sum())
        worst = max(worst, abs(now - total) / max(total, 1e-12))
        total = now
    check("advection conserves the channel", abs(total - start) < start * 1e-9,
          f"{start:.6f} -> {total:.6f}")
    _report("worst single-step drift", f"{worst:.3e}")


def test_channels_do_not_leak_through_rock():
    print("\n[4] a smell does not seep through stone")
    med = Medium(W, H)
    creatures.install_channels(med)
    med.carve(400.0, 0.0, 96.0, float(H))       # a wall, floor to ceiling
    for _ in range(120):
        med.step(1 / 15.0)
    for _ in range(400):
        med.deposit("chum", 200.0, 350.0, 0.5)
        med.step(1 / 15.0)
    left = float(med.channels["chum"][:, : int(400 / med.cell_size)].sum())
    right = float(med.channels["chum"][:, int(496 / med.cell_size):].sum())
    check("nothing crosses a solid wall", right <= left * 1e-6,
          f"left {left:.3f}, right {right:.6f}")
    inside = float(med.channels["chum"][med.solid].sum())
    check("no channel sits inside rock", inside == 0.0, f"{inside:.6f}")


def test_eating_flattens_the_peak():
    """The mechanism that stops the aggregation collapsing to one cell."""
    print("\n[5] eating takes the peak down")
    med = Medium(W, H)
    creatures.install_channels(med)
    med.deposit("bloom", 450.0, 350.0, 8.0)
    peak_before = float(med.channels["bloom"].max())
    got = med.consume("bloom", 450.0, 350.0, 3.0)
    peak_after = float(med.channels["bloom"].max())
    check("consume returns what it took", abs(got - 3.0) < 1e-9, f"{got:.6f}")
    check("and the peak actually fell", peak_after < peak_before - 2.9,
          f"{peak_before:.3f} -> {peak_after:.3f}")
    over = med.consume("bloom", 450.0, 350.0, 1e6)
    check("nothing can eat more than is there", over <= peak_after + 1e-9,
          f"asked 1e6, got {over:.4f}")
    check("and a channel never goes negative",
          float(med.channels["bloom"].min()) >= 0.0)


# --- the behaviour ------------------------------------------------------------


def test_everything_can_find_its_own_food():
    """Failure (3): a creature 300 px from a patch used to freeze."""
    print("\n[6] every species reaches a patch 300 px away")
    pairs = (("scavenger", "chum"), ("decomposer", "nutrient"),
             ("drifter", "bloom"), ("grazer", "swarm"), ("hunter", "shoal"))
    patch = (600.0, 350.0)
    worst = 0.0
    worst_kind = ""
    for kind, channel in pairs:
        med = Medium(W, H)
        creatures.install_channels(med)
        for _ in range(120):
            med.step(1 / 15.0)
        c = creatures.make_cycle(kind, (patch[0] - 300.0, patch[1]))
        c.feed_rate = 0.0                    # measure the climb, not the meal
        for i in range(int(90.0 / DT)):
            med.deposit(channel, patch[0], patch[1], 10.0 * DT)
            c.step(DT, med, ())
            if i % 2 == 0:
                med.step(2 * DT)
        d = math.dist(c.pos, patch)
        if d > worst:
            worst, worst_kind = d, kind
        _report(kind, f"300 px -> {d:.0f} px")
    check("nothing is left stranded out of range", worst < 120.0,
          f"worst {worst:.0f} px by the {worst_kind}")


def test_it_aggregates():
    """The go/no-go. RIGS.md 13.8 test 1."""
    print("\n[7] the cycle gathers itself, with no player in the water")
    med, packs, seeps, rng = world()
    sites = [s.pos for s in seeps]
    run(med, packs, seeps, rng, 420.0)

    # Two different claims, measured two different ways, because one metric
    # cannot carry both.
    #
    # Nearest-neighbour distance is only meaningful with enough animals to have
    # neighbours -- with four hunters in a 900x700 ocean it is dominated by
    # geometry, not by behaviour, and reading it as "the hunters failed to
    # aggregate" was a mistake this suite made once. So NND is checked where
    # n >= 6, and everything is checked for being drawn to where food is made.
    clump = {}
    site = {}
    for kind in creatures.CYCLE_ORDER:
        pts = positions(packs[kind])
        base_nnd, base_site = random_control(len(pts), sites)
        clump[kind] = base_nnd / max(nnd(pts), 1e-9)
        site[kind] = base_site / max(to_nearest(pts, sites), 1e-9)
        _with_seeps[kind] = clump[kind]
        _report(kind, f"n={len(pts):<3} neighbour x{clump[kind]:4.2f}   "
                      f"to a seep x{site[kind]:4.2f}")

    crowded = [k for k in creatures.CYCLE_ORDER if COUNTS[k] >= 6]
    worst = min(clump[k] for k in crowded)
    check("every species with neighbours ends up clumped rather than scattered",
          worst > 1.15,
          f"worst x{worst:.2f} ({min(crowded, key=lambda k: clump[k])})")

    # The base of the web has to sit on the seeps: that is the whole claim of
    # [8] and of RIGS.md 13.3.
    #
    # Scavengers are NOT in this group, and putting them in it was a mistake.
    # They read `chum`, which comes from bodies, not from seeps -- so once
    # creatures started dying, the scavengers correctly stopped caring where
    # the seeps are and started following the dead around. Test [9] is where
    # their claim belongs.
    base = ("decomposer", "drifter")
    worst_base = min(site[k] for k in base)
    check("the bottom of the food web sits where the food is made",
          worst_base > 1.4,
          f"worst x{worst_base:.2f} ({min(base, key=lambda k: site[k])})")

    # And the grazers must NOT be on the seeps, because the hunters are. This
    # is the one that looks like a failure and is the design working: prey
    # gather near the food and away from the things eating them, which is the
    # long-range/short-range split of 13.4 showing up at ecosystem scale.
    check("the grazers keep off the seeps the hunters are sitting on",
          site["grazer"] < site["hunter"],
          f"grazer x{site['grazer']:.2f} vs hunter x{site['hunter']:.2f}")

    at_wall = 0
    for kind in creatures.CYCLE_ORDER:
        for x, y in positions(packs[kind]):
            if x < 24 or x > W - 24 or y < 24 or y > H - 24:
                at_wall += 1
    total = sum(len(packs[k]) for k in creatures.CYCLE_ORDER)
    check("and nothing is pinned against the edge of the world",
          at_wall <= total * 0.2, f"{at_wall}/{total} at a wall")

    # Reported, not asserted, and the reason is worth stating: there are three
    # hunters in the whole ocean, so where their centroid lands is mostly
    # luck. Asserting on it produced a check that passed or failed on the
    # seed. The claim that survives measurement is the one above -- the BOTTOM
    # of the web sits on the seeps -- plus the standoff in [10], which is
    # measured on the grazers where there are enough of them to mean anything.
    top = to_nearest(positions(packs["hunter"]), sites)
    _, base_site = random_control(len(packs["hunter"]), sites)
    _report("hunters to a seep", f"{top:.0f} px vs {base_site:.0f} at random "
                                 f"(n={len(packs['hunter'])}, reported not asserted)")


def test_uniform_food_produces_no_aggregation():
    """The negative control for failure (4), and the reason `Seep` exists.

    If this one ever starts passing with the seeps removed, the clustering in
    [7] is coming from something other than the food being somewhere.
    """
    print("\n[8] with food everywhere, nothing gathers -- the control")
    # The control has to be GENUINELY uniform. The first version turned the
    # snow up instead, and snow falls as discrete specks -- so the "uniform"
    # control was still a rain of point sources, creatures aggregated on them,
    # and it scored x2.30. That is a true result about specks and says nothing
    # at all about uniformity. This one adds the same mass to every cell.
    # Nothing may die during the control either, and that is a correction
    # this test needed once creatures started starving to death. A carcass is
    # a concentrated food source, so a world with no seeps in it still grows
    # its own hotspots out of its own dead -- the A/B read x0.88, meaning the
    # seeps looked irrelevant, when what had actually happened is that the
    # ecosystem had started making its own. Both sources have to be off for
    # "evenly distributed food gathers nothing" to be the thing being asked.
    real_starve = creatures.STARVE_SECONDS
    creatures.STARVE_SECONDS = 1e9
    med, packs, _seeps, rng = world(seeps=())
    per_cell = 0.9 / (med.nx * med.ny)

    def flat(*_a, **_k):
        med.channels["nutrient"] += per_cell
        return 0

    real = creatures.snowfall
    creatures.snowfall = flat
    try:
        run(med, packs, (), rng, 420.0)
    finally:
        creatures.snowfall = real
        creatures.STARVE_SECONDS = real_starve

    # This is an A/B against [7] rather than an absolute bar, and that is a
    # correction the measurement forced.
    #
    # "Uniform food" turns out not to be achievable in an ocean that moves.
    # The same mass added to every cell does not stay that way: the tide
    # carries it (`_advect_channels`) and piles it up wherever the flow
    # converges, so a perfectly even snowfall becomes a patchy field within a
    # couple of minutes and the decomposers gather on the patches at 2.0x
    # chance. That is not the test failing, it is a real thing about the
    # world -- convergence zones concentrate food, which is why fronts and
    # eddies are worth anything in a real ocean, and it arrives here for free
    # out of a flux term written for a different reason.
    #
    # So the claim this control can honestly make is comparative: seeps have
    # to account for most of the clustering, not all of it.
    weaker = {}
    for kind in creatures.CYCLE_ORDER:
        if COUNTS[kind] < 6:
            continue
        pts = positions(packs[kind])
        base_nnd, _ = random_control(len(pts), [(0.0, 0.0)])
        got = base_nnd / max(nnd(pts), 1e-9)
        weaker[kind] = got
        _report(kind, f"clumping x{got:4.2f} without seeps, "
                      f"x{_with_seeps.get(kind, float('nan')):4.2f} with them")
    ratio = (sum(_with_seeps[k] for k in weaker)
             / max(sum(weaker.values()), 1e-9))
    check("taking the seeps away takes most of the aggregation with them",
          ratio > 1.5, f"seeps account for x{ratio:.2f}")
    _report("aggregation attributable to the seeps", f"x{ratio:.2f}")


def test_a_carcass_seeds_the_cycle():
    """RIGS.md 13.4: death is a resource, and it propagates."""
    print("\n[9] a body pulls the cycle to it")
    med, packs, seeps, rng = world()
    far = (W - 120.0, 120.0)
    for c in packs["scavenger"]:
        c.pos = (120.0, H - 120.0)          # the opposite corner
    body = creatures.Carcass(pos=far)
    run(med, packs, seeps, rng, 240.0, bodies=(body,))
    d = to_nearest(positions(packs["scavenger"]), [body.pos])
    check("the scavengers cross the map to a carcass", d < 260.0,
          f"mean {d:.0f} px from the body")
    _report("carcass", f"at {body.pos[0]:.0f},{body.pos[1]:.0f}; "
                       f"{body.yield_left:.0f} of {creatures.CARCASS_YIELD:.0f} left")
    check("and a body sinks while it does it", body.pos[1] > far[1] + 20.0,
          f"y {far[1]:.0f} -> {body.pos[1]:.0f}")


def test_a_hunter_thins_the_shoal():
    """Long-range attraction with short-range repulsion, measured."""
    print("\n[10] a hunter makes a hole in a shoal without any code for it")
    med = Medium(W, H)
    creatures.install_channels(med)
    for _ in range(120):
        med.step(1 / 15.0)
    for _ in range(300):
        med.deposit("swarm", 450.0, 350.0, 0.4)
        med.step(1 / 15.0)

    def settle(with_hunter):
        pack = [creatures.make_cycle("grazer", (450.0 + 70 * math.cos(i), 350.0 + 70 * math.sin(i)))
                for i in range(12)]
        h = creatures.make_cycle("hunter", (450.0, 350.0)) if with_hunter else None
        for i in range(int(40.0 / DT)):
            med.deposit("swarm", 450.0, 350.0, 0.4 * DT)
            if h is not None:
                h.pos = (450.0, 350.0)       # pinned: measure the grazers
                h.step(DT, med, ())
            for g in pack:
                g.step(DT, med, ())
            if i % 2 == 0:
                med.step(2 * DT)
        return to_nearest([g.pos for g in pack], [(450.0, 350.0)])

    without = settle(False)
    with_one = settle(True)
    check("grazers keep their distance when a hunter is in the middle",
          with_one > without, f"{without:.0f} px alone -> {with_one:.0f} px with a hunter")
    _report("standoff", f"{with_one - without:+.0f} px")


def test_the_tide_carries_a_smell():
    """RIGS.md 13.6: which way you approach a thing decides what you can smell."""
    print("\n[11] a plume goes downstream, not outward")
    med = Medium(W, H)
    creatures.install_channels(med)
    for _ in range(120):
        med.step(1 / 15.0)
    sx, sy = 450.0, 200.0
    for _ in range(500):
        med.deposit("chum", sx, sy, 0.6)
        med.step(1 / 15.0)
    f = med.channels["chum"]
    row = med._cell(sx, sy)[0]
    col = med._cell(sx, sy)[1]
    left = float(f[row, :col].sum())
    right = float(f[row, col + 1:].sum())
    lopsided = max(left, right) / max(min(left, right), 1e-12)
    check("the plume is not symmetric about its source", lopsided > 1.2,
          f"upstream {min(left, right):.3f} vs downstream {max(left, right):.3f}")
    _report("asymmetry", f"x{lopsided:.2f} along the row")
    check("and the channel reaches further than diffusion alone would",
          float((f > CHANNEL_FLOOR).sum()) > 40.0,
          f"{int((f > CHANNEL_FLOOR).sum())} cells carry it")


def main():
    print("=" * 72)
    print("RIGS -- the cycle gathers itself")
    print("=" * 72)
    test_the_loop_closes()
    test_the_cycle_cannot_run_on_itself()
    test_advection_moves_without_creating()
    test_channels_do_not_leak_through_rock()
    test_eating_flattens_the_peak()
    test_everything_can_find_its_own_food()
    test_it_aggregates()
    test_uniform_food_produces_no_aggregation()
    test_a_carcass_seeds_the_cycle()
    test_a_hunter_thins_the_shoal()
    test_the_tide_carries_a_smell()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
