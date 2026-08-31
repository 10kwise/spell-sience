"""Analyzer (design doc §4.1, §2.9): a filter bank per terminal turning the
radiated waveform into per-band energy, which the Coupler then maps onto
world fields. Biquad bandpass over Goertzel per the doc's own preference —
cheap, and yields the per-frame energy quantity directly.

Band center frequencies are in cycles/sample (of the sim's own fixed step),
not Hz — consistent with how resonance was measured in selftest_graph.py.
"""

import math


class BiquadBandpass:
    """RBJ cookbook constant-skirt-gain bandpass, Direct Form I."""

    def __init__(self, center_freq: float, q: float):
        w0 = 2 * math.pi * center_freq
        alpha = math.sin(w0) / (2 * q)
        cos_w0 = math.cos(w0)

        a0 = 1 + alpha
        self.b0 = alpha / a0
        self.b1 = 0.0
        self.b2 = -alpha / a0
        self.a1 = (-2 * cos_w0) / a0
        self.a2 = (1 - alpha) / a0

        self.x1 = self.x2 = 0.0
        self.y1 = self.y2 = 0.0

    def process(self, x: float) -> float:
        y = self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2 - self.a1 * self.y1 - self.a2 * self.y2
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y


class FilterBank:
    def __init__(self, n_bands: int = 6, f_min: float = 0.01, f_max: float = 0.4, q: float = 3.0, envelope_coef: float = 0.05):
        log_min, log_max = math.log(f_min), math.log(f_max)
        self.centers = [math.exp(log_min + (log_max - log_min) * i / (n_bands - 1)) for i in range(n_bands)]
        self.bands = [BiquadBandpass(f, q) for f in self.centers]
        self.envelope_coef = envelope_coef
        self.energies = [0.0] * n_bands

    def process(self, sample: float) -> list:
        for i, band in enumerate(self.bands):
            filtered = band.process(sample)
            self.energies[i] += self.envelope_coef * (filtered * filtered - self.energies[i])
        return self.energies
