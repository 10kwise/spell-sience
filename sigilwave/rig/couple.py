"""Where a rig meets the real ocean. RIGS.md 3, 6.1, 9.1, 10.

`chain.py` evaluates a rig against an idealised `Ambient`. This module is the
other half: it reads the ambient out of a live `medium.Medium`, and it writes
the rig's consequences back into it. Everything RIGS.md 6.1 claims about
couplings -- the warm wake, the starved gill, the blind spot in your own sonar
-- happens here, or rather happens in `field.py` as a consequence of what this
module puts there.

THE AMPLIFICATION, AND WHY IT LIVES HERE AND NOT IN THE LEDGER
---------------------------------------------------------------
A cell of ocean is 16 m square and weighs about 256 tonnes, so warming it by
one degree takes 1.07 GJ. An honest hand-portable rig moves a few kilograms a
second and would need most of a day. SUBMERGED hit this exact wall and named
`HEAT_PER_ABSORBED_UNIT`; this is the same wall from the other side.

The important part is the placement. The rig's own books are exact to float
precision and `selftest_conservation` proves it at 26/26. The amplification is
applied **at the boundary, after the ledger has balanced**, and only to the
amount that lands in the water. So there is exactly one lie, it is in one
file, and it cannot reach the conservation proof.

WHAT MEASURING THE COUPLING CHANGED
-----------------------------------
`THERMAL_COUPLING` was first set to 900 by analogy with SUBMERGED's constant,
and it was wrong by a factor of five for a reason worth writing down.

SUBMERGED 8.2 is a hard design rule: sound-speed contrast must stay inside
1.05-1.5x, because past it every boundary becomes a perfect mirror at every
angle, the critical angle stops existing, and the skill it was supposed to
teach evaporates. Working backwards through `field.py`'s own numbers --
`GRADIENT_EXAGGERATION` of 30 on a real 4.6 m/s per degree -- the whole usable
band is a temperature anomaly of **0.54 to 5.4 degC**. At 900 a running heater
crossed the entire band in under half a second and turned the room into a wall.

So the constant is not chosen for visibility, it is chosen so that a second of
holding lands in the middle of the band that keeps mirrors usable. That is
SUBMERGED 8.3's "dose, not presence" rule arriving from a third direction.
"""

import math

import numpy as np

from ..medium.field import (
    METRES_PER_PIXEL,
    NUCLEATION_RADIUS,
)
from ..medium.front import Front
from .slug import Ambient
from .units import (
    C_P_WATER,
    ECONOMY_JOULES_PER_UNIT,
    GAS_COUPLING,
    RHO_WATER,
    RIG_MASS_FLOW,
    THERMAL_COUPLING,
)

# The aperture a rig's port presents to the world, in world metres, at the
# default bore. WIDEN and NARROW scale it, so the span a front is born with is
# a thing the player placed rather than a number in a table.
#
# SUBMERGED 7.4's two scales are still in force: the world is one pixel per
# metre and the machine is an instrument you hold. A real 0.02 m^2 port is
# sub-pixel, so the span is stated in world units directly and the ratio --
# which is what WIDEN and NARROW actually change -- is what carries over.
BASE_SPAN_M = 2.4

# A cell's thermal mass, in joules per degree. Derived rather than chosen:
# cell_size^2 square metres of water, one metre thick.
def cell_heat_capacity(medium) -> float:
    area = (medium.cell_size * METRES_PER_PIXEL) ** 2
    return area * 1.0 * RHO_WATER * C_P_WATER


def cell_water_mass(medium) -> float:
    return (medium.cell_size * METRES_PER_PIXEL) ** 2 * 1.0 * RHO_WATER


# --- reading the water -------------------------------------------------------


def ambient_from(medium, x: float, y: float) -> Ambient:
    """The real water at a world position, as the rig sees it.

    Reads the medium's OWN temperature and gas rather than the idealised
    profile in `chain.ambient_at`, which matters as soon as anything has been
    heated or stripped: a rig standing in its own warm wake must see the wake.
    That is what makes 6.1's couplings self-inflicted rather than theoretical.
    """
    row, col = medium._cell(x, y)
    return Ambient(
        temp=float(medium.temp[row, col]),
        pressure=float(medium.pressure[row, 0]),
        gas=float(medium.gas[row, col]),
        depth=float(y * METRES_PER_PIXEL),
    )


# --- writing the consequences ------------------------------------------------


