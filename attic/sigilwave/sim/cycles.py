"""Chirality (design doc §2.8): a property of loops, not waves, computed
once per sigil edit via a cycle basis over the SigilGraph.

1. Spanning tree (BFS) -> one fundamental cycle per non-tree edge.
2. Signed area (shoelace) of each cycle's polygon -> its winding sign.
3. Circumference -> fundamental frequency f_c = 1/L_c (in cycles/sample,
   same units as the filter bank's band centers).
4. For each band, weight cycles by nearness to their own harmonics and
   average the signs -> chi_b, a small bands x cycles matrix computed once
   and then just looked up at runtime.
"""

import math
from collections import deque

from .graph import SigilGraph


def _build_adjacency(graph: SigilGraph) -> dict:
    adjacency = {nid: [] for nid in graph.nodes}
    for idx, edge in enumerate(graph.edges):
        adjacency[edge.node_a].append((idx, edge.node_b))
        if edge.node_a != edge.node_b:
            adjacency[edge.node_b].append((idx, edge.node_a))
    return adjacency


def _spanning_tree(graph: SigilGraph, adjacency: dict) -> set:
    visited = set()
    tree_edges = set()
    for start in graph.nodes:
        if start in visited:
            continue
        visited.add(start)
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for edge_idx, v in adjacency[u]:
                edge = graph.edges[edge_idx]
                if edge.node_a == edge.node_b:
                    continue  # a self-loop can never be a tree edge
                if v not in visited:
                    visited.add(v)
                    tree_edges.add(edge_idx)
                    queue.append(v)
    return tree_edges


def _path_in_tree(graph: SigilGraph, adjacency: dict, tree_edges: set, start: int, end: int) -> list:
    """Sequence of (edge_idx, from_node, to_node) walking start -> end using
    only tree edges."""
    if start == end:
        return []
    visited = {start}
    queue = deque([(start, [])])
    while queue:
        u, path = queue.popleft()
        for edge_idx, v in adjacency[u]:
            if edge_idx not in tree_edges or v in visited:
                continue
            new_path = path + [(edge_idx, u, v)]
            if v == end:
                return new_path
            visited.add(v)
            queue.append((v, new_path))
    raise ValueError("start and end are not connected in the spanning tree")


def _cycle_polygon_points(graph: SigilGraph, cycle_edges: list) -> list:
    points = []
    for edge_idx, frm, _to in cycle_edges:
        edge = graph.edges[edge_idx]
        poly = edge.polyline
        seg = poly[:-1] if edge.node_a == frm else list(reversed(poly))[:-1]
        points.extend(seg)
    return points


def _signed_area(points: list) -> float:
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = points[i].x, points[i].y
        x2, y2 = points[(i + 1) % n].x, points[(i + 1) % n].y
        area += x1 * y2 - x2 * y1
    return area / 2.0


class Cycle:
    def __init__(self, sign: float, fundamental_freq: float):
        self.sign = sign
        self.fundamental_freq = fundamental_freq


def find_loop_closing_edges(graph: SigilGraph) -> list:
    """Non-tree edges (self-loops included) — the ones that actually close a
    loop. §2.6: nonlinearity is sited at junctions, and every closed loop
    necessarily has at least one such node (a plain circle's start meeting
    its end is the simplest case)."""
    adjacency = _build_adjacency(graph)
    tree_edges = _spanning_tree(graph, adjacency)
    return [idx for idx in range(len(graph.edges)) if idx not in tree_edges]


def find_loop_closing_nodes(graph: SigilGraph) -> set:
    nodes = set()
    for idx in find_loop_closing_edges(graph):
        edge = graph.edges[idx]
        nodes.add(edge.node_a)
        nodes.add(edge.node_b)
    return nodes


def find_cycles(graph: SigilGraph, dx: float) -> list:
    """One Cycle per non-tree edge (including self-loops, which are always
    non-tree by construction)."""
    adjacency = _build_adjacency(graph)
    tree_edges = _spanning_tree(graph, adjacency)

    cycles = []
    for idx, edge in enumerate(graph.edges):
        if idx in tree_edges:
            continue
        if edge.node_a == edge.node_b:
            cycle_edges = [(idx, edge.node_a, edge.node_b)]
        else:
            path = _path_in_tree(graph, adjacency, tree_edges, edge.node_a, edge.node_b)
            cycle_edges = path + [(idx, edge.node_b, edge.node_a)]

        points = _cycle_polygon_points(graph, cycle_edges)
        area = _signed_area(points)
        if abs(area) < 1e-6:
            continue  # degenerate (zero-area) loop: no meaningful winding

        circumference = sum(graph.edges[e].length for e, _f, _t in cycle_edges)
        length_samples = max(1.0, circumference / dx)
        fundamental_freq = 1.0 / length_samples

        cycles.append(Cycle(sign=math.copysign(1.0, area), fundamental_freq=fundamental_freq))

    return cycles


def compute_chirality(
    graph: SigilGraph, band_centers: list, dx: float, sigma: float = 0.03, max_harmonic: int = 8
) -> list:
    """chi_b per band (§2.8's w(b,c) / chi_b formulas).

    A shape with no closed loop has no winding to read a sign from, but it
    must NOT collapse the kinetic/thermal coupling to zero — coupling.py
    uses this vector as a signed multiplier on band energy (§2.9: "sign from
    chi"), so a literal 0.0 here would silence every un-looped shape's push
    and burn entirely. That would contradict stage 5's own vertical slice
    (a plain open line was the shape used to first prove "something moves"
    from a drawing, §9) and leave open strokes almost inert once chirality
    is wired in. Defaulting to +1.0 keeps that baseline outward push/burn
    for any radiating shape; drawing an actual loop is what lets a player
    choose the opposite sign (pull, chill) via winding direction.
    """
    cycles = find_cycles(graph, dx)
    if not cycles:
        return [1.0] * len(band_centers)

    chirality = []
    for f_b in band_centers:
        total_weight = 0.0
        weighted_sign = 0.0
        nearest_sign, nearest_dist = 1.0, None
        for cycle in cycles:
            weight = 0.0
            for n in range(1, max_harmonic + 1):
                harmonic = n * cycle.fundamental_freq
                dist = abs(f_b - harmonic)
                weight += math.exp(-((dist / sigma) ** 2))
                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist, nearest_sign = dist, cycle.sign
            total_weight += weight
            weighted_sign += cycle.sign * weight

        if total_weight > 1e-12:
            chirality.append(weighted_sign / total_weight)
        else:
            # No cycle's harmonics reach anywhere near this band — the
            # Gaussian sum underflows to numerical zero. A plain 0.0 here
            # would silently cancel this band's signed kinetic/thermal
            # coupling even though a real loop with a real winding sign
            # exists (the same bug class as the no-loop case above; this is
            # a large low-f0 loop's high bands specifically — and
            # THERMAL_BAND_WEIGHTS peaks on the top band, so this used to
            # quietly kill "ice" for most kinetic-sized loops). Falling back
            # to the nearest cycle's own sign keeps it directional instead
            # of neutralizing it.
            chirality.append(nearest_sign)

    return chirality
