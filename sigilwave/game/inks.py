"""Ink families — the material palette, and the run's main progression axis.

Design rule every family obeys: **each ink pulls exactly one physical knob
hard, and its downside is the direct consequence of that same knob.** No ink
has an authored drawback. Quicksilver can't hold a charge *because* it
radiates so freely; Emberglass has a low output ceiling *because* it
saturates early (that's what tanh clipping does); Bonewhite barely emits
*because* its terminals are nearly closed.

The intended consequence, which is not stated anywhere in-game: no single
ink makes a complete sigil. A good sigil is a composite — a slate body that
carries energy a long way, tipped with a quicksilver terminal that actually
lets it out. Players discover that by being annoyed that their beautiful
slate sigil is silent, then touching one stroke of quicksilver to its end.
That moment is the whole game in miniature.
"""

from sigilwave.ink import InkType

CHALK = InkType(
    name="Chalk",
    impedance=50.0,
    broadband_gain_per_sample=0.9995,
    lowpass_coef_per_sample=0.995,
    rad_admittance_fraction=0.6,
    nl_threshold=3.0,
    nl_asymmetry=0.25,
    coupler_range=30.0,
    cost_per_px=1.0,
    color=(196, 200, 210),
    blurb="Honest. Middling at everything. The ruler you measure other inks against.",
)

QUICKSILVER = InkType(
    name="Quicksilver",
    impedance=22.0,
    broadband_gain_per_sample=0.9994,
    lowpass_coef_per_sample=0.996,
    rad_admittance_fraction=0.92,   # nearly wide open: pours energy out
    nl_threshold=3.5,
    nl_asymmetry=0.2,
    coupler_range=26.0,
    cost_per_px=1.3,
    color=(190, 225, 255),
    blurb="Wide open. Fires the instant you touch it, and holds nothing at all.",
)

BONEWHITE = InkType(
    name="Bonewhite",
    impedance=150.0,                # big mismatch against everything: reflects
    broadband_gain_per_sample=0.99975,
    lowpass_coef_per_sample=0.9965,
    rad_admittance_fraction=0.10,   # nearly closed: stores, barely emits
    nl_threshold=4.0,
    nl_asymmetry=0.15,
    coupler_range=18.0,
    cost_per_px=1.6,
    color=(240, 236, 214),
    blurb="Dense and nearly sealed. Hoards charge. Reflects what it doesn't like.",
)

EMBERGLASS = InkType(
    name="Emberglass",
    impedance=44.0,
    broadband_gain_per_sample=0.9993,
    lowpass_coef_per_sample=0.994,
    rad_admittance_fraction=0.65,
    nl_threshold=0.85,              # saturates early -> harmonics, low ceiling
    nl_asymmetry=0.55,              # asymmetric -> *even* harmonics -> doubling
    coupler_range=30.0,
    cost_per_px=1.8,
    color=(255, 150, 90),
    blurb="Folds early. Doubles a slow loop up into the hot bands — and caps low.",
)

SLATE = InkType(
    name="Slate",
    impedance=64.0,
    broadband_gain_per_sample=0.99992,  # almost lossless conductor
    lowpass_coef_per_sample=0.9985,     # even the hot bands survive distance
    rad_admittance_fraction=0.18,       # ...but it will not let go of them
    nl_threshold=5.0,
    nl_asymmetry=0.1,
    coupler_range=24.0,
    cost_per_px=2.0,
    color=(140, 170, 190),
    blurb="Carries anything, anywhere, almost free. Emits almost nothing.",
)

VOIDGLASS = InkType(
    name="Voidglass",
    impedance=58.0,
    broadband_gain_per_sample=0.9988,   # lossy: what tunnels arrives thinner
    lowpass_coef_per_sample=0.992,
    rad_admittance_fraction=0.5,
    nl_threshold=3.0,
    nl_asymmetry=0.3,
    coupler_range=96.0,                 # reaches across a room
    cost_per_px=2.4,
    color=(186, 140, 255),
    blurb="Leaks sideways through empty air. Whatever crosses arrives weaker.",
)

ALL_INKS = [CHALK, QUICKSILVER, BONEWHITE, EMBERGLASS, SLATE, VOIDGLASS]
STARTER_INKS = [CHALK, QUICKSILVER]
INKS_BY_NAME = {ink.name: ink for ink in ALL_INKS}

# Unlock order for run rewards — roughly ascending conceptual difficulty.
# Bonewhite (storage) before Emberglass (harmonics) before Voidglass
# (action at a distance), because that is the order the ideas build in.
UNLOCK_ORDER = [BONEWHITE, EMBERGLASS, SLATE, VOIDGLASS]


def ink_by_name(name: str) -> InkType:
    return INKS_BY_NAME.get(name, CHALK)
