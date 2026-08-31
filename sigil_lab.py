"""Build order §9, stages 2-8: Parser + Compiler, damping, terminals + filter
bank + kinetic field, chirality + the full three-field coupling matrix,
evanescent couplers (tunneling), and now nonlinearity — the last and
riskiest piece of the physical model (§2.6, §8).

Draw ink with the mouse; it gets parsed into a SigilGraph and compiled into
a live SimNetwork, same pipeline a real cast would use. Every open end
radiates (§2.4); that radiated waveform runs through a per-terminal filter
bank (§2.9). Chirality (§2.8) — a property of the sigil's closed loops, CW
vs CCW — decides the *sign* of the kinetic and thermal coupling: the same
shape drawn the other way round pulls instead of pushes, chills instead of
burns. A loop is what gives a sigil chirality a *sign* at all; a shape with
no closed loop has no sign to read and defaults to a plain outward
push/burn instead of going silent (see cycles.compute_chirality).
Two strokes drawn close together without touching (closer than g_max, but
not close enough to snap into a real junction) get an evanescent coupler
(§2.7) — energy tunnels across the gap, favoring long wavelengths.

Controls:
  LEFT DRAG   draw a stroke
  SPACE       inject a burst at every open end (or every node, if the sigil
              has no open ends — e.g. a closed loop)
  C           clear all ink
  P           dump a screenshot to debug_output/
  ESC         quit
"""

import math
import os

import numpy as np
import pygame

from sigilwave.ink import DEFAULT_INK, Stroke
from sigilwave.scenarios import SCENARIOS, scenario_by_key
from sigilwave.sim.compiler import compile_graph
from sigilwave.sim.coupling import (
    kinetic_drive_from_bands,
    phase_drive_from_bands,
    thermal_drive_from_bands,
)
from sigilwave.sim.couplers import find_coupler_sites, kappa_for_gap
from sigilwave.sim.cycles import compute_chirality, find_loop_closing_nodes
from sigilwave.sim.filterbank import FilterBank
from sigilwave.sim.network import raised_cosine_burst
from sigilwave.sim.parser import parse_strokes
from sigilwave.world import Token

DEBUG_SCREENSHOT_PATH = os.path.join(os.path.dirname(__file__), "debug_output", "sigil_lab_debug.png")

WIDTH, HEIGHT = 1200, 800
DX = 4.0  # coarser than the design doc's dx=1 so parsing stays snappy interactively
WAVE_SPEED_C = 400.0  # px/s — the design doc's own reference value (§5); c is global and constant
FIXED_DT = DX / WAVE_SPEED_C  # dt = dx/c (§5), so this is the actual knob for how fast ink "feels"
SNAP_EPS = 8.0
COUPLER_G_MAX = 30.0
AMPLITUDE_SCALE = 4.0  # brightness sensitivity
HELD_TONE_ATTACK_STEPS = 60  # ramp-up so a held tone doesn't itself start as a broadband click
HELD_TONE_AMPLITUDE = 0.8
# An un-looped shape has no single resonance to lock onto, so holding H
# instead drives a low (kinetic-band) + high (phase-band) tone together —
# verified this is what it actually takes to cross PHASE_GHOST_THRESHOLD at
# all (a single low tone alone never does, per experiment_reports/
# couplers_nonlinearity_phase.md) — while a looped shape locks to its own f0
# (a single frequency at resonance, for overcharge/charge-and-release).
HELD_TONE_KINETIC_FREQ = 0.015
HELD_TONE_PHASE_FREQ = 0.38
HELD_TONE_PHASE_AMPLITUDE = 2.4
KINETIC_IMPULSE_SCALE = 40000.0  # tuned empirically against selftest_terminal's measured drive magnitudes
THERMAL_SCALE = 400.0
PHASE_SCALE = 40.0
BAND_CENTERS = FilterBank().centers  # a shared reference; chirality is computed once per band, not per terminal

