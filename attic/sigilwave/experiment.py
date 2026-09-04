"""Headless experiment harness (no display needed) for exploring which sigil
shapes / ink parameters / drive patterns produce the gameplay-meaningful
effects the design doc names in §3 and §10 — shields, teleports, parries,
elements, overcharge, etc. Same Ink -> Parser -> Compiler -> Sim -> Analyzer
-> Coupler pipeline sigil_lab.py uses, just callable from a script and
inspectable as numbers/JSON instead of only as pixels.

Typical use:

    from sigilwave.experiment import Sim, circle_points, tap, held_tone

    sim = Sim([Stroke(points=circle_points((0, 0), 80), ink_type=my_ink)])
    records = sim.run(2000, drive_fn=tap(sim.terminals[:1], amplitude=1.0))
    print(sim.network.total_energy())
"""

import json
import math
import os

import pygame

from .ink import InkType, Stroke
from .sim.compiler import compile_graph
from .sim.coupling import (
    kinetic_drive_from_bands,
    phase_drive_from_bands,
    thermal_drive_from_bands,
)
from .sim.cycles import compute_chirality
from .sim.filterbank import FilterBank
from .sim.network import raised_cosine_burst
from .sim.parser import parse_strokes
from .world import Token

# Same reference constants sigil_lab.py uses, so results transfer directly.
DX = 4.0
WAVE_SPEED_C = 400.0
FIXED_DT = DX / WAVE_SPEED_C
SNAP_EPS = 8.0
COUPLER_G_MAX = 30.0
DEFAULT_MAX_ENERGY = 50.0


# ---------------------------------------------------------------------------
# Shape generators — parametric strokes for building scenarios programmatically.
# ---------------------------------------------------------------------------

def circle_points(center, radius, n=48):
    center = pygame.Vector2(center)
    return [center + pygame.Vector2(radius, 0).rotate(360.0 * i / n) for i in range(n + 1)]


def line_points(p0, p1, n=24):
    p0, p1 = pygame.Vector2(p0), pygame.Vector2(p1)
    return [p0 + (p1 - p0) * (i / n) for i in range(n + 1)]


def spiral_points(center, r0, r1, turns, n=96):
    center = pygame.Vector2(center)
    pts = []
    for i in range(n + 1):
        t = i / n
        r = r0 + (r1 - r0) * t
        pts.append(center + pygame.Vector2(r, 0).rotate(360.0 * turns * t))
    return pts


def zigzag_points(p0, p1, amplitude, cycles, n=48):
    """A straight run with a wiggle — extra path length / high spatial
    frequency content packed into the same span."""
    p0, p1 = pygame.Vector2(p0), pygame.Vector2(p1)
    axis = p1 - p0
    length = axis.length()
    if length < 1e-6:
        return [p0, p1]
    dir_along = axis / length
    dir_perp = pygame.Vector2(-dir_along.y, dir_along.x)
    pts = []
    for i in range(n + 1):
        t = i / n
        base = p0 + axis * t
        offset = amplitude * math.sin(2 * math.pi * cycles * t)
        pts.append(base + dir_perp * offset)
    return pts


