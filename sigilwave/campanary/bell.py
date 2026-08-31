"""A Bell: drawn metal, compiled into a resonator you can strike.

This is the seam between the physics package - which is finished, tested and
untouched - and the game. Everything above it talks to a Bell and never to a
Network.

Three deliberate departures from the old Sigil class, each of them a feel
fix rather than a physics change:

1. **The whole ring sounds.** A closed loop in the raw simulation has no
   terminal, so it stores energy beautifully and radiates none of it - which
   made the first thing every player draws the one thing that does nothing.
   A real bell is a closed shell that radiates from its whole body, so the
   near field is the primary output here and terminals are a *bias* on top
   of it. Draw a circle, get a bell. The friction that used to sit between a
   new player and their first working object is gone.

2. **Output is consumed, not streamed.** The old build emitted a mote every
   time a terminal accumulated a quantum, producing a hose of dots. Here the
   bell accumulates what it radiates into a pool and the strike *takes* the
   pool, all at once, as one ring. Which means striking on the swell - when
   the loop has genuinely reinforced and the pool is fuller - hands you a
   bigger ring, and none of that reinforcement is faked. The groove is the
   simulation's.

3. **The octave is not authored.** Drive a loop-closing junction past its
   saturation threshold and it folds, and the strongest thing folding makes
   is the second harmonic. The notes are exact octaves, so the second
   harmonic lands exactly one note up. `live_note` reads the analyser, not a
   flag, so the climb is something the physics does and the UI reports.
"""

import math

import pygame

from sigilwave.ink import Stroke
from sigilwave.sim.compiler import compile_graph
from sigilwave.sim.coupling import kinetic_drive_from_bands
from sigilwave.sim.couplers import find_coupler_sites, lowpass_coef_for_gap
from sigilwave.sim.cycles import compute_chirality, find_cycles, find_loop_closing_nodes
from sigilwave.sim.parser import parse_strokes

from . import notes
from .metals import BRONZE, metal_by_name
from .notes import DX, N_NOTES, SIM_DT, make_bank

SNAP_EPS = 8.0
MAX_ENERGY = 40.0           # the doc's runaway ceiling; a safety net only

# sqrt(Y_rad) of plain Bronze, so every other metal reads as a ratio against
# it. Radiated amplitude goes as u_j * sqrt(Y_rad); feeding raw junction
# pressure to the analyser measures the wrong thing in the exactly wrong
# direction, because a nearly-sealed terminal holds a *large* pressure
# precisely because so little is escaping.
RAD_REFERENCE = (0.45 / 50.0) ** 0.5

# One strike is one period of the bell's own fundamental, which is what
# striking an instrument does: burst length sets bandwidth, so a fixed-width
# tap excites a big ring well and a small one barely at all.
STRIKE_AMPLITUDE = 1.15
STRIKE_MIN_SAMPLES = 6
STRIKE_MAX_SAMPLES = 220

# The swell. Holding does not sit at one amplitude, it keeps climbing: that
# is what makes the octave reachable at all, because folding a junction
# needs it driven past its linear region. One button, a real risk curve,
# every step of it physics.
SWELL_ATTACK_STEPS = 40
SWELL_AMPLITUDE = 0.9
SWELL_GAIN = 3.1
SWELL_GAIN_STEPS = 190
SWELL_FALLBACK_F0 = 0.0125

# The climb. A loop resonates at f0 *and* at every harmonic of it, and the
# notes in this game are exact octaves, so the loop's second mode is exactly
# one note up - the same ring, sounding higher, with nothing invented.
#
# What moves the drive up there is the fold. Past its saturation threshold a
# junction stops returning what it is given and starts generating the second
# harmonic, and the swell follows that harmonic onto the mode that can carry
# it. So "ring it harder and it climbs a note" is one line of code pointing
# at a mode the ring already had, rather than a spectrum written by hand -
# and a metal that folds early climbs early, because those are the same fact.
SWELL_CLIMB_SATURATION = 1.05   # fold depth at which the drive is fully up
SWELL_CLIMB_GAIN = 1.35         # the second mode needs more push to ring

