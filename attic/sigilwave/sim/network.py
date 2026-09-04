"""Minimal waveguide network: edges as bidirectional delay-line pairs,
scattering at nodes (design doc §2.3, §2.4). This is stage 1 of the build
order in §9 — just enough to watch reflection and interference on screen
before any parser/compiler exists to generate it from a drawing.

Every step is strictly split into read -> scatter -> write (§4.3's own
pseudocode), because collapsing those phases per-node makes the result
depend on node iteration order: a node that writes a line another node is
about to read in the same step would short-circuit the delay entirely.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from .delayline import DelayLine, LossFilter, OnePoleLowpass


@dataclass
class Edge:
    edge_id: int
    node_a: int
    node_b: int
    length_samples: int
    impedance: float  # Z
    broadband_gain: float = 1.0
    lowpass_coef: float = 1.0

    def __post_init__(self) -> None:
        # forward: A -> B. backward: B -> A.
        self.forward = DelayLine(self.length_samples)
        self.backward = DelayLine(self.length_samples)
        self.loss_a_to_b = LossFilter(self.broadband_gain, self.lowpass_coef)
        self.loss_b_to_a = LossFilter(self.broadband_gain, self.lowpass_coef)

    @property
    def admittance(self) -> float:
        return 1.0 / self.impedance

    def read_incident_a(self) -> float:
        """Loss-filtered sample arriving at A this step (read-only)."""
        return self.loss_b_to_a.process(self.backward.read_tail())

    def read_incident_b(self) -> float:
        """Loss-filtered sample arriving at B this step (read-only)."""
        return self.loss_a_to_b.process(self.forward.read_tail())

    def total_energy(self) -> float:
        y = self.admittance
        return self.forward.energy(y) + self.backward.energy(y)


@dataclass
class Port:
    edge: Edge
    is_a_side: bool


@dataclass
class Node:
    node_id: int
    ports: list = field(default_factory=list)  # list[Port]
    rad_admittance: float = 0.0  # Y_rad; 0 = free end / lossless internal junction
    last_emitted: float = 0.0  # u_j from the most recent scatter(); what a terminal's analyzer listens to
    nl_a: float | None = None  # nonlinearity steepness (§2.6); None = linear junction
    nl_d: float = 0.0  # asymmetry offset — this is what buys even harmonics

    def add_port(self, edge: Edge, is_a_side: bool) -> None:
        self.ports.append(Port(edge, is_a_side))

    def scatter(
        self,
        incident_a: dict,
        incident_b: dict,
        pending_forward: dict,
        pending_backward: dict,
        injected: float = 0.0,
    ) -> float:
        """Junction scattering (§2.3/§2.4) using already-held incident
        values. Writes pending outputs; does not touch buffers directly.
        Returns radiated energy this step (0 unless rad_admittance > 0)."""
        sum_y = self.rad_admittance
        sum_yu = 0.0
        incident = []
        for port in self.ports:
            eid = port.edge.edge_id
            u_plus = incident_a[eid] if port.is_a_side else incident_b[eid]
            y = port.edge.admittance
            sum_y += y
            sum_yu += y * u_plus
            incident.append((port, u_plus))

        u_j = (2.0 * sum_yu / sum_y) + injected if sum_y > 0 else injected

        if self.nl_a is not None:
            # Asymmetric saturating map (§2.6). Passes through the origin
            # regardless of d, and is near-identity for |u_j| well under
            # ~1/nl_a — the "threshold" the doc describes isn't a hard
            # branch, it's just where this smooth curve visibly bends.
            a, d = self.nl_a, self.nl_d
            u_j = (math.tanh(a * (u_j + d)) - math.tanh(a * d)) / a

        self.last_emitted = u_j

        for port, u_plus in incident:
            u_minus = u_j - u_plus
            eid = port.edge.edge_id
            if port.is_a_side:
                pending_forward[eid] = u_minus
            else:
                pending_backward[eid] = u_minus

        return (u_j ** 2) * self.rad_admittance


class CouplerChannel:
    """One direction-pair of an evanescent coupler (§2.7): a 2x2 rotation
    where the cross-coupled term is low-pass filtered (long wavelengths
    tunnel further) while the straight-through term stays full-band. That
    filtering means the rotation is only approximately lossless, so a
    passivity clamp (§8) scales the output down if it ever exceeds the
    input energy.
    """

    def __init__(self, kappa: float, lowpass_coef: float):
        self.kappa = kappa
        self.scale = math.sqrt(max(0.0, 1.0 - kappa * kappa))
        self.lp_b_into_a = OnePoleLowpass(lowpass_coef)
        self.lp_a_into_b = OnePoleLowpass(lowpass_coef)

    def process(self, a_in: float, b_in: float) -> tuple[float, float]:
        b_leak = self.lp_b_into_a.process(b_in)
        a_leak = self.lp_a_into_b.process(a_in)
        a_out = self.scale * a_in + self.kappa * b_leak
        b_out = self.scale * b_in - self.kappa * a_leak

        e_in = a_in * a_in + b_in * b_in
        e_out = a_out * a_out + b_out * b_out
        if e_out > e_in and e_out > 1e-15:
            factor = math.sqrt(e_in / e_out)
            a_out *= factor
            b_out *= factor

        return a_out, b_out


class Coupler:
    def __init__(self, edge_a: Edge, pos_a: int, edge_b: Edge, pos_b: int, kappa: float, lowpass_coef: float):
        self.edge_a = edge_a
        self.pos_a = pos_a
        self.edge_b = edge_b
        self.pos_b = pos_b
        self.kappa = kappa
        self.forward_channel = CouplerChannel(kappa, lowpass_coef)
        self.backward_channel = CouplerChannel(kappa, lowpass_coef)

    def process(self) -> None:
        len_a = self.edge_a.forward.length
        len_b = self.edge_b.forward.length

        a_f = self.edge_a.forward.peek(self.pos_a)
        b_f = self.edge_b.forward.peek(self.pos_b)
        new_a_f, new_b_f = self.forward_channel.process(a_f, b_f)

        a_b = self.edge_a.backward.peek(len_a - 1 - self.pos_a)
        b_b = self.edge_b.backward.peek(len_b - 1 - self.pos_b)
        new_a_b, new_b_b = self.backward_channel.process(a_b, b_b)

        self.edge_a.forward.poke(self.pos_a, new_a_f)
        self.edge_b.forward.poke(self.pos_b, new_b_f)
        self.edge_a.backward.poke(len_a - 1 - self.pos_a, new_a_b)
        self.edge_b.backward.poke(len_b - 1 - self.pos_b, new_b_b)


class Network:
    def __init__(self):
        self.edges: dict[int, Edge] = {}
        self.nodes: dict[int, Node] = {}
        self.couplers: list[Coupler] = []
        self._next_edge_id = 0
        # §8: nonlinearity + feedback loops are the most likely way this
        # design dies. A hard ceiling is the mitigation the doc names
        # explicitly — None disables it (used by tests that want to see
        # unclamped behavior).
        self.max_energy: float | None = None

    def add_node(self, node_id: int, rad_admittance: float = 0.0) -> Node:
        node = Node(node_id, rad_admittance=rad_admittance)
        self.nodes[node_id] = node
        return node

    def add_edge(
        self,
        node_a: int,
        node_b: int,
        length_samples: int,
        impedance: float,
        broadband_gain: float = 1.0,
        lowpass_coef: float = 1.0,
    ) -> Edge:
        edge_id = self._next_edge_id
        self._next_edge_id += 1
        edge = Edge(edge_id, node_a, node_b, length_samples, impedance, broadband_gain, lowpass_coef)
        self.edges[edge_id] = edge
        self.nodes[node_a].add_port(edge, is_a_side=True)
        self.nodes[node_b].add_port(edge, is_a_side=False)
        return edge

    def add_coupler(self, edge_a_id: int, pos_a: int, edge_b_id: int, pos_b: int, kappa: float, lowpass_coef: float) -> Coupler:
        edge_a = self.edges[edge_a_id]
        edge_b = self.edges[edge_b_id]
        pos_a = max(0, min(edge_a.length_samples - 1, pos_a))
        pos_b = max(0, min(edge_b.length_samples - 1, pos_b))
        coupler = Coupler(edge_a, pos_a, edge_b, pos_b, kappa, lowpass_coef)
        self.couplers.append(coupler)
        return coupler

    def step(self, injections: dict[int, float] | None = None) -> float:
        """Advance the whole network by one fixed sim step. Returns total
        radiated energy this step (summed over all terminals)."""
        injections = injections or {}

        incident_a = {eid: edge.read_incident_a() for eid, edge in self.edges.items()}
        incident_b = {eid: edge.read_incident_b() for eid, edge in self.edges.items()}
        pending_forward: dict[int, float] = {}
        pending_backward: dict[int, float] = {}

        radiated = 0.0
        for node_id, node in self.nodes.items():
            radiated += node.scatter(
                incident_a, incident_b, pending_forward, pending_backward, injections.get(node_id, 0.0)
            )

        for eid, edge in self.edges.items():
            edge.forward.push(pending_forward[eid])
            edge.backward.push(pending_backward[eid])

        # Couplers touch interior buffer slots the junction phase above
        # never reads or writes this same step (as long as a coupler isn't
        # placed at the very ends), so operating on the just-written state
        # here is safe regardless of order relative to the phases above.
        for coupler in self.couplers:
            coupler.process()

        if self.max_energy is not None:
            self._clamp_energy()

        return radiated

    def _clamp_energy(self) -> None:
        total = self.total_energy()
        if total > self.max_energy and total > 1e-15:
            factor = math.sqrt(self.max_energy / total)
            for edge in self.edges.values():
                edge.forward.buffer *= factor
                edge.backward.buffer *= factor

    def total_energy(self) -> float:
        return sum(edge.total_energy() for edge in self.edges.values())


def raised_cosine_burst(n_samples: int, amplitude: float = 1.0) -> list:
    """Injection pulse shape (§4.3): a raised-cosine burst. Burst length sets
    bandwidth — short is broadband, long is a near-tone."""
    if n_samples < 1:
        return []
    t = np.linspace(0, 1, n_samples, endpoint=False)
    window = 0.5 * (1 - np.cos(2 * np.pi * t))
    return (amplitude * window).tolist()
