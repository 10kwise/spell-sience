"""Every constant, and every place the game puts its thumb on the physics.

RIGS.md 3, 4. CAMPANARY started a tradition worth keeping: name the numbers
the game is allowed to choose, and measure rather than argue about the rest.
There are exactly four chosen numbers in this module and each says out loud
what it is doing and why nothing else would work.

THE UNITS CONTRACT
------------------
Everything in the rig is SI and absolute:

    mass        kg
    temperature K internally, degC at the edges (see K and C helpers)
    pressure    bar absolute, because that is what medium/field.py speaks
    energy      J
    speed       m/s
    area        m^2
    gas         mass fraction, dimensionless

`medium/field.py` speaks degC, bar, and a dimensionless gas fraction, so the
only conversions live at the boundary in `couple.py`. Nothing inside the rig
converts anything.

THE ONE ARCHITECTURAL RULE
--------------------------
**Every module computes the ENERGY it moves, and derives the temperature
change from that energy. Never the other way round.**

    dT = Q / (m * C_P_WATER)

If a module picks a temperature change and then works out what it must have
cost, the two drift apart under composition and conservation becomes a thing
you test for and occasionally fail. Deriving temperature from energy makes
conservation *structural*: `selftest_conservation` cannot fail without a term
being genuinely forgotten, which is the only kind of failure worth catching.

WHAT WATER BEING INCOMPRESSIBLE DID TO THE FIRST DRAFT
------------------------------------------------------
RIGS.md 4 says "squeeze water and it heats". Water's bulk modulus is 2.25 GPa
(`field.WATER_BULK_MODULUS`), so squeezing it three times harder heats it by
about a thousandth of a degree. The law as first written was false, and a
constant large enough to rescue it would have been a pure fudge -- the exact
thing this project has twice written post-mortems about.

The fix is not a bigger constant. It is noticing what in the water is
actually compressible: **the gas it carries.** Wood's equation is already in
`field.py` and already says this -- a trace of gas wrecks a mixture's
stiffness because gas is thousands of times more compressible than water.
`GAS_ADIABATIC = 1.4` is already sitting there being used for exactly this.

So compression heating is proportional to the dissolved gas fraction, and
three things fall out that nobody designed:

  - **Deep water makes better rigs.** Capacity rises with pressure, so there
    is more gas to compress at 700 m than at the station.
  - **A hot rig degrades itself.** Warm water holds less gas, so a rig that
    is heating up loses the very thing its compressor works on.
  - **Stripping a room of gas disables your own machine.** FILTER takes gas
    out of the water. Take too much and the compressor stops working there.

None of that is authored. It is what a gas-driven compressor in water is.
"""

import math

# Import the ocean's own constants rather than restating them. If field.py
# ever changes what gas does, the rig changes with it and cannot silently
# disagree with the water it is sitting in.
from ..medium.field import (
    GAS_ADIABATIC,
    GAS_HENRY,
    GAS_TEMP_GAIN,
    PRESSURE_PER_METRE,
    PRESSURE_SURFACE,
    REFERENCE_TEMP,
)

# --- physical, not chosen ----------------------------------------------------

C_P_WATER = 4186.0        # J/kg/K
C_P_GAS = 1005.0          # J/kg/K, air at constant pressure
RHO_WATER = 1000.0        # kg/m^3
PASCALS_PER_BAR = 1.0e5
KELVIN_ZERO = 273.15

# The adiabatic exponent, (gamma-1)/gamma, from the ocean's own gamma.
ADIABATIC_EXPONENT = (GAS_ADIABATIC - 1.0) / GAS_ADIABATIC   # = 0.2857...


def K(celsius: float) -> float:
    """degC -> K. Compression is a ratio law and ratios need absolute zero."""
    return celsius + KELVIN_ZERO


def C(kelvin: float) -> float:
    return kelvin - KELVIN_ZERO


# --- the shape of a module ---------------------------------------------------

# A module has no knobs (RIGS.md 5), so the ratio it works at is fixed and the
# only way to get more is to place more of them. That is the whole reason a
# chain is countable: three squeezes is three times the ratio, visibly, and
# "how much" is a thing you can point at rather than a number you tuned.
PRESSURE_RATIO = 3.0
AREA_RATIO = 2.0

