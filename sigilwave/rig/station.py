"""Home. RIGS.md 13.

The station is the one thing in this world that gives instead of taking, and
the design problem it poses is that a place which is simply *safe* is a menu
with a position. So it is built out of the same physics as everything else,
and the consequences are allowed to be inconvenient:

**It is warm.** A pressurised hull full of people and machinery leaks heat,
and heat in water does what heat in water does -- it rises, it drags a
circulation up with it, and it is visible to anything that reads temperature.
So the safest place in the ocean is also the loudest thing in it on every
channel a creature uses, and there is a permanent updraft over the door.
Nobody authored that. It is `Medium._buoyancy` and `Medium._compute_flow`
being told there is a heat source here.

**It is a power source, and its reach is short.** `sources.Source` already
says what a source is -- a rate, a note, and a place -- and the station is one
with a large rate and a small reach. That is SUBMERGED 3.1's whole
progression curve: hour one you are never more than a room from the station
and power is free, hour twenty you are three rooms out and the only thing
between you and the surface is a rig that pays for itself.

**It does not refill you instantly.** Air comes back at a rate, so leaving
early is a decision and coming home hurt costs you minutes rather than a
loading screen.

WHAT IT DELIBERATELY IS NOT
---------------------------
It is not a dive timer and it is not a fail state. RIGS.md 12.2 had "a dive
that can end" on the list and it came off on purpose: a run that ends is a
structure imposed on top of the simulation, and everything good in this
project so far has come from the simulation being allowed to say what happens.
The station is a place you want to be near. That is enough of a rule.
"""

import math

import pygame

from ..medium.field import METRES_PER_PIXEL
from ..sources import AIR_MAX, Source

V = pygame.Vector2

# What the hull leaks, in degC per second into the cell above the door. The
# same shape as `Vent.heat_rate` and deliberately a small fraction of it: a
# station should be findable and should stir the water, without being a vent
# you can also sleep in.
#
# At 3.0 the updraft over the door threw a stationary diver 190 px in eight
# seconds -- a full cruising speed, straight up, which makes docking a fight
# rather than a decision. It does not scale linearly, because the plume builds
# over minutes and the buoyancy compounds: 1.1 still gave 124 px. At 0.45 it
# is about 55, so you drift off the dock in five or six seconds of doing
# nothing and a touch of trim holds you there. That is the difference between
# weather and a hazard, and home should have weather.
HULL_HEAT = 0.45

# How close you have to be to be plugged in, in pixels. Small enough that
# holding it against the updraft is a thing you are doing rather than a thing
# that happens.
DOCK_RADIUS = 44.0

# Air per second while docked. A full tank in about twelve seconds, which is
# long enough to be a decision and short enough not to be a chore.
AIR_RATE = 8.5

# Units per second into the pack while docked. Faster than any vent, because
# the station has a reactor and the ocean does not.
CHARGE_RATE = 4.0

# The rate and reach it presents to `Economy.draw_energy`. The reach is the
# number that matters: it is the radius of "free", and everything interesting
# happens outside it.
STATION_RATE = 3.4
STATION_REACH = 300.0

# It hums. Low, because low notes carry (units.pipe_loss, and the same law
# outside the pipe) -- so the station is audible from further away than it is
# visible, which is what you want from a thing you have to find in the dark.
STATION_NOTE = 117.0


class Station(Source):
    """A place, not a menu."""

    def __init__(self, pos, rate: float = STATION_RATE,
                 reach: float = STATION_REACH):
        super().__init__(pos, rate, STATION_NOTE, reach, "station")
        self.heat_rate = HULL_HEAT
        self.dock_radius = DOCK_RADIUS
        self.docked_seconds = 0.0

    # --- what it does to the water ------------------------------------------

    def warm(self, medium, dt: float) -> None:
        """Leak. Identical in shape to `Vent.warm`, and for the same reason:
        the medium is the only place a heat source is allowed to exist."""
        medium.add_heat(self.pos.x, self.pos.y - 8.0, self.heat_rate * dt)

    # --- what it does for you -----------------------------------------------

    def distance_to(self, pos) -> float:
        return (V(pos) - self.pos).length()

    def docked(self, pos) -> bool:
        return self.distance_to(pos) <= self.dock_radius

    def resupply(self, pos, economy, dt: float) -> dict:
        """Air and charge, at a rate, while you are actually at the door.

        Returns what was given, so a HUD can say so and a test can check it.
        Nothing happens at all if you are not docked, which is the whole
        content of the mechanic.
        """
        given = {"air": 0.0, "charge": 0.0, "docked": False}
        if economy is None or not self.docked(pos):
            return given
        given["docked"] = True
        self.docked_seconds += dt

        before = economy.air
        economy.air = min(AIR_MAX, economy.air + AIR_RATE * dt)
        given["air"] = economy.air - before

        cap = getattr(economy, "charge", None)
        if cap is not None:
            from ..sources import CHARGE_MAX

            before_c = economy.charge
            economy.charge = min(CHARGE_MAX, economy.charge + CHARGE_RATE * dt)
            given["charge"] = economy.charge - before_c
        return given

    # --- what it is to a player ---------------------------------------------

    def bearing_from(self, pos) -> V:
        """A unit vector pointing home, for a compass that has to be earned
        rather than given -- the station hums at 117 Hz and a rig that listens
        can find it. This is the answer that instrument would give."""
        d = self.pos - V(pos)
        if d.length_squared() < 1e-12:
            return V(0.0, 0.0)
        return d.normalize()

    def report(self, pos, economy=None) -> str:
        """One line for a HUD, in the same register as `couple.report`."""
        d = self.distance_to(pos)
        if self.docked(pos):
            bits = ["DOCKED"]
            if economy is not None:
                bits.append(f"air {economy.air:.0f}")
                if hasattr(economy, "charge"):
                    bits.append(f"pack {economy.charge:.1f}")
            return "  ".join(bits)
        power = self.available_at(pos)
        home = f"{d * METRES_PER_PIXEL:.0f} m home"
        if power <= 0.0:
            return f"{home}  --  on your own"
        return f"{home}  --  {power:.2f}/s from the station"
