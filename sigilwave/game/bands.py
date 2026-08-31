"""The shared vocabulary between physics and player.

Everything the player learns is anchored to six numbers: the analyzer's six
log-spaced bands. An enemy's weakness is a band. A sigil's output is a band
profile. The hue of every mote, ring and meter in the game is that band's
hue. The first thing a new player learns is "orange things need orange
energy" — which is a colour-matching game — and the *last* thing they learn
is that orange means a short loop, because heat can't travel far (doc 2.5).
Same fact, two depths, one colour.
"""

from sigilwave.sim.filterbank import FilterBank

# The analyser's default range (0.01 - 0.4 cyc/sample) is a sensible span for
# a physics bench, but it is the wrong span for a game, and the mismatch is
# not cosmetic. A loop's fundamental is f0 = dx/L, so a band's centre
# frequency *is* a stroke length: at dx=4, band 5 at 0.4 asks for a 10px
# loop. The parser's minimum edge is 16px. The top two bands were therefore
# unreachable by drawing anything at all — which silently deleted heat,
# phase, and every enemy that would have been tuned to them.
#
# Capping at 0.20 puts the six bands on loops of roughly 500, 263, 138, 72,
# 38 and 20px. The first five are comfortable to draw; the sixth sits right
# at the parser's floor, so it is reachable in practice only by harmonic
# doubling out of band 4 (doc 2.6). That is a deliberate gate: the hottest
# band in the game is the one you have to understand nonlinearity to reach.
GAME_F_MIN = 0.008
GAME_F_MAX = 0.20
N_BANDS = 6
BAND_Q = 3.0


def make_bank() -> FilterBank:
    """Every analyser in the game is built here, so the UI's band centres,
    the chirality matrix and the per-terminal filters can never drift apart."""
    return FilterBank(n_bands=N_BANDS, f_min=GAME_F_MIN, f_max=GAME_F_MAX, q=BAND_Q)


BAND_CENTERS = make_bank().centers

# The loop circumference that rings at each band centre, for the Forge's
# ruler overlay: this is the single most useful number a player can be
# handed, because it converts "I want that colour" into "draw this big".
BAND_LOOP_PX = [4.0 / f for f in BAND_CENTERS]

# Blue (slow, heavy, far-travelling) to red (fast, hot, short-range). The
# luminance ramps as well as the hue, so the spectrum is still readable
# without colour discrimination.
BAND_COLORS = [
    (70, 120, 255),
    (60, 190, 255),
    (70, 235, 190),
    (180, 240, 110),
    (255, 190, 80),
    (255, 105, 85),
]

# Short names the Assay uses in prose. Deliberately physical, not magical:
# the player should end up thinking in frequency, not in elements.
BAND_NAMES = ["deep", "low", "mid", "high", "keen", "sear"]

# What each band reads as in the world, for the tooltip layer.
BAND_FEEL = [
    "heavy shove, long reach",
    "shove, long reach",
    "mixed",
    "mixed, warming",
    "burn, short reach",
    "sear + decohere, very short reach",
]

# Resonant vulnerability (doc 3 "resonant shattering": object resonances are
# the *only* authored part of the elements system). Gaussian rather than a
# lock, so a near-miss band still does something — a player who is one band
# off should feel "close", not "wrong".
VULN_SIGMA = 1.15


def vulnerability_curve(center_band: float, sigma: float = VULN_SIGMA) -> list:
    """Per-band damage multiplier for a thing that rings at `center_band`."""
    import math

    return [math.exp(-(((i - center_band) / sigma) ** 2)) for i in range(N_BANDS)]


def band_color(index: float) -> tuple:
    """Interpolated hue for a fractional band index, so an enemy tuned
    between two bands gets a colour between two hues."""
    i = max(0.0, min(N_BANDS - 1.0, float(index)))
    lo = int(i)
    hi = min(N_BANDS - 1, lo + 1)
    t = i - lo
    a, b = BAND_COLORS[lo], BAND_COLORS[hi]
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def dominant_band(band_energies: list) -> tuple:
    """(fractional band index, total energy) — the energy-weighted centroid
    rather than the argmax, so a two-band output reads as sitting between
    them instead of snapping to whichever is marginally larger."""
    total = sum(band_energies)
    if total <= 1e-12:
        return 0.0, 0.0
    centroid = sum(i * e for i, e in enumerate(band_energies)) / total
    return centroid, total


def spectrum_match(band_energies: list, curve: list) -> float:
    """How much of this emission lands where the target is vulnerable."""
    return sum(e * c for e, c in zip(band_energies, curve))


# ---------------------------------------------------------------------------
# The coupling curve (doc 2.9: "keep the coupling curve in a data file so it
# can be tuned without a rebuild"). This is the one place the game is allowed
# to put its thumb on the scale, and it is doing exactly one job.
#
# The physics hands out wildly unequal amounts of energy per band, and it is
# right to: a big ring stores a lot and rings for seconds, a small ring
# stores little and is finished in a tenth of a second. Measured, a band-4
# ring delivers about 11x less in-band energy per strike than a band-1 ring.
#
# Left alone that would mean heat is simply worse than force, and the whole
# spectrum collapses back to "draw the biggest circle you can" — which is
# the failure mode where a deep system reads as a wrong-answer generator.
# These weights are the measured inverse, so an in-band hit is worth about
# the same wherever you land it.
#
# The *difficulty* of the hot bands is not expressed here and must not be:
# it is already expressed as short range in the air, early saturation, and
# char. Hot is not weaker. Hot is harder to deliver.
BAND_DAMAGE_WEIGHT = [3.6, 1.0, 1.65, 3.2, 11.5, 25.0]


def weighted_match(band_energies: list, curve: list) -> float:
    """Spectrum overlap with the coupling curve applied — the quantity that
    actually becomes hit points."""
    return sum(
        e * c * w for e, c, w in zip(band_energies, curve, BAND_DAMAGE_WEIGHT)
    )