# --- efficiencies: the Second Law, and where it shows up ---------------------
#
# Every conversion loses, and what it loses becomes HEAT IN THE SLUG. That is
# not a penalty bolted on, it is what an inefficient machine physically does,
# and it is load-bearing for three separate things:
#
#   - A squeeze followed by an expansion comes back HOTTER than it started,
#     so the do-nothing chain is not "nothing happened" but "you made heat and
#     achieved nothing". A sharper lesson, taught by thermodynamics.
#   - Long chains run hot, so length has a cost that needs no rule.
#   - IT BOILS (RIGS.md 7) has a real cause instead of a threshold.
#
# A compressor puts ALL its work into the fluid; being inefficient means you
# get less pressure for the same work, not less heat. That is why ETA divides
# the work requirement and does not scale the heat.
ETA_COMPRESSOR = 0.82
ETA_TURBINE = 0.78
ETA_PUMP = 0.70
ETA_RESONATOR = 0.45     # transducers really are this bad
ETA_COIL = 0.90          # a heat exchanger never quite reaches ambient

# --- CHOSEN NUMBER 1: COMPRESSION_GAIN ---------------------------------------
#
# The same shape as field.py's GRADIENT_EXAGGERATION, and stated with the same
# bluntness. The RELATIONSHIP is real and keeps its sign and structure --
# compression heating is proportional to the gas fraction, to absolute
# temperature, and to (P2/P1)^0.2857 - 1, with gamma taken from the ocean.
# Only the MAGNITUDE is multiplied.
#
# It is needed because a real void fraction is a couple of percent and a real
# hand-portable rig moves a few kg/s, which together heat water by
# thousandths of a degree. At this gain a single SQUEEZE on gas-saturated
# water at the station moves it by a handful of degrees -- a change you watch
# happen rather than infer.
#
# It cannot break conservation. The work drawn is derived from the same dT it
# produces, so the gain scales both sides of the ledger together and only
# changes what a given temperature swing COSTS.
#
# Calibrated by hand against the cooler before any code was written: one
# SQUEEZE on saturated station water moves the slug about 11 degC, which is a
# change you watch happen. The first draft used 320 and cooked the slug to
# 181 degC in one module.
COMPRESSION_GAIN = 20.0

# What fraction of the water is actually compressible when it is fully
# saturated. field.py already declares this number for exactly this purpose --
# BUBBLE_VOID_FRACTION, "real void fraction at bubbles == 1.0" -- so the rig
# and the ocean agree on what a unit of gas means.
SATURATED_WORKING_FRACTION = 0.020

# The working fluid a parcel is carrying is fixed AT THE INTAKE and does not
# re-equilibrate as it crosses the rig. That is kinetics rather than
# equilibrium and it is the physically correct call: a compressor stroke takes
# milliseconds and gas dissolution takes seconds, so the gas does not have
# time to go back into solution partway down the chain.
#
# It is also what makes a rig REASONABLE ABOUT. How well your machine
# compresses is a property of the water you took in -- deep, cold and
# gas-rich is a strong rig; stripped or starved water is a weak one -- rather
# than something that drifts module by module for reasons the player cannot
# see. The first draft recomputed it from equilibrium at every step, and the
# cooler lost three quarters of its stroke to gas quietly dissolving.
#
# EXPAND nucleates more free gas, up to this ceiling, which is why a chain
# that expands before it squeezes compresses better than one that does not.
MAX_WORKING_FRACTION = 0.045

# How fast the free-gas fraction grows when the pressure drops -- and shrinks
# again when it rises, because compression drives gas back into solution.
#
# The two directions have to use the SAME factor, and the version that only
# grew it was a bug with a large tail. The working fluid ratcheted up through
# five expansions, stayed at the ceiling through the recompression, and each
# return step therefore did full-strength work at a temperature the previous
# step had already raised. The lamp came back at +155 degC at 400 m purely
# from that asymmetry. Nucleation and re-dissolution are the same process run
# backwards and the code now says so.
WORKING_NUCLEATION = 1.35
MIN_WORKING_FRACTION = 0.012

