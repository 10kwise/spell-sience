"""Where the drawing meets the water. SUBMERGED.md 5.

A mouth is the only part that touches the ocean, so this is the whole
interface between the two halves of the game: on one side a waveguide network
holding energy, on the other a medium carrying wavefronts. Nothing else
crosses.

**The merge rule (5).** *Mouths close enough together merge into one wider
mouth: an arc drawn between them. The same energy spread over more width hits
softer and covers more.* So an output is four facts, all read off the
drawing and none of them a number the player types:

| fact | where it comes from |
|---|---|
| **width** | the arc length through the merged mouths |
| **intensity** | energy divided by that width |
| **direction** | the arc's outward normal |
| **focus** | the arc's curvature |

**Curvature is derived, not chosen.** 5.1: width does two opposite things at
once, because a narrow aperture *diffracts*. A single mouth cannot throw a
collimated pencil however carefully it is aimed -- its beam spreads at about
one wavelength per aperture width, and that spreading is added here as a
convex term no drawing can cancel:

    curvature = what_was_drawn + 2 * wavelength / span^2

A point mouth is therefore near-omnidirectional no matter what, a long arc
holds its beam, and the two behaviours come from the same expression rather
than from two cases. It also couples the machine's *note* to its beam: a low
note has a long wavelength and spreads harder, so the deep-carrying notes are
exactly the ones that will not stay narrow. Nobody has to be told that.
"""

import math
from dataclasses import dataclass, field

import pygame

from ..medium.front import Front
from .parts import SIM_DT, WAVE_C

V = pygame.Vector2

# Mouths within this of each other are one mouth. Comfortably larger than
# JOIN_EPS (6 px, where ends fuse into a fork) and than GAP_MAX (30 px, where
# they couple through the water): merging is about what the OUTPUT looks like
# from outside, not about whether the wires are connected, and two ends can
# be electrically unrelated and still radiate as one aperture.
MERGE_DIST = 46.0

# A single mouth still has a physical width -- an aperture of literally zero
# would be a division by zero and an infinitely bright lance, which 5.1 spent
# a whole section explaining is not a thing.
MIN_SPAN = 7.0

# Radiated energy is gathered for this many sim steps and released as one
# front. Long enough that a front carries a meaningful amount rather than the
# renderer drowning in near-empty ones; short enough that a machine firing on
# its own beat produces visibly separate fronts.
EMIT_STRIDE = 12
EMIT_FLOOR = 1e-6

# Frequency is estimated from the radiated signal's own zero crossings rather
# than declared: a machine's note is whatever it is actually emitting, which
# may not be the note of any loop in it once saturation has doubled things.
# Crossings are counted on a SMOOTHED signal. A mouth's output is not a pure
# tone -- junction reflections ring, and a cavitation collapse is broadband
# by definition -- and counting raw zero crossings reports the fastest thing
# present rather than the pitch. Measured, a machine driven at 234 Hz read as
# 3262 Hz, which put it outside the band of the very gadget it was built to
# run. One pole at roughly 4 kHz in water terms: above every drawable note
# (the whistle is 3750 Hz) and below the ringing.
PITCH_SMOOTHING = 0.5

FREQ_WINDOW = 64
FREQ_MIN = 20.0
FREQ_MAX = 30000.0

# THE TWO SCALES, and why they are not the same number.
#
# The world is drawn at one pixel per metre, because the sound channel needs
# a kilometre of water column to exist at all (7.3) and the room is 800 px
# tall. The DRAWING is not at that scale: a machine is an instrument you
# hold, not a structure a kilometre across, so one bench pixel is one
# centimetre.
#
# Getting this wrong is silent and total. The bench clock runs at 100 Hz, so
# its loops lap at 0.31-5 Hz and 7.4's claimed 40 Hz - 4 kHz band was out by
# three orders of magnitude -- every range law, every absorption figure and
# every bubble resonance in 7 was being handed a note from the wrong universe.
#
# The conversion is independent of loop size, which is what makes it a single
# constant rather than a table: a loop's bench note is WAVE_C/circumference
# and its real note is c_water/(circumference * BENCH_M_PER_PX), so the ratio
# is c_water/(WAVE_C * BENCH_M_PER_PX) and the circumference cancels.
BENCH_M_PER_PX = 0.01          # one bench pixel is a centimetre
C_WATER = 1500.0               # m/s, seawater
WATER_FREQ_RATIO = C_WATER / (WAVE_C * BENCH_M_PER_PX)

# Which puts the drawable ladder where 7.4 always wanted it:
#   swell 1280 px = 12.8 m ->  117 Hz      ping   160 px = 1.6 m ->  937 Hz
#   groan  640 px =  6.4 m ->  234 Hz      chirp   80 px = 0.8 m -> 1875 Hz
#   hum    320 px =  3.2 m ->  469 Hz      whistle 40 px = 0.4 m -> 3750 Hz