# Char is driven by how deep the junctions are folding, not by stored energy.
# Energy scales with how much metal you drew, so a big bell would char for
# existing; saturation depth is size-independent and is literally the metal
# being worked past what it can take. It also makes a metal's harmonic
# talent and its fragility the same number - Blackglass folds at 1.8 where
# Bronze folds at 3.0, so it buys the octave and burns itself doing it.
CHAR_ONSET = 0.55
CHAR_RATE = 0.62
CHAR_COOL = 0.34
CHAR_CRACK_AT = 1.0
CHAR_RECOVER_AT = 0.55

# --- body radiation --------------------------------------------------------
# A bell is a closed shell that sounds through its whole body, and sounding
# costs it energy. The raw simulation only loses energy through open ends and
# through the loss filters, so a closed ring rang forever and the pool of
# "what it radiated" was bookkeeping invented alongside the physics rather
# than taken out of it. Measured, that let a bell struck on its own beat
# climb from 2.5 to 132 units of output in six strikes - a 50x range nothing
# downstream could ever be balanced against.
#
# So the body radiates for real: a fraction of stored energy leaves the
# network every step and that exact quantity is what the ring carries. The
# loop now reaches a steady state on its own, compounding lands around 3x
# instead of 50x, and the number on the meter is conserved rather than
# asserted.
#
# The fraction is the metal's own radiating admittance, so this is not a new
# knob - Silver pours itself out and cannot sustain, Bronze rings long, and
# both facts are the one number that was already in the material.
BODY_RADIATION = 0.0042
BODY_RAD_REFERENCE = 0.45
# Bronze's impedance, and the reason this constant has to exist.
#
# The network measures stored energy as sum(buffer^2) * admittance, so a
# low-impedance metal reports more energy for the *same wave*. Reading the
# radiated amount straight off that number therefore counted the admittance
# twice - once in the stored energy and once in the radiating fraction - and
# handed every low-impedance metal a flat multiplier on its output for free.
#
# Measured, Silver came out 4.8x louder than Bronze on the first strike and
# 5.7x louder settled, which is not a tradeoff, it is simply the best metal;
# and it directly contradicted the one thing Silver is supposed to be, which
# is a bell that gives you everything at once and then has nothing left.
# Normalising the output against impedance leaves the *fraction* radiated as
# the material's real identity: Silver dumps twice as fast as Bronze, which
# makes it loud now and empty later, exactly as advertised.
IMPEDANCE_REFERENCE = 50.0

# Display scales, not caps.
CHARGE_REFERENCE = 6.0
OUTPUT_SCALE = 190.0


