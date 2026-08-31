"""SigilGraph -> SimNetwork (design doc §4.1, §4.3). Edit-time only, like the
parser. Stage 5 (§9) gives terminals real radiation: Y_rad is a fraction of
the touching edge's own admittance (set by that edge's ink type), rather
than the free-end default (Y_rad=0) used in earlier stages. Stage 7 adds
evanescent couplers between edges that pass close without touching (§2.7).
"""

from .couplers import find_coupler_sites, kappa_for_gap, lowpass_coef_for_gap
from .cycles import find_loop_closing_edges
from .graph import SigilGraph
from .network import Network


def compile_graph(
    graph: SigilGraph, dx: float, snap_eps: float = 8.0, g_max: float = 30.0, max_energy: float = 50.0
) -> Network:
    net = Network()
    net.max_energy = max_energy

    # A terminal is degree-1, so it has exactly one touching edge; that
    # edge's ink decides how hard this open end radiates (§2.4).
    terminal_rad_admittance: dict = {}
    for edge in graph.edges:
        ink = edge.ink_type
        edge_admittance = 1.0 / ink.impedance
        y_rad = ink.rad_admittance_fraction * edge_admittance
        for node_id in (edge.node_a, edge.node_b):
            if graph.nodes[node_id].is_terminal:
                terminal_rad_admittance[node_id] = y_rad

    for node_id, node in graph.nodes.items():
        y_rad = terminal_rad_admittance.get(node_id, 0.0) if node.is_terminal else 0.0
        net.add_node(node_id, rad_admittance=y_rad)

    for edge in graph.edges:
        length_samples = max(4, round(edge.length / dx))
        ink = edge.ink_type
        # §2.5: consolidate N per-sample loss applications into one filter
        # applied once per step, so a longer edge damps more per traversal.
        broadband_gain = ink.broadband_gain_per_sample ** length_samples
        lowpass_coef = ink.lowpass_coef_per_sample ** length_samples
        net.add_edge(
            edge.node_a,
            edge.node_b,
            length_samples,
            impedance=ink.impedance,
            broadband_gain=broadband_gain,
            lowpass_coef=lowpass_coef,
        )

    # Coupler detection relies on add_edge having assigned edge_id 0..N-1 in
    # the same order as graph.edges, which the loop above guarantees.
    for site in find_coupler_sites(graph, dx, snap_eps=snap_eps, g_max=g_max):
        kappa = kappa_for_gap(site.gap, g_max)
        coupler_lowpass = lowpass_coef_for_gap(site.gap, g_max)
        pos_a_samples = round(site.pos_a / dx)
        pos_b_samples = round(site.pos_b / dx)
        net.add_coupler(site.edge_a, pos_a_samples, site.edge_b, pos_b_samples, kappa, coupler_lowpass)

    # §2.6: nonlinearity is sited at junctions that actually close a loop —
    # every closed loop has at least one, even a plain circle (its own
    # start-meets-end node). Nodes touched by no loop stay purely linear.
    for edge_idx in find_loop_closing_edges(graph):
        edge = graph.edges[edge_idx]
        ink = edge.ink_type
        a = 1.0 / ink.nl_threshold
        d = ink.nl_threshold * ink.nl_asymmetry
        for node_id in (edge.node_a, edge.node_b):
            net.nodes[node_id].nl_a = a
            net.nodes[node_id].nl_d = d

    return net
