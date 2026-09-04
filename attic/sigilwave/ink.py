"""The Ink Layer (design doc §4.1): strokes as world-space objects. Owns raw
points and ink properties; resampling to uniform arclength happens here
because the parser needs it and nothing upstream cares about raw mouse
sample spacing."""

from dataclasses import dataclass, field

import pygame


@dataclass
class InkType:
    """Damping coefficients are *per sample*, not per edge (design doc §2.5):
    'g_total = g^N for delay length N' — the compiler raises these to the
    power of each edge's own length_samples, so a longer stroke of the same
    ink attenuates more per traversal than a short one. That length
    dependence is what makes the range/element tradeoff emerge instead of
    being authored per ink type.

    Values tuned (see selftest_damping.py) so a near-DC signal survives long
    runs (kinetic sigils can sprawl) while a high band signal decays hard
    over the same distance (heat sigils stay compact) — at short lengths the
    two bands are barely distinguishable, at long lengths they diverge by an
    order of magnitude or more.
    """

    name: str
    impedance: float = 50.0
    broadband_gain_per_sample: float = 0.9995
    lowpass_coef_per_sample: float = 0.995
    # Y_rad at an open end, as a fraction of the edge's own admittance
    # (§2.4): a blunt/open stroke end radiates hard (large fraction), a
    # tapered one radiates gently and stores energy instead. Not yet tied to
    # actual stroke-end geometry — a fixed per-ink property for now.
    rad_admittance_fraction: float = 0.6
    # Nonlinearity (§2.6): the amplitude scale at which a loop-closing
    # junction starts to saturate, and how asymmetric that saturation is
    # (0 = symmetric tanh, odd harmonics only; >0 buys the even harmonics
    # that thermal-doubling depends on). Large threshold = effectively
    # linear until driven hard.
    nl_threshold: float = 3.0
    nl_asymmetry: float = 0.25
    # --- game-layer properties (physics above, economy/identity below) ---
    # How far this ink reaches across an empty gap to tunnel (2.7). A per-ink
    # property rather than one global g_max, because "how far can I blink"
    # is the single most interesting number to hand a player as a material
    # choice. The compile pass takes the *max* of the two edges' ranges:
    # a long-reach ink reaches out to an ordinary one.
    coupler_range: float = 30.0
    # Ink budget is spent in pixels of stroke; this scales that.
    cost_per_px: float = 1.0
    color: tuple = (150, 158, 172)
    blurb: str = ""


DEFAULT_INK = InkType("default")


def smooth_points(points: list, window: int = 5) -> list:
    """Light box-filter smoothing to take the edge off freehand jitter
    without erasing the drawn shape (window is in *points*, and add_point's
    min_spacing already keeps point spacing roughly constant regardless of
    draw speed, so a small fixed window covers a roughly constant arc-length
    no matter how fast someone draws). Endpoints are preserved exactly so a
    stroke doesn't visibly shrink away from where it was started or ended —
    that matters for parsing, since terminals/junctions anchor to those
    exact points."""
    if len(points) < 3 or window < 3:
        return list(points)

    half = window // 2
    smoothed = []
    for i in range(len(points)):
        lo = max(0, i - half)
        hi = min(len(points), i + half + 1)
        chunk = points[lo:hi]
        smoothed.append(sum(chunk, pygame.Vector2(0, 0)) / len(chunk))

    smoothed[0] = pygame.Vector2(points[0])
    smoothed[-1] = pygame.Vector2(points[-1])
    return smoothed


@dataclass
class Stroke:
    points: list = field(default_factory=list)  # list[pygame.Vector2], raw
    ink_type: InkType = field(default_factory=lambda: DEFAULT_INK)

    def add_point(self, p: pygame.Vector2, min_spacing: float = 3.0) -> None:
        if self.points and (p - self.points[-1]).length() < min_spacing:
            return
        self.points.append(pygame.Vector2(p))

    def length(self) -> float:
        return sum((self.points[i + 1] - self.points[i]).length() for i in range(len(self.points) - 1))

    def resampled(self, dx: float, smoothing_window: int = 5) -> list:
        """Uniform-arclength resample (design doc §4.3 parse step 1), after
        a light smoothing pass on the raw freehand points. Always includes
        the exact start and end points."""
        points = smooth_points(self.points, smoothing_window) if smoothing_window else self.points
        if len(points) < 2:
            return list(points)

        total_length = sum((points[i + 1] - points[i]).length() for i in range(len(points) - 1))
        if total_length < 1e-6:
            return [pygame.Vector2(points[0])]

        n_samples = max(2, round(total_length / dx) + 1)
        targets = [i * total_length / (n_samples - 1) for i in range(n_samples)]

        out = []
        seg_i = 0
        seg_start_dist = 0.0
        seg_vec = points[1] - points[0]
        seg_len = seg_vec.length()

        for target in targets:
            while seg_start_dist + seg_len < target and seg_i < len(points) - 2:
                seg_i += 1
                seg_start_dist += seg_len
                seg_vec = points[seg_i + 1] - points[seg_i]
                seg_len = seg_vec.length()

            local = 0.0 if seg_len < 1e-9 else (target - seg_start_dist) / seg_len
            local = min(1.0, max(0.0, local))
            out.append(points[seg_i] + seg_vec * local)

        return out