class Bell:
    """One drawn instrument."""

    def __init__(self, name="new bell", strokes=None):
        self.name = name
        self.strokes = list(strokes or [])

        self.graph = None
        self.network = None
        self.terminals = []
        self.chirality = [1.0] * N_NOTES
        self.loops = []
        self.near_bank = None
        self.near_node = None
        self.strike_node = None

        self.char = 0.0
        self.cracked = False
        self.saturation = 0.0
        self.time = 0.0
        self.extent = 1.0
        self.bias = pygame.Vector2(0, 0)   # where the shape points its output
        self.body_rad = BODY_RADIATION
        self.out_gain = 1.0

        self._accum = 0.0
        self._burst = []
        self._burst_i = 0
        self._swell = False
        self._swell_steps = 0
        self._swell_f0 = SWELL_FALLBACK_F0
        self._pool = [0.0] * N_NOTES       # radiated, waiting to be taken
        self._live = [0.0] * N_NOTES       # what it is emitting right now
        self.climb_drive = 0.0             # 0..1, how far the swell has folded

        self.recompile()

    # ------------------------------------------------------------ building

    def recompile(self) -> None:
        self.graph = parse_strokes(self.strokes, DX, snap_eps=SNAP_EPS)
        self.network = compile_graph(
            self.graph, DX, snap_eps=SNAP_EPS, g_max=0.0, max_energy=MAX_ENERGY
        )
        self._add_couplers()
        self.chirality = compute_chirality(self.graph, notes.BAND_CENTERS, DX)
        self._build_loops()
        self._build_terminals()
        self._pick_strike_node()
        self._build_near_field()
        self._measure_extent()
        self._measure_bias()
        self._measure_body_radiation()

    def _measure_body_radiation(self) -> None:
        """How freely this bell's metal lets go of what it is holding, and
        the unit correction that stops impedance being a free multiplier."""
        fracs = [getattr(s.ink_type, "rad_admittance_fraction", BODY_RAD_REFERENCE)
                 for s in self.strokes]
        zs = [getattr(s.ink_type, "impedance", IMPEDANCE_REFERENCE)
              for s in self.strokes]
        mean = sum(fracs) / len(fracs) if fracs else BODY_RAD_REFERENCE
        z = sum(zs) / len(zs) if zs else IMPEDANCE_REFERENCE
        self.body_rad = BODY_RADIATION * (mean / BODY_RAD_REFERENCE)
        self.out_gain = z / IMPEDANCE_REFERENCE

    def _add_couplers(self) -> None:
        """Per-metal reach with a soft edge. The cliff in the raw sim makes
        tuning a gap feel broken exactly where a player would be probing."""
        edges = self.graph.edges
        if len(edges) < 2:
            return
        reach_of = {i: getattr(e.ink_type, "coupler_range", 30.0) for i, e in enumerate(edges)}
        kept = []
        for site in find_coupler_sites(
            self.graph, DX, snap_eps=SNAP_EPS, g_max=max(reach_of.values()), max_couplers=48
        ):
            reach = max(reach_of[site.edge_a], reach_of[site.edge_b])
            if site.gap >= reach:
                continue
            t = site.gap / reach
            taper = 1.0 - t * t
            kappa = 0.85 * math.exp(-2.0 * t) * taper * taper
            if kappa < 1e-4:
                continue
            site.reach, site.kappa = reach, kappa
            kept.append(site)
        kept.sort(key=lambda s: -s.kappa)
        for site in kept[:16]:
            self.network.add_coupler(
                site.edge_a, round(site.pos_a / DX),
                site.edge_b, round(site.pos_b / DX),
                site.kappa, lowpass_coef_for_gap(site.gap, site.reach),
            )

    def _build_loops(self) -> None:
        """(circumference, f0, winding sign), largest first."""
        self.loops = []
        for cyc in find_cycles(self.graph, DX):
            if cyc.fundamental_freq <= 1e-9:
                continue
            self.loops.append((DX / cyc.fundamental_freq, cyc.fundamental_freq, cyc.sign))
        self.loops.sort(key=lambda lp: -lp[0])

    def _build_terminals(self) -> None:
        self.terminals = []
        for node_id, node in self.graph.nodes.items():
            if not node.is_terminal:
                continue
            y_rad = self.network.nodes[node_id].rad_admittance
            self.terminals.append({
                "node_id": node_id,
                "pos": pygame.Vector2(node.pos),
                "heading": self._terminal_heading(node_id),
                "bank": make_bank(),
                "rad_gain": math.sqrt(max(0.0, y_rad)) / RAD_REFERENCE,
            })

    def _terminal_heading(self, node_id: int) -> pygame.Vector2:
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

    def _pick_strike_node(self) -> None:
        """Where the hammer lands. A loop-closing junction beats a terminal:
        a terminal leaks each strike straight back out before it can
        reinforce anything."""
        loop_nodes = sorted(find_loop_closing_nodes(self.graph))
        if loop_nodes:
            self.strike_node = loop_nodes[0]
            return
        terms = sorted(n for n, node in self.graph.nodes.items() if node.is_terminal)
        self.strike_node = terms[0] if terms else next(iter(sorted(self.graph.nodes)), None)

    def _build_near_field(self) -> None:
        """The microphone on the body of the bell.

        Terminal analysers measure what left through an open end, which is
        the right quantity for a projectile and the wrong one for a bell. A
        bell is a closed shell that sounds through its whole body, so this
        listens at a loop-closing junction where the standing wave peaks and
        it is the *primary* output path. Nothing has to be drawn open before
        it will make a sound.
        """
        self.near_bank = make_bank()
        loop_nodes = sorted(find_loop_closing_nodes(self.graph)) if self.graph else []
        if loop_nodes:
            self.near_node = loop_nodes[0]
        elif self.strike_node is not None:
            self.near_node = self.strike_node
        else:
            self.near_node = next(iter(sorted(self.graph.nodes)), None) if self.graph else None

    def _measure_extent(self) -> None:
        xs, ys = [], []
        for stroke in self.strokes:
            for p in stroke.points:
                xs.append(p.x)
                ys.append(p.y)
        self.extent = max(1.0, max(max(xs) - min(xs), max(ys) - min(ys))) if xs else 1.0

    def _measure_bias(self) -> None:
        """Which way the shape leans.

        The old build turned every open end into a projectile, so the drawn
        shape was a firing pattern and an unclosed doodle sprayed
        everywhere. A ring does not spray - so instead the open ends bias
        the ring, making it brighter and harder on the side they point. A
        symmetric bell hits evenly; a bell with a horn on one side hits like
        a horn. Same principle, no failure state.
        """
        v = pygame.Vector2(0, 0)
        for term in self.terminals:
            v += term["heading"] * term["rad_gain"]
        self.bias = v.normalize() if v.length_squared() > 1e-6 else pygame.Vector2(0, 0)

    # ---------------------------------------------------------- properties

    @property
    def is_empty(self) -> bool:
        return not self.graph or not self.graph.edges

    @property
    def has_loop(self) -> bool:
        return bool(self.loops)

    @property
    def note(self) -> float:
        """The note this bell is cast at, read off its geometry alone.

        Geometry, not measurement, and that ordering is the point: f0 = dx/L
        is fixed by the ring the moment it closes, so the tuner can report it
        *while the player is still drawing*, before a single strike. That is
        the difference between shaping something and guessing at it.
        """
        if not self.loops:
            return -1.0
        return notes.note_from_f0(self.loops[0][1])

    @property
    def live_note(self) -> float:
        """What it is emitting *right now*, measured.

        Diverges from `note` when the bell is being swelled hard enough to
        fold its junctions, because the second harmonic is an octave up and
        the notes are exact octaves. The climb is read here, never set.
        """
        centre, total = notes.note_from_bands(self._live)
        return centre if total > 1e-9 else max(0.0, self.note)

    @property
    def climbed(self) -> float:
        """How far the live note has risen above the cast note, 0..1+."""
        base = self.note
        return max(0.0, self.live_note - base) if base >= 0 else 0.0

    @property
    def period(self) -> float:
        """The bell's own pulse: the loop's round trip, L/c, doubled until a
        person can play it. Nobody chose it; it is the ring you drew."""
        if not self.loops:
            return 0.0
        return notes.playable_period(self.loops[0][0] / notes.WAVE_C)

    @property
    def reach(self) -> float:
        """How far this bell's ring will carry, from the ring you drew.

        Geometry, not the live measurement, and the difference is a feel bug
        rather than a philosophical one. Reach is drawn on the floor as a
        promise the player positions against, and the emitted spectrum
        wobbles from strike transient to sustain - so reading it live made
        the circle jump between 400 and 560px several times a second while
        the player was trying to stand on its edge. A promise that moves is
        not a promise.

        The ring the strike actually throws still computes its own extent
        from its own spectrum, so a swelled bell really does carry further
        or less far than the circle said. The circle is what you aim with;
        the spectrum is what happens.
        """
        n = self.note
        return notes.reach_for(n if n >= 0 else max(0.0, self.live_note))

    @property
    def color(self) -> tuple:
        return notes.note_color(max(0.0, self.live_note))

    @property
    def push(self) -> float:
        """+1 pushes, -1 pulls. This is the winding direction and nothing
        else: the same ring drawn the other way round inverts every impulse
        it makes."""
        if not self.loops:
            return 1.0
        i = max(0, min(N_NOTES - 1, int(round(max(0.0, self.note)))))
        return 1.0 if self.chirality[i] >= 0 else -1.0

    @property
    def metal_cost(self) -> float:
        return sum(s.length() * getattr(s.ink_type, "cost_per_px", 1.0) for s in self.strokes)

    @property
    def charge(self) -> float:
        return min(1.0, self.network.total_energy() / CHARGE_REFERENCE) if self.network else 0.0

    @property
    def beat_phase(self) -> float:
        p = self.period
        return (self.time % p) / p if p > 1e-6 else 0.0

    def beat_offset(self) -> float:
        """Seconds to (negative) or from (positive) the nearest swell."""
        p = self.period
        if p <= 1e-6:
            return 0.0
        frac = (self.time % p) / p
        return (frac - 1.0) * p if frac > 0.5 else frac * p

    def on_beat(self) -> bool:
        return abs(self.beat_offset()) <= notes.BEAT_WINDOW

    # ------------------------------------------------------------- playing

    def strike(self) -> bool:
        """Hammer on metal. Returns whether it landed on the swell."""
        if self.cracked or self.strike_node is None:
            return False
        n = STRIKE_MAX_SAMPLES
        if self.loops and self.loops[0][1] > 1e-9:
            n = int(max(STRIKE_MIN_SAMPLES, min(STRIKE_MAX_SAMPLES, round(1.0 / self.loops[0][1]))))
        self._burst = _bipolar_burst(n, STRIKE_AMPLITUDE)
        self._burst_i = 0
        return self.on_beat()

    def set_swell(self, on: bool) -> None:
        if self.cracked:
            self._swell = False
            return
        if on and not self._swell:
            self._swell_steps = 0
            self._swell_f0 = self.loops[0][1] if self.loops else SWELL_FALLBACK_F0
        self._swell = bool(on) and self.strike_node is not None

    @property
    def swelling(self) -> bool:
        return self._swell

    def take_output(self) -> tuple:
        """Everything the bell has radiated since this was last called.

        Taking rather than streaming is what makes the groove real: strike
        on the swell, the loop reinforces, the pool is fuller, the ring is
        bigger - and no part of that is a bonus applied afterwards.
        """
        out = self._pool
        self._pool = [0.0] * N_NOTES
        return out, sum(out)

    def peek_output(self) -> list:
        return list(self._pool)

    def silence(self) -> None:
        """Drop everything stored. Used when swapping bells so a bell does
        not keep pouring into a ring the player is no longer holding."""
        self._swell = False
        self._burst = []
        self._burst_i = 0

    # ------------------------------------------------------------ stepping

    def advance(self, dt: float, max_steps: int = 10) -> None:
        if self.network is None or self.is_empty:
            return
        self._accum += dt
        steps = 0
        while self._accum >= SIM_DT and steps < max_steps:
            self._accum -= SIM_DT
            steps += 1
            self._step()
        if steps >= max_steps:
            self._accum = 0.0
        self._update_char(dt)
        self.time += dt

    def _step(self) -> None:
        node = self.strike_node
        injections = {}

        if node is not None and self._burst_i < len(self._burst):
            injections[node] = injections.get(node, 0.0) + self._burst[self._burst_i]
            self._burst_i += 1

        if self._swell and node is not None:
            k = self._swell_steps
            attack = min(1.0, k / SWELL_ATTACK_STEPS)
            over = 1.0 + SWELL_GAIN * min(1.0, max(0, k - SWELL_ATTACK_STEPS) / SWELL_GAIN_STEPS)
            amp = SWELL_AMPLITUDE * attack * over
            # How far the junctions have folded decides how much of the
            # drive has moved onto the loop's second mode.
            c = min(1.0, self.saturation / SWELL_CLIMB_SATURATION)
            self.climb_drive = c
            f = self._swell_f0
            sample = amp * (
                (1.0 - c) * math.sin(2 * math.pi * f * k)
                + c * SWELL_CLIMB_GAIN * math.sin(2 * math.pi * 2.0 * f * k)
            )
            injections[node] = injections.get(node, 0.0) + sample
            self._swell_steps += 1
        elif not self._swell:
            self.climb_drive = 0.0

        self.network.step(injections)

        sat = 0.0
        for n in self.network.nodes.values():
            if n.nl_a is None:
                continue
            sat = max(sat, min(1.5, abs(n.last_emitted) * n.nl_a))
        # Peak-hold with a slow bleed: a junction only folds on the crest of
        # each cycle, so an instantaneous sample reads zero most steps.
        self.saturation = max(sat, self.saturation * 0.97)

        if self.cracked:
            self._live = [0.0] * N_NOTES
            return

        live = [0.0] * N_NOTES

        # The body of the bell - the primary voice.
        if self.near_node is not None:
            bands = self.near_bank.process(self.network.nodes[self.near_node].last_emitted)
            for i in range(N_NOTES):
                live[i] += bands[i]

        # Open ends add on top, scaled by how freely they actually radiate.
        for term in self.terminals:
            sample = self.network.nodes[term["node_id"]].last_emitted * term["rad_gain"]
            bands = term["bank"].process(sample)
            for i in range(N_NOTES):
                live[i] += bands[i] * 0.6

        quiet = max(0.0, 1.0 - self.char)
        self._live = [b * quiet for b in live]

        # Take the radiated energy out of the network for real. The spectrum
        # says *what* leaves; the energy balance says *how much*, and the two
        # are no longer allowed to disagree.
        stored = self.network.total_energy()
        if stored > 1e-12:
            leaving = stored * self.body_rad * quiet
            if leaving > 1e-15:
                factor = math.sqrt(max(0.0, (stored - leaving) / stored))
                for edge in self.network.edges.values():
                    edge.forward.buffer *= factor
                    edge.backward.buffer *= factor
                shape_total = sum(self._live)
                if shape_total > 1e-12:
                    gain = leaving * OUTPUT_SCALE * self.out_gain / shape_total
                    for i in range(N_NOTES):
                        self._pool[i] += self._live[i] * gain

    def _update_char(self, dt: float) -> None:
        if self.saturation > CHAR_ONSET:
            over = (self.saturation - CHAR_ONSET) / (1.0 - CHAR_ONSET)
            self.char = min(1.4, self.char + CHAR_RATE * min(1.0, over) * dt)
        else:
            self.char = max(0.0, self.char - CHAR_COOL * dt)

        if self.char >= CHAR_CRACK_AT:
            if not self.cracked:
                self.cracked = True
                self._swell = False
        elif self.cracked and self.char < CHAR_RECOVER_AT:
            self.cracked = False

    # ------------------------------------------------------------ viewing

    def wave_samples(self, per_edge: int = 56) -> list:
        """Where the energy actually is, right now, along the metal.

        Returns [(local_point, signed_amplitude), ...] per edge. The
        simulation stores each edge as two delay lines whose buffers *are*
        the wave in physical order, so this is not a visualisation of the
        state - it is the state, mapped onto the polyline the player drew.

        This is the single largest piece of feedback the Foundry was
        missing. Striking a bell used to move some numbers on a panel; now
        the pulse visibly races around the ring, meets itself, and stands.
        A player can see their bell resonate, which is the thing the entire
        design is about and which was, until now, invisible.
        """
        if self.network is None or self.graph is None:
            return []
        out = []
        for i, edge in enumerate(self.graph.edges):
            net_edge = self.network.edges.get(i)
            poly = edge.polyline
            if net_edge is None or len(poly) < 2:
                continue
            fwd = net_edge.forward.spatial_profile()
            bwd = net_edge.backward.spatial_profile()
            if len(fwd) < 2:
                continue
            # Forward runs A->B and backward B->A, so the standing wave at a
            # point is the sum of the two travelling waves passing through it.
            total = fwd + bwd[::-1]
            n = min(per_edge, len(total))
            pts = []
            for k in range(n):
                t = k / max(1, n - 1)
                idx = int(t * (len(total) - 1))
                pi = t * (len(poly) - 1)
                lo = int(pi)
                hi = min(len(poly) - 1, lo + 1)
                f = pi - lo
                p = poly[lo] + (poly[hi] - poly[lo]) * f
                pts.append((p, float(total[idx])))
            out.append(pts)
        return out

    def spectrum(self) -> list:
        """What it is emitting right now, for the meter."""
        return list(self._live)

    # ----------------------------------------------------------- transport

    def clone(self) -> "Bell":
        return Bell.from_dict(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "strokes": [
                {
                    "metal": s.ink_type.name,
                    "points": [[round(p.x, 2), round(p.y, 2)] for p in s.points],
                }
                for s in self.strokes
            ],
        }

    @staticmethod
    def from_dict(data: dict) -> "Bell":
        strokes = []
        for s in data.get("strokes", []):
            pts = [pygame.Vector2(x, y) for x, y in s.get("points", [])]
            if len(pts) >= 2:
                strokes.append(Stroke(points=pts, ink_type=metal_by_name(s.get("metal", "Bronze"))))
        return Bell(data.get("name", "bell"), strokes)


