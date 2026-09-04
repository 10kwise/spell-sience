"""Strokes -> SigilGraph (design doc §4.1, §4.3). Pure and deterministic,
runs on edit rather than per frame.

Intersection detection here is brute-force point-proximity rather than a
proper spatial hash / segment-intersection test — correct at prototype scale
(soft cap of 64 edges per §5) and exactly what the doc calls out as a later
performance optimization, not a correctness requirement.
"""

import pygame

from .graph import GraphEdge, GraphNode, SigilGraph


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def parse_strokes(strokes: list, dx: float, snap_eps: float = 8.0, min_edge_length: float | None = None) -> SigilGraph:
    """Sloppy drawings must parse the way they look (§4.3) — near-crossings
    and near-touching endpoints within snap_eps are snapped into real nodes.
    """
    if not strokes:
        return SigilGraph()

    if min_edge_length is None:
        min_edge_length = dx * 4  # §4.3: no edge should quantize below ~4 samples

    resampled = [s.resampled(dx) for s in strokes]
    split_indices = [set([0, len(pts) - 1]) for pts in resampled]

    min_index_gap = max(3, int(round(snap_eps / dx)))

    for i in range(len(resampled)):
        pts_i = resampled[i]
        for j in range(i, len(resampled)):
            pts_j = resampled[j]
            for a in range(len(pts_i)):
                for b in range(len(pts_j)):
                    if i == j and abs(a - b) < min_index_gap:
                        continue
                    if (pts_i[a] - pts_j[b]).length_squared() < snap_eps * snap_eps:
                        split_indices[i].add(a)
                        split_indices[j].add(b)

    candidates = [(i, a) for i in range(len(resampled)) for a in split_indices[i]]
    uf = _UnionFind()
    for idx1 in range(len(candidates)):
        i, a = candidates[idx1]
        for idx2 in range(idx1 + 1, len(candidates)):
            j, b = candidates[idx2]
            if (resampled[i][a] - resampled[j][b]).length_squared() < snap_eps * snap_eps:
                uf.union((i, a), (j, b))

    cluster_points: dict = {}
    for key in candidates:
        cluster_points.setdefault(uf.find(key), []).append(resampled[key[0]][key[1]])

    root_to_node_id: dict = {}
    nodes: dict = {}
    for node_id, (root, pts) in enumerate(cluster_points.items()):
        avg = sum(pts, pygame.Vector2(0, 0)) / len(pts)
        nodes[node_id] = GraphNode(node_id, avg)
        root_to_node_id[root] = node_id

    edges = []
    for i, pts in enumerate(resampled):
        cuts = sorted(split_indices[i])
        for k in range(len(cuts) - 1):
            a_idx, b_idx = cuts[k], cuts[k + 1]
            if b_idx <= a_idx:
                continue
            sub_poly = list(pts[a_idx : b_idx + 1])

            node_a = root_to_node_id[uf.find((i, a_idx))]
            node_b = root_to_node_id[uf.find((i, b_idx))]
            sub_poly[0] = pygame.Vector2(nodes[node_a].pos)
            sub_poly[-1] = pygame.Vector2(nodes[node_b].pos)

            edge_len = sum((sub_poly[m + 1] - sub_poly[m]).length() for m in range(len(sub_poly) - 1))
            if edge_len < min_edge_length:
                continue

            edges.append(GraphEdge(node_a, node_b, sub_poly, strokes[i].ink_type))

    for edge in edges:
        nodes[edge.node_a].degree += 1
        nodes[edge.node_b].degree += 1

    return SigilGraph(nodes=nodes, edges=edges)
