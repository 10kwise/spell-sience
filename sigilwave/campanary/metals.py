"""Three metals. One sentence each.

The old build had six inks with nine tuned physical parameters apiece, and
the player was expected to hold all of it. Almost none of it was ever
*decided* with: you took whatever the run handed you and drew the same ring
in it.

Three is enough to make a real choice, and each one pulls exactly one knob
so its downside is the same fact as its upside:

    BRONZE     the honest bell. Nothing to say about it.
    SILVER     lets go instantly - loud now, gone now.
    BLACKGLASS folds early - climbs the octave cheaply, and cracks doing it.

Nothing here is an authored drawback. Silver cannot sustain *because* it is
wide open; Blackglass chars *because* it is the same low saturation
threshold that buys it the octave. Same number, both consequences.
"""

from sigilwave.ink import InkType

BRONZE = InkType(
    name="Bronze",
    impedance=50.0,
    broadband_gain_per_sample=0.99975,
    lowpass_coef_per_sample=0.9965,
    rad_admittance_fraction=0.45,
    nl_threshold=3.0,
    nl_asymmetry=0.25,
    coupler_range=30.0,
    cost_per_px=1.0,
    color=(214, 168, 108),
    blurb="The honest bell. Rings long, rings true, asks nothing of you.",
)

SILVER = InkType(
    name="Silver",
    impedance=22.0,
    broadband_gain_per_sample=0.9993,
    lowpass_coef_per_sample=0.996,
    rad_admittance_fraction=0.94,     # wide open: pours it all out at once
    nl_threshold=3.6,
    nl_asymmetry=0.2,
    coupler_range=26.0,
    cost_per_px=1.35,
    color=(206, 232, 255),
    blurb="Wide open. Everything at once, and then nothing. Will not swell.",
)

BLACKGLASS = InkType(
    name="Blackglass",
    impedance=44.0,
    broadband_gain_per_sample=0.9992,
    lowpass_coef_per_sample=0.9945,
    rad_admittance_fraction=0.6,
    nl_threshold=0.7,                 # folds early -> the octave, cheaply
    nl_asymmetry=0.55,                # asymmetric -> the *even* harmonic
    coupler_range=30.0,
    cost_per_px=1.7,
    color=(196, 150, 255),
    blurb="Folds early. Climbs the octave on half a swell - and cracks on the way.",
)

ALL_METALS = [BRONZE, SILVER, BLACKGLASS]
STARTER_METALS = [BRONZE]
UNLOCK_ORDER = [SILVER, BLACKGLASS]
METALS_BY_NAME = {m.name: m for m in ALL_METALS}


def metal_by_name(name: str) -> InkType:
    return METALS_BY_NAME.get(name, BRONZE)
