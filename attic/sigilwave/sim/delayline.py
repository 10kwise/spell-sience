"""A single-direction delay line: a ring buffer where read-then-write each
step gives an exact N-sample delay (design doc §2.1 — 'propagation is a
ring-buffer read/write')."""

import numpy as np


class DelayLine:
    def __init__(self, length_samples: int):
        if length_samples < 1:
            raise ValueError("delay line must be at least 1 sample")
        self.length = length_samples
        self.buffer = np.zeros(length_samples, dtype=np.float64)
        self.ptr = 0

    def read_tail(self) -> float:
        """The sample about to exit this step (does not advance the buffer)."""
        return float(self.buffer[self.ptr])

    def push(self, value: float) -> None:
        """Overwrite the just-read slot and advance the write head."""
        self.buffer[self.ptr] = value
        self.ptr = (self.ptr + 1) % self.length

    def spatial_profile(self) -> np.ndarray:
        """Buffer contents in physical order: index 0 is the sample nearest
        to exiting (the far end), index -1 is the most recently injected
        sample (the near end). For visualization only."""
        return np.roll(self.buffer, -self.ptr)

    def peek(self, offset_from_near_end: int) -> float:
        """Read the sample currently `offset` steps into the line from the
        near (entry) end, without disturbing anything — used by couplers
        (§2.7) to reach an interior point rather than just the boundary."""
        idx = (self.ptr + self.length - 1 - offset_from_near_end) % self.length
        return float(self.buffer[idx])

    def poke(self, offset_from_near_end: int, value: float) -> None:
        idx = (self.ptr + self.length - 1 - offset_from_near_end) % self.length
        self.buffer[idx] = value

    def energy(self, admittance: float) -> float:
        return float(np.sum(self.buffer ** 2) * admittance)


class OnePoleLowpass:
    """Frequency-dependent loss (design doc §2.5): high frequencies decay
    faster than low ones, which is what makes heat sigils range-limited and
    kinetic sigils long-range without anyone coding that tradeoff directly."""

    def __init__(self, coef: float = 1.0):
        self.coef = coef  # 1.0 = no filtering (passthrough)
        self.state = 0.0

    def process(self, x: float) -> float:
        self.state += self.coef * (x - self.state)
        return self.state


class LossFilter:
    """Broadband attenuation (g_total, applied once per read at the junction
    end rather than per internal sample) plus the one-pole lowpass above."""

    def __init__(self, broadband_gain: float = 1.0, lowpass_coef: float = 1.0):
        self.broadband_gain = broadband_gain
        self.lowpass = OnePoleLowpass(lowpass_coef)

    def process(self, x: float) -> float:
        return self.lowpass.process(x * self.broadband_gain)
