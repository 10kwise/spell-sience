"""Coupler detection (design doc §2.7): at compile time, find any pair of
non-adjacent edges whose closest approach is under g_max and hand back
where along each edge the gap is narrowest — the compiler turns that into
an actual Coupler on the Network.

Point-proximity brute force again (as in parser.py), not a spatial hash —
fine at the doc's own soft cap of 64 edges, and explicitly called out there
as a later perf optimization rather than a correctness requirement.
"""

import math

from .graph import SigilGraph


class CouplerSite:
    def __init__(self, edge_a: int, pos_a: float, edge_b: int, pos_b: float, gap: float):
        self.edge_a = edge_a
        self.pos_a = pos_a  # arclength distance from node_a, in px
        self.edge_b = edge_b
        self.pos_b = pos_b
        self.gap = gap


def _edges_share_node(edge_a, edge_b) -> bool:
    nodes_a = {edge_a.node_a, edge_a.node_b}
    nodes_b = {edge_b.node_a, edge_b.node_b}
    return bool(nodes_a & nodes_b)


def find_coupler_sites(
    graph: SigilGraph, dx: float, snap_eps: float = 8.0, g_max: float = 30.0, max_couplers: int = 16
) -> list:
    sites = []
    edges = graph.edges
    for i in range(len(edges)):
        edge_a = edges[i]
        for j in range(i + 1, len(edges)):
            edge_b = edges[j]
            if _edges_share_node(edge_a, edge_b):
                continue

            best = None
            for ai, pa in enumerate(edge_a.polyline):
                for bi, pb in enumerate(edge_b.polyline):
                    d = (pa - pb).length()
                    if d < snap_eps or d >= g_max:
                        continue
                    if best is None or d < best[0]:
                        best = (d, ai, bi)

            if best is not None:
                gap, ai, bi = best
                sites.append(CouplerSite(i, ai * dx, j, bi * dx, gap))

    sites.sort(key=lambda s: s.gap)
    return sites[:max_couplers]


def kappa_for_gap(gap: float, g_max: float, kappa_max: float = 0.85) -> float:
    """Small gap ~ wireless junction (kappa near max); kappa falls off with
    distance and the detection cutoff (g_max) is the hard 'nothing crosses
    past here' boundary (§2.7)."""
    return kappa_max * math.exp(-2.0 * gap / g_max)


def lowpass_coef_for_gap(gap: float, g_max: float, min_coef: float = 0.02, max_coef: float = 0.4) -> float:
    """Wider gaps only let progressively lower frequencies through — a long
    wavelength tunnels further than a short one at the same gap (§2.7)."""
    t = min(1.0, gap / g_max)
    return max_coef - (max_coef - min_coef) * t
