"""A Sigil: drawn ink, compiled into a live instrument you can play.

This is the seam between the physics package (which is finished and tested,
and which this module does not modify) and the game. Everything above it —
combat, the forge, enemies — talks to a Sigil and never to a Network.

Three things happen here that the raw sim does not do on its own:

1. **Per-ink coupler reach, with a soft edge.** The sim takes one global
   g_max; materials want their own. The reach of a pair is the *larger* of
   the two inks' reaches, and kappa is tapered to zero at the boundary
   rather than falling off a cliff (the cliff is real in the sim and makes
   "tune your blink range" feel broken right where a player would be
   probing hardest).

2. **Playing.** Tap, hold, and rhythm. A tap is broadband; a hold is a tone
   locked to the sigil's own loop resonance; tapping on the loop's beat
   compounds. None of that is faked — the sim genuinely rings — but the
   readouts here are what let a player *see* it happening.

3. **Char.** The doc's named failure mode (section 8): an overdriven sigil
   burns out. Energy sitting near the clamp ceiling accumulates char, and
   charred ink goes quiet until it cools. This is the only thing standing
   between "hold the button" and "hold the button forever".
"""

import math

import pygame

from sigilwave.ink import Stroke
from sigilwave.sim.compiler import compile_graph
from sigilwave.sim.coupling import (
    kinetic_drive_from_bands,
    phase_drive_from_bands,
    thermal_drive_from_bands,
)
from sigilwave.sim.couplers import find_coupler_sites, lowpass_coef_for_gap
from sigilwave.sim.cycles import compute_chirality, find_cycles, find_loop_closing_nodes
from sigilwave.sim.parser import parse_strokes

from .bands import BAND_CENTERS, BAND_NAMES, N_BANDS, dominant_band, make_bank


def _coupling_at(band: float):
    """The three world couplings, interpolated at a fractional band index.

    Straight off the doc's own data-driven coupling matrix (2.9) — this is a
    lookup into it rather than a new rule."""
    from sigilwave.sim.coupling import (
        KINETIC_BAND_WEIGHTS,
        PHASE_BAND_WEIGHTS,
        THERMAL_BAND_WEIGHTS,
    )

    i = max(0.0, min(float(N_BANDS - 1), band))
    lo = int(i)
    hi = min(N_BANDS - 1, lo + 1)
    f = i - lo
    def at(w):
        return w[lo] + (w[hi] - w[lo]) * f
    return at(KINETIC_BAND_WEIGHTS), at(THERMAL_BAND_WEIGHTS), at(PHASE_BAND_WEIGHTS)


def broadband_tap(n_samples: int, amplitude: float = 1.0) -> list:
    """A zero-mean strike.

    The sim ships `raised_cosine_burst`, which is the doc's own injection
    shape and is a raised-cosine *window* — so it is unipolar, and half its
    energy is at DC. Injecting that is physically fine (it is a pluck), but
    the analyser's lowest band sits at 0.01 cyc/sample with a skirt running
    down toward DC, so every tap of it lands in band 0 no matter what was
    drawn. That silently collapses the entire elemental system: a 20px ring
    and a 400px ring both read as "deep".

    Windowing one full sine cycle instead keeps the raised cosine's smooth
    edges (so the strike is still broadband, not a click) while removing the
    DC term, which hands band selection back to the sigil's own geometry —
    where the design wants it. The sim's version is left untouched; it is
    what the selftests measure against.
    """
    if n_samples < 1:
        return []
    import numpy as np

    t = np.linspace(0, 1, n_samples, endpoint=False)
    window = 0.5 * (1 - np.cos(2 * np.pi * t))
    return (amplitude * window * np.sin(2 * np.pi * t)).tolist()

DX = 4.0                    # px per sim sample; matches the lab's interactive value
WAVE_C = 400.0              # px/s, global and constant (doc 2.2)
SIM_DT = DX / WAVE_C        # 0.01 s -> a 100 Hz sim step
SNAP_EPS = 8.0
MAX_ENERGY = 40.0           # the doc's section 8 runaway ceiling (a safety net)
# sqrt(Y_rad) of plain Chalk, used to normalise terminal radiation gain so
# that Chalk reads as 1.0 and every other ink is a ratio against it.
RAD_GAIN_REFERENCE = (0.6 / 50.0) ** 0.5
# Impedance of open ground, for the barrier reflection coefficient.
BARRIER_REFERENCE_Z = 34.0
BARRIER_SAMPLE_STEP = 14.0

# Raw radiated/injected for a well-built sigil, used to turn the ratio into a
# 0-100 grade. The raw number is a real measurement but a useless *readout*:
# it lives between 0.006 and 0.04, so every sigil in the game — the good ones
# included — reports "3%" and the player learns to ignore the one figure the
# design most wants them to optimise. Grading against a good sigil keeps the
# ordering exactly as measured and makes the differences legible.
EFFICIENCY_REFERENCE = 0.04
CHARGE_REFERENCE = 6.0      # display scale for the charge meter, not a limit