@dataclass
class MouthGroup:
    """One aperture: either a lone open end or several merged into an arc."""

    node_ids: list
    positions: list
    centre: V
    outward: V
    span: float
    drawn_curvature: float
    accum: float = 0.0
    # Instantaneous radiated power and the last note actually measured.
    # `accum` and `crossings` are reset every emit stride because they batch
    # fronts for the renderer, so anything asking "what is this mouth doing
    # right now" -- thrust (8.4), gadgets -- must not read them. It read as a
    # dead machine three steps out of four.
    power_now: float = 0.0
    last_freq: float = 0.0
    crossings: int = 0
    # Frequency is measured from the INTERVAL between zero crossings, kept as
    # a rolling average, not by counting crossings inside the emit window.
    # The window is 12 steps and a 300 Hz note has a 125-step period, so
    # counting inside it can only ever report "one crossing" and read 1562 Hz
    # for a 300 Hz drive -- five times wrong, and wrong in the direction that
    # makes every gadget refuse a machine that was driving it correctly.
    _last_cross: int = -1
    _interval: float = 0.0
    _smooth: float = 0.0
    _last_sign: int = 0
    _window: int = 0
    emitted: int = 0
    history: list = field(default_factory=list)

    def shape(self) -> str:
        """What this aperture is, in the vocabulary of 5.1's table."""
        if len(self.node_ids) == 1:
            return "spitter"
        if self.drawn_curvature < -1e-4:
            return "sniper"
        if self.drawn_curvature > 1e-4:
            return "wash"
        return "carry"


def _outward_at(assembly, node_id, pos):
    """Which way energy leaves. A run radiates along its own last segment --
    the wire points where it points -- so this reads the polyline rather than
    guessing from the shape of the assembly."""
    best = None
    for track in assembly.edge_tracks():
        pts = track[0] if isinstance(track, tuple) else track
        try:
            a, b = V(pts[0]), V(pts[-1])
        except (TypeError, IndexError):
            continue
        for end, inward in ((a, V(pts[1]) if len(pts) > 1 else b),
                            (b, V(pts[-2]) if len(pts) > 1 else a)):
            d = (end - pos).length()
            if d < 1.0 and (best is None or d < best[0]):
                away = end - inward
                if away.length_squared() > 1e-9:
                    best = (d, away.normalize())
    return best[1] if best else V(1.0, 0.0)


