"""The five parts of SUBMERGED §4, of which only two are placed.

    RUN   a line     placed
    LOOP  a ring     placed
    FORK  a junction emerges where three or more run ends meet at a point
    GAP   a coupler  emerges where two strokes pass close without touching
    MOUTH an open end emerges where a run end is left free

That asymmetry is the design thesis in miniature: few primitives, meaning
from arrangement. It is also why this module compiles nothing itself.
`sigilwave/sim/` already finds all three emergent parts — a SigilGraph's
degree-1 nodes are mouths, its degree>=3 nodes are forks, `find_coupler_sites`
finds gaps by proximity, and `find_loop_closing_edges` sites the nonlinearity
on whatever closes a cycle. An Assembly is therefore a thin, honest thing: it
holds placed geometry, hands it to `parse_strokes` and `compile_graph`, and
reads the emergent parts back out of the same structures the simulation is
actually running. There is exactly one topology in the build, and the picture
the player is shown cannot disagree with the physics they are watching.


THE TWO DISTANCES
-----------------
§9.2 forbids ambiguous middles: two run ends are either joined or gapped and
never in between. So there are two constants and one hard rule between them.

    JOIN_EPS = 6.0 px       within this, ends snap onto one shared node
    GAP_MAX  = 30.0 px      out to here, they stay apart and couple
                            beyond it, they are unrelated

The bands are half-open and touching — [0, 6) join, [6, 30) gap, [30, inf)
nothing — so every distance lands in exactly one, which `selftest_bench`
check 7 sweeps and proves. That is the cheap half. The half that matters is
that the classification is *visible*, and it is visible because a join moves
the geometry: `add_run` snaps the placed endpoint onto its anchor, so a join
drawn at 5.9 px renders as a single node dot at 0 px separation while a gap
drawn at 6.1 px renders as two dots 6.1 px apart with a spark between them.
The rendered discontinuity at the boundary is the whole of JOIN_EPS, not a
hair. (A renderer must therefore draw a node dot no larger than JOIN_EPS/2 in
radius, or it paints the boundary back over.)

Why 6.0 and not the sim's default 8.0, which is what every other caller
passes? Because the join radius turns out to be the same number as the
smallest loop, in disguise. `parse_strokes` snaps *any* pair of points within
snap_eps, including two points on the same stroke either side of a small
ring's closure, and when it does it eats a snap_eps-sized bite out of that
ring. Measured, at dx=4: at snap_eps=8 the bottom two rungs of the ladder
below compile to 19 and 8 samples instead of 20 and 10 — a 17% error in the
smallest loop's note, silently. At snap_eps<=7 the same rungs compile to 20
and 9. So JOIN_EPS is bounded above by the smallest note the ladder has to
be able to say, and below by dx=4 (two ends the sim cannot resolve apart must
still join). 6.0 px is 1.5 samples, sits in the middle of that window, and is
about the width of a drawn stroke, which is what makes "they touch" read as
touching.

GAP_MAX = 30.0 px is the sim's own default g_max and DEFAULT_INK's
coupler_range. It is not an arbitrary wall: `kappa_for_gap` decays to
0.85*e^-2 = 0.115 there, and a burst across a 29.5 px gap delivers 1.7e-5 of
its energy — the cutoff is placed where nothing was happening anyway.


THE LOOP LADDER
---------------
§2.1 is the post-mortem of two builds: continuous systems are unlearnable,
because a slightly bigger circle that feels like nothing *is* nothing you can
name. So radius quantises to a ladder of exact octaves, and each rung has a
name, because "a signal caught in a loop laps forever, its lap time is its
note" (§4) only pays if the notes are countable.

Exact octaves, not a nice spread of six sizes over §7.4's two decades, for
CAMPANARY's reason: SATURATION (§4.1) folds a driven loop into its second
harmonic, which is one octave up, so a doubling ladder is the only one where
"drive it hard and it climbs a note" lands on another rung instead of between
two. Six rungs is 32:1, about 1.5 of §7.4's two decades; the missing half
decade is above the top of the ladder and is reached by driving, not drawing.

Six names, five of them placeable. The bottom rung is a 6.4 px radius, and
measured at dx=4 it compiles to a 9-sample lap where its own octave wants 10:
a 10% error in the one thing a loop is for. That is not a tuning problem, it
is the sampling floor — a decagon on a 6.4 px circle is as close to a circle
as dx=4 can get. A rung whose note is 10% wrong is worse than no rung, since
§9.1 allows a part one sentence and no exceptions, so `snap_radius` will not
place it and `DRAWABLE_RUNGS` stops at five. The sixth keeps its name because
it is still reachable: it is exactly what driving the fifth into SATURATION
sounds like. That is CAMPANARY's SPARROW gate, arrived at from the sampling
rate rather than chosen — and it is the same finding, that the bottom of a
size ladder is set by dx and not by what a hand can hold.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import pygame

from ..ink import DEFAULT_INK, InkType, Stroke
from ..sim.compiler import compile_graph
from ..sim.couplers import find_coupler_sites
# Private, and on purpose: loops() must report the same cycle basis the
# compiler uses to site nonlinearity (compiler.py -> find_loop_closing_edges),
# or the rings the player is told they drew and the rings that actually
# saturate would be two different lists. Re-deriving a second basis here is
# precisely the "write a second compiler" mistake. Read-only use.
from ..sim.cycles import _build_adjacency, _path_in_tree, _spanning_tree, find_loop_closing_edges
from ..sim.graph import SigilGraph
from ..sim.network import Network
from ..sim.parser import parse_strokes

V = pygame.Vector2

DX = 4.0                    # px per sim sample; the value every other caller uses
WAVE_C = 400.0              # px/s, still water, constant across the bench tank
SIM_DT = DX / WAVE_C        # 0.01 s -> a 100 Hz sim step

JOIN_EPS = 6.0              # see THE TWO DISTANCES above
GAP_MAX = 30.0

MIN_RUN_LENGTH = 4.0 * DX   # parse_strokes' own min_edge_length: below this an
                            # edge quantises under 4 samples and is discarded
MAX_ENERGY = 50.0           # the sim's passivity ceiling (§8), passed through

# A placed ring is emitted as a polyline. Spacing has to be well under dx or
# ink.smooth_points' 5-point box filter measurably shrinks small circles
# (measured: 2.0 px spacing costs the 12.7 px rung 4.7% of its circumference,
# 0.5 px costs it 2.6%, and the remainder is chord error rather than
# smoothing). Half a pixel is where that curve flattens.
RING_POINT_SPACING = 0.5


@dataclass(frozen=True)
class LoopRung:
    """One nameable size. `lap_samples` is what the sim will actually do with
    it: one lap is one traversal of the closed delay line, so the note is
    dx/lap_samples in cycles per sample and the lap is visible as motion,
    which is what §9.3 demands instead of a readout."""

    name: str
    circumference: float
    radius: float
    drawable: bool = True  # False = past the sampling floor; reached by driving, not drawing

    @property
    def lap_samples(self) -> float:
        return self.circumference / DX

    @property
    def lap_seconds(self) -> float:
        return self.circumference / WAVE_C

    @property
    def note_hz(self) -> float:
        return WAVE_C / self.circumference


# Low to high, each exactly half the one before. Named for the sound, because
# the size *is* the note and nothing else about a loop is a free parameter.
_LADDER_CIRCUMFERENCES = [1280.0, 640.0, 320.0, 160.0, 80.0, 40.0]
_LADDER_NAMES = ["swell", "groan", "hum", "ping", "chirp", "whistle"]

LOOP_LADDER = [
    LoopRung(name, circ, circ / (2.0 * math.pi), drawable=circ >= 80.0)
    for name, circ in zip(_LADDER_NAMES, _LADDER_CIRCUMFERENCES)
]

# What a player can place. The rung past the end of this list is the
# SATURATION gate (§4.1) and is measured, not drawn.
DRAWABLE_RUNGS = [rung for rung in LOOP_LADDER if rung.drawable]
GATE_RUNG = LOOP_LADDER[-1]


def snap_radius(radius: float) -> LoopRung:
    """Nearest placeable rung in log space, because the ladder is geometric:
    halfway between two rungs by ratio is halfway by ear, not halfway by
    pixels. Anything smaller than the bottom rung becomes the bottom rung
    rather than the gate rung below it, which cannot hold its own note."""
    r = max(1e-6, float(radius))
    return min(DRAWABLE_RUNGS, key=lambda rung: abs(math.log(r / rung.radius)))


def rung_for_length(length: float) -> LoopRung:
    """The rung a *measured* closed path is nearest to. Used to name loops
    that emerged from joined runs rather than from a placed ring — they get
    the same vocabulary, since it is the lap time that has the name."""
    return min(LOOP_LADDER, key=lambda rung: abs(math.log(max(1e-6, length) / rung.circumference)))


_RUN_WORDS = ((160.0, "short"), (640.0, "long"))


def _length_word(length: float) -> str:
    """Runs are the one placed thing this module does *not* quantise, because
    §9.3 is satisfied for a run without a ladder: its whole property is delay,
    and delay is already readable as motion. The cost shows up here, in
    describe() — three buckets is all the vocabulary a continuous length can
    honestly support."""
    for limit, word in _RUN_WORDS:
        if length < limit:
            return word
    return "very long"


@dataclass
class Part:
    """A placed part. Two kinds, and that is the whole list (§4): everything
    else in the game emerges from where these end up."""

    part_id: int
    kind: str  # "run" | "loop"
    p0: V = field(default_factory=V)
    p1: V = field(default_factory=V)
    centre: V = field(default_factory=V)
    rung: LoopRung | None = None

    @property
    def length(self) -> float:
        if self.kind == "run":
            return (self.p1 - self.p0).length()
        return self.rung.circumference

    def anchors(self) -> list:
        """The points another part can join to. A ring has no ends, so a run
        may land anywhere on its circumference; `Assembly._snap` handles that
        case separately rather than pretending a ring has anchors."""
        return [self.p0, self.p1] if self.kind == "run" else []

    def translate(self, delta: V) -> None:
        self.p0 += delta
        self.p1 += delta
        self.centre += delta

    def points(self) -> list:
        if self.kind == "run":
            return [V(self.p0), V(self.p1)]
        r = self.rung.radius
        n = max(8, int(math.ceil(2.0 * math.pi * r / RING_POINT_SPACING)))
        return [
            self.centre + V(r * math.cos(2.0 * math.pi * i / n), r * math.sin(2.0 * math.pi * i / n))
            for i in range(n + 1)  # closes exactly on the first point
        ]


class Assembly:
    """Placed parts, plus the topology that emerges from where they were put.

    Every derived thing — graph, network, forks, mouths, gaps, loops, the
    sentence — comes off one cached parse. Editing marks it dirty; nothing
    recomputes per frame, because the parse is an edit-time operation exactly
    as the sim's own parser and compiler are.
    """

    def __init__(self, ink: InkType = DEFAULT_INK, dx: float = DX):
        self.ink = ink
        self.dx = dx
        self._parts: dict[int, Part] = {}
        self._next_id = 0
        self._graph: SigilGraph | None = None
        self._network: Network | None = None
        self._edge_owner: list = []       # graph edge index -> part id
        self._network_dx: float | None = None
        self._tracks: list | None = None

    # ------------------------------------------------------------- placing

    def add_run(self, p0, p1) -> int:
        """Place a line. Both ends snap: within JOIN_EPS of an existing run
        end they land *on* it, and within JOIN_EPS of a placed ring they land
        on the ring. The snap moves the geometry rather than only the
        topology, so the join the player made is the join they see (§9.2)."""
        a, b = self._snap(V(p0)), self._snap(V(p1))
        part = Part(self._next_id, "run", p0=a, p1=b)
        return self._add(part)

    def add_loop(self, centre, radius, rung: LoopRung | None = None) -> int:
        """Place a ring. The radius quantises to DRAWABLE_RUNGS on the way in;
        there is no such thing as a loop between two rungs, which is §2.1's
        entire complaint about the previous two builds.

        Passing `rung` outright is how `selftest_bench` measures the gate rung
        that snapping refuses to place. It is not a way round the ladder.
        """
        chosen = rung if rung is not None else snap_radius(radius)
        part = Part(self._next_id, "loop", centre=self._snap_ring(V(centre), chosen), rung=chosen)
        return self._add(part)

    def _add(self, part: Part) -> int:
        self._parts[part.part_id] = part
        self._next_id += 1
        self._invalidate()
        return part.part_id

    def remove(self, part_id: int) -> None:
        self._parts.pop(part_id, None)
        self._invalidate()

    def move(self, part_id: int, delta) -> None:
        """Drag a part. It re-snaps where it lands, on the same terms as
        placing it: dragging a run end onto another one has to make the same
        join, and read as the same join, as drawing it there would."""
        part = self._parts.get(part_id)
        if part is None:
            return
        part.translate(V(delta))
        if part.kind == "run":
            part.p0 = self._snap(part.p0, ignore=part_id)
            part.p1 = self._snap(part.p1, ignore=part_id)
        else:
            part.centre = self._snap_ring(part.centre, part.rung, ignore=part_id)
        self._invalidate()

    def _snap_ring(self, centre: V, rung: LoopRung, ignore: int | None = None) -> V:
        """A ring has no ends of its own, so it snaps by sliding its centre
        until its circumference passes exactly through a nearby run end.
        Without this a loop dropped 5 px off a mouth would join in the graph
        while still rendering with a visible space, which is the ambiguous
        middle §9.2 exists to forbid."""
        best, best_d = None, JOIN_EPS
        for part in self._parts.values():
            if part.kind != "run" or part.part_id == ignore:
                continue
            for anchor in part.anchors():
                offset = anchor - centre
                d = abs(offset.length() - rung.radius)
                if d < best_d and offset.length() > 1e-9:
                    best, best_d = anchor - offset.normalize() * rung.radius, d
        return best if best is not None else centre

    def _snap(self, p: V, ignore: int | None = None) -> V:
        """Nearest join within JOIN_EPS, or the point untouched. Ring
        circumferences are snapped to as well, so a run can be tapped onto a
        loop and make the fork that §4 says a junction is."""
        best, best_d = None, JOIN_EPS
        for part in self._parts.values():
            if part.part_id == ignore:
                continue
            if part.kind == "run":
                for anchor in part.anchors():
                    d = (p - anchor).length()
                    if d < best_d:
                        best, best_d = V(anchor), d
            else:
                offset = p - part.centre
                d = abs(offset.length() - part.rung.radius)
                if d < best_d and offset.length() > 1e-9:
                    best, best_d = part.centre + offset.normalize() * part.rung.radius, d
        return best if best is not None else p

    def _invalidate(self) -> None:
        self._graph = None
        self._network = None
        self._network_dx = None
        self._edge_owner = []
        self._tracks = None

    # ------------------------------------------------------------ compiling

    @property
    def parts(self) -> list:
        return [self._parts[pid] for pid in sorted(self._parts)]

    def strokes(self) -> list:
        out = []
        for part in self.parts:
            stroke = Stroke(ink_type=self.ink)
            stroke.points = part.points()
            out.append(stroke)
        return out

    def to_graph(self) -> SigilGraph:
        """The sim's own parser, at JOIN_EPS. Sloppy placement parses the way
        it looks; that is `parse_strokes`' job and this module does not
        second-guess it."""
        if self._graph is None:
            self._graph = parse_strokes(self.strokes(), self.dx, snap_eps=JOIN_EPS)
            self._edge_owner = self._attribute_edges(self._graph)
        return self._graph

    def compile(self, dx: float | None = None, max_energy: float = MAX_ENERGY) -> Network:
        """The sim's own compiler, at JOIN_EPS and GAP_MAX. This is the whole
        of the bench's physics: everything §4 promises is already in here."""
        dx = self.dx if dx is None else dx
        if self._network is None or self._network_dx != dx:
            self._network = compile_graph(
                self.to_graph(), dx, snap_eps=JOIN_EPS, g_max=GAP_MAX, max_energy=max_energy
            )
            self._network_dx = dx
        return self._network

    def _attribute_edges(self, graph: SigilGraph) -> list:
        """Which part each graph edge came from. `parse_strokes` splits a
        stroke wherever something touches it and drops sub-edges under
        min_edge_length, so edge order is not part order; attributing by
        geometry is robust to both, and placed parts only ever cross at
        points, never run alongside each other, so nearest-stroke is exact."""
        clouds = []
        for part in self.parts:
            pts = part.points()
            clouds.append((part.part_id, np.array([[p.x, p.y] for p in pts])))

        owners = []
        for edge in graph.edges:
            poly = edge.polyline
            probes = [poly[len(poly) // 3], poly[2 * len(poly) // 3]]
            best_pid, best_d = None, None
            for pid, cloud in clouds:
                d = 0.0
                for probe in probes:
                    deltas = cloud - np.array([probe.x, probe.y])
                    d += float(np.min(np.hypot(deltas[:, 0], deltas[:, 1])))
                if best_d is None or d < best_d:
                    best_pid, best_d = pid, d
            owners.append(best_pid)
        return owners

    def ignored(self) -> list:
        """Parts that compiled to nothing — a run under MIN_RUN_LENGTH, or a
        stub swallowed by a snap. `parse_strokes` drops them silently; the
        bench must not, because a placed part that does nothing is exactly the
        failure §9.5 says has to be visible."""
        self.to_graph()
        alive = set(self._edge_owner)
        return [pid for pid in sorted(self._parts) if pid not in alive]

    # ------------------------------------------------- what emerged, for the
    # ------------------------------------------------- renderer and the player

    def forks(self) -> list:
        """Where three or more run ends meet. Degree>=3 in the graph is the
        same node the network scatters at, so this list is the junctions, not
        a drawing of them."""
        graph = self.to_graph()
        return [V(node.pos) for node in graph.nodes.values() if node.degree >= 3]

    def mouths(self) -> list:
        """Free ends. Degree 1 is `GraphNode.is_terminal`, which is exactly
        what the compiler gives a radiating admittance to — the only part that
        touches the water (§4)."""
        graph = self.to_graph()
        return [V(node.pos) for node in graph.nodes.values() if node.is_terminal]

    def gaps(self) -> list:
        """(pos_a, pos_b, gap_distance) for every coupler the compiler will
        build. Same call, same arguments, so the sparks drawn and the couplers
        simulated are one list."""
        graph = self.to_graph()
        out = []
        for site in find_coupler_sites(graph, self.dx, snap_eps=JOIN_EPS, g_max=GAP_MAX):
            pos_a = _point_at_arclength(graph.edges[site.edge_a].polyline, site.pos_a)
            pos_b = _point_at_arclength(graph.edges[site.edge_b].polyline, site.pos_b)
            out.append((pos_a, pos_b, site.gap))
        return out

    def loops(self) -> list:
        """Which parts form closed cycles: one entry per fundamental cycle, as
        (part_ids, circumference, rung). A placed ring is the one-part case; a
        ring of joined runs is the same fact arrived at by arrangement, and
        gets the same name off the ladder."""
        graph = self.to_graph()
        if not graph.edges:
            return []
        adjacency = _build_adjacency(graph)
        tree_edges = _spanning_tree(graph, adjacency)

        out = []
        for idx in find_loop_closing_edges(graph):
            edge = graph.edges[idx]
            if edge.node_a == edge.node_b:
                cycle = [(idx, edge.node_a, edge.node_b)]
            else:
                cycle = _path_in_tree(graph, adjacency, tree_edges, edge.node_a, edge.node_b)
                cycle = cycle + [(idx, edge.node_b, edge.node_a)]
            circumference = sum(graph.edges[e].length for e, _f, _t in cycle)
            part_ids = sorted({self._edge_owner[e] for e, _f, _t in cycle})
            out.append((part_ids, circumference, rung_for_length(circumference)))
        return out

    def edge_tracks(self) -> list:
        """Per graph edge, (xs, ys, arclength) as float arrays, in edge-id
        order. Static between edits and rebuilt with the graph, because the
        pulse render walks all of it every frame and rebuilding it there costs
        more than the simulation step does — measured, 2.2 ms against 78 us.
        Arclength rather than vertex index: `parse_strokes` resamples at a
        uniform dx, but it then moves the two end vertices onto snapped node
        positions, so the last segment of an edge is not dx long."""
        graph = self.to_graph()
        if self._tracks is None:
            self._tracks = []
            for edge in graph.edges:
                poly = edge.polyline
                xs = np.array([p.x for p in poly], dtype=np.float64)
                ys = np.array([p.y for p in poly], dtype=np.float64)
                steps = np.hypot(np.diff(xs), np.diff(ys))
                self._tracks.append((xs, ys, np.concatenate(([0.0], np.cumsum(steps)))))
        return self._tracks

    def node_at(self, pos, radius: float = JOIN_EPS * 2):
        """Nearest graph node id within radius, or None. The bench fires one
        pulse into a mouth; this is how a click becomes a node id."""
        graph = self.to_graph()
        best, best_d = None, radius
        for nid, node in graph.nodes.items():
            d = (V(pos) - node.pos).length()
            if d < best_d:
                best, best_d = nid, d
        return best

    def mouth_nodes(self) -> list:
        graph = self.to_graph()
        return [(nid, V(node.pos)) for nid, node in graph.nodes.items() if node.is_terminal]

    # -------------------------------------------------------------- naming

    def describe(self) -> str:
        """One sentence naming what was drawn (§9.6).

        Not a convenience. "If the only available description is 'a squiggle',
        the system has already failed" — so this method is a live check on the
        design, and where it gives up it is reporting a real limit rather than
        a missing feature. It gives up in two places, both stated out loud in
        what it returns: an assembly with more than four separate pieces, and
        one with more than a dozen edges. Past there a machine genuinely has
        no name, which is the finding.
        """
        graph = self.to_graph()
        if not self._parts:
            return "nothing placed"
        if not graph.edges:
            n = len(self._parts)
            return f"{n} part{'s' if n != 1 else ''} too short to be anything"

        components = _components(graph)
        n_loops = len(self.loops())
        if len(components) > 4 or len(graph.edges) > 12:
            n_runs = sum(1 for p in self.parts if p.kind == "run")
            return (
                f"a tangle of {n_runs} runs and {n_loops} loops in {len(components)} pieces"
                " - too much to name in one sentence"
            )

        gaps = self.gaps()
        gap_pairs = self._gap_components(graph, components)

        components.sort(key=lambda c: (-len(c.edges), -sum(graph.edges[e].length for e in c.edges)))
        trunk = components[0]
        phrase = self._component_phrase(graph, trunk, as_gap_target=False)

        for other in components[1:]:
            linked = (id(trunk), id(other)) in gap_pairs or (id(other), id(trunk)) in gap_pairs
            said = self._component_phrase(graph, other, as_gap_target=linked)
            if linked:
                phrase += ", gapped to " + said
            else:
                phrase += ", and a separate " + _drop_article(said)

        if len(components) == 1 and gaps:
            phrase += ", gapped back onto itself"

        clauses = [phrase]
        ignored = self.ignored()
        if ignored:
            clauses.append(f"{len(ignored)} part{'s' if len(ignored) != 1 else ''} too short to count")
        if not self.mouths():
            clauses.append("no mouth, so nothing leaves")
        return " - ".join(clauses)

    def _gap_components(self, graph: SigilGraph, components: list) -> set:
        owner = {}
        for comp in components:
            for e in comp.edges:
                owner[e] = comp
        pairs = set()
        for site in find_coupler_sites(graph, self.dx, snap_eps=JOIN_EPS, g_max=GAP_MAX):
            a, b = owner.get(site.edge_a), owner.get(site.edge_b)
            if a is not None and b is not None:
                pairs.add((id(a), id(b)))
        return pairs

    def _component_phrase(self, graph: SigilGraph, comp, as_gap_target: bool) -> str:
        forks = [n for n in comp.nodes if graph.nodes[n].degree >= 3]
        terminals = [n for n in comp.nodes if graph.nodes[n].is_terminal]
        cycles = [c for c in self.loops() if any(self._edge_owner[e] in c[0] for e in comp.edges)]

        if forks:
            branches, walked = [], set()
            for e in _incident_edges(graph, comp, forks[0]):
                if e in walked:
                    # A branch that came back here already named the whole
                    # ring it went round; the other end of that ring is the
                    # same loop, not a second one.
                    continue
                said, seen = self._branch_phrase(graph, comp, forks[0], e)
                walked |= seen
                branches.append(said)
            branches.sort(key=lambda s: ("loop" in s, s))
            return "a fork into " + _join_list(_collapse(branches))

        if cycles:
            return f"a {cycles[0][2].name} loop"

        if as_gap_target and terminals:
            # What a gap delivers into is the free end past it; naming the
            # whole run would bury the part that does something.
            return "a mouth"
        return f"a {_length_word(sum(graph.edges[e].length for e in comp.edges))} run"

    def _branch_phrase(self, graph: SigilGraph, comp, fork: int, edge_idx: int) -> tuple:
        """Walk out of a fork along one edge until something happens: a free
        end, another fork, or arrival back where we started. Returns the
        phrase and the edges it consumed on the way."""
        edge = graph.edges[edge_idx]
        if edge.node_a == edge.node_b:
            return f"a {rung_for_length(edge.length).name} loop", {edge_idx}

        length = edge.length
        cur = edge.node_b if edge.node_a == fork else edge.node_a
        seen = {edge_idx}
        while graph.nodes[cur].degree == 2 and cur != fork:
            nxt = next((e for e in _incident_edges(graph, comp, cur) if e not in seen), None)
            if nxt is None:
                break
            seen.add(nxt)
            edge = graph.edges[nxt]
            length += edge.length
            cur = edge.node_b if edge.node_a == cur else edge.node_a

        if cur == fork:
            return f"a {rung_for_length(length).name} loop", seen
        if graph.nodes[cur].is_terminal:
            return f"a {_length_word(length)} run", seen
        return "another fork", seen


@dataclass
class _Component:
    nodes: set = field(default_factory=set)
    edges: set = field(default_factory=set)


def _components(graph: SigilGraph) -> list:
    adjacency = {nid: [] for nid in graph.nodes}
    for idx, edge in enumerate(graph.edges):
        adjacency[edge.node_a].append((idx, edge.node_b))
        adjacency[edge.node_b].append((idx, edge.node_a))

    seen, out = set(), []
    for start in graph.nodes:
        if start in seen:
            continue
        comp = _Component()
        stack = [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.nodes.add(u)
            for idx, v in adjacency[u]:
                comp.edges.add(idx)
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if comp.edges:
            out.append(comp)
    return out


def _incident_edges(graph: SigilGraph, comp, node_id: int) -> list:
    return [e for e in sorted(comp.edges) if node_id in (graph.edges[e].node_a, graph.edges[e].node_b)]


def _collapse(phrases: list) -> list:
    """"a long run and a long run" is a worse name than "two long runs"."""
    out, counts = [], {}
    for p in phrases:
        counts[p] = counts.get(p, 0) + 1
    for p in phrases:
        if p in counts:
            n = counts.pop(p)
            out.append(p if n == 1 else _pluralise(p, n))
    return out


def _drop_article(phrase: str) -> str:
    return phrase[2:] if phrase.startswith("a ") else phrase


_NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def _pluralise(phrase: str, n: int) -> str:
    return f"{_NUMBER_WORDS.get(n, str(n))} {_drop_article(phrase)}s"


def _join_list(items: list) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _point_at_arclength(polyline: list, s: float) -> V:
    """Where a coupler site actually is in the world. `CouplerSite` reports
    arclength from node_a because that is what the delay line indexes by."""
    if s <= 0.0 or len(polyline) < 2:
        return V(polyline[0])
    walked = 0.0
    for i in range(len(polyline) - 1):
        seg = polyline[i + 1] - polyline[i]
        seg_len = seg.length()
        if walked + seg_len >= s:
            t = 0.0 if seg_len < 1e-9 else (s - walked) / seg_len
            return polyline[i] + seg * t
        walked += seg_len
    return V(polyline[-1])
