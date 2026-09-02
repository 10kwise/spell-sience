"""Why it did not work, in sentences. SUBMERGED.md 3.2 and 9.5.

The player's complaint, verbatim: *"I tried making random things, they didn't
work - which is good - but you can't figure it out."*

Both halves of that are the design. Random drawings failing is 2.2 working as
intended -- a system where failure is impossible is one where understanding is
worthless -- and 3.2's promise is that *"why did that not work" is answerable
by looking*. A failure nobody can diagnose is not a lesson, it is noise, and
until this module existed the bench answered the first half and nothing
answered the second.

So: no new physics, no new numbers, no tuning. Every sentence in here is a
failure mode this project has already **measured**, in `selftest_bench`,
`selftest_cavitation` or `selftest_mouths`, restated as something a person
would say. The measurements are pinned as constants at the top with the file
that took them, so a note that goes stale goes stale loudly.


WHAT A NOTE IS ALLOWED TO SAY
-----------------------------
9.3: *no property readable only from a number.* A readout that means nothing
until you have learned what a good value is has taught nothing. So a note is
one plain sentence naming the thing and what to do about it, and it carries a
number only where the player can act on the number:

    good  "your mouth is 160 px wide and needs about 640 to aim this note"
    bad   "coupling coefficient 0.893 exceeds loaded-Q threshold"

Severity is the whole vocabulary and it is four words. **dead** is nothing
will happen at all. **wasteful** works but bleeds. **fine** emits, but not the
way it was meant to. **good** exists because a player who is never told they
got it right cannot tell a lucky drawing from an understood one, and 2.2 is
only paid off if success is as legible as failure.


READ WHILE DRAWING, NOT AFTER FIRING
------------------------------------
Every note here is computed from the *drawing* -- the parsed graph, the
couplers the compiler will build, the apertures the mouths will merge into --
and none of them needs the machine to have been fired. That is deliberate.
10's bench exists so a machine can be understood before it is run, and advice
that only arrives after a shot arrives after the player has stopped asking.
`network` is therefore accepted and unused: a caller has one, and any future
note that genuinely needs live state belongs behind that parameter rather
than behind a second call. `emitter` is used for exactly one thing, the note
the machine is *actually* radiating, which beats guessing it from the loops.


WHAT IS DELIBERATELY NOT HERE
-----------------------------
Two diagnostics were dropped rather than guessed at, because a wrong
diagnosis teaches a wrong rule and that is the failure three rewrites have
been spent escaping.

**"This gate will fire."** Whether a gap trips depends on the drive reaching
the Blake threshold at that point in the wires, and nothing short of running
the simulation knows that -- the same rig fires 178 times at the surface and
not at all at 700 m. So the gap notes describe *placement*, which is
geometry and certain, and never promise a firing.

**"This aperture is aimed at the thing you want."** Focus distance is
computable and is reported; whether the focus lands on a target is a fact
about the world, and the bench is still water with nothing in it.

And one note is narrower than the thing it is reading. `Assembly.ignored()`
reports parts that compiled to nothing, which is two different facts wearing
one name: a part genuinely too short to hold a signal, and a part whose edges
were attributed to a neighbour. The second happens whenever two strokes run
*alongside* each other rather than crossing at a point -- a fan of branches
leaving one fork is the ordinary case -- and it is a bookkeeping artefact, not
a death: the branch is in the graph, radiating, with a mouth on the end. So
the note fires only where the part's own length is under the parser's minimum
edge, which is the half of `ignored()` that is certain. The other half stays
silent rather than telling a player their working branch is dead.
"""

import heapq
import math
from dataclasses import dataclass

import pygame

from ..sim.couplers import find_coupler_sites
from .mouths import (BENCH_M_PER_PX, C_WATER, FREQ_MIN, MERGE_DIST,
                     diffraction_curvature, merge_mouths)
from .parts import GAP_MAX, JOIN_EPS, MIN_RUN_LENGTH, rung_for_length

V = pygame.Vector2

# --------------------------------------------------------------- measured

# selftest_cavitation, "LOOP + GAP: the timer 6 struck out". The same drive
# into the same loop, joined to its feed and gapped 10 px off it.
JOINED_LOOP_PEAK = 0.071
GAPPED_LOOP_PEAK = 1.311