def apply(result, medium, x: float, y: float, dt: float,
          coil_at=None) -> dict:
    """Put one rig-second's worth of consequence into the ocean.

    The ledger is in joules per second because `RIG_MASS_FLOW` is kg/s, so
    everything here scales by `dt` and the caller gets a rate, which is
    SUBMERGED 8.3's rule that every world-changing verb is a rate.

    `coil_at` is where the COIL dumps, and it defaults to the rig's own
    position. Letting it be somewhere else is the whole of RIGS.md 4.1: heat
    has to go somewhere and **where is a decision**. A player who dumps into
    the water they are standing in has cooked themselves; one who runs the
    coil down a line has built a radiator.
    """
    if dt <= 0.0:
        return {}
    led = result.ledger
    applied = {"heat_c": 0.0, "gas": 0.0, "bubbles": 0.0}

    cx, cy = (x, y) if coil_at is None else coil_at
    joules_per_degree = cell_heat_capacity(medium)

    # --- heat ---------------------------------------------------------------
    net_joules = (led.heat_to_ocean - led.heat_from_ocean) * dt
    if abs(net_joules) > 0.0:
        degrees = net_joules / joules_per_degree * THERMAL_COUPLING
        medium.add_heat(cx, cy, degrees)
        applied["heat_c"] = degrees

    # Water that leaves the port carries its own temperature with it, and it
    # leaves at the PORT rather than at the coil -- which is why a cooler
    # makes a cold place in front of you and a warm place beside you, and why
    # those are two different places you chose.
    port_joules = led.heat_out * dt
    if abs(port_joules) > 0.0:
        degrees = port_joules / joules_per_degree * THERMAL_COUPLING
        medium.add_heat(x, y, degrees)
        applied["heat_c"] += degrees

    # --- gas ----------------------------------------------------------------
    # A FILTER takes gas out of the water it is standing in. Take enough and
    # the room stops being breathable, and your own compressor stops working
    # in it (units.working_fraction). Emergent scarcity, no rule.
    if led.tank_gas > 0.0:
        row, col = medium._cell(x, y)
        if not medium.solid[row, col]:
            fraction = (led.tank_gas * dt / cell_water_mass(medium)) * GAS_COUPLING
            taken = min(fraction, float(medium.gas[row, col]))
            medium.gas[row, col] -= taken
            medium._dirty = True
            applied["gas"] = taken

    # --- bubbles ------------------------------------------------------------
    # Two sources, and they are different events. `out_bubbles` is gas the
    # water could not hold at the pressure it left at; `bubbles_shed` is the
    # cloud a collapsing cavity shatters into, which is the one that survives
    # the pressure recovering.
    cloud = (result.out_bubbles or 0.0) + (
        led.bubbles_shed / max(cell_water_mass(medium), 1e-9) * GAS_COUPLING)
    if cloud > 0.0:
        row, _ = medium._cell(x, y)
        radius = NUCLEATION_RADIUS * float(medium.pressure[row, 0]) ** (-1.0 / 3.0)
        amount = cloud * dt
        medium.add_bubbles(x, y, amount, radius)
        applied["bubbles"] = amount

    return applied


# --- thrust, honestly --------------------------------------------------------


def thrust_from(result) -> float:
    """Newtons. Mass flow times exit velocity, and nothing else.

    SUBMERGED named `THRUST_PER_ENERGY` as a deliberate lie because acoustic
    radiation pressure genuinely cannot move a diver. A port ejecting water
    can, so the lie is not needed any more: this is momentum flux, which is
    what a jet is.

    `diver.py` is not modified. Wiring it up is one line at the call site --
    pass this in place of the `thrust` vector's magnitude -- and it is left
    for whoever builds the dive loop, because changing the diver while the
    bench is still the only screen would be changing two things at once.
    """
    return RIG_MASS_FLOW * result.out_speed


def thrust_vector(result, direction):
    """The same number, aimed. `direction` points where the PORT faces; the
    reaction pushes the other way, which is the only sign convention here and
    the one people get wrong."""
    d = np.asarray(direction, dtype=np.float64).reshape(2)
    n = float(np.hypot(d[0], d[1]))
    if n < 1e-12:
        return np.zeros(2)
    return -(d / n) * thrust_from(result)


# --- sound -------------------------------------------------------------------


def emit_front(result, medium, origin, direction, curvature: float = 0.0):
    """A front carrying whatever left the port as sound, or None.

    The span is read off the slug's final aperture, so WIDEN and NARROW decide
    what shape the sound is born as -- which is SUBMERGED 5 intact, driven by
    a token count instead of a measured arc. Everything downstream (refraction,
    the sound channel, caustics, the aperture rule) is `front.py` unmodified.
    """
    if result.out_acoustic <= 0.0 or result.out_note <= 0.0:
        return None
    area = _final_area(result)
    span = BASE_SPAN_M * (area / 0.02)
    return Front(
        origin=origin,
        direction=direction,
        arc_span=max(span, 0.5),
        arc_curvature=curvature,
        energy=result.out_acoustic,
        freq=result.out_note,
    )


def _final_area(result) -> float:
    """The aperture the last live stage was pushing through.

    `Stage` does not carry area -- it carries the five properties the bench
    draws -- so it is recovered from the NARROW and WIDEN that actually ran.
    Counting the modules rather than storing the number keeps `Stage` at the
    five things RIGS.md 3.1 promises.
    """
    from .units import AREA_RATIO

    area = 0.02
    for st in result.stages:
        if st.dead:
            continue
        if st.kind == "NARROW":
            area /= AREA_RATIO
        elif st.kind == "WIDEN":
            area *= AREA_RATIO
    return area


# --- the bill ----------------------------------------------------------------


def bill(result, economy, sources, at, dt) -> tuple:
    """Charge the economy for one rig-second.

    `sources.Economy.draw_energy` takes what the world will give first and
    only then breathes, which SUBMERGED 6 measured as the whole progression
    curve in one number. Nothing here changes that ordering -- the rig simply
    presents a larger and more legible bill than a drawn machine did, because
    `Result.cost` is a real thermodynamic quantity rather than a drive level.
    """
    want = max(0.0, result.cost)
    return economy.draw_energy(want, sources, at, dt)


def report(result, medium, x, y) -> str:
    """One line for a HUD. Deliberately the same quantities the bench draws,
    so that reading the machine at the bench and reading it in the water are
    the same skill."""
    amb = ambient_from(medium, x, y)
    bits = [f"{result.cost:.2f}/s"]
    if abs(result.delta_temp) > 0.1:
        bits.append(f"{result.delta_temp:+.1f} C out")
    if result.out_speed > 0.1:
        bits.append(f"{thrust_from(result):.0f} N")
    if result.ledger.tank_gas > 1e-4:
        bits.append(f"{result.ledger.tank_gas:.1f} kg gas")
    if result.tore:
        bits.append("TEARING")
    if result.fault:
        bits.append(result.fault.kind)
    return f"[{amb.temp:.1f} C {amb.pressure:.0f} bar]  " + "  ".join(bits)