COLOR_BG = (10, 11, 15)
COLOR_STROKE_LIVE = (90, 100, 115)
COLOR_NODE_INTERNAL = (140, 150, 165)
COLOR_NODE_TERMINAL = (240, 220, 140)
COLOR_TEXT = (170, 190, 205)
COLOR_BASE_INK = (40, 46, 58)
COLOR_TOKEN = (180, 230, 150)
COLOR_NL_FLASH = (255, 240, 120)


def terminal_heading(graph, node_id: int) -> pygame.Vector2:
    """Direction the stroke was heading when it reached this open end,
    extended outward — what the kinetic impulse pushes along (§2.1: the
    traveling-wave decomposition hands terminals an emission heading)."""
    for edge in graph.edges:
        if edge.node_a == node_id and len(edge.polyline) >= 2:
            tail = edge.polyline[0] - edge.polyline[1]
            return tail.normalize() if tail.length_squared() > 1e-9 else pygame.Vector2(1, 0)
        if edge.node_b == node_id and len(edge.polyline) >= 2:
            tail = edge.polyline[-1] - edge.polyline[-2]
            return tail.normalize() if tail.length_squared() > 1e-9 else pygame.Vector2(1, 0)
    return pygame.Vector2(0, 0)


def amplitude_color(value: float) -> tuple:
    """Brightness by |amplitude|, hue by sign — a cheap stand-in for the real
    frequency->hue mapping planned in §7 once bands exist."""
    mag = min(1.0, abs(value) * AMPLITUDE_SCALE)
    if value >= 0:
        base = np.array([120, 200, 230])
    else:
        base = np.array([230, 150, 110])
    color = np.array(COLOR_BASE_INK) + (base - np.array(COLOR_BASE_INK)) * mag
    return tuple(int(c) for c in color)


