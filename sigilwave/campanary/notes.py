"""The whole vocabulary of the game, in one file.

WAVEWRIGHT asked the player to learn six log-spaced analyser bands, an
impedance model, an efficiency ratio and a coupling matrix. CAMPANARY asks
them to learn one sentence:

    A big bell is deep. A small bell is high. That is all size does.

Everything else in this file is that sentence made exact.

The five notes are **exact octaves**. That is not decoration — it is the
reason the whole design closes:

  * f0 = dx / L, so one octave up is one halving of the ring you draw. Size
    and pitch are the same fact, and the player can *see* the ratio.
  * The saturating junction folds a driven loop into its own harmonics, and
    the strongest of those is the second — one octave up. So "drive a bell
    hard and it climbs a note" is not a rule anybody wrote, it is what
    doubling is, and it lands exactly on the next note because the notes are
    exactly octaves.
  * SPARROW is one octave above the smallest ring a hand can draw. It is
    therefore reachable *only* by folding CHIME upward, which is the single
    gate in the game and it gates itself.

Five, not six. The sixth band of the old build bought one more colour and
cost the player a whole extra thing to hold in their head while shrinking
every drawable ring by a factor of two. Four drawable notes with an octave
between each is a ladder you can see; six crowded ones is a gradient you
have to read off a chart.
"""

import math

from sigilwave.sim.filterbank import FilterBank

# --- the ladder ------------------------------------------------------------
# Chosen from the drawable end backwards. BOURDON is the largest ring that
# fits comfortably on the canvas with room to shape it; each note above is
# exactly half of it; SPARROW lands at a 6px radius, which is under what a
# mouse can hold steady, and that is deliberate.
N_NOTES = 5
DX = 4.0                # px per sim sample (the lab's interactive value)
WAVE_C = 400.0          # px/s, global and constant
SIM_DT = DX / WAVE_C    # 0.01s -> a 100Hz sim step

LOOP_PX = [640.0, 320.0, 160.0, 80.0, 40.0]
NOTE_F0 = [DX / L for L in LOOP_PX]        # 0.00625 .. 0.1 cycles/sample
NOTE_RADIUS = [L / (2 * math.pi) for L in LOOP_PX]   # 102, 51, 25, 13, 6.4

BANK_Q = 5.5


def make_bank() -> FilterBank:
    """Every analyser in the game is built here so nothing can drift."""
    return FilterBank(n_bands=N_NOTES, f_min=NOTE_F0[0], f_max=NOTE_F0[-1], q=BANK_Q)


BAND_CENTERS = make_bank().centers

NOTE_NAMES = ["BOURDON", "TENOR", "TREBLE", "CHIME", "SPARROW"]
NOTE_SHORT = ["BRD", "TEN", "TRE", "CHM", "SPW"]

# What each one is, in the fewest words that are still true. These are the
# only descriptions of the system the game ever shows.
NOTE_BLURB = [
    "the great bell - washes the room, tolls slow",
    "the working bell - long reach, steady",
    "carries a fair way, quick to play",
    "short reach - you have to be close",
    "arm's length only - no hand can draw it",
]

# Deep blue -> hot ember. Luminance ramps with hue so the ladder survives
# colour blindness, and pitch carries the same information in the audio, so
# nothing in the game depends on telling two hues apart.
NOTE_COLORS = [
    (86, 132, 255),
    (72, 206, 236),
    (110, 235, 160),
    (255, 190, 84),
    (255, 108, 92),
]

# --- how far a note carries ------------------------------------------------
# The sim damps high bands hard in ink and the old build damped them hard in
# the air too. Both are true and neither was *legible*: "your motes fade"
# is something a player infers after a dozen deaths. Here the same fact is a
# hard radius drawn on the ground, so the tradeoff is visible before the
# strike lands rather than inferred after it misses.
NOTE_REACH = [520.0, 360.0, 240.0, 155.0, 100.0]