def loop_with_tail_points(center, radius, tail_length, n=48, clockwise=True):
    """A closed loop cannot radiate on its own — a terminal is a degree-1
    node with the Y_rad port that actually leaks energy out (§2.4), and a
    bare circle has none. This is the shape that actually demonstrates
    chirality's push/pull, burn/chill sign flip (§2.8): a loop (for the
    resonance and the winding sign) with a short open tail (the terminal the
    world actually reads). Matches the doc's own charge-and-release pattern
    — loop stores, terminal discharges."""
    center = pygame.Vector2(center)
    sign = 1.0 if clockwise else -1.0
    attach = center + pygame.Vector2(radius, 0)
    tip = center + pygame.Vector2(radius + tail_length, 0)
    tail = line_points(tip, attach, n=max(2, int(tail_length // 8)))
    loop = [center + pygame.Vector2(radius, 0).rotate(sign * 360.0 * i / n) for i in range(n + 1)]
    return tail[:-1] + loop


def tapered_line_points(p0, p1, n=24):
    """Geometry alone can't taper impedance in this model (Z is per-ink,
    §2.2) — kept for visual/topology experiments, not impedance tapering."""
    return line_points(p0, p1, n)


# ---------------------------------------------------------------------------
# Drive patterns — callables of (step_i, sim) -> injections dict, matching
# Sim.run's drive_fn contract.
# ---------------------------------------------------------------------------

def tap(node_ids, amplitude=1.0, burst_len=24):
    """A single raised-cosine burst at t=0 (§4.3): broadband, one hit."""
    burst = raised_cosine_burst(burst_len, amplitude=amplitude)

    def drive(step_i, sim):
        if step_i < len(burst):
            return {nid: burst[step_i] for nid in node_ids}
        return None

    return drive


def held_tone(node_ids, frequency, amplitude=1.0, attack_steps=200, duration_steps=None):
    """A sustained narrowband tone at `frequency` (cycles/sample) — the
    doc's 'held tap' (§4.3), and the only clean way to drive a specific
    resonance without exciting every harmonic at once."""

    def drive(step_i, sim):
        if duration_steps is not None and step_i >= duration_steps:
            return None
        attack = min(1.0, step_i / max(1, attack_steps))
        sample = amplitude * attack * math.sin(2 * math.pi * frequency * step_i)
        return {nid: sample for nid in node_ids}

    return drive


def repeated_taps(node_ids, period_steps, amplitude=1.0, burst_len=8, n_taps=20, phase_offset_steps=0):
    """Tapping on a beat (§4.3's rhythm mechanic) — in-phase with a loop's
    own f0 builds resonance; off-beat (large phase_offset_steps relative to
    period) cancels the player's own buildup."""
    burst = raised_cosine_burst(burst_len, amplitude=amplitude)

    def drive(step_i, sim):
        s = step_i - phase_offset_steps
        if s < 0:
            return None
        tap_index = s // period_steps
        if tap_index >= n_taps:
            return None
        offset = s % period_steps
        if offset >= len(burst):
            return None
        return {nid: burst[offset] for nid in node_ids}

    return drive


def dual_tap(node_ids_a, node_ids_b, amplitude=1.0, burst_len=24, delay_steps=0, sign_b=1.0):
    """Two ignition points, optionally phase/time offset — for parry
    (antiphase cancellation, §3) and dual-loop beat-frequency experiments.
    Injections add rather than overwrite, so if node_ids_a and node_ids_b
    share a node the two bursts genuinely superpose there (matching how a
    real network junction would combine them) instead of one silently
    clobbering the other."""
    burst = raised_cosine_burst(burst_len, amplitude=amplitude)

    def drive(step_i, sim):
        injections = {}
        if step_i < len(burst):
            for nid in node_ids_a:
                injections[nid] = injections.get(nid, 0.0) + burst[step_i]
        j = step_i - delay_steps
        if 0 <= j < len(burst):
            for nid in node_ids_b:
                injections[nid] = injections.get(nid, 0.0) + sign_b * burst[j]
        return injections or None

    return drive


# ---------------------------------------------------------------------------
# The harness itself.
# ---------------------------------------------------------------------------

class Sim:
    """One compiled sigil (strokes -> graph -> network) plus a token,
    steppable and fully inspectable without a display. Mirrors sigil_lab.py's
    SigilLab.step_sim exactly, so numbers measured here transfer to the
    interactive lab and vice versa."""

    def __init__(self, strokes, dx=DX, snap_eps=SNAP_EPS, g_max=COUPLER_G_MAX,
                 token_pos=(0.0, 0.0), max_energy=DEFAULT_MAX_ENERGY):
        self.dx = dx
        self.strokes = strokes
        self.graph = parse_strokes(strokes, dx, snap_eps=snap_eps)
        self.network = compile_graph(self.graph, dx, snap_eps=snap_eps, g_max=g_max, max_energy=max_energy)
        self.band_centers = FilterBank().centers
        self.chirality = compute_chirality(self.graph, self.band_centers, dx)
        self.terminals = [nid for nid, n in self.graph.nodes.items() if n.is_terminal]
        self.internal_nodes = [nid for nid, n in self.graph.nodes.items() if not n.is_terminal]
        self.terminal_filters = {nid: FilterBank() for nid in self.terminals}
        self.token = Token(pygame.Vector2(token_pos))
        self.time = 0.0
        self.injected_energy_proxy = 0.0
        self.radiated_energy_total = 0.0

    def all_nodes(self):
        return list(self.graph.nodes.keys())

    def step(self, injections=None):
        injections = injections or {}
        for v in injections.values():
            self.injected_energy_proxy += v * v
        radiated = self.network.step(injections)
        self.radiated_energy_total += radiated

        drives = {}
        for node_id, bank in self.terminal_filters.items():
            sample = self.network.nodes[node_id].last_emitted
            bands = bank.process(sample)
            drives[node_id] = {
                "kinetic": kinetic_drive_from_bands(bands, self.chirality),
                "thermal": thermal_drive_from_bands(bands, self.chirality),
                "phase": phase_drive_from_bands(bands),
                "bands": list(bands),
                "last_emitted": sample,
            }
        self.time += FIXED_DT
        return radiated, drives

    def apply_world_coupling(self, drives, heading_by_node=None,
                              kinetic_scale=40000.0, thermal_scale=400.0, phase_scale=40.0):
        """Optional: push a step's drives into self.token, same scaling
        sigil_lab.py uses, for experiments that care about token motion."""
        for node_id, d in drives.items():
            heading = heading_by_node.get(node_id, pygame.Vector2(1, 0)) if heading_by_node else pygame.Vector2(1, 0)
            self.token.apply_kinetic_impulse(heading * d["kinetic"] * kinetic_scale * FIXED_DT)
            self.token.apply_thermal(d["thermal"] * thermal_scale * FIXED_DT)
            self.token.apply_phase(d["phase"] * phase_scale * FIXED_DT)
        self.token.update(FIXED_DT, pygame.Rect(-100000, -100000, 200000, 200000))

    def run(self, n_steps, drive_fn=None, record_every=1, track_token=False, heading_by_node=None):
        records = []
        for i in range(n_steps):
            injections = drive_fn(i, self) if drive_fn else None
            radiated, drives = self.step(injections)
            if track_token:
                self.apply_world_coupling(drives, heading_by_node)
            if record_every and i % record_every == 0:
                rec = {
                    "step": i,
                    "t": self.time,
                    "network_energy": self.network.total_energy(),
                    "radiated": radiated,
                    "drives": drives,
                }
                if track_token:
                    rec["token_pos"] = (self.token.pos.x, self.token.pos.y)
                    rec["token_vel"] = (self.token.vel.x, self.token.vel.y)
                    rec["token_temperature"] = self.token.temperature
                    rec["token_phase"] = self.token.phase
                records.append(rec)
        return records

    def efficiency(self):
        """Crude proxy for the doc's mana efficiency (§6): radiated / injected,
        both in the same (amplitude^2-ish) units. Not calibrated to a real
        energy unit — useful only for comparing scenarios against each other."""
        if self.injected_energy_proxy < 1e-12:
            return 0.0
        return self.radiated_energy_total / self.injected_energy_proxy


def terminal_heading(graph, node_id):
    """Copied from sigil_lab.py's terminal_heading — kept independent here so
    the harness has no import-time dependency on the pygame-display-using lab
    module."""
    for edge in graph.edges:
        if edge.node_a == node_id and len(edge.polyline) >= 2:
            tail = edge.polyline[0] - edge.polyline[1]
            return tail.normalize() if tail.length_squared() > 1e-9 else pygame.Vector2(1, 0)
        if edge.node_b == node_id and len(edge.polyline) >= 2:
            tail = edge.polyline[-1] - edge.polyline[-2]
            return tail.normalize() if tail.length_squared() > 1e-9 else pygame.Vector2(1, 0)
    return pygame.Vector2(0, 0)


def save_records(records, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def default(o):
        if isinstance(o, pygame.Vector2):
            return [o.x, o.y]
        return float(o)

    with open(path, "w") as f:
        json.dump(records, f, indent=2, default=default)