class SigilLab:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Sigil / Wave — stage 2: parser + compiler")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.font = pygame.font.SysFont("consolas", 16)
        self.clock = pygame.time.Clock()
        self.running = True

        self.strokes: list[Stroke] = []
        self.current_stroke: Stroke | None = None
        self.graph = parse_strokes([], DX)
        self.network = compile_graph(self.graph, DX)
        self.terminal_filters: dict = {}
        self.terminal_headings: dict = {}
        self.chirality: list = [0.0] * len(BAND_CENTERS)
        self.coupler_sites: list = []

        self.pending_burst: list = []
        self.pending_burst_targets: list = []
        self.pending_burst_i = 0

        # §4.3: "a quick tap is broadband, a held tap is a narrowband tone."
        # SPACE (above) is the quick tap; holding H is the sustained tone —
        # the only way to actually drive resonance-buildup, overcharge, or
        # a high enough phase reading to ghost, none of which a short burst
        # can reach (verified directly: even 30 rapid re-taps never cross
        # PHASE_GHOST_THRESHOLD).
        self.held_tone_active = False
        self.held_tone_targets: list = []
        self.held_tone_freq = HELD_TONE_KINETIC_FREQ
        self.held_tone_is_loop = False
        self.held_tone_steps = 0

        self.token = Token(pygame.Vector2(WIDTH / 2, HEIGHT / 2))
        self.time = 0.0

        # §7's live efficiency meter: useful radiated energy vs. what was
        # injected. Crude proxy (amplitude^2 units, not a calibrated energy
        # unit) but consistent enough to compare sigils against each other.
        self.injected_energy = 0.0
        self.radiated_energy = 0.0
        self.active_scenario_name: str | None = None

    def recompile(self) -> None:
        self.graph = parse_strokes(self.strokes, DX, snap_eps=SNAP_EPS)
        self.network = compile_graph(self.graph, DX, snap_eps=SNAP_EPS, g_max=COUPLER_G_MAX)

        terminals = [nid for nid, n in self.graph.nodes.items() if n.is_terminal]
        self.terminal_filters = {nid: FilterBank() for nid in terminals}
        self.terminal_headings = {nid: terminal_heading(self.graph, nid) for nid in terminals}
        # Chirality is a property of the whole sigil's loops (§2.8), computed
        # once per edit — not per terminal, not per step.
        self.chirality = compute_chirality(self.graph, BAND_CENTERS, DX)
        # Recomputed here (compile_graph already did this once internally)
        # purely to get world-space positions for the shimmer overlay (§7).
        self.coupler_sites = find_coupler_sites(self.graph, DX, snap_eps=SNAP_EPS, g_max=COUPLER_G_MAX)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self._inject_burst()
                elif event.key == pygame.K_h:
                    self._start_held_tone()
                elif event.key == pygame.K_c:
                    self.strokes.clear()
                    self.active_scenario_name = None
                    self.injected_energy = 0.0
                    self.radiated_energy = 0.0
                    self.held_tone_active = False
                    self.recompile()
                elif event.key == pygame.K_p:
                    self._save_debug_screenshot()
                elif event.unicode and event.unicode in "123456789":
                    self._load_scenario(event.unicode)
            elif event.type == pygame.KEYUP and event.key == pygame.K_h:
                self.held_tone_active = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.current_stroke = Stroke(ink_type=DEFAULT_INK)
                self.current_stroke.add_point(pygame.Vector2(event.pos))
            elif event.type == pygame.MOUSEMOTION and self.current_stroke is not None:
                self.current_stroke.add_point(pygame.Vector2(event.pos))
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.current_stroke is not None:
                    self.current_stroke.add_point(pygame.Vector2(event.pos))
                    if len(self.current_stroke.points) >= 2:
                        self.strokes.append(self.current_stroke)
                        self.recompile()
                    self.current_stroke = None

    def _inject_burst(self) -> None:
        # A single ignition point (§4.3), not every open end at once: hitting
        # every terminal together made a plain symmetric line's kinetic
        # pushes cancel exactly (each end recoils opposite the other),
        # masking the very effect stage 5 is supposed to demonstrate.
        #
        # Prefer a loop-closing junction over a terminal when one exists:
        # a terminal's own Y_rad leak bleeds each tap straight back out
        # before repeated on-beat tapping (§4.3's resonance mechanic) can
        # build anything, whereas the junction is where the loop actually
        # accumulates energy — measured directly (experiment_reports/
        # chirality_elements_resonance.md): tapping the terminal barely
        # outperforms a single tap (~1.8x after 20+ on-beat taps) while
        # tapping the junction reaches 2.3-2.7x.
        loop_junctions = list(find_loop_closing_nodes(self.graph))
        terminals = [nid for nid, n in self.graph.nodes.items() if n.is_terminal]
        candidates = loop_junctions or terminals or list(self.graph.nodes.keys())
        self.pending_burst_targets = candidates[:1]
        self.pending_burst = raised_cosine_burst(24, amplitude=1.0)
        self.pending_burst_i = 0

    def _start_held_tone(self) -> None:
        """H: hold for a sustained narrowband tone (§4.3) instead of SPACE's
        quick broadband tap — this is the only way to actually drive
        resonance buildup, overcharge, or a phase reading high enough to
        ghost. Same ignition-site preference as _inject_burst (loop
        junction over terminal). Frequency locks to the sigil's own loop f0
        when it has one, so holding H taps it at exactly its resonance;
        an un-looped shape falls back to a fixed generic frequency."""
        loop_junctions = list(find_loop_closing_nodes(self.graph))
        terminals = [nid for nid, n in self.graph.nodes.items() if n.is_terminal]
        candidates = loop_junctions or terminals or list(self.graph.nodes.keys())
        if not candidates:
            return
        self.held_tone_targets = candidates[:1]
        self.held_tone_steps = 0

        self.held_tone_freq = HELD_TONE_KINETIC_FREQ
        self.held_tone_is_loop = False
        for edge in self.network.edges.values():
            if edge.node_a == edge.node_b:  # a self-loop edge closes a loop
                self.held_tone_freq = 1.0 / edge.forward.length
                self.held_tone_is_loop = True
                break
        self.held_tone_active = True

    def _load_scenario(self, key: str) -> None:
        scenario = scenario_by_key(key)
        if scenario is None:
            return
        center = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.strokes = [
            Stroke(points=[center + pygame.Vector2(p) for p in s.points], ink_type=s.ink)
            for s in scenario.strokes
        ]
        self.active_scenario_name = scenario.name
        self.injected_energy = 0.0
        self.radiated_energy = 0.0
        self.held_tone_active = False
        self.token = Token(center)
        self.recompile()
        print(f"[scenario] loaded '{scenario.name}': {scenario.description}")
        print(f"[scenario] drive: {scenario.drive_hint}")

    def _save_debug_screenshot(self) -> None:
        os.makedirs(os.path.dirname(DEBUG_SCREENSHOT_PATH), exist_ok=True)
        pygame.image.save(self.screen, DEBUG_SCREENSHOT_PATH)
        print(f"[debug] screenshot saved to {DEBUG_SCREENSHOT_PATH}")

    def step_sim(self) -> None:
        injections = {}
        if self.pending_burst_i < len(self.pending_burst):
            sample = self.pending_burst[self.pending_burst_i]
            for node_id in self.pending_burst_targets:
                injections[node_id] = injections.get(node_id, 0.0) + sample
            self.pending_burst_i += 1

        if self.held_tone_active:
            attack = min(1.0, self.held_tone_steps / HELD_TONE_ATTACK_STEPS)
            if self.held_tone_is_loop:
                sample = HELD_TONE_AMPLITUDE * attack * math.sin(2 * math.pi * self.held_tone_freq * self.held_tone_steps)
            else:
                low = math.sin(2 * math.pi * self.held_tone_freq * self.held_tone_steps)
                high = math.sin(2 * math.pi * HELD_TONE_PHASE_FREQ * self.held_tone_steps)
                sample = attack * (HELD_TONE_AMPLITUDE * low + HELD_TONE_PHASE_AMPLITUDE * high)
            for node_id in self.held_tone_targets:
                injections[node_id] = injections.get(node_id, 0.0) + sample
            self.held_tone_steps += 1

        for v in injections.values():
            self.injected_energy += v * v

        radiated = self.network.step(injections)
        self.radiated_energy += radiated

        for node_id, bank in self.terminal_filters.items():
            sample = self.network.nodes[node_id].last_emitted
            bands = bank.process(sample)

            kinetic = kinetic_drive_from_bands(bands, self.chirality)
            thermal = thermal_drive_from_bands(bands, self.chirality)
            phase = phase_drive_from_bands(bands)

            heading = self.terminal_headings[node_id]
            self.token.apply_kinetic_impulse(heading * kinetic * KINETIC_IMPULSE_SCALE * FIXED_DT)
            self.token.apply_thermal(thermal * THERMAL_SCALE * FIXED_DT)
            self.token.apply_phase(phase * PHASE_SCALE * FIXED_DT)

        self.token.update(FIXED_DT, pygame.Rect(0, 0, WIDTH, HEIGHT))
        self.time += FIXED_DT

    def _position_on_edge(self, edge_idx: int, pos_px: float) -> pygame.Vector2:
        poly = self.graph.edges[edge_idx].polyline
        idx = max(0, min(len(poly) - 1, round(pos_px / DX)))
        return poly[idx]

    def _draw_couplers(self) -> None:
        """A shimmer across the gap, opacity by current kappa (§7)."""
        for site in self.coupler_sites:
            a = self._position_on_edge(site.edge_a, site.pos_a)
            b = self._position_on_edge(site.edge_b, site.pos_b)
            kappa = kappa_for_gap(site.gap, COUPLER_G_MAX)
            pulse = 0.6 + 0.4 * math.sin(self.time * 6.0)
            alpha = int(220 * kappa * pulse)
            width = max(1, int(2 + 3 * kappa))

            surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(surface, (210, 230, 255, alpha), a, b, width)
            self.screen.blit(surface, (0, 0))

    def _draw_token(self) -> None:
        """Temperature tints the token red (hot) or blue (cold); phase fades
        it out and adds a ghost ring once it's ignoring collision (§2.9)."""
        t = max(-1.0, min(1.0, self.token.temperature))
        base = np.array(COLOR_TOKEN)
        if t >= 0:
            color = base + (np.array([255, 90, 60]) - base) * t
        else:
            color = base + (np.array([90, 170, 255]) - base) * (-t)
        color = tuple(int(c) for c in color)

        alpha = int(255 * (1.0 - 0.7 * self.token.phase))
        surface = pygame.Surface((self.token.radius * 2 + 4,) * 2, pygame.SRCALPHA)
        center = surface.get_width() / 2
        pygame.draw.circle(surface, (*color, alpha), (center, center), self.token.radius)
        if self.token.phase > 0.05:
            ring_alpha = int(180 * self.token.phase)
            pygame.draw.circle(surface, (200, 220, 255, ring_alpha), (center, center), self.token.radius + 3, 2)
        self.screen.blit(surface, (self.token.pos.x - center, self.token.pos.y - center))

    def draw(self) -> None:
        self.screen.fill(COLOR_BG)

        for i, graph_edge in enumerate(self.graph.edges):
            net_edge = self.network.edges[i]
            forward = net_edge.forward.spatial_profile()
            backward = net_edge.backward.spatial_profile()
            displacement = forward[::-1] + backward

            poly = graph_edge.polyline
            n = len(poly)
            for k in range(n - 1):
                sample_idx = min(len(displacement) - 1, int(k / max(1, n - 2) * (len(displacement) - 1)))
                color = amplitude_color(float(displacement[sample_idx]))
                pygame.draw.line(self.screen, color, poly[k], poly[k + 1], 3)

        self._draw_couplers()

        for node_id, node in self.graph.nodes.items():
            net_node = self.network.nodes[node_id]
            color = COLOR_NODE_TERMINAL if node.is_terminal else COLOR_NODE_INTERNAL
            pygame.draw.circle(self.screen, color, node.pos, 5)

            # §7: nodes flash when the nonlinearity actually engages, not
            # just because they're capable of it — engagement means the
            # emitted amplitude is deep enough into the saturating curve to
            # matter (roughly comparable to the ink's own threshold, 1/nl_a).
            if net_node.nl_a is not None and abs(net_node.last_emitted) * net_node.nl_a > 0.5:
                pygame.draw.circle(self.screen, COLOR_NL_FLASH, node.pos, 10, 2)

        if self.current_stroke is not None and len(self.current_stroke.points) >= 2:
            pygame.draw.lines(self.screen, COLOR_STROKE_LIVE, False, self.current_stroke.points, 2)

        self._draw_token()

        total_energy = self.network.total_energy()
        chi_str = ", ".join(f"{c:+.1f}" for c in self.chirality)
        efficiency = self.radiated_energy / self.injected_energy if self.injected_energy > 1e-12 else 0.0
        scenario_keys = ", ".join(f"{s.key}={s.name}" for s in SCENARIOS)
        lines = [
            "LEFT DRAG draw | SPACE tap | HOLD H sustained tone | C clear | P screenshot | ESC quit | 1-9 preload",
            f"strokes={len(self.strokes)}  nodes={len(self.graph.nodes)}  edges={len(self.graph.edges)}  "
            f"energy={total_energy:.4f}  efficiency={efficiency:.3f}",
            f"chirality (low->high band) = [{chi_str}]",
            f"token: temp={self.token.temperature:+.2f}  phase={self.token.phase:.2f}",
            f"scenario: {self.active_scenario_name or '(none — hand-drawn)'}",
            scenario_keys,
        ]
        for i, line in enumerate(lines):
            text = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (12, 10 + i * 18))

        pygame.display.flip()

    def run(self) -> None:
        accumulator = 0.0
        while self.running:
            frame_time = min(self.clock.tick(240) / 1000.0, 0.05)
            self.handle_events()

            accumulator += frame_time
            while accumulator >= FIXED_DT:
                self.step_sim()
                accumulator -= FIXED_DT

            self.draw()

        pygame.quit()


if __name__ == "__main__":
    SigilLab().run()