# selftest_bench, "GAP: it is never mistakable for a join". Fraction of the
# energy on the wire that arrives past the gap; a join delivers 0.893, which
# is the number the whole band has to stay clear of.
GAP_CROSSING = ((JOIN_EPS, 0.159), (12.0, 0.057), (20.0, 0.0106),
                (25.0, 0.0023), (29.5, 0.00016))

# Where a gap stops being a coupling and starts being a wall. Not a taste
# call: it is the row of the table above where crossing falls to a hundredth,
# and it is still 70x better than the widest placeable gap, so there is real
# advice on either side of it.
WIDE_GAP = 20.0

# Measured here: energy out of the far mouth of a spine with n three-way
# junctions on it, lossless ink, so the only loss is the sharing out that
# selftest_bench measured at 0.4444 down each way on and 0.1111 straight
# back. Slightly above 0.4444**n, because the back-reflections eventually
# find their way out too - which is why this is a table and not an exponent.
FORK_SURVIVAL = ((1, 0.42), (2, 0.20), (3, 0.11), (4, 0.06))
FORK_CHAIN = 3          # three in a row is where a tenth is left

# Measured here: energy radiated from the far end of one straight run of this
# length, default ink. Damping is per sample, so length is the whole story.
RUN_SURVIVAL = ((100.0, 0.945), (200.0, 0.887), (400.0, 0.765),
                (800.0, 0.526), (1600.0, 0.199), (3200.0, 0.020))
LONG_RUN = 800.0        # where half of it is gone

# 7.4a: below about two wavelengths the diffraction term swamps anything
# drawn and the mouth is a point source however carefully it was cupped.
AIM_WAVELENGTHS = 2.0

# The bench tank is 1200 x 720 (app.py). A focus past the far wall is a focus
# the player cannot use or even see happen.
TANK_REACH = 1200.0

# Two mouths this much past MERGE_DIST were probably meant to be one aperture
# and missed; further apart than this and they are two mouths on purpose.
NEARLY_MERGED = MERGE_DIST * 1.5

_SEVERITY_ORDER = {"dead": 0, "wasteful": 1, "fine": 2, "good": 3}


@dataclass
class Note:
    """One thing to say, and where to point while saying it."""

    severity: str    # "dead" | "wasteful" | "fine" | "good"
    text: str        # one plain sentence, no jargon
    where: object    # world position to point at, or None


def diagnose(assembly, network=None, emitter=None, note_hz=None) -> list:
    """Everything worth saying about this drawing, most important first.

    Ordering is severity and then, inside a severity, the order the notes are
    appended below -- which is not arbitrary. The loop wired straight to its
    feed goes first among the wasteful ones because it is the measured
    difference between a machine that charges and one that does not, and
    because it is the note that catches the naive move: connecting it
    properly is the thing that fails.
    """
    graph = assembly.to_graph()
    parts = {p.part_id: p for p in assembly.parts}

    if not parts:
        return [Note("dead",
                     "there is nothing drawn yet - place a run, leave one end"
                     " free, and whatever you fire in at the other end will"
                     " come back out of it", None)]

    dead = [Note("dead",
                 f"this part is too short to be anything - nothing under about"
                 f" {MIN_RUN_LENGTH:.0f} px across can hold a signal, so the"
                 f" drawing throws it away",
                 _part_centre(parts[pid]))
            for pid in assembly.ignored()
            if pid in parts and parts[pid].length < MIN_RUN_LENGTH]

    if not graph.edges:
        return dead

    adjacency = _adjacency(graph)
    sites = find_coupler_sites(graph, assembly.dx, snap_eps=JOIN_EPS, g_max=GAP_MAX)
    gaps = _gap_positions(assembly, sites)
    rings = _rings(graph, adjacency)
    terminals = [nid for nid, node in graph.nodes.items() if node.is_terminal]

    if not terminals:
        dead.append(Note("dead",
                         "nothing you have drawn has a free end, so the energy"
                         " just goes round and round inside it and the water"
                         " never hears a thing - open one end and it can get"
                         " out",
                         _centroid(graph, range(len(graph.edges)))))

    dead += _orphan_notes(graph, adjacency, sites)

    bleeding = _loop_feed_notes(graph, adjacency, rings, terminals)
    bleeding += _fork_notes(graph, adjacency, terminals)
    bleeding += _gap_width_notes(gaps)
    bleeding += _length_notes(graph, adjacency, terminals)

    wavelength, source = _wavelength(assembly, emitter, note_hz, rings)
    groups = list(emitter.groups) if emitter is not None else merge_mouths(assembly)

    shape = _aperture_notes(groups, wavelength, source)
    shape += _near_merge_notes(groups)

    ok = _good_loop_notes(graph, adjacency, rings, terminals, sites, gaps)
    ok += _good_aperture_notes(groups, wavelength, source)
    if terminals:
        ok.append(Note("good",
                       "there is a free end here for the energy to leave by,"
                       " so this machine will actually put something into the"
                       " water",
                       V(graph.nodes[terminals[0]].pos)))

    notes = dead + bleeding + shape + ok
    notes.sort(key=lambda n: _SEVERITY_ORDER.get(n.severity, 9))
    return notes


