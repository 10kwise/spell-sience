"""The palette. Near-monochrome, and dark on purpose.

LIMBO and Little Nightmares both work the same way: a world reduced almost to
grey, so that the ONE light source in frame carries every bit of the contrast.
Colour is not spent on the scenery; it is saved for the thing that matters.

So the water ramp here is desaturated cold grey-green and it is very dark --
the brightest band is dimmer than the old palette's *middle*. The two things
allowed to be bright are the ping, which is the pale light you see the room
by, and a vent, which is the only warm thing in the ocean and therefore reads
as a landmark without a label on it.

Depth is the game's progression axis, so the ramp still has to be MONOTONIC in
value: deeper is unambiguously darker, with no clever mid-ramp lift.
"""

import numpy as np

# Surface to abyss. Index 0 is the dim top, index -1 is the deep. The hue is
# barely there -- a cold green-blue cast, not a colour.
# The ramp is shallower than it looks like it should be, because the sight
# pass multiplies it down again before anything reaches the screen. Baking the
# darkness into the palette AS WELL drove the whole picture to black and threw
# away the banding -- which is the thing worth keeping.
WATER = (
    (86, 102, 102),
    (76, 91, 92),
    (67, 81, 83),
    (58, 71, 74),
    (50, 62, 65),
    (43, 54, 57),
    (36, 46, 49),
    (30, 39, 42),
    (25, 33, 35),
    (20, 27, 29),
    (16, 22, 24),
)

# What little of the surface reaches down. Kept cold and nearly grey: the
# moment this goes warm or bright the whole picture reads as a sunny lagoon,
# which is the exact opposite of the brief.
CAUSTIC = (96, 116, 116)

# A vent plume -- the one warm thing in the picture, and the only saturated
# colour in the palette. Muted rather than orange-hot, so it reads as a glow
# in fog instead of as fire.
WARM = (168, 96, 52)

# Bubbles. Pale, cold, and slightly luminous, because a cloud scatters
# whatever light there is.
GAS = (150, 168, 170)

# Rock in three tones, because one tone is a hole rather than a surface.
# FLOOR is near-black: a silhouette is the whole LIMBO idea. RIM and TOP are
# what a ping paints onto it, so they are pale and cold -- they are lit BY the
# ping, and they are almost the only way the room is ever seen.
ROCK_FLOOR = (5, 7, 8)
ROCK_RIM = (74, 88, 92)
ROCK_TOP = (104, 122, 126)

SNOW = (104, 120, 124)

# The ping. The brightest thing on screen by a wide margin, and deliberately
# the only near-white: it is the light source, so every other value in the
# palette is chosen to sit beneath it.
WAKE = (206, 232, 236)


def build_lut() -> np.ndarray:
    """(bands, 3) uint8, for a single gather over a full-resolution index."""
    return np.array(WATER, dtype=np.uint8)