def _bipolar_burst(n_samples: int, amplitude: float = 1.0) -> list:
    """A zero-mean strike.

    The sim ships a raised-cosine *window*, which is unipolar, so half its
    energy sits at DC - and the analyser's lowest band has a skirt running
    down toward DC, so every strike of it would land on BOURDON no matter
    what was drawn. Windowing one full sine cycle keeps the smooth edges
    (still a strike, not a click) while removing the DC term, which hands
    note selection back to the ring's geometry, where the design wants it.
    The sim's own version is left untouched; the selftests measure it.
    """
    if n_samples < 1:
        return []
    import numpy as np

    t = np.linspace(0, 1, n_samples, endpoint=False)
    window = 0.5 * (1 - np.cos(2 * np.pi * t))
    return (amplitude * window * np.sin(2 * np.pi * t)).tolist()


def ring_reach(band_energies: list, floor: float = 0.06) -> float:
    """How far a ring carrying this spectrum gets before there is nothing
    left of it.

    The old build expressed the range/pitch tradeoff as a per-second decay
    on a projectile, which is correct and invisible - the player watched
    their motes fade and concluded the game was weak rather than that heat
    is short-ranged. Here it is a radius, drawn on the ground before the
    strike lands.
    """
    total = sum(band_energies)
    if total <= 1e-12:
        return notes.NOTE_REACH[-1]
    far = notes.NOTE_REACH[-1]
    for i, e in enumerate(band_energies):
        if e / total >= floor:
            far = max(far, notes.NOTE_REACH[i])
    return far


def band_survival(note_index: int, radius: float) -> float:
    """What fraction of one note survives out to `radius`.

    Quadratic rather than linear so the falloff has a visible shoulder: a
    ring is at full strength near the caster and thins fast as it runs out,
    which is what makes stepping in worth doing.
    """
    reach = notes.NOTE_REACH[max(0, min(notes.N_NOTES - 1, note_index))]
    if radius >= reach:
        return 0.0
    t = radius / reach
    return (1.0 - t * t) ** 0.8


def survived(band_energies: list, radius: float) -> list:
    """The spectrum of a ring by the time it has grown to `radius`.

    This is the single most load-bearing function in the combat layer: it is
    why a small bell has to be played nose-to-nose and a great one washes a
    room, and it is why one ring visibly cools from hot to deep as it goes.
    """
    return [e * band_survival(i, radius) for i, e in enumerate(band_energies)]