# ------------------------------------------------------------------- dead


def _orphan_notes(graph, adjacency, sites) -> list:
    """A piece nothing reaches. Components joined *or* gapped to one another
    are one machine -- a gap is a way through, which is the whole of 4.1 --
    so the grouping unions across couplers before it calls anything orphaned.
    The biggest group by total wire is the machine; the rest are pieces the
    player thinks are part of it and are not."""
    comps = _components(graph, adjacency)
    if len(comps) < 2:
        return []

    parent = list(range(len(comps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, comp in enumerate(comps):
        for e in comp:
            owner[e] = i
    for site in sites:
        a, b = owner.get(site.edge_a), owner.get(site.edge_b)
        if a is not None and b is not None:
            parent[find(a)] = find(b)

    groups = {}
    for i, comp in enumerate(comps):
        groups.setdefault(find(i), set()).update(comp)
    if len(groups) < 2:
        return []

    ranked = sorted(groups.values(),
                    key=lambda es: (-sum(graph.edges[e].length for e in es), -len(es)))
    return [Note("dead",
                 "this piece is not touching anything else you drew and is not"
                 " close enough to spark across to it, so nothing you fire into"
                 " the rest of the machine will ever reach it",
                 _centroid(graph, es))
            for es in ranked[1:]]


# -------------------------------------------------------------- wasteful


def _loop_feed_notes(graph, adjacency, rings, terminals) -> list:
    """The highest-value note in the file, and the one that catches the move
    every player makes first: connecting the feed *properly*.

    Measured (selftest_cavitation): the same drive into the same loop peaks at
    0.071 joined to its feed and 1.311 gapped 10 px off it, and only the
    gapped one ever reaches the threshold that tears the water open. A run
    joined onto a ring and left free at its other end is an open port -- the
    energy leaves the way it came, and the ring is a wire with a bend in it.
    """
    out = []
    for ring in rings:
        feed = _open_branch(graph, adjacency, ring, terminals)
        if feed is None:
            continue
        out.append(Note("wasteful",
                        f"this loop is wired straight to its feed, so the energy"
                        f" leaves the way it came and the loop never charges -"
                        f" leave a small gap instead and the same drive builds"
                        f" about {GAPPED_LOOP_PEAK / JOINED_LOOP_PEAK:.0f} times"
                        f" higher",
                        V(graph.nodes[feed].pos)))
    return out


def _fork_notes(graph, adjacency, terminals) -> list:
    """Every split shares out and throws a little back, so depth is the enemy.
    Measured at a three-way junction: 0.4444 of the energy down each way on
    and 0.1111 straight back. Counted along the worst path a pulse can be
    asked to take, from one free end to another."""
    count, where = _deepest_forks(graph, adjacency, terminals)
    if count < FORK_CHAIN:
        return []
    return [Note("wasteful",
                 f"energy has to get past {count} splits to cross this machine,"
                 f" and each one keeps under half of what arrives and bounces a"
                 f" little back, so only about {_percent(_lookup(FORK_SURVIVAL, count))}"
                 f" of what you put in comes out the far end - fewer splits, or"
                 f" feed the branch that matters on its own",
                 where)]


def _gap_width_notes(gaps) -> list:
    """A gap is a clean attenuator controlled by distance (4.0), with 5500:1
    of range across the placeable band. That is a knob, and a knob left at the
    wrong end is worth a sentence: the difference between a 6 px gap and a
    20 px one is fourteen times the energy, for a drawing change of a
    centimetre."""
    out = []
    for pos_a, pos_b, gap in gaps:
        if gap < WIDE_GAP:
            continue
        crossing = _lookup(GAP_CROSSING, gap)
        best = GAP_CROSSING[0][1]
        out.append(Note("wasteful",
                        f"this gap is {gap:.0f} px across and only about"
                        f" {_percent(crossing)} of what reaches it gets over -"
                        f" close it to about {JOIN_EPS:.0f} px and roughly"
                        f" {best / max(crossing, 1e-9):.0f} times more will cross",
                        _midpoint(pos_a, pos_b)))
    return out


def _length_notes(graph, adjacency, terminals) -> list:
    """Damping is per sample, so length is not free and the cost is not
    subtle. Measured from end to end of one straight run: 95% of the energy
    survives 100 px and 2% survives 3200."""
    length, where = _longest_way(graph, adjacency, terminals)
    if length < LONG_RUN:
        return []
    return [Note("wasteful",
                 f"energy has about {length:.0f} px of drawing to cross to get"
                 f" here and only about {_percent(_lookup(RUN_SURVIVAL, length))}"
                 f" of it survives the trip, because the drawing dims it the"
                 f" whole way along - shorter is brighter",
                 where)]


# ------------------------------------------------------------------- shape


def _aperture_notes(groups, wavelength, source) -> list:
    """7.4a, in the player's own units.

    *An aperture narrower than its own wavelength cannot be aimed at all* --
    below about two wavelengths the diffraction term swamps whatever was
    drawn. And a loop of circumference L rings at c/L, so its wavelength in
    bench pixels is exactly L, which turns the rule into a sentence about the
    drawing: **the mouth must be about twice as wide as the loop that made
    it.** A lone mouth is left alone; a spitter is a tool, not a mistake, and
    9.5 is about failure being visible, not about everything being a failure.
    """
    if wavelength is None:
        return []
    needed = AIM_WAVELENGTHS * wavelength

    out = []
    for g in groups:
        if len(g.node_ids) < 2 or g.span >= needed:
            continue
        out.append(Note("fine",
                        f"your mouth is {g.span:.0f} px wide and needs about"
                        f" {needed:.0f} to aim {source}, so it sprays whatever"
                        f" you cup it into - a mouth has to be about twice as"
                        f" wide as the loop that made the note",
                        V(g.centre)))

    for g in groups:
        if g.span < needed or g.drawn_curvature >= -1e-4:
            continue
        focus = _focus_distance(g, wavelength)
        if focus is None or focus <= TANK_REACH:
            continue
        out.append(Note("fine",
                        f"this cupped mouth does come to a point, but about"
                        f" {focus:.0f} px out in front of it, further than the"
                        f" tank is wide - cup it harder and the point comes in",
                        V(g.centre) + V(g.outward) * min(focus, TANK_REACH)))
    return out


def _near_merge_notes(groups) -> list:
    """Mouths merge into one wider mouth within 46 px and not a pixel past it
    (MERGE_DIST). A player building a wide arc out of separate ends will miss
    that by a hair, and two lances where an arc was intended is a different
    weapon, not a weaker one."""
    out = []
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            if V(a.outward).dot(V(b.outward)) < 0.5:
                continue
            d = min((V(pa) - V(pb)).length() for pa in a.positions for pb in b.positions)
            if not MERGE_DIST < d <= NEARLY_MERGED:
                continue
            out.append(Note("fine",
                            f"these two mouths are {d:.0f} px apart and only"
                            f" merge into one wider mouth within about"
                            f" {MERGE_DIST:.0f} - move them a little closer and"
                            f" they will fire as one arc instead of two",
                            _midpoint(a.centre, b.centre)))
    return out


# ------------------------------------------------------------------- good


def _good_loop_notes(graph, adjacency, rings, terminals, sites, gaps) -> list:
    """Success has to be as legible as failure or the player cannot tell a
    drawing that worked from one that got away with it."""
    out = []
    for ring in rings:
        if _open_branch(graph, adjacency, ring, terminals) is not None:
            continue
        touching = [i for i, s in enumerate(sites)
                    if (s.edge_a in ring.edges) != (s.edge_b in ring.edges)]
        if not touching:
            continue
        out.append(Note("good",
                        f"this loop is gapped off its feed rather than wired to"
                        f" it, which is the only way it charges instead of"
                        f" draining straight back out the way it came",
                        ring.centre))
        for i in touching:
            pos_a, pos_b, _gap = gaps[i] if i < len(gaps) else (None, None, 0.0)
            out.append(Note("good",
                            "this gap sits right on the loop, so once the loop"
                            " has charged it can tear the water open here and"
                            " dump - that is a trigger you can build on",
                            _midpoint(pos_a, pos_b)))
    return out


def _good_aperture_notes(groups, wavelength, source) -> list:
    if wavelength is None:
        return []
    needed = AIM_WAVELENGTHS * wavelength
    out = []
    for g in groups:
        if len(g.node_ids) < 2 or g.span < needed:
            continue
        out.append(Note("good",
                        f"this mouth is {g.span:.0f} px across where"
                        f" {source} needs about {needed:.0f}, so it is wide"
                        f" enough to point where you cup it",
                        V(g.centre)))
        focus = _focus_distance(g, wavelength)
        if focus is not None and focus <= TANK_REACH:
            out.append(Note("good",
                            f"and the cup on it brings that to a point about"
                            f" {focus:.0f} px out, which is how far away the"
                            f" thing you are shooting has to be",
                            V(g.centre) + V(g.outward) * focus))
    return out


# ------------------------------------------------------------- the drawing


class _Ring:
    __slots__ = ("edges", "nodes", "circumference", "centre")

    def __init__(self, edges, nodes, circumference, centre):
        self.edges = edges
        self.nodes = nodes
        self.circumference = circumference
        self.centre = centre

    @property
    def name(self) -> str:
        return rung_for_length(self.circumference).name


def _adjacency(graph) -> dict:
    adj = {nid: [] for nid in graph.nodes}
    for idx, edge in enumerate(graph.edges):
        adj[edge.node_a].append((idx, edge.node_b))
        adj[edge.node_b].append((idx, edge.node_a))
    return adj


def _components(graph, adjacency) -> list:
    """Edge sets, one per connected piece of the drawing. Pieces gapped to
    one another are still separate here; the union happens where it means
    something, in `_orphan_notes`."""
    seen, out = set(), []
    for start in graph.nodes:
        if start in seen:
            continue
        seen.add(start)
        stack, edges = [start], set()
        while stack:
            u = stack.pop()
            for idx, v in adjacency[u]:
                edges.add(idx)
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if edges:
            out.append(edges)
    return out


def _bridges(graph, adjacency) -> set:
    """Edges whose removal disconnects the drawing -- so every edge that is
    *not* one is on a ring. Doing it this way rather than re-deriving a cycle
    basis keeps parallel edges honest: a ring split by a run joined onto it
    becomes two edges between the same pair of nodes, and neither is a bridge,
    which is exactly the case the loop notes turn on. Edges are skipped by id
    rather than by endpoint, or those two would eat each other."""
    disc, low, bridges = {}, {}, set()
    timer = 0
    for start in graph.nodes:
        if start in disc:
            continue
        disc[start] = low[start] = timer
        timer += 1
        stack = [(start, -1, iter(adjacency[start]))]
        while stack:
            u, from_edge, it = stack[-1]
            descended = False
            for idx, v in it:
                if idx == from_edge:
                    continue
                if v in disc:
                    low[u] = min(low[u], disc[v])
                else:
                    disc[v] = low[v] = timer
                    timer += 1
                    stack.append((v, idx, iter(adjacency[v])))
                    descended = True
                    break
            if descended:
                continue
            stack.pop()
            if stack:
                parent = stack[-1][0]
                low[parent] = min(low[parent], low[u])
                if low[u] > disc[parent]:
                    bridges.add(from_edge)
    return bridges


def _rings(graph, adjacency) -> list:
    """One entry per closed piece of the drawing. A placed ring is the
    one-edge case; runs joined nose to tail are the same fact arrived at by
    arrangement, and get the same name off the ladder."""
    on_ring = set(range(len(graph.edges))) - _bridges(graph, adjacency)
    if not on_ring:
        return []

    node_edges = {}
    for idx in on_ring:
        edge = graph.edges[idx]
        node_edges.setdefault(edge.node_a, []).append(idx)
        node_edges.setdefault(edge.node_b, []).append(idx)

    seen, out = set(), []
    for start in sorted(node_edges):
        if start in seen:
            continue
        seen.add(start)
        stack, edges, nodes = [start], set(), {start}
        while stack:
            u = stack.pop()
            for idx in node_edges.get(u, ()):
                edges.add(idx)
                edge = graph.edges[idx]
                for v in (edge.node_a, edge.node_b):
                    if v not in seen:
                        seen.add(v)
                        nodes.add(v)
                        stack.append(v)
                nodes.add(edge.node_a)
                nodes.add(edge.node_b)
        if edges:
            out.append(_Ring(edges, nodes,
                             sum(graph.edges[e].length for e in edges),
                             _centroid(graph, edges)))
    return out


def _open_branch(graph, adjacency, ring, terminals):
    """The node where a run joined onto this ring runs off to a free end.

    That free end is what makes the join fatal: a terminal radiates, so the
    branch is an open port hanging off the resonator and the ring drains into
    it every lap. A branch that goes somewhere else -- into another ring, into
    a fork with no way out -- is not the measured case and does not get the
    measured sentence.
    """
    if not terminals:
        return None
    terminal_set = set(terminals)
    for nid in sorted(ring.nodes):
        for idx, far in adjacency[nid]:
            if idx in ring.edges:
                continue
            if _reaches_terminal(adjacency, far, ring.nodes, terminal_set):
                return nid
    return None


def _reaches_terminal(adjacency, start, blocked, terminals) -> bool:
    if start in blocked:
        return False
    seen, stack = {start}, [start]
    while stack:
        u = stack.pop()
        if u in terminals:
            return True
        for _idx, v in adjacency[u]:
            if v not in seen and v not in blocked:
                seen.add(v)
                stack.append(v)
    return False


def _walk(graph, adjacency, source):
    """Shortest way from one free end to everywhere else, in px, carrying the
    number of splits crossed on the way. Shortest rather than longest because
    that is the path the *first* arrival takes, and the first arrival is the
    one the player watches."""
    dist = {source: 0.0}
    forks = {source: 0}
    queue = [(0.0, 0, source)]
    while queue:
        d, f, u = heapq.heappop(queue)
        if d > dist.get(u, math.inf) + 1e-9:
            continue
        for idx, v in adjacency[u]:
            step = d + graph.edges[idx].length
            crossed = f + (1 if graph.nodes[v].degree >= 3 else 0)
            if step < dist.get(v, math.inf) - 1e-9:
                dist[v] = step
                forks[v] = crossed
                heapq.heappush(queue, (step, crossed, v))
    return dist, forks


def _deepest_forks(graph, adjacency, terminals):
    best, where = 0, None
    for source in terminals[:32]:
        _dist, forks = _walk(graph, adjacency, source)
        for nid in terminals:
            n = forks.get(nid, 0)
            if n > best:
                best, where = n, V(graph.nodes[nid].pos)
    return best, where


def _longest_way(graph, adjacency, terminals):
    best, where = 0.0, None
    for source in terminals[:32]:
        dist, _forks = _walk(graph, adjacency, source)
        for nid in terminals:
            d = dist.get(nid, 0.0)
            if d > best:
                best, where = d, V(graph.nodes[nid].pos)
    return best, where


# --------------------------------------------------------------- the note


def _wavelength(assembly, emitter, note_hz, rings):
    """What the machine is saying, as a length on the bench, plus how to name
    it in a sentence.

    Three sources, in order of how much they know. A frequency handed in wins.
    Then whatever the emitter has actually measured coming out, which beats
    any guess because saturation can put the output an octave off every loop
    in the drawing. Failing both, the biggest ring: a loop of circumference L
    rings at c/L and its wavelength in bench pixels is exactly L, so the
    conversion is the identity and the advice can be phrased in the drawing's
    own units.

    None means the machine has no note anyone can name -- no loop, nothing
    fired yet -- and every aperture note is skipped rather than guessed.
    """
    if note_hz is not None:
        return _wavelength_for(note_hz), "this note"
    if emitter is not None:
        # A reading sitting on FREQ_MIN is not a low note, it is the emitter
        # saying it heard no zero crossings in that window -- a mouth with
        # nothing coming out of it yet. Taking it at face value asks for a
        # 15000 px aperture off a machine that is working fine, which is the
        # loudest possible way to cry wolf.
        measured = [g.history[-1][2] for g in emitter.groups
                    if g.history and g.history[-1][2] > FREQ_MIN * 1.01]
        if measured:
            return _wavelength_for(min(measured)), "the note it is making"
    if rings:
        biggest = max(rings, key=lambda r: r.circumference)
        return biggest.circumference, f"the note a {biggest.name} loop makes"
    return None, ""


def _wavelength_for(freq: float) -> float:
    return (C_WATER / max(float(freq), 1e-9)) / BENCH_M_PER_PX


def _focus_distance(group, wavelength):
    """Where a cupped aperture comes to a point: 1 / curvature, with the
    curvature the emitter will actually launch -- what was drawn plus the
    spreading no drawing can cancel. A convex total never converges and
    reports nothing rather than a negative distance."""
    freq = C_WATER / (max(wavelength, 1e-9) * BENCH_M_PER_PX)
    total = group.drawn_curvature + diffraction_curvature(group.span, freq)
    if total >= -1e-9:
        return None
    return 1.0 / -total


# -------------------------------------------------------------- plumbing


def _lookup(table, x: float) -> float:
    """Read a measured table between its rows.

    Straight in x, logarithmic in the fraction, because every one of these
    three losses is a per-step multiplication: damping is per sample, a gap's
    coupling falls off as e^-2g, and a split takes its share once per split.
    So the honest curve is a straight line through log(fraction), and it lands
    within a couple of percent of a fresh measurement everywhere it was
    checked. Outside the table it clamps - the measurements stop where they
    stop, and extrapolating them would be inventing a number.
    """
    xs = [row[0] for row in table]
    ys = [row[1] for row in table]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            t = 0.0 if span <= 0 else (x - xs[i]) / span
            return math.exp(math.log(max(ys[i], 1e-12)) * (1 - t)
                            + math.log(max(ys[i + 1], 1e-12)) * t)
    return ys[-1]


def _percent(fraction: float) -> str:
    """A share, said the way a person says it. 9.3: a number is only allowed
    where it means something on its own, and once a fraction is small enough
    that its percentage reads as zero, "one part in four hundred" is the form
    that still tells you how far off you are."""
    if fraction >= 0.1:
        return f"{fraction * 100:.0f}%"
    return f"one part in {1.0 / max(fraction, 1e-12):.0f}"


def _part_centre(part):
    return V(part.centre) if part.kind == "loop" else (V(part.p0) + V(part.p1)) * 0.5


def _midpoint(a, b):
    """Where to point when the thing being talked about is between two
    places. Either end may be missing - `_gap_positions` refuses to guess a
    position it cannot pair up - and a note with nowhere to point is still a
    note worth saying."""
    if a is None or b is None:
        return V(a) if a is not None else (V(b) if b is not None else None)
    return (V(a) + V(b)) * 0.5


def _centroid(graph, edge_ids):
    total, n = V(0.0, 0.0), 0
    for idx in edge_ids:
        for p in graph.edges[idx].polyline:
            total += p
            n += 1
    return total / n if n else None


def _gap_positions(assembly, sites) -> list:
    """`Assembly.gaps()` is the same `find_coupler_sites` call with the same
    arguments, so it is the same list in the same order -- but this pairs them
    up explicitly rather than trusting that, because a note pointing at the
    wrong gap is worse than a note with nowhere to point."""
    gaps = assembly.gaps()
    if len(gaps) != len(sites):
        return [(None, None, s.gap) for s in sites]
    return [(a, b, g) if abs(g - s.gap) < 1e-6 else (None, None, s.gap)
            for (a, b, g), s in zip(gaps, sites)]
