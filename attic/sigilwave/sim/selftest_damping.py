"""Stage 4 (design doc §9): damping, both broadband and frequency-dependent.
Checks the specific claim in §2.5 — the range/element tradeoff (heat sigils
must be compact, kinetic sigils can be long) falls out of one lowpass
coefficient, without anywhere coding "heat = short range" as a rule.

Run with:

    python -m sigilwave.sim.selftest_damping
"""

import math

import numpy as np

from ..ink import DEFAULT_INK, InkType
from .network import Network

LOW_FREQ = 0.003  # cycles/sample, near-DC — stands in for a low/kinetic band
HIGH_FREQ = 0.15  # cycles/sample — stands in for a high/thermal band


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def measure_survival(length_samples: int, freq: float, ink: InkType = DEFAULT_INK) -> float:
    """Inject a sustained tone at a free end, absorb it at a matched
    termination on the far side (no reflection), and measure how much
    amplitude made the one-way trip.

    The loss filter's output only ever feeds the junction scattering math at
    the far node — it never writes back into the delay line buffer itself
    (that buffer is only touched by pushes from the *other* end). So the
    filtered amplitude has to be recovered from what the terminal actually
    absorbed (radiated = u_j^2 * Y_rad), not by peeking at the raw buffer.
    """
    net = Network()
    net.add_node(0)  # free end: injection point
    y_rad = 1.0 / ink.impedance
    net.add_node(1, rad_admittance=y_rad)  # matched: absorbs, doesn't reflect

    broadband_gain = ink.broadband_gain_per_sample ** length_samples
    lowpass_coef = max(1e-6, ink.lowpass_coef_per_sample ** length_samples)
    net.add_edge(0, 1, length_samples, ink.impedance, broadband_gain, lowpass_coef)

    warmup = length_samples + 200
    total = warmup + 2000
    radiated = np.empty(total)
    for i in range(total):
        radiated[i] = net.step({0: math.sin(2 * math.pi * freq * i)})

    in_rms = 1.0 / math.sqrt(2)  # RMS of a unit sine
    u_j_mean_sq = float(np.mean(radiated[warmup:])) / y_rad  # radiated = u_j^2 * y_rad
    out_rms = math.sqrt(max(0.0, u_j_mean_sq))
    return out_rms / in_rms


def test_short_edge_barely_distinguishes_bands() -> None:
    low = measure_survival(30, LOW_FREQ)
    high = measure_survival(30, HIGH_FREQ)
    check(
        f"short edge (N=30): low/high survival close ({low:.2f} vs {high:.2f}, ratio {low/high:.1f}x)",
        low / high < 2.0,
    )


def test_long_edge_kills_high_band_but_not_low() -> None:
    low = measure_survival(500, LOW_FREQ)
    high = measure_survival(500, HIGH_FREQ)
    check(
        f"long edge (N=500): low band survives ({low:.2f}), high band mostly dies ({high:.2f})",
        low > 0.5 and high < 0.1,
    )
    check(
        f"long edge (N=500): low/high survival ratio is large ({low/high:.1f}x)",
        low / high > 5.0,
    )


def test_high_band_survival_drops_with_length() -> None:
    short_high = measure_survival(30, HIGH_FREQ)
    long_high = measure_survival(500, HIGH_FREQ)
    check(
        f"high band survives much better short (N=30: {short_high:.2f}) than long (N=500: {long_high:.2f})",
        short_high > 5 * long_high,
    )


def test_low_band_survives_long_runs() -> None:
    long_low = measure_survival(500, LOW_FREQ)
    check(
        f"low band still mostly survives at N=500 ({long_low:.2f}) — kinetic sigils can sprawl",
        long_low > 0.5,
    )


def main() -> None:
    tests = [
        test_short_edge_barely_distinguishes_bands,
        test_long_edge_kills_high_band_but_not_low,
        test_high_band_survival_drops_with_length,
        test_low_band_survives_long_runs,
    ]
    for test in tests:
        test()
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