def _fit_curvature(points, outward):
    """Signed curvature of the arc through these mouths.

    Negative is concave -- bending toward what it faces, which is the sniper
    of 5.1 -- and positive is convex. Three points define a circle; two
    define a straight aperture; one has no drawn shape at all and gets its
    entire spreading from diffraction.
    """
    if len(points) < 3:
        return 0.0
    a, b, c = V(points[0]), V(points[len(points) // 2]), V(points[-1])
    area2 = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
    if abs(area2) < 1e-9:
        return 0.0
    la, lb, lc = (b - c).length(), (a - c).length(), (a - b).length()
    if la * lb * lc < 1e-9:
        return 0.0
    kappa = 2.0 * area2 / (la * lb * lc)
    # Sign it against the direction the aperture faces: bulging into the
    # water is convex, cupping away from it is concave.
    chord = (c - a)
    if chord.length_squared() < 1e-9:
        return 0.0
    bulge = (b - (a + c) * 0.5)
    return -abs(kappa) if bulge.dot(outward) < 0 else abs(kappa)


def merge_mouths(assembly, merge_dist: float = MERGE_DIST) -> list:
    """Group the assembly's open ends into apertures."""
    mouths = assembly.mouth_nodes()
    if not mouths:
        return []

    # Single-linkage clustering: an aperture is a chain of mouths each near
    # the next, so three ends evenly spaced 40 px apart are one 80 px arc
    # rather than three lances, which is what "merge" has to mean if a player
    # is going to build a wall by placing ends in a row.
    ids = [nid for nid, _ in mouths]
    pos = {nid: V(p) for nid, p in mouths}
    parent = {nid: nid for nid in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if (pos[a] - pos[b]).length() <= merge_dist:
                parent[find(a)] = find(b)

    clusters = {}
    for nid in ids:
        clusters.setdefault(find(nid), []).append(nid)

    groups = []
    for members in clusters.values():
        pts = [pos[n] for n in members]
        outward = V(0.0, 0.0)
        for n in members:
            outward += _outward_at(assembly, n, pos[n])
        outward = outward.normalize() if outward.length_squared() > 1e-9 else V(1.0, 0.0)

        if len(pts) > 1:
            # Order along the aperture: project onto the axis perpendicular
            # to the way it faces, which is the direction the arc runs.
            axis = V(-outward.y, outward.x)
            order = sorted(range(len(pts)), key=lambda i: pts[i].dot(axis))
            members = [members[i] for i in order]
            pts = [pts[i] for i in order]
            span = sum((pts[i + 1] - pts[i]).length() for i in range(len(pts) - 1))
        else:
            span = 0.0

        centre = pts[len(pts) // 2] if len(pts) % 2 else (pts[len(pts) // 2 - 1] + pts[len(pts) // 2]) * 0.5
        groups.append(MouthGroup(
            node_ids=members,
            positions=pts,
            centre=centre,
            outward=outward,
            span=max(span, MIN_SPAN),
            drawn_curvature=_fit_curvature(pts, outward),
        ))
    return groups


def wavelength_px(freq: float) -> float:
    """The emitted wavelength, in BENCH pixels.

    This mixed its scales in the first version -- bench sound speed against a
    water frequency -- and the error is not small: it under-reported the
    wavelength by 375x and made every aperture look enormous compared with
    the wave coming out of it, so nothing ever diffracted and nothing ever
    failed to focus. The wave lives in the water; the aperture is drawn on
    the bench; the conversion belongs here and nowhere else.
    """
    return (C_WATER / max(freq, FREQ_MIN)) / BENCH_M_PER_PX


def diffraction_curvature(span: float, freq: float) -> float:
    """The spreading a drawing cannot cancel (5.1).

    Beam divergence off an aperture is about one wavelength per width, and a
    front of span w diverging at angle theta is geometrically a convex arc of
    curvature 2*theta/w. Hence 2*lambda/w^2.

    The consequence is sharper than 5.1 guessed: **an aperture narrower than
    its own wavelength cannot be aimed at all.** Below w = lambda the
    diffraction term swamps any curvature that was drawn, and the mouth is a
    point source no matter how carefully it was cupped. So the sniper is not
    available at every note -- it is available only where the drawing is
    several wavelengths across, which at these scales means the HIGH notes.
    Low notes carry far and spray; high notes die fast and can be aimed. That
    pairing was not designed, it is what an aperture is.
    """
    return 2.0 * wavelength_px(freq) / max(span, MIN_SPAN) ** 2


def aperture_wavelengths(span: float, freq: float) -> float:
    """How many wavelengths wide this mouth is. Under about 2, it cannot
    focus; the number is worth showing because it is the whole reason a
    sniper works at one note and not another."""
    return span / max(wavelength_px(freq), 1e-9)


class Emitter:
    """Watches a compiled machine and births fronts out of its mouths.

    Call `step()` after `network.step()`. Energy is gathered per aperture and
    released on a stride, so a machine driven continuously produces a train of
    fronts and a single pulse produces one.
    """

    def __init__(self, assembly, network, c: float = WAVE_C):
        self.assembly = assembly
        self.network = network
        self.c = c
        self.groups = merge_mouths(assembly)
        self.steps = 0
        self.born = 0
        self.radiated_now = 0.0
        self.thrust_now = [0.0, 0.0]

    def step(self) -> list:
        self.steps += 1
        # Radiated energy THIS step, per aperture, kept apart from the
        # accumulator that batches fronts for the renderer. Thrust (8) has to
        # read the real rate: a machine radiates continuously, and reading it
        # off the batched fronts instead made propulsion arrive as two jolts
        # in four seconds with drag eating both.
        self.radiated_now = 0.0
        self.thrust_now = [0.0, 0.0]
        for g in self.groups:
            emitted = 0.0
            for nid in g.node_ids:
                node = self.network.nodes.get(nid)
                if node is None:
                    continue
                u = node.last_emitted
                emitted += u * u * node.rad_admittance
                g._smooth = (g._smooth * PITCH_SMOOTHING
                             + u * (1.0 - PITCH_SMOOTHING))
                u = g._smooth
                s = 1 if u > 0 else (-1 if u < 0 else 0)
                if s and g._last_sign and s != g._last_sign:
                    g.crossings += 1
                    if g._last_cross >= 0:
                        gap = self.steps - g._last_cross
                        g._interval = (gap if g._interval <= 0.0
                                       else g._interval * 0.7 + gap * 0.3)
                    g._last_cross = self.steps
                if s:
                    g._last_sign = s
            g.accum += emitted
            g.power_now = emitted
            g._window += 1
            self.radiated_now += emitted
            self.thrust_now[0] -= g.outward.x * emitted
            self.thrust_now[1] -= g.outward.y * emitted

        if self.steps % EMIT_STRIDE:
            return []

        out = []
        for g in self.groups:
            if g.accum <= EMIT_FLOOR:
                g.accum = 0.0
                g.crossings = 0
                g._window = 0
                continue
            freq = self._freq(g)
            if g._interval > 0.0:
                g.last_freq = freq
            curvature = g.drawn_curvature + diffraction_curvature(g.span, freq)
            out.append(Front(
                (g.centre.x, g.centre.y),
                (g.outward.x, g.outward.y),
                g.span,
                curvature,
                g.accum,
                freq,
                n_vertices=48,
                max_vertices=256,
            ))
            g.history.append((self.steps, g.accum, freq, g.accum / g.span))
            g.emitted += 1
            g.accum = 0.0
            g.crossings = 0
            g._window = 0
        self.born += len(out)
        return out

    def _freq(self, g) -> float:
        """One half-cycle per zero crossing, from the rolling interval.

        Measuring an interval rather than counting inside a fixed window is
        what makes low notes measurable at all: the window is EMIT_STRIDE
        steps and any period longer than that reads as exactly one crossing
        however slow it really is."""
        if g._interval <= 0.0:
            return FREQ_MIN
        bench_hz = 1.0 / (2.0 * g._interval * SIM_DT)
        return max(FREQ_MIN, min(FREQ_MAX, bench_hz * WATER_FREQ_RATIO))
