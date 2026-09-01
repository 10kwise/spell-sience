"""The stage: one room of ocean, built once and then left alone.

This module owns nothing but scene construction. It exists so that `app.py`
never contains a magic number about where a rock is, and so that `shots.py`
can build the identical room headlessly and photograph it.

The room is a cross-section (SUBMERGED.md 1.1): y is depth, down is deeper,
and every vertical structure in the medium -- the thermocline, the sound
channel, buoyancy, rising bubbles -- is therefore visible rather than
projected away.
"""

import math

from ..medium.field import Medium

WIDTH = 1200
HEIGHT = 800
CELL = 16.0

# The surface is warm, there is a sharp thermocline in the upper third, and
# the deep is near-freezing. This is an ordinary ocean profile and it is the
# whole reason a sound channel exists: c falls with depth while temperature
# dominates, then rises again once pressure does, leaving a minimum in
# between that nobody placed there.
#
# It is deliberately ASYMMETRIC -- steeper above the axis than below -- and
# 7.3 explains why that matters: under a symmetric profile every horizontal
# ping is trapped from everywhere, "outside the channel" stops meaning
# anything, and the discovery has no before.
SURFACE_TEMP = 22.0
DEEP_TEMP = 3.5
THERMOCLINE_TOP = 0.14
THERMOCLINE_BOTTOM = 0.42


def temperature_profile(depth_fraction: float) -> float:
    """Warm mixed layer, a sharp thermocline, then cold and slowly colder."""
    d = depth_fraction
    if d <= THERMOCLINE_TOP:
        return SURFACE_TEMP
    if d >= THERMOCLINE_BOTTOM:
        # Still cooling below the thermocline, but gently -- so the pressure
        # term overtakes it and c turns back upward.
        tail = (d - THERMOCLINE_BOTTOM) / (1.0 - THERMOCLINE_BOTTOM)
        return DEEP_TEMP - 1.2 * tail
    t = (d - THERMOCLINE_TOP) / (THERMOCLINE_BOTTOM - THERMOCLINE_TOP)
    # smoothstep, so there is no corner in the gradient for the marcher to
    # trip over at either end of the thermocline
    t = t * t * (3.0 - 2.0 * t)
    return SURFACE_TEMP + (DEEP_TEMP - SURFACE_TEMP) * t


def _seabed(medium: Medium) -> None:
    """An uneven floor. Sound arriving at a slope leaves in a direction that
    has nothing to do with where it came from, which is most of what makes
    listening to a room interesting."""
    for x in range(0, WIDTH, int(CELL)):
        h = (
            96.0
            + 46.0 * math.sin(x * 0.0067)
            + 26.0 * math.sin(x * 0.0191 + 1.3)
            + 13.0 * math.sin(x * 0.0431 + 2.7)
        )
        medium.carve(x, HEIGHT - h, CELL, h)


def _pillars(medium: Medium) -> None:
    """Three masses in open water at three different ranges, so a single ping
    returns three echoes at three different times. The whole identify layer
    is that spacing."""
    medium.carve(250, 470, 70, 210)
    medium.carve(300, 545, 120, 60)

    medium.carve(690, 300, 54, 150)
    medium.carve(660, 300, 130, 46)

    medium.carve(980, 520, 150, 90)


def _overhang(medium: Medium) -> None:
    """A shelf near the surface with water under it. Rock blocks bubbles, so
    an overhang collects a gas pocket for free -- and a gas pocket is a
    mirror once Wood's collapse is in the field."""
    medium.carve(60, 150, 300, 40)
    medium.carve(60, 150, 40, 130)


def build() -> Medium:
    """The room. Deterministic: no seed, no randomness, so a screenshot taken
    now is comparable with one taken after a change."""
    medium = Medium(WIDTH, HEIGHT, CELL)
    medium.set_temperature_profile(temperature_profile)
    _seabed(medium)
    _pillars(medium)
    _overhang(medium)
    return medium


def channel_depth(medium: Medium) -> float:
    """Where c is slowest, in pixels. Not shown to the player -- the whole
    point of 7.3 is that you find this by pinging -- but the debug overlay
    and the shot harness both need to know the truth to check against."""
    column = medium.c_field[:, medium.nx // 2]
    row = int(column.argmin())
    return (row + 0.5) * medium.cell_size