# The floor is not cosmetic. Compression dissolving its own working fluid gives
# stacked squeezes genuine diminishing returns, which is good physics and a
# good rule -- but with no floor it converged so fast that IT BOILS became
# unreachable by squeezing at all, and a failure mode you cannot reach is not
# a failure mode. Measured at the station: 5 squeezes reach 63 degC, 9 reach
# 99, and 11 reach 119. So stacking still works, it just pays less each time,
# and cooking yourself remains a thing you can do by trying too hard.

# --- CHOSEN NUMBER 2: RIG_MASS_FLOW ------------------------------------------
#
# How much water a rig moves per second, in kg. A real 50 L/s industrial pump
# is about 50; this is larger because the rig has to make a visible mark on a
# 16 m cell of ocean, and the alternative was lying about the ocean's thermal
# mass instead. Lying about the machine is better than lying about the world:
# the world has six selftests pinned to it and the machine does not.
RIG_MASS_FLOW = 240.0

# --- CHOSEN NUMBER 3: THERMAL_COUPLING ---------------------------------------
#
# SUBMERGED's HEAT_PER_ABSORBED_UNIT, arrived at from the other side. A cell
# of ocean is cell_size^2 metres of water and weighs hundreds of tonnes, so an
# honest joule count warms it by a millionth of a degree per second and the
# acoustic mirror of 7.3 is unreachable in a human lifetime.
#
# THE IMPORTANT PART: this is applied at the BOUNDARY, in couple.py, AFTER the
# rig's ledger has balanced. The rig's own books are exact to float precision.
# Only the amount that lands in the water is amplified, and it says so.
#
# The value is NOT chosen for visibility. SUBMERGED 8.2 requires sound-speed
# contrast to stay inside 1.05-1.5x or the critical angle stops existing and
# every boundary becomes a perfect mirror; working that back through field.py's
# own numbers makes the whole usable band a 0.54-5.4 degC anomaly. This is set
# so a second of running lands in the middle of that band. The first value was
# 900 and crossed the entire band in under half a second. See couple.py.
THERMAL_COUPLING = 170.0

# --- CHOSEN NUMBER 4: GAS_COUPLING -------------------------------------------
#
# The same argument for dissolved gas. field.py's `gas` is a fraction of a
# cell, capacity ~0.02 at the surface, and a rig straining a few grams out of
# hundreds of tonnes moves it by nothing. Amplified at the boundary, exactly
# and only there, so that stripping a room of its gas is something a player
# can actually do -- which is what makes it a consequence rather than a note.
GAS_COUPLING = 30.0

# --- cavitation: the tear point ----------------------------------------------
#
# Water is held together by its own ambient pressure. Drive the absolute
# pressure below the Blake threshold and it tears open into a vapour cavity,
# which bangs, flashes, and leaves bubbles -- SUBMERGED 4.1, and the same
# effect it uses as a logic gate.
#
# Stated as an absolute pressure rather than a delta, which is what makes
# RIGS.md 9.1 true for free: ambient is 1 bar at the surface and 77 bar at
# 760 m, so the number of EXPANDs needed to reach the tear point rises with
# depth. A machine tuned at the station simply refuses to tear at depth, and
# nobody had to write that down.
TEAR_PRESSURE = 0.06      # bar absolute
VAPOUR_PRESSURE = 0.023   # bar, water at 20 degC -- what it tears INTO

# --- what the other modules cost ---------------------------------------------
#
# Sized so that one PUMP puts the slug at about 4 m/s, which is a shove you
# can feel and not a railgun. Note how small these are against a SQUEEZE
# (~8 MJ): moving water is cheap and moving HEAT is expensive, by three orders
# of magnitude. That is true of real machines and it is the shape the economy
# should have -- thermal work is the expensive, high-value verb, and thrust
# and sound are the utilities you spend it on.
PUMP_WORK = 2750.0        # J per module
RESONATOR_WORK = 9000.0   # J per module

# What one unit of the sources.py economy is worth in joules. That module
# counts in small abstract numbers and this one counts in joules, so exactly
# one constant joins them and it lives here rather than being smeared across
# the coupling layer.
ECONOMY_JOULES_PER_UNIT = 2.0e6