TAP_BURST_LEN = 24
TAP_AMPLITUDE = 1.0
HOLD_ATTACK_STEPS = 45
HOLD_AMPLITUDE = 0.85
# Holding does not sit at one amplitude — it keeps climbing. This is what
# makes the hot bands reachable at all: the top band needs harmonics, and
# harmonics need the junction driven deep into its saturating curve (2.6),
# which a fixed polite amplitude never does. So "hold longer" means "push
# past the linear region", which means heat and phase, which means char.
# One button, a real risk curve, and every step of it is the physics.
HOLD_OVERDRIVE_GAIN = 2.6
HOLD_OVERDRIVE_STEPS = 260
HOLD_FALLBACK_LOW = 0.015   # un-looped shapes have no f0 to lock to, so drive
HOLD_FALLBACK_HIGH = 0.19   # a low+high pair (the only way to reach phase)
HOLD_FALLBACK_HIGH_AMP = 2.2

# Char is driven by how deep the junctions are actually being pushed into
# their saturating curve, not by total stored energy. Energy is the wrong
# signal: it scales with how much ink you drew, so a big sigil would char
# for existing while a small one could be flogged forever. Saturation depth
# is size-independent and is literally the ink being cooked.
#
# It also makes an ink's harmonic talent and its fragility the same number.
# Emberglass folds at 0.85 where Chalk folds at 3.0, so the same drive puts
# Emberglass 3.5x deeper into the curve: it buys you the hot bands and it
# burns itself doing it. Nobody had to author that as a drawback.
CHAR_SATURATION_ONSET = 0.55
CHAR_RATE = 0.55            # char/sec at full saturation
CHAR_COOL_RATE = 0.30       # char/sec recovered when not overdriven
CHAR_SILENT_AT = 1.0

EMIT_QUANTUM = 0.30        # band-energy per emitted mote; sets mote density,
                            # not total output — the accounting renormalises,
                            # so this trades many thin motes for few fat ones
                            # without changing how much damage arrives.


class Emission:
    """One packet of radiated energy leaving one terminal, in sigil-local
    space. The field turns this into a world-space Pulse."""

    __slots__ = ("local_pos", "local_heading", "bands", "kinetic_sign", "thermal_sign", "energy")

    def __init__(self, local_pos, local_heading, bands, kinetic_sign, thermal_sign, energy):
        self.local_pos = local_pos
        self.local_heading = local_heading
        self.bands = bands
        self.kinetic_sign = kinetic_sign
        self.thermal_sign = thermal_sign
        self.energy = energy


class Loop:
    __slots__ = ("circumference", "f0", "sign", "beat_period")

    def __init__(self, circumference, f0, sign):
        self.circumference = circumference
        self.f0 = f0
        self.sign = sign
        # Round-trip time of the loop, in seconds. This is the tempo the
        # player taps to; it is not a chosen number, it is L/c.
        self.beat_period = circumference / WAVE_C if circumference > 1e-6 else 0.0


class Assay:
    """What the game *measured*, in plain language — never what it decided.

    The distinction is the whole discoverability strategy (doc section 8).
    If the readout said "FIRE SPELL" the player would learn a lookup table.
    Saying "ring 248px, f0 0.041, output centred on band 1, 34% efficient"
    teaches the actual machine, and the same sentence keeps being true in
    cases the designer never thought about."""

    def __init__(self):
        self.lines = []
        self.loops = []
        self.n_terminals = 0
        self.n_couplers = 0
        self.n_nodes = 0
        self.n_edges = 0
        self.ink_names = []
        self.output_bands = [0.0] * N_BANDS
        self.output_center = 0.0
        self.output_total = 0.0
        self.efficiency = 0.0      # graded 0..1 against a good sigil
        self.efficiency_raw = 0.0  # the underlying radiated/injected ratio
        self.kinetic_sign = 1.0
        self.thermal_sign = 1.0
        self.beat_period = 0.0
        self.ink_cost = 0.0