# --- tempo -----------------------------------------------------------------
# A loop's round trip is L/c, and that is the bell's own pulse: nobody chose
# these numbers, they fall out of the ring you drew. A BOURDON tolls every
# 1.6s; a CHIME swings five times a second.
#
# Five times a second is not a rhythm a person can play, so the small bells
# are played on every second or fourth swing - which is what a ringer does
# with a light bell, and which is the *only* correct way to slow them down.
#
# The first cut of this used a flat floor of 0.26s instead, and the damage
# was not cosmetic: a CHIME's loop turns over every 0.2s, so striking it
# every 0.26s landed each blow a third of a cycle out of phase, and what
# reinforced was not the fundamental but the second harmonic. Measured, a
# tapped CHIME was emitting 94% SPARROW - it could not play its own note at
# all, and the only enemy it was meant to answer had become immune to it.
# Doubling keeps every strike phase-locked to the loop, so what compounds is
# the note the player drew.
MIN_PLAYABLE = 0.30


def playable_period(raw: float) -> float:
    """The loop's own period, doubled until a person can play it."""
    if raw <= 1e-6:
        return 0.0
    p = raw
    while p < MIN_PLAYABLE:
        p *= 2.0
    return p


NOTE_PERIOD = [playable_period(L / WAVE_C) for L in LOOP_PX]
BEAT_FLOOR = MIN_PLAYABLE

# How wide the on-beat window is, in seconds either side of the swell. This
# is the forgiving-groove number: generous enough that a player who is
# feeling the pulse rather than counting it lands it, tight enough that
# mashing does not.
BEAT_WINDOW = 0.11
OFF_BEAT_SCALE = 0.4      # an off-beat strike is never worthless

# Consecutive on-beat strikes compound. Reset by a miss or by taking a hit,
# so the groove is something you can lose.
CHORUS_STEPS = [1.0, 1.25, 1.55, 2.0]

# --- matching --------------------------------------------------------------
# How sharply a note has to match to crack something. Much tighter than the
# old build's 1.15: at sigma 0.50 a whole octave off is 1.8% and a third of
# an octave is 64%. So a wrong note is *wrong* and a slightly flat one is
# nearly fine - which is the shape you want, because tuning has to be
# roughly right without ever having to be exact.
MATCH_SIGMA = 0.50


def match_curve(note: float, sigma: float = MATCH_SIGMA) -> list:
    """Per-note crack multiplier for a thing that rings at `note`."""
    return [math.exp(-(((i - note) / sigma) ** 2)) for i in range(N_NOTES)]


def note_color(note: float) -> tuple:
    """Interpolated colour for a fractional note, so a bell that is tuned
    between two notes reads as being between two colours."""
    i = max(0.0, min(N_NOTES - 1.0, float(note)))
    lo = int(i)
    hi = min(N_NOTES - 1, lo + 1)
    t = i - lo
    a, b = NOTE_COLORS[lo], NOTE_COLORS[hi]
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def note_name(note: float) -> str:
    """Nearest name, plus how far off it is. This is the tuner's readout and
    it is the only assay the game has."""
    i = int(round(max(0.0, min(N_NOTES - 1.0, note))))
    return NOTE_NAMES[i]


def cents_off(note: float) -> int:
    """How far from the nearest true note, in cents.

    Cents because the notes are exact octaves: one note apart is 1200 cents,
    so the number is a real musical quantity rather than a made-up percent.
    A guitar tuner reads in cents and everyone has seen a guitar tuner - the
    UI teaches itself.
    """
    i = round(max(0.0, min(N_NOTES - 1.0, note)))
    return int(round((note - i) * 1200))


def reach_for(note: float) -> float:
    i = max(0.0, min(N_NOTES - 1.0, float(note)))
    lo = int(i)
    hi = min(N_NOTES - 1, lo + 1)
    t = i - lo
    return NOTE_REACH[lo] + (NOTE_REACH[hi] - NOTE_REACH[lo]) * t


