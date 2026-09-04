"""Coupler (design doc §2.9): band energies x chirality -> world field
impulses via a data-driven matrix M[band][field]. Three fields now (stage 6
of the build order):

  Kinetic  - low bands,  signed by chirality (push vs pull)
  Thermal  - high bands, signed by chirality (burn vs chill)
  Phase    - one narrow upper band, unsigned (magnitude only — "how much
             this matter stops interacting", not a push/pull duality)

These weight vectors are plain lists so they can move to a real data file
later (as the doc suggests) without the analyzer or world code changing.
Index-aligned with FilterBank's log-spaced bands.
"""

KINETIC_BAND_WEIGHTS = [1.0, 0.7, 0.4, 0.2, 0.08, 0.03]
THERMAL_BAND_WEIGHTS = [0.03, 0.08, 0.2, 0.4, 0.7, 1.0]
PHASE_BAND_WEIGHTS = [0.0, 0.0, 0.0, 0.05, 0.3, 1.0]


def _weighted_sum(band_energies: list, weights: list, chirality: list | None) -> float:
    n = min(len(weights), len(band_energies))
    total = 0.0
    for i in range(n):
        sign = chirality[i] if chirality is not None else 1.0
        total += weights[i] * band_energies[i] * sign
    return total


def kinetic_drive_from_bands(band_energies: list, chirality: list | None = None) -> float:
    return _weighted_sum(band_energies, KINETIC_BAND_WEIGHTS, chirality)


def thermal_drive_from_bands(band_energies: list, chirality: list | None = None) -> float:
    return _weighted_sum(band_energies, THERMAL_BAND_WEIGHTS, chirality)


def phase_drive_from_bands(band_energies: list) -> float:
    return _weighted_sum(band_energies, PHASE_BAND_WEIGHTS, None)