class Sigil:
    def __init__(self, name="unnamed", strokes=None):
        self.name = name
        self.strokes = list(strokes or [])
        self.ignition_override = None   # node id, if the player picked one

        self.graph = None
        self.network = None
        self.terminals = []             # one dict per degree-1 node
        self.chirality = [1.0] * N_BANDS
        self.coupler_sites = []
        self.loops = []
        self.ignition_node = None

        self.char = 0.0
        self.disabled = False
        self.saturation = 0.0   # 0..1, how deep the NL junctions are folding
        # Mote granularity. Total delivered energy is renormalised against
        # this, so raising it trades many thin motes for few fat ones and
        # changes nothing about damage — only cost and readability. Enemies
        # run coarse: a volley of eight legible motes you can dodge or parry
        # beats a spray of two hundred you can only flinch at.
        self.emit_scale = 1.0

        self._accum = 0.0
        self._burst = []
        self._burst_i = 0
        self._hold = False
        self._hold_steps = 0
        self._hold_freq = HOLD_FALLBACK_LOW
        self._hold_is_loop = False

        self.injected_energy = 0.0
        self.radiated_energy = 0.0
        self.dissipated_energy = 0.0
        self._dissipation_pool = 0.0
        self.time = 0.0
        self.beat_phase = 0.0
        self.on_beat_flash = 0.0
        self.extent = 1.0
        self._barrier_pts = []
        self.near_bank = None
        self.near_node = None

        self.recompile()

    # ---------------------------------------------------------------- build

    def recompile(self) -> None:
        self.graph = parse_strokes(self.strokes, DX, snap_eps=SNAP_EPS)
        # g_max=0 disables the compiler's own coupler pass; we run our own
        # below so reach can be a per-ink property with a soft edge.
        self.network = compile_graph(
            self.graph, DX, snap_eps=SNAP_EPS, g_max=0.0, max_energy=MAX_ENERGY
        )
        self._add_couplers()
        self.chirality = compute_chirality(self.graph, BAND_CENTERS, DX)
        self._build_loops()
        self._build_terminals()
        self._pick_ignition()
        self._measure_extent()
        self._build_barrier_points()
        self._build_near_field()

    def _build_near_field(self) -> None:
        """An analyser on the inside of the sigil.

        The terminal analysers measure what *left*, which is the right
        quantity for a projectile and the wrong one for everything else. A
        loop with no terminal has no terminal analyser at all, so it reported
        a flat zero spectrum and every near-field effect it should have had —
        aura, detonation, the whole reason to draw a closed ring — evaluated
        to nothing. The sigil could be visibly blazing with stored energy and
        the game would insist it was doing nothing.

        So the near field gets its own bank, listening to a loop-closing
        junction where the standing wave actually peaks. Same analyser, same
        bands, different microphone position.
        """
        self.near_bank = make_bank()
        loop_nodes = sorted(find_loop_closing_nodes(self.graph)) if self.graph else []
        if loop_nodes:
            self.near_node = loop_nodes[0]
        elif self.ignition_node is not None:
            self.near_node = self.ignition_node
        else:
            self.near_node = next(iter(sorted(self.graph.nodes)), None) if self.graph else None

    def _build_barrier_points(self) -> None:
        """Thin the drawn polylines down to a handful of collision samples.

        The shape you drew is a physical object in the world, not just a
        picture of one — incoming energy has to be able to hit it. Sampled
        coarsely on purpose: this runs against every hostile mote near the
        player every frame, and the ink is 3px wide anyway."""
        pts = []
        for edge in (self.graph.edges if self.graph else []):
            acc = BARRIER_SAMPLE_STEP
            poly = edge.polyline
            for i in range(len(poly) - 1):
                seg = (poly[i + 1] - poly[i]).length()
                acc += seg
                if acc >= BARRIER_SAMPLE_STEP:
                    acc = 0.0
                    pts.append(pygame.Vector2(poly[i]))
        self._barrier_pts = pts

    def _measure_extent(self) -> None:
        """Half-diagonal of the drawn shape, cached at edit time for the
        renderer. Recomputing it per frame would mean walking every polyline
        of every live sigil every frame to draw a circle."""
        xs, ys = [], []
        for stroke in self.strokes:
            for p in stroke.points:
                xs.append(p.x)
                ys.append(p.y)
        if not xs:
            self.extent = 1.0
            return
        self.extent = max(1.0, max(max(xs) - min(xs), max(ys) - min(ys)))

    def _build_loops(self) -> None:
        self.loops = []
        for cyc in find_cycles(self.graph, DX):
            # find_cycles reports f0 in cycles/sample; circumference in px is
            # dx/f0. Deriving the tempo back through the same constant keeps
            # what the player taps to identical to what the sim resonates at.
            if cyc.fundamental_freq <= 1e-9:
                continue
            self.loops.append(Loop(DX / cyc.fundamental_freq, cyc.fundamental_freq, cyc.sign))
        self.loops.sort(key=lambda lp: -lp.circumference)

    def _add_couplers(self) -> None:
        """Per-ink reach, tapered at the edge (see module docstring)."""
        edges = self.graph.edges
        self.coupler_sites = []
        if len(edges) < 2:
            return

        reach_of = {i: getattr(e.ink_type, "coupler_range", 30.0) for i, e in enumerate(edges)}
        global_max = max(reach_of.values())

        kept = []
        for site in find_coupler_sites(
            self.graph, DX, snap_eps=SNAP_EPS, g_max=global_max, max_couplers=48
        ):
            pair_reach = max(reach_of[site.edge_a], reach_of[site.edge_b])
            if site.gap >= pair_reach:
                continue
            kappa = self._kappa(site.gap, pair_reach)
            if kappa < 1e-4:
                continue
            site.reach = pair_reach
            site.kappa = kappa
            kept.append(site)

        kept.sort(key=lambda s: -s.kappa)
        kept = kept[:16]
        for site in kept:
            self.network.add_coupler(
                site.edge_a,
                round(site.pos_a / DX),
                site.edge_b,
                round(site.pos_b / DX),
                site.kappa,
                lowpass_coef_for_gap(site.gap, site.reach),
            )
        self.coupler_sites = kept

    @staticmethod
    def _kappa(gap: float, reach: float, kappa_max: float = 0.85) -> float:
        """Exponential falloff (the sim's own shape) times a window that
        reaches exactly zero at `reach`. Without the window there is a step
        discontinuity at the cutoff, and a player tuning a gap right at the
        edge — which is exactly what a player tuning a gap does — watches
        energy vanish entirely for a one-pixel change."""
        if gap >= reach or reach <= 1e-6:
            return 0.0
        t = gap / reach
        taper = 1.0 - t * t
        return kappa_max * math.exp(-2.0 * t) * taper * taper

    def _build_terminals(self) -> None:
        self.terminals = []
        for node_id, node in self.graph.nodes.items():
            if not node.is_terminal:
                continue
            y_rad = self.network.nodes[node_id].rad_admittance
            self.terminals.append(
                {
                    "node_id": node_id,
                    "pos": pygame.Vector2(node.pos),
                    "heading": self._terminal_heading(node_id),
                    "bank": make_bank(),
                    "accum": 0.0,
                    # Amplitude of the wave that actually leaves, per unit of
                    # junction pressure. See _sim_step.
                    "rad_gain": math.sqrt(max(0.0, y_rad)) / RAD_GAIN_REFERENCE,
                }
            )

    def _terminal_heading(self, node_id: int) -> pygame.Vector2:
        """Where the stroke was pointing when it ran out of ink. This is the
        firing direction, which means the shape of what you drew *is* your
        firing pattern — draw two ends facing opposite ways and you shoot
        both ways, and nobody had to author a spread shot."""
        for edge in self.graph.edges:
            poly = edge.polyline
            if len(poly) < 2:
                continue
            if edge.node_a == node_id:
                tail = poly[0] - poly[min(3, len(poly) - 1)]
            elif edge.node_b == node_id:
                tail = poly[-1] - poly[max(-4, -len(poly))]
            else:
                continue
            if tail.length_squared() > 1e-9:
                return tail.normalize()
        return pygame.Vector2(1, 0)

    def _pick_ignition(self) -> None:
        """Where a tap goes in. A loop-closing junction beats a terminal: a
        terminal leaks each tap straight back out before it can reinforce
        anything (measured in this project's own experiment reports — about
        1.8x buildup at a terminal against 2.3-2.7x at the junction)."""
        if self.ignition_override is not None and self.ignition_override in self.graph.nodes:
            self.ignition_node = self.ignition_override
            return
        loop_nodes = sorted(find_loop_closing_nodes(self.graph))
        if loop_nodes:
            self.ignition_node = loop_nodes[0]
            return
        terminals = sorted(n for n, node in self.graph.nodes.items() if node.is_terminal)
        self.ignition_node = terminals[0] if terminals else next(iter(sorted(self.graph.nodes)), None)

    # ----------------------------------------------------------- properties

    @property
    def is_empty(self) -> bool:
        return not self.graph or not self.graph.edges

    @property
    def beat_period(self) -> float:
        return self.loops[0].beat_period if self.loops else 0.0

    @property
    def predicted_band(self):
        """Which band this sigil will ring in, read off its geometry alone.

        A loop's fundamental is dx/L, so the size of the ring already says
        what colour it will be — before it has ever been fired, before there
        is a single measurement to look at. That makes this the number the
        Forge can show *while you are still drawing*, which is the whole
        difference between designing and guessing.

        Returns None for a shape with no loop, because an open path has no
        resonance and predicting one would be a lie.
        """
        if not self.loops or self.loops[0].f0 <= 1e-9:
            return None
        f0 = self.loops[0].f0
        if f0 <= BAND_CENTERS[0]:
            return 0.0
        if f0 >= BAND_CENTERS[-1]:
            return float(N_BANDS - 1)
        for i in range(N_BANDS - 1):
            lo, hi = BAND_CENTERS[i], BAND_CENTERS[i + 1]
            if lo <= f0 <= hi:
                # Bands are log-spaced, so interpolate in log space or the
                # answer is wrong by most of a band in the middle.
                return i + (math.log(f0 / lo) / math.log(hi / lo))
        return float(N_BANDS - 1)

    @property
    def ink_cost(self) -> float:
        return sum(s.length() * getattr(s.ink_type, "cost_per_px", 1.0) for s in self.strokes)

    def total_energy(self) -> float:
        return self.network.total_energy() if self.network else 0.0

    def charge_fraction(self) -> float:
        """For the charge meter. A display scale, not a cap."""
        return min(1.0, self.total_energy() / CHARGE_REFERENCE) if self.network else 0.0

    def _measure_saturation(self) -> float:
        """How far the loop-closing junctions have folded. The saturating map
        caps |u| at roughly 1/nl_a, so |u|*nl_a approaching 1 is a junction
        generating serious harmonics — the same quantity that makes a node
        flash in the visualisation."""
        worst = 0.0
        for node in self.network.nodes.values():
            if node.nl_a is None:
                continue
            worst = max(worst, min(1.5, abs(node.last_emitted) * node.nl_a))
        return worst

    # -------------------------------------------------------------- playing

    def tap(self, amplitude: float = TAP_AMPLITUDE) -> bool:
        """A quick broadband strike. The returned on-beat flag is
        presentation only — the reinforcement itself belongs to the sim, not
        to a bonus applied here."""
        if self.disabled or self.ignition_node is None:
            return False
        # Match the strike to the instrument. Burst length sets bandwidth
        # (doc 4.3), so a fixed-length tap puts its energy at a fixed
        # frequency — which means it excites a 400px ring well and a 60px
        # ring barely at all, and small sigils read as broken. One period of
        # the sigil's own fundamental centres the strike where the loop can
        # actually use it, which is also what striking a real instrument
        # does. Un-looped shapes have nothing to match, so they keep the
        # default width.
        n = TAP_BURST_LEN
        if self.loops and self.loops[0].f0 > 1e-9:
            n = int(max(5, min(64, round(1.0 / self.loops[0].f0))))
        self._burst = broadband_tap(n, amplitude)
        self._burst_i = 0
        on_beat = False
        bp = self.beat_period
        if bp > 1e-6:
            frac = (self.time % bp) / bp
            on_beat = frac < 0.18 or frac > 0.82
            if on_beat:
                self.on_beat_flash = 0.35
        return on_beat

    def set_hold(self, on: bool) -> None:
        if self.disabled:
            self._hold = False
            return
        if on and not self._hold:
            self._hold_steps = 0
            self._hold_is_loop = bool(self.loops)
            self._hold_freq = self.loops[0].f0 if self.loops else HOLD_FALLBACK_LOW
        self._hold = on and self.ignition_node is not None

    def release(self) -> None:
        self._hold = False

    # ------------------------------------------------------------- stepping

    def advance(self, dt: float, max_steps: int = 8) -> list:
        """Run the sim forward by `dt` of game time and hand back whatever
        radiated. Capped so one hitch cannot cascade into a longer hitch."""
        if self.network is None or self.is_empty:
            return []

        self._accum += dt
        emissions = []
        steps = 0
        while self._accum >= SIM_DT and steps < max_steps:
            self._accum -= SIM_DT
            steps += 1
            emissions.extend(self._sim_step())

        if steps >= max_steps:
            self._accum = 0.0

        self._update_char(dt)
        self.time += dt
        bp = self.beat_period
        self.beat_phase = (self.time % bp) / bp if bp > 1e-6 else 0.0
        self.on_beat_flash = max(0.0, self.on_beat_flash - dt)
        return emissions

    def _sim_step(self) -> list:
        injections = {}
        node = self.ignition_node

        if node is not None and self._burst_i < len(self._burst):
            injections[node] = injections.get(node, 0.0) + self._burst[self._burst_i]
            self._burst_i += 1

        if self._hold and node is not None:
            attack = min(1.0, self._hold_steps / HOLD_ATTACK_STEPS)
            over = 1.0 + HOLD_OVERDRIVE_GAIN * min(
                1.0, max(0, self._hold_steps - HOLD_ATTACK_STEPS) / HOLD_OVERDRIVE_STEPS
            )
            attack *= over
            k = self._hold_steps
            if self._hold_is_loop:
                # Locked to the loop's own f0: the sustained-resonance drive,
                # which is what overcharge and charge-and-release need.
                sample = HOLD_AMPLITUDE * attack * math.sin(2 * math.pi * self._hold_freq * k)
            else:
                low = math.sin(2 * math.pi * HOLD_FALLBACK_LOW * k)
                high = math.sin(2 * math.pi * HOLD_FALLBACK_HIGH * k)
                sample = attack * (HOLD_AMPLITUDE * low + HOLD_FALLBACK_HIGH_AMP * high)
            injections[node] = injections.get(node, 0.0) + sample
            self._hold_steps += 1

        injected_now = 0.0
        for v in injections.values():
            injected_now += v * v
        self.injected_energy += injected_now

        # Exact energy accounting, because the *unradiated* half of a sigil's
        # output is the half the first build threw away.
        #
        # Energy leaves a network two ways: out of a terminal as radiation,
        # or into the loss filters as dissipation. Only the first was being
        # used, so a closed loop with no terminal - the single most natural
        # thing a person draws - stored energy beautifully and did nothing
        # with it, forever. Dissipation is not waste; it is energy going into
        # the medium the ink is lying on, which is a field, which is the
        # world. Radiation aims. Dissipation soaks. Every sigil now has both,
        # and their ratio is decided by geometry rather than by a mode switch.
        before = self.network.total_energy()
        radiated = self.network.step(injections)
        after = self.network.total_energy()
        self.radiated_energy += radiated
        dissipated = max(0.0, before + injected_now - after - radiated)
        self.dissipated_energy += dissipated
        self._dissipation_pool += dissipated
        sat = self._measure_saturation()
        # Peak-hold with a slow bleed: a junction only folds on the crest of
        # each cycle, so sampling instantaneously would read zero most steps.
        self.saturation = max(sat, self.saturation * 0.97)

        if self.disabled:
            return []

        if self.near_node is not None and self.near_bank is not None:
            self.near_bank.process(self.network.nodes[self.near_node].last_emitted)

        out = []
        silence = max(0.0, 1.0 - self.char)
        for term in self.terminals:
            # Analyse what *leaves*, not what is present at the junction.
            #
            # `last_emitted` is the junction pressure u_j, and radiated power
            # is u_j^2 * Y_rad, so the amplitude that escapes goes as
            # u_j * sqrt(Y_rad). Feeding raw u_j to the analyser measures the
            # wrong thing, and it measures it in the exactly wrong direction:
            # a nearly-sealed terminal holds a *large* pressure precisely
            # because so little of it is getting out. Left uncorrected, that
            # inverted every material in the game - Slate, whose whole
            # identity is "carries anything, emits almost nothing", measured
            # as the strongest emitter in the set, and the intended lesson
            # that a good sigil pairs a low-loss body with a wide-open tip
            # was not merely unteachable but actively false.
            #
            # Normalised against Chalk so this is a relative correction and
            # the damage calibration downstream still holds.
            sample = self.network.nodes[term["node_id"]].last_emitted * term["rad_gain"]
            bands = term["bank"].process(sample)
            power = sum(bands)
            quantum = EMIT_QUANTUM * self.emit_scale
            term["accum"] += power * silence
            if term["accum"] >= quantum:
                packets = min(3, int(term["accum"] / quantum))
                term["accum"] -= packets * quantum
                # Renormalise so the packet carries exactly the energy that
                # was accumulated, whatever the frame rate happened to be.
                scale = quantum * packets / max(power, 1e-9)
                snap = [b * scale for b in bands]
                ksign = 1.0 if kinetic_drive_from_bands(bands, self.chirality) >= 0 else -1.0
                tsign = 1.0 if thermal_drive_from_bands(bands, self.chirality) >= 0 else -1.0
                out.append(
                    Emission(term["pos"], term["heading"], snap, ksign, tsign, quantum * packets)
                )
        return out

    def _update_char(self, dt: float) -> None:
        sat = self.saturation
        if sat > CHAR_SATURATION_ONSET:
            over = (sat - CHAR_SATURATION_ONSET) / (1.0 - CHAR_SATURATION_ONSET)
            self.char = min(1.4, self.char + CHAR_RATE * min(1.0, over) * dt)
        else:
            self.char = max(0.0, self.char - CHAR_COOL_RATE * dt)

        if self.char >= CHAR_SILENT_AT:
            self.disabled = True
            self._hold = False
        elif self.disabled and self.char < CHAR_SILENT_AT * 0.6:
            self.disabled = False

    # ------------------------------------------------------- world coupling

    def near_bands(self) -> list:
        """Spectrum of the standing wave inside the ink — what the near field
        couples to, as distinct from what leaves through a terminal."""
        return list(self.near_bank.energies) if self.near_bank else [0.0] * N_BANDS

    def field_payload(self):
        """Continuous near-field output: (kinetic, thermal, phase, band).

        Energy sitting in ink is energy in the world, so a charged sigil
        pushes on its surroundings whether or not it has anywhere to radiate.
        This is the channel that makes a sigil a *spell* rather than a gun —
        it is what lays fire down, freezes ground, shoves crowds and thins
        matter, none of which a projectile can express.

        The three couplings are read off the spectrum's **centroid**, not off
        a weighted sum over the whole spectrum. The sum is the physically
        natural quantity and it is the wrong one to build on here: the near
        field is broadband, so the normalised sum lands around 0.05-0.2 for
        everything and does not even order correctly by band — a band-1 shove
        sigil measured *hotter* than a band-3 fire sigil, and consequently
        set the room alight and cooked its own caster in eleven seconds.

        The centroid is monotone in ring size, spans the full weight range,
        and is exactly the number already displayed to the player as the
        output band. What the meter says is now what the world does.
        """
        bands = self.near_bands()
        total = sum(bands)
        if total < 1e-9 or self.disabled:
            return 0.0, 0.0, 0.0, 0.0
        centre = self.coupling_band
        charge = self.charge_fraction()
        silence = max(0.0, 1.0 - self.char)
        gain = charge * silence
        k, t, p = _coupling_at(centre)
        sign = self._chirality_at(centre)
        return k * gain * sign, t * gain * sign, p * gain, centre

    @property
    def coupling_band(self) -> float:
        """The band the world should be coupled through.

        Geometry first, measurement second — and that ordering is the whole
        point. The near-field analyser listens to junction pressure, which is
        broadband and does *not* track the ring that produced it: a band-1
        shove sigil measures a near-field centroid around 2.9 in live play.
        Driving world coupling off that number made a cold sigil behave like
        a hot one, set rooms on fire nobody asked to burn, and resisted three
        successive attempts to fix it by tuning magnitudes — because the
        input was wrong, not the scale.

        A loop's fundamental is fixed by its circumference, so the predicted
        band is stable, monotone in ring size, and already the number shown
        to the player in the Forge. What the readout promises is now what the
        world does. Shapes with no loop have nothing to predict from and fall
        back to what is actually being measured.
        """
        pb = self.predicted_band
        if pb is not None:
            return pb
        centre, total = dominant_band(self.near_bands())
        return centre if total > 1e-9 else 0.0

    def _chirality_at(self, band: float) -> float:
        """Chirality sampled at a fractional band index. Sign only — this is
        what makes the same ring wound backwards pull and chill."""
        if not self.chirality:
            return 1.0
        i = max(0, min(N_BANDS - 1, int(round(band))))
        return 1.0 if self.chirality[i] >= 0 else -1.0

    def detonation_payload(self):
        """Everything at once: (energy, kinetic_sign, thermal, phase, band).

        A loop with no terminal cannot leak, which in the first build made it
        the most useless thing a person could draw — it stored beautifully
        and did nothing forever. It is in fact a capacitor, and the missing
        verb was *release*. Charge it as far as the char will allow, then let
        go, and the whole stored quantity lands in the world in one frame.

        What that release does is not chosen from a menu; it is read off the
        spectrum. Big ring, low band: a shockwave. Small ring driven into
        harmonics: a firestorm. Wound counter-clockwise: it implodes and
        freezes instead of blasting and burning. The player picks the effect
        by drawing, which is the only place in this game effects should ever
        be picked.
        """
        stored = self.total_energy()
        bands = self.near_bands()
        total = sum(bands)
        if total < 1e-9:
            return 0.0, 1.0, 0.0, 0.0, 0.0
        centre = self.coupling_band
        k, t, p = _coupling_at(centre)
        sign = self._chirality_at(centre)
        return stored, k * sign, t * sign, p, centre

    @property
    def is_capacitor(self) -> bool:
        """No terminal, so nothing leaves except by release."""
        return bool(self.loops) and not self.terminals

    @property
    def barrier_strength(self) -> float:
        """How hard this ink turns incoming energy away.

        Straight off the doc's own reflection coefficient for a junction
        between two impedances (2.2): r = (Z2 - Z1)/(Z2 + Z1), against a
        reference for open ground. Dense ink reflects, thin ink does not, and
        so an arc of Bonewhite drawn across the front of a sigil is a shield
        because of what Bonewhite *is* — not because a shield was authored.
        """
        if not self.strokes:
            return 0.0
        total_len = sum(st.length() for st in self.strokes) or 1.0
        acc = 0.0
        for st in self.strokes:
            z = st.ink_type.impedance
            r = (z - BARRIER_REFERENCE_Z) / (z + BARRIER_REFERENCE_Z)
            acc += max(0.0, r) * st.length()
        return acc / total_len

    def barrier_points(self):
        """Local-space samples along the ink, for barrier collision."""
        return self._barrier_pts

    def drain_dissipation(self) -> float:
        """Take the dissipation accumulated since the last call.

        Pulled rather than pushed so the field layer decides the cadence and
        the sim never has to know a world exists."""
        out = self._dissipation_pool
        self._dissipation_pool = 0.0
        return out

    def quench(self) -> None:
        """Dump all stored energy. The panic button — and the price of panic
        is that everything you spent time charging is gone."""
        if not self.network:
            return
        for edge in self.network.edges.values():
            edge.forward.buffer[:] = 0.0
            edge.backward.buffer[:] = 0.0
        self._burst = []
        self._hold = False
        for term in self.terminals:
            term["bank"] = make_bank()
            term["accum"] = 0.0
        self.near_bank = make_bank()

    # ---------------------------------------------------------------- assay

    def measured_bands(self) -> list:
        total = [0.0] * N_BANDS
        for term in self.terminals:
            for i, e in enumerate(term["bank"].energies):
                total[i] += e
        return total

    def assay(self) -> Assay:
        a = Assay()
        a.n_nodes = len(self.graph.nodes) if self.graph else 0
        a.n_edges = len(self.graph.edges) if self.graph else 0
        a.n_terminals = len(self.terminals)
        a.n_couplers = len(self.coupler_sites)
        a.loops = self.loops
        a.beat_period = self.beat_period
        a.ink_cost = self.ink_cost
        a.ink_names = sorted({s.ink_type.name for s in self.strokes})

        total = self.measured_bands()
        a.output_bands = total
        a.output_center, a.output_total = dominant_band(total)
        raw = self.radiated_energy / self.injected_energy if self.injected_energy > 1e-12 else 0.0
        a.efficiency_raw = raw
        a.efficiency = min(1.0, raw / EFFICIENCY_REFERENCE)
        # Before anything has been fired there is no measured spectrum, and
        # asking for the sign of an all-zero vector returns a meaningless
        # +1 — so a freshly drawn counter-clockwise ring would sit in the
        # Forge insisting it pushes, right at the moment the player is
        # looking for confirmation that winding direction did anything.
        # Falling back to a flat unit spectrum reads the sign straight off
        # the chirality vector instead: a prediction rather than a
        # measurement, but the correct one, and available while drawing.
        probe = total if sum(total) > 1e-12 else [1.0] * N_BANDS
        a.kinetic_sign = 1.0 if kinetic_drive_from_bands(probe, self.chirality) >= 0 else -1.0
        a.thermal_sign = 1.0 if thermal_drive_from_bands(probe, self.chirality) >= 0 else -1.0
        a.lines = self._assay_lines(a)
        return a

    def _assay_lines(self, a: Assay) -> list:
        lines = []
        if a.n_edges == 0:
            return ["no ink"]

        if not a.loops:
            lines.append("open path, no loop - no resonance to tap into")
        else:
            # The prediction comes first, because it is the only line that is
            # true before the sigil has ever been fired - which is exactly
            # when the player is deciding whether to keep drawing.
            pb = self.predicted_band
            if pb is not None:
                lines.append(
                    f"geometry predicts band {pb:.1f} ({BAND_NAMES[int(round(pb))]}) "
                    f"before firing"
                )
        if a.loops:
            biggest = a.loops[0]
            spin = "clockwise" if biggest.sign >= 0 else "counter-clockwise"
            plural = "s" if len(a.loops) > 1 else ""
            lines.append(
                f"{len(a.loops)} loop{plural}, largest {biggest.circumference:.0f}px "
                f"-> f0 {biggest.f0:.4f} ({spin}, beat {biggest.beat_period:.2f}s)"
            )
            if len(a.loops) > 1:
                detune = abs(a.loops[0].f0 - a.loops[1].f0)
                if detune > 1e-6:
                    lines.append(
                        f"two loops detuned by {detune:.4f} -> envelope swings every "
                        f"{SIM_DT / detune:.1f}s"
                    )

        push = "push" if a.kinetic_sign >= 0 else "PULL"
        burn = "burn" if a.thermal_sign >= 0 else "CHILL"
        lines.append(f"{a.n_terminals} terminal(s) -> {push} / {burn}")

        if a.n_couplers:
            gaps = ", ".join(f"{s.gap:.0f}px" for s in self.coupler_sites[:3])
            lines.append(f"{a.n_couplers} coupler(s) across {gaps} - energy crosses empty air")

        if a.output_total > 1e-9:
            name = BAND_NAMES[max(0, min(N_BANDS - 1, int(round(a.output_center))))]
            lines.append(
                f"output centred on band {a.output_center:.1f} ({name}), "
                f"efficiency {a.efficiency * 100:.0f}%"
            )
        else:
            lines.append("no measured output yet - tap it")

        if self.char > 0.05:
            lines.append(f"char {self.char * 100:.0f}%" + (" - BURNED OUT" if self.disabled else ""))
        return lines

    # ------------------------------------------------------------ serialise

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ignition": self.ignition_override,
            "strokes": [
                {
                    "ink": s.ink_type.name,
                    "pts": [[round(p.x, 1), round(p.y, 1)] for p in s.points],
                }
                for s in self.strokes
            ],
        }

    @staticmethod
    def from_dict(data: dict) -> "Sigil":
        from .inks import ink_by_name

        strokes = []
        for s in data.get("strokes", []):
            pts = [pygame.Vector2(p[0], p[1]) for p in s.get("pts", [])]
            if len(pts) >= 2:
                strokes.append(Stroke(points=pts, ink_type=ink_by_name(s.get("ink", "Chalk"))))
        sig = Sigil(data.get("name", "unnamed"), strokes)
        ign = data.get("ignition")
        if ign is not None:
            sig.ignition_override = ign
            sig._pick_ignition()
        return sig

    def clone(self) -> "Sigil":
        return Sigil.from_dict(self.to_dict())