def period_for(note: float) -> float:
    i = int(round(max(0.0, min(N_NOTES - 1.0, note))))
    return NOTE_PERIOD[i]


def hz_for(note: float) -> float:
    """Audible pitch. The notes are exact octaves in the simulation, so they
    are exact octaves in the ear: A1 through A5. What you hear IS what you
    drew, transposed into the range a speaker can reproduce - and matching
    an enemy's hum by ear is the same act as matching its band.
    """
    return 55.0 * (2.0 ** max(0.0, min(4.0, float(note))))


def note_from_f0(f0: float) -> float:
    """Fractional note index from a loop's fundamental.

    Log-spaced octaves, so this is just a base-2 logarithm of the frequency
    ratio - which is also why the tuner can report honest cents.
    """
    if f0 <= 1e-9:
        return 0.0
    return max(0.0, min(float(N_NOTES - 1), math.log2(f0 / NOTE_F0[0])))


def note_from_bands(band_energies: list) -> tuple:
    """(fractional note, total energy) - the energy-weighted centroid, so a
    bell putting out two notes reads as sitting between them."""
    total = sum(band_energies)
    if total <= 1e-12:
        return 0.0, 0.0
    return sum(i * e for i, e in enumerate(band_energies)) / total, total


# --- the exchange rate -----------------------------------------------------
# The physics hands out wildly unequal energy per note and it is right to: a
# 640px ring stores a lot and rings for seconds, a 40px ring stores almost
# nothing and is done in a tenth of one. Measured, a BOURDON delivers about
# sixty times what a CHIME does per strike. Left alone that means "always
# draw the biggest bell", which collapses the ladder into one rung.
#
# These are the measured inverse (see `calibrate.py`), so an on-note strike
# is worth about the same wherever on the ladder it lands. The *difficulty*
# of the small bells is not expressed here and must not be: it is already
# expressed as reach on the ground, where the player can see it.
NOTE_POWER = [0.33, 1.0, 3.8, 21.5, 2.0]


def match_of(band_energies: list, curve: list) -> float:
    """0..1 - how much of this ring's *shape* lands where the target is weak.

    Shape, not energy, and that separation is load-bearing. The first cut of
    this applied the exchange rate per band, which quietly made spectral
    leakage lethal: a TENOR ring genuinely carries a few percent of its
    energy an octave up (a loop rings at its harmonics; that is what a loop
    is), and multiplying that few percent by the small bells' 13x exchange
    rate turned it into half a correct hit. Measured, a TENOR was killing a
    CHIME-tuned Glasswing in four strikes - the gate the whole game rests on
    was leaking through the balance table rather than through the physics.

    Matching the normalised shape and scaling by the ring's *own* note keeps
    the two questions apart: how right is this note, and how much of it is
    there.
    """
    total = sum(band_energies)
    if total <= 1e-12:
        return 0.0
    return min(1.0, sum(e * c for e, c in zip(band_energies, curve)) / total)


def carrying(band_energies: list) -> float:
    """How much ring there is, on the ladder's common scale."""
    centre, total = note_from_bands(band_energies)
    if total <= 1e-12:
        return 0.0
    i = max(0.0, min(N_NOTES - 1.0, centre))
    lo = int(i)
    hi = min(N_NOTES - 1, lo + 1)
    t = i - lo
    weight = NOTE_POWER[lo] + (NOTE_POWER[hi] - NOTE_POWER[lo]) * t
    return total * weight


def strike_value(band_energies: list, curve: list) -> float:
    """What this ring is worth against this target: how right, times how
    much. The quantity that becomes crack."""
    return match_of(band_energies, curve) * carrying(band_energies)


# Kept as the name the feedback layer reads, because "purity" is what the
# flash and the pitch of the hit are keyed to.
purity = match_of