# --- failure thresholds ------------------------------------------------------

BOIL_TEMP = 100.0         # degC. The rig cooks and so do you.
STALL_FLOW = 3.2          # how much more flow than one intake supplies

# Water stops cooling at freezing. Neither number here is chosen: 0 degC is
# where water freezes and 334 kJ/kg is its latent heat of fusion.
#
# This was added after the fact, and the reason is worth recording. Without a
# floor the cold side ran away: five expansions at 400 m took the slug to
# -37.65 degC, and because compression work scales with absolute temperature
# the return leg then compounded and delivered water at +101 degC. Both ends
# were nonsense and they were the same bug.
#
# Freezing is the physical answer and it turns out to be the better design
# answer too. IT BOILS had no partner, and the vocabulary is built out of
# opposed pairs (RIGS.md 5) -- so the hot end failing and the cold end failing
# are now the same shape of mistake, reached from opposite directions.
FREEZE_TEMP = 0.0
LATENT_HEAT_FUSION = 334000.0    # J/kg


def working_fraction(gas: float, pressure_bar: float, temp_c: float) -> float:
    """How much of this water is compressible working fluid.

    Free gas plus the gas that is on the point of coming free, as a fraction.
    Saturated water gives SATURATED_WORKING_FRACTION; water that has been
    stripped by a FILTER gives proportionally less, which is why taking all
    the gas out of a room disables your own compressor in it.

    Normalised against local capacity on purpose. Absolute dissolved gas
    swings fifty-fold between the surface and 500 m in field.py's model, and
    letting that multiply compression heating directly made every rig at depth
    boil in one module. Saturation is the quantity that actually describes how
    ready the water is to give up gas, it stays in a sane band everywhere, and
    depth still reaches the rig through three other channels -- the tear point,
    the coil's temperature difference, and how much gas a FILTER can take.
    """
    cap = gas_capacity(pressure_bar, temp_c)
    if cap <= 1e-12:
        return 0.0
    saturation = float(gas) / cap
    free = max(0.0, saturation - 1.0)     # already bubbling: more to work with
    return min(
        MAX_WORKING_FRACTION,
        SATURATED_WORKING_FRACTION * (min(1.0, saturation) + free),
    )


def ambient_pressure(depth_m: float) -> float:
    """bar absolute at a depth, matching field.py exactly."""
    return PRESSURE_SURFACE + PRESSURE_PER_METRE * float(depth_m)


def gas_capacity(pressure_bar: float, temp_c: float) -> float:
    """The most gas water can hold here. field.py's `_gas_capacity`, per-value.

    Kept as a function rather than imported because field.py's version is a
    whole-array operation on a grid, and the rig deals in one parcel at a
    time. The formula is identical and `selftest_conservation` checks that it
    still agrees with the ocean's, so the two cannot drift apart.
    """
    warmth = 1.0 + GAS_TEMP_GAIN * (float(temp_c) - REFERENCE_TEMP)
    return max(0.0, min(1.0, GAS_HENRY * float(pressure_bar) / max(warmth, 0.1)))


def compression_work(mass, working, temp_c, p_from, p_to):
    """The ideal adiabatic work to take this parcel's working fluid p_from -> p_to.

    Positive to compress, negative to expand. This is the ONLY place the
    compression law lives, and both SQUEEZE and EXPAND call it, which is what
    makes them exact inverses before efficiency is applied -- so any asymmetry
    the player sees is the Second Law and nothing else.

    `working` is the compressible fraction from `working_fraction()`, carried
    on the slug and fixed at the intake. Everything else here is real: the
    adiabatic exponent comes from the ocean's own gamma, the work scales with
    absolute temperature because that is what an adiabatic law does, and the
    only invented quantity is the magnitude.
    """
    if p_from <= 0.0 or p_to <= 0.0 or mass <= 0.0:
        return 0.0
    gas_mass = float(mass) * max(0.0, float(working))
    if gas_mass <= 0.0:
        return 0.0
    ratio = (float(p_to) / float(p_from)) ** ADIABATIC_EXPONENT
    return gas_mass * C_P_GAS * K(float(temp_c)) * (ratio - 1.0) * COMPRESSION_GAIN
