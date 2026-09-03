"""The medium (design doc §7): a coarse vertical cross-section of ocean.

y increases downward, so y=0 is the surface and y=height is the seabed. This
is a side view, not a plan view, which is the whole point: the interaction
matrix in §7.2 is almost entirely about depth, and every consequence in §7.3
-- stratification, the mirror, the channel, bubbles changing note as they rise
-- needs a vertical axis to happen along.

It is deliberately not a fluid solver. §7.1 promises six systems of two or
three rules each, and the design thesis is that each system is individually
understandable, so every rule below is a handful of lines and none of them is
allowed to grow. Buoyancy is a density-driven exchange between vertically
adjacent cells, not advection: there is no velocity field, no pressure
projection, no divergence to clean up. What that buys is that the exchange is
exactly antisymmetric, so heat and salt are conserved to machine precision and
"why did that patch of water end up there" stays answerable by looking.

    THE ONE DELIBERATE LIE
    ----------------------
    Sound speed in real seawater is about 1500 m/s and varies by roughly
    30 m/s across a kilometre of depth. That is a 2% spread, and it bends a
    ray over a turning radius of tens of kilometres. Rendered in a 1200x800
    pixel room it is a straight line, and §7.3 -- "a wavefront bends toward
    slower water", the sentence this whole module exists to demonstrate --
    would be a claim the player could never once see happen.

    So: every real relationship here keeps its exact sign and structure, and
    the *magnitude of the c variation alone* is multiplied by
    GRADIENT_EXAGGERATION. Set it to 1.0 and this module is oceanography. Set
    it to 30 and it is a room in which a ping visibly turns over a few hundred
    pixels. Nothing else in this file is falsified, and no other constant is
    doing this job -- if bending is too weak or too violent, that one number
    is the only thing to touch.

One pixel is one metre (METRES_PER_PIXEL), so a 1200x800 domain is 1.2 km wide
and 800 m deep. That is honestly the scale at which a sound channel exists; it
is only the visibility of the refraction that is a lie.

    UNITS CONTRACT
    --------------
    Every coordinate crossing this boundary, in or out, is **pixels**. The
    medium owns the conversion to physical units and does it internally; no
    caller should ever multiply by METRES_PER_PIXEL.

    - `sound_speed` returns **pixels per second**. It is derived from a
      formula in m/s and then divided by METRES_PER_PIXEL, so at the current
      1 px = 1 m the two numbers coincide -- but a marcher advancing
      `x += dx * c * dt` is doing pixel arithmetic and must keep doing it if
      that constant ever moves.
    - `c_gradient` returns (dc/dx, dc/dy) in **(px/s) per px**, i.e. 1/s.
      The ray turn rate `-(grad c . n_hat)` is therefore rad/s directly.
    - `absorption` returns **nepers per pixel**, so Beer-Lambert is
      `amplitude *= exp(-alpha * ds)` with ds in pixels. Not dB, not
      intensity: it attenuates amplitude, and a factor of e is alpha*ds = 1.
    - `density` is kg/m^3 and `pressure_at` is bar. Those are read for
      display and comparison, never integrated along a path, so they stay in
      the units a person recognises.

    Batched variants (`sound_speed_at`, `c_gradient_at`, `absorption_at`,
    `is_solid_at`) take numpy arrays of coordinates and return numpy arrays.
    They are bit-identical to the scalar methods, not merely close, and exist
    because a wavefront of a few hundred vertices cannot afford a Python-level
    call per vertex per substep.
"""

from __future__ import annotations

import math

import numpy as np

# --- scale -----------------------------------------------------------------

METRES_PER_PIXEL = 1.0
GRADIENT_EXAGGERATION = 30.0  # read the module docstring before changing this
C_REFERENCE = 1500.0          # what the exaggerated field is pinned to at the reference state
C_FLOOR = 60.0                # see below

# C_FLOOR is a guard rail, not a physical claim. Two things push c down without
# limit: the exaggeration applied to very cold water, and Wood's collapse in a
# bubble cloud. A marcher's step length is c*dt, so c reaching zero stalls a
# front in place and c going negative runs it backwards. 60 px/s is chosen as
# "the slowest water that still moves a front a visible distance per frame"
# (1 px at 60 Hz) -- below that a front is not propagating, it is stuck. In
# practice nothing attainable reaches it: the slowest state the model can
# produce is a saturated bubble curtain in surface water, about 157 px/s, so
# the floor never actually clamps and never introduces the flat spot -- and the
# gradient discontinuity at its edge -- that a binding clamp would.

# --- sound speed (Mackenzie's equation, truncated) --------------------------
# c rises with temperature, with salinity, and with depth. The cubic term is
# not decoration: without it dc/dT turns negative above ~42 C, and a
# hard-driven mouth would start making water *slower* by heating it.

C_ZERO = 1449.2
C_TEMP_1, C_TEMP_2, C_TEMP_3 = 4.6, -0.055, 0.00029
C_SAL, C_SAL_TEMP = 1.34, -0.010
C_DEPTH = 0.016
REFERENCE_SALINITY = 35.0
REFERENCE_TEMP = 10.0
REFERENCE_DEPTH_M = 400.0

# --- density (linearised equation of state) ---------------------------------
# Colder is denser, saltier is denser. Bubbles lighten water (§7.2, "bubbles
# lighten water -> a rising column"), which is why a bubble plume drags warm
# water up with it instead of drifting through it.

DENSITY_ZERO = 1000.0
THERMAL_EXPANSION = 0.20   # kg/m^3 per degree, subtracted
HALINE_CONTRACTION = 0.80  # kg/m^3 per psu, added
BUBBLE_LIGHTENING = 40.0   # kg/m^3 at bubble fraction 1

# --- pressure ---------------------------------------------------------------

PRESSURE_SURFACE = 1.0     # bar
PRESSURE_PER_METRE = 0.1   # bar

# --- heat -------------------------------------------------------------------

HEAT_DIFFUSIVITY = 60.0     # px^2/s: a heated patch smears about one cell per second
MAX_DIFFUSION_ALPHA = 0.24  # the explicit 5-point stencil is unstable past 0.25

# --- trophic channels (RIGS.md 13.4) ----------------------------------------
# The ecosystem cycle is carried by diffusing scalars rather than by creatures
# perceiving one another, and that choice is the whole reason RIGS.md 9's one
# rule survives contact with a food web: a creature still reads only fields.
#
# It also buys the range laws for free. 9.0 measured that heat's usable
# gradient is gone by 140 px at HEAT_DIFFUSIVITY = 60, so a channel's
# diffusivity IS its reach, and a channel's half-life is how long a place
# stays interesting after whatever made it interesting has left. Those two
# numbers per channel are the entire tuning surface.
#
# The floor exists so a channel that nothing is feeding actually reaches zero
# rather than leaving a vanishing gradient for a creature to climb forever.
CHANNEL_FLOOR = 1e-7

# Upwind advection is stable to a Courant number of 1. The fastest water the
# medium can make is a few px/s against a 16 px cell, so the real number is
# about 0.03 and this clamp never binds -- it is a guard rail against a future
# faster current, not a correction to this one.
MAX_ADVECT_COURANT = 0.5

# --- buoyancy ---------------------------------------------------------------
# An unstable vertical pair (heavy sitting on light) swaps a fraction of its
# contents. The fraction is proportional to how badly it is inverted, so
# neutral water does nothing at all and a 20-degree anomaly moves fast. The
# rate is set against HEAT_DIFFUSIVITY rather than in isolation: those two are
# in a race for the same anomaly, and if diffusion wins, nothing ever visibly
# rises.

BUOYANCY_RATE = 20.0  # exchanged fraction per second per kg/m^3 of inversion
MAX_EXCHANGE = 0.4    # a full swap in one step would ring

# --- gas and bubbles --------------------------------------------------------
# Henry's law: capacity is linear in pressure and falls as water warms. That
# one expression is both "pressure forces gas into solution" and "warm water
# sheds dissolved gas" (§7.2), and it is why the fizz line moves deeper when
# you heat a column.

GAS_HENRY = 0.02              # saturation fraction per bar
GAS_TEMP_GAIN = 0.03          # per degree above REFERENCE_TEMP
GAS_INITIAL_SATURATION = 0.9  # start every cell quietly under-saturated

# --- the water moves ---------------------------------------------------------
#
# Until this block the ocean had temperature, gas, bubbles and a sound speed,
# and no VELOCITY -- so a diver's drag was measured against the ground and
# swimming was identical to flying with the numbers turned down. Water that
# does not move is not water.
#
# Nothing new is invented. The vertical part is the buoyancy `_buoyancy`
# already applies to heat, read as a speed instead of as a transport; the
# horizontal part is whatever CONTINUITY requires, because the flow is
# incompressible and the books have to close in space the same way the rig's
# close in energy. That single constraint is what makes a plume a plume: warm
# water going up over a vent has to be replaced, so there is an inflow at the
# bottom and an outflow at the top, and nobody drew it.
#
# It is read against the mean at each depth for exactly the reason `diver.py`
# already learned the hard way: an ordinary stratified column has heavy water
# under light water everywhere, always, by design, and reading the raw
# gradient turns that into a permanent updraft. A stable column is STILL. Only
# an anomaly moves.
#
# CHOSEN, in the tradition of GRADIENT_EXAGGERATION and COMPRESSION_GAIN: the
# relationship is real and the magnitude is a game's. At an honest scale a
# plume rises at a fraction of a pixel per second against a diver who
# cruises at 24, so the water would be moving and nobody would ever notice.
# This puts a vent's updraft at about a third of cruising speed.
BUOYANT_FLOW = 4.0        # px/s of rise per kg/m^3 the water is light by

# The background drift, and the two things that make it interesting.
#
# Real oceans are sheared: a wind-driven surface layer runs fast and the deep
# is nearly still. So shallow water pushes you around and deep water does not,
# which hands RIGS.md 9.1's "depth flips the sign" one more channel without
# anybody adding a rule -- the shallows are where travel is cheap in one
# direction and expensive in the other, and the deep is where you are on your
# own.
#
# And it turns, slowly. A tide means "the current is against me" is a thing
# you can wait out rather than only a thing you pay for, which is the
# difference between a hazard and a system.
DRIFT_SURFACE = 7.0       # px/s at the surface
DRIFT_DECAY_M = 190.0     # e-folding depth of the sheared layer
TIDE_PERIOD_S = 240.0     # how long until it runs the other way
OUTGAS_RATE = 2.0             # fraction of the excess shed per second

NUCLEATION_RADIUS = 0.004  # m, the radius a shed bubble takes at 1 bar
BUBBLE_RISE_SPEED = 40.0   # px/s
MAX_RISE_FRACTION = 0.9
MIN_BUBBLE_RADIUS = 1e-5
MAX_BUBBLE_RADIUS = 0.05

# --- absorption -------------------------------------------------------------
# §7.1: high dies fast, low carries far. Real seawater absorption goes as
# roughly f^1.5 to f^2; the exponent is kept, and the coefficient is set so a
# low note crosses the room nearly intact and a high one does not survive it.
# Bubbles eat sound violently, and worst at their own Minnaert note, which is
# what makes "a bubble at your note rings with you" something a player can aim
# at on purpose.

ABSORPTION_REF_FREQ = 1000.0
ABSORPTION_AT_REF_FREQ = 3e-4  # nepers per metre in clear water (converted to per px on use)
ABSORPTION_FREQ_POWER = 1.6
BUBBLE_ABSORPTION = 0.08       # nepers per metre at bubble fraction 1, off resonance
BUBBLE_RESONANCE_GAIN = 40.0
BUBBLE_Q = 3.0
MINNAERT_CONSTANT = 3.26       # Hz*m at 1 bar: f0 = K*sqrt(P)/radius

# --- bubbles bend sound too (Wood's equation) --------------------------------
# A bubbly mixture is a spring made of gas carrying the mass of water: it takes
# the compressibility of the gas and the density of the liquid, and the result
# is slower than either one alone. A 1% void fraction drops c from 1500 m/s to
# about 120. That is not an exaggeration and it is not tuned -- it is the one
# place in this file where reality is already more violent than the game needs,
# which is exactly why the collapse is applied *outside* GRADIENT_EXAGGERATION
# rather than inside it. Multiplying this by 30 would take c negative.
#
# The payoff is that a bubble curtain is a mirror as well as a wall, so one
# system does two jobs, and the rule a player holds is one sentence: sound
# bends hard toward bubbles.
#
# BUBBLE_VOID_FRACTION is the mapping between the game's `bubbles` field (a
# 0..1 density, not a volume) and a real void fraction. At 2% the collapse
# curve spans the whole useful range of the field instead of saturating at the
# first whiff of gas, which it would if bubbles=1 meant a void fraction of 1.

WATER_BULK_MODULUS = 2.25e9  # Pa; rho0 * 1500^2, so clear water comes back exactly 1500
GAS_ADIABATIC = 1.4          # gamma; an ideal gas has rho*c^2 = gamma*P
PASCALS_PER_BAR = 1.0e5
BUBBLE_VOID_FRACTION = 0.02  # real void fraction at bubbles == 1.0

# --- the default water ------------------------------------------------------

SURFACE_TEMP = 18.0
DEEP_TEMP = 4.0
MIXED_LAYER_FRACTION = 0.08
THERMOCLINE_FRACTION = 0.20


def default_temperature_profile(depth_fraction: float) -> float:
    """A sun-warmed mixed layer over an exponentially decaying thermocline.

    This shape is what produces the sound channel, and it produces it without
    anybody authoring one. Near the surface the water cools fast with depth
    and temperature beats pressure, so c falls. Deep down the temperature has
    flattened out, nothing is left but the pressure term, and c rises. The
    minimum sits exactly where those two cancel -- an interior depth that
    moves when the profile changes, which is precisely why a player can build
    one rather than merely find one.
    """
    if depth_fraction <= MIXED_LAYER_FRACTION:
        return SURFACE_TEMP
    fall = (depth_fraction - MIXED_LAYER_FRACTION) / THERMOCLINE_FRACTION
    return DEEP_TEMP + (SURFACE_TEMP - DEEP_TEMP) * math.exp(-fall)


def _c_real(temp, salinity, depth_m):
    """Sound speed in m/s before exaggeration. Scalars or arrays."""
    return (
        C_ZERO
        + C_TEMP_1 * temp
        + C_TEMP_2 * temp**2
        + C_TEMP_3 * temp**3
        + (C_SAL + C_SAL_TEMP * temp) * (salinity - REFERENCE_SALINITY)
        + C_DEPTH * depth_m
    )


C_REAL_REFERENCE = _c_real(REFERENCE_TEMP, REFERENCE_SALINITY, REFERENCE_DEPTH_M)


class Medium:
    """A grid of water in cross-section.

    Cell (row, col) covers the world rectangle from (col*cell_size,
    row*cell_size) to one cell_size further in each axis, so the row index is
    depth and every array is indexed [y, x] in numpy order.

    Sampling is bilinear and clamps outside the domain rather than raising or
    returning a sentinel: a marcher that steps one pixel past the seabed gets
    seabed water, not a NaN. Callers that care about leaving the room check
    their own bounds.
    """

    def __init__(self, width: int, height: int, cell_size: float = 16.0) -> None:
        self.width = float(width)
        self.height = float(height)
        self.cell_size = float(cell_size)
        self.nx = max(1, int(math.ceil(width / self.cell_size)))
        self.ny = max(1, int(math.ceil(height / self.cell_size)))
        shape = (self.ny, self.nx)

        # Column vectors: everything depth-dependent is per-row and broadcasts.
        self.depth_m = ((np.arange(self.ny) + 0.5) * self.cell_size * METRES_PER_PIXEL).reshape(-1, 1)
        self.pressure = PRESSURE_SURFACE + PRESSURE_PER_METRE * self.depth_m

        self.temp = np.zeros(shape)
        self.salinity = np.full(shape, REFERENCE_SALINITY)
        self.gas = np.zeros(shape)
        self.bubbles = np.zeros(shape)
        self.bubble_radius = np.zeros(shape)
        self.solid = np.zeros(shape, dtype=bool)

        # Trophic channels (RIGS.md 13.4). Empty by default: a medium with no
        # ecosystem in it costs exactly nothing, and `selftest_field` should
        # not have to know this exists.
        self.channels: dict[str, np.ndarray] = {}
        self._channel_rates: dict[str, tuple[float, float]] = {}

        self._nucleation_radius = NUCLEATION_RADIUS * self.pressure ** (-1.0 / 3.0)
        # Boyle: a bubble carries a fixed amount of gas, so r ~ P^(-1/3), and a
        # bubble crossing one cell upward grows by exactly this ratio.
        self._rise_expansion = (self.pressure[1:] / self.pressure[:-1]) ** (1.0 / 3.0)
        self.bubble_radius[:] = self._nucleation_radius

        self._dirty = True
        # The tide needs a clock, and this is the only stateful thing in the
        # medium that is not a field. `step` advances it.
        self.elapsed = 0.0
        self.set_temperature_profile(default_temperature_profile)

    # --- derived fields -----------------------------------------------------

    def _compute_density(self):
        return (
            DENSITY_ZERO
            - THERMAL_EXPANSION * (self.temp - REFERENCE_TEMP)
            + HALINE_CONTRACTION * (self.salinity - REFERENCE_SALINITY)
            - BUBBLE_LIGHTENING * self.bubbles
        )

    def _gas_capacity(self):
        warmth = 1.0 + GAS_TEMP_GAIN * (self.temp - REFERENCE_TEMP)
        return np.clip(GAS_HENRY * self.pressure / np.maximum(warmth, 0.1), 0.0, 1.0)

    def _wood_ratio(self):
        """How much slower a bubbly cell is than the same water with no gas in
        it, as a multiplier on c.

        Wood's equation: the mixture's compressibility is the volume-weighted
        average of its parts, while its density is too, and c = 1/sqrt(rho/K).
        Gas is thousands of times more compressible than water and hardly
        weighs anything, so a trace of it wrecks the stiffness without
        relieving the mass -- which is why the mixture is slower than water
        *and* slower than air.

        Two consequences worth knowing before tuning anything. Deep bubbles
        bend sound far less than shallow ones, because the gas spring stiffens
        with pressure (rho*c^2 = gamma*P), so a bubble mirror is a shallow-water
        instrument. And clear water returns exactly 1.0, by construction and by
        an explicit branch, so nothing here can perturb the sound channel.
        """
        beta = BUBBLE_VOID_FRACTION * self.bubbles
        gas_modulus = GAS_ADIABATIC * self.pressure * PASCALS_PER_BAR
        compressibility = beta / gas_modulus + (1.0 - beta) / WATER_BULK_MODULUS
        mixture_density = (1.0 - beta) * DENSITY_ZERO
        clear = math.sqrt(WATER_BULK_MODULUS / DENSITY_ZERO)
        ratio = 1.0 / (np.sqrt(mixture_density * compressibility) * clear)
        return np.where(self.bubbles > 0.0, ratio, 1.0)

    def _compute_flow(self):
        """(u, v) in px/s per cell. Buoyancy, closed by continuity.

        Sign convention, stated because getting it wrong is invisible: row 0
        is the surface and +v is DOWNWARD, so light water -- a negative
        density anomaly -- gets a negative v and rises.

        The horizontal component is not modelled, it is DEDUCED. For an
        incompressible field du/dx = -dv/dy, so integrating that along each row
        gives the only horizontal flow consistent with the vertical one. The
        row mean is removed afterwards because the integration constant is free
        and a non-zero one would be a phantom drift across the whole domain.
        """
        anomaly = self._rho - self._layer
        v = BUOYANT_FLOW * anomaly
        v = np.where(self.solid, 0.0, v)

        dvdy = np.gradient(v, self.cell_size, axis=0)
        u = -np.cumsum(dvdy, axis=1) * self.cell_size
        u -= u.mean(axis=1, keepdims=True)

        # The sheared background layer, and the tide that turns it.
        depth = self.depth_m
        phase = math.cos(2.0 * math.pi * self.elapsed / TIDE_PERIOD_S)
        u = u + DRIFT_SURFACE * np.exp(-depth / DRIFT_DECAY_M) * phase

        u = np.where(self.solid, 0.0, u)
        return u, v

    def density_anomaly_at(self, x: float, y: float) -> float:
        """kg/m^3 this water differs from the rest of its own depth by.

        NEGATIVE means lighter than its layer, and lighter is what rises.

        Exactly zero in an ordinary stratified column, at every position and
        not merely at cell centres -- which sounds too obvious to state and was
        not. `diver._buoyancy` compared a BILINEAR sample of the density
        against a SINGLE ROW's mean, so between one row centre and the next it
        read a difference that was pure stratification, flipped sign twice per
        cell, and reached 7 kg/m^3 in water where nothing had happened. A diver
        trimmed to hover bobbed instead, and it was invisible until trim made
        vertical motion slow enough to watch.

        One definition, in the medium, used by everything that needs it.
        """
        self._ensure_derived()
        return (self._bilinear(self._rho, x, y)
                - self._bilinear(self._layer, x, y))

    @property
    def flow_field(self):
        """Live (u, v) per cell, in px/s. For a renderer that wants to draw
        the water moving, and for anything that has to swim in it."""
        self._ensure_derived()
        return self._u, self._v

    def flow_at(self, x: float, y: float):
        """(u, v) in px/s at a world position, bilinear. What the water is
        doing where you are, which is the velocity every drag law in this
        project should be measured against."""
        self._ensure_derived()
        return (self._bilinear(self._u, x, y), self._bilinear(self._v, x, y))

    def flow_at_many(self, xs, ys):
        """Vectorised `flow_at`, for creatures and particles."""
        self._ensure_derived()
        weights = self._sample_weights(xs, ys)
        return self._gather(self._u, weights), self._gather(self._v, weights)

    @property
    def density_field(self):
        """Live kg/m^3 per cell, for a renderer that wants to draw the layers.
        A property rather than an attribute so it cannot silently go stale one
        frame after a step()."""
        self._ensure_derived()
        return self._rho

    @property
    def c_field(self):
        """Live exaggerated sound speed per cell. See the module docstring for
        what "exaggerated" means before drawing a number from it."""
        self._ensure_derived()
        return self._c

    def _ensure_derived(self) -> None:
        if not self._dirty:
            return
        self._rho = self._compute_density()
        # What the density WOULD be with no anomalies: the mean at each depth,
        # spread back across the row. Everything that asks "is this water
        # unusual" has to compare against this rather than against a constant,
        # because an ordinary stratified column is heavy-under-light
        # everywhere by design and is not unusual anywhere.
        self._layer = np.broadcast_to(
            self._rho.mean(axis=1, keepdims=True), self._rho.shape)
        self._u, self._v = self._compute_flow()
        real = _c_real(self.temp, self.salinity, self.depth_m)
        exaggerated = C_REFERENCE + GRADIENT_EXAGGERATION * (real - C_REAL_REFERENCE)
        # Wood's collapse multiplies the finished field rather than joining the
        # clear-water formula, because it must not be exaggerated -- see the
        # constants block. The division is the m/s -> px/s conversion promised
        # in the units contract; it is exact at 1 px per metre and correct if
        # that ever changes.
        self._c = (
            np.maximum(exaggerated * self._wood_ratio(), C_FLOOR) / METRES_PER_PIXEL
        )
        # np.gradient with pixel spacing gives per-pixel slopes, which is the
        # unit a marcher stepping in pixels wants. An axis only one cell wide
        # has no slope to measure -- the bench (§10) is allowed to be a tank
        # smaller than a cell, and a marcher in it should get flat water
        # rather than an exception.
        self._dcdy = (
            np.gradient(self._c, self.cell_size, axis=0)
            if self.ny > 1
            else np.zeros_like(self._c)
        )
        self._dcdx = (
            np.gradient(self._c, self.cell_size, axis=1)
            if self.nx > 1
            else np.zeros_like(self._c)
        )
        self._dirty = False

    # --- sampling -----------------------------------------------------------

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        col = int(x / self.cell_size)
        row = int(y / self.cell_size)
        col = 0 if col < 0 else (self.nx - 1 if col >= self.nx else col)
        row = 0 if row < 0 else (self.ny - 1 if row >= self.ny else row)
        return row, col

    def _bilinear(self, field, x: float, y: float) -> float:
        fx = x / self.cell_size - 0.5
        fy = y / self.cell_size - 0.5
        i0 = int(math.floor(fx))
        j0 = int(math.floor(fy))
        tx = min(1.0, max(0.0, fx - i0))
        ty = min(1.0, max(0.0, fy - j0))
        i0c = 0 if i0 < 0 else (self.nx - 1 if i0 > self.nx - 1 else i0)
        i1c = 0 if i0 + 1 < 0 else (self.nx - 1 if i0 + 1 > self.nx - 1 else i0 + 1)
        j0c = 0 if j0 < 0 else (self.ny - 1 if j0 > self.ny - 1 else j0)
        j1c = 0 if j0 + 1 < 0 else (self.ny - 1 if j0 + 1 > self.ny - 1 else j0 + 1)
        top = field[j0c, i0c] * (1.0 - tx) + field[j0c, i1c] * tx
        bottom = field[j1c, i0c] * (1.0 - tx) + field[j1c, i1c] * tx
        return float(top * (1.0 - ty) + bottom * ty)

    def _sample_weights(self, xs, ys):
        """Corner indices and blend fractions for a whole array of points.

        Deliberately the same arithmetic as `_bilinear`, in the same order, so
        the batched results are bit-identical rather than merely close -- a
        marcher must not see a front behave differently depending on which
        entry point sampled the water. The index clamp to [-1, nx] before the
        integer cast is what keeps a wild coordinate from overflowing intp;
        it cannot change an answer, because outside that range both corners
        of the interpolation are already the same cell.
        """
        fx = np.asarray(xs, dtype=np.float64) / self.cell_size - 0.5
        fy = np.asarray(ys, dtype=np.float64) / self.cell_size - 0.5
        ix = np.floor(fx)
        iy = np.floor(fy)
        tx = np.clip(fx - ix, 0.0, 1.0)
        ty = np.clip(fy - iy, 0.0, 1.0)
        ix = np.clip(ix, -1.0, float(self.nx)).astype(np.intp)
        iy = np.clip(iy, -1.0, float(self.ny)).astype(np.intp)
        return (
            np.clip(iy, 0, self.ny - 1),
            np.clip(iy + 1, 0, self.ny - 1),
            np.clip(ix, 0, self.nx - 1),
            np.clip(ix + 1, 0, self.nx - 1),
            tx,
            ty,
        )

    @staticmethod
    def _gather(field, weights):
        j0, j1, i0, i1, tx, ty = weights
        top = field[j0, i0] * (1.0 - tx) + field[j0, i1] * tx
        bottom = field[j1, i0] * (1.0 - tx) + field[j1, i1] * tx
        return top * (1.0 - ty) + bottom * ty

    def sound_speed_at(self, xs, ys) -> np.ndarray:
        """Vectorised `sound_speed`. Same units (px/s), same values."""
        self._ensure_derived()
        return self._gather(self._c, self._sample_weights(xs, ys))

    def c_gradient_at(self, xs, ys) -> tuple[np.ndarray, np.ndarray]:
        """Vectorised `c_gradient`. One index computation feeds both axes,
        which is most of why batching pays for a marcher that always wants
        the pair."""
        self._ensure_derived()
        weights = self._sample_weights(xs, ys)
        return self._gather(self._dcdx, weights), self._gather(self._dcdy, weights)

    def absorption_at(self, xs, ys, freq) -> np.ndarray:
        """Vectorised `absorption`, for one frequency across many points.

        The scalar version returns early in clear water; here the bubble term
        is computed everywhere and multiplied by a bubble fraction of zero,
        which is exactly the same number because the resonance factor is
        always finite -- the radius is floored precisely so that it is.
        """
        self._ensure_derived()
        freq = max(float(freq), 1e-6)
        clear = (
            ABSORPTION_AT_REF_FREQ
            * (freq / ABSORPTION_REF_FREQ) ** ABSORPTION_FREQ_POWER
            * METRES_PER_PIXEL
        )
        weights = self._sample_weights(xs, ys)
        fraction = self._gather(self.bubbles, weights)
        radius = np.maximum(self._gather(self.bubble_radius, weights), MIN_BUBBLE_RADIUS)
        depth = np.maximum(np.asarray(ys, dtype=np.float64), 0.0) * METRES_PER_PIXEL
        pressure = PRESSURE_SURFACE + PRESSURE_PER_METRE * depth
        resonant = MINNAERT_CONSTANT * np.sqrt(pressure) / radius
        detune = freq / resonant - resonant / freq
        peak = 1.0 / (1.0 + (BUBBLE_Q * detune) ** 2)
        return clear + BUBBLE_ABSORPTION * METRES_PER_PIXEL * fraction * (
            1.0 + BUBBLE_RESONANCE_GAIN * peak
        )

    def is_solid_at(self, xs, ys) -> np.ndarray:
        """Vectorised `is_solid`. Nearest cell with clamping, so a point past
        the seabed reads as whatever the seabed cell is."""
        cols = np.clip(
            np.clip(np.floor(np.asarray(xs, dtype=np.float64) / self.cell_size), -1.0, float(self.nx)).astype(np.intp),
            0,
            self.nx - 1,
        )
        rows = np.clip(
            np.clip(np.floor(np.asarray(ys, dtype=np.float64) / self.cell_size), -1.0, float(self.ny)).astype(np.intp),
            0,
            self.ny - 1,
        )
        return self.solid[rows, cols]

    def pressure_at(self, y: float) -> float:
        """Bar at world depth y. Linear in y and in nothing else (§7.1)."""
        return PRESSURE_SURFACE + PRESSURE_PER_METRE * max(0.0, y) * METRES_PER_PIXEL

    def sound_speed(self, x: float, y: float) -> float:
        self._ensure_derived()
        return self._bilinear(self._c, x, y)

    def c_gradient(self, x: float, y: float) -> tuple[float, float]:
        """(dc/dx, dc/dy) per pixel.

        A wavefront bends toward slower water, so a marcher turns its heading
        by the component of the negated gradient perpendicular to travel.
        Everything in §7.3 -- refraction, shadow zones, the acoustic mirror,
        the sound channel -- is downstream of these two numbers, and none of
        it is authored anywhere else.
        """
        self._ensure_derived()
        return self._bilinear(self._dcdx, x, y), self._bilinear(self._dcdy, x, y)

    def density(self, x: float, y: float) -> float:
        self._ensure_derived()
        return self._bilinear(self._rho, x, y)

    def is_solid(self, x: float, y: float) -> bool:
        row, col = self._cell(x, y)
        return bool(self.solid[row, col])

    def absorption(self, x: float, y: float, freq: float) -> float:
        """Attenuation in nepers per pixel: amplitude *= exp(-absorption*dist).

        Two terms, and the second is the interesting one. Clear water is a
        power law in frequency, so a low note crosses the room and a high note
        does not. A bubble field adds orders of magnitude more, peaking sharply
        at the bubbles' own Minnaert frequency -- which scales with the square
        root of pressure, so the same curtain eats a different note at every
        depth, and eats a sliding note as it rises.
        """
        freq = max(float(freq), 1e-6)
        clear = (
            ABSORPTION_AT_REF_FREQ
            * (freq / ABSORPTION_REF_FREQ) ** ABSORPTION_FREQ_POWER
            * METRES_PER_PIXEL
        )
        bubble_fraction = self._bilinear(self.bubbles, x, y)
        if bubble_fraction <= 0.0:
            return clear
        radius = max(self._bilinear(self.bubble_radius, x, y), MIN_BUBBLE_RADIUS)
        resonant = MINNAERT_CONSTANT * math.sqrt(self.pressure_at(y)) / radius
        detune = freq / resonant - resonant / freq
        peak = 1.0 / (1.0 + (BUBBLE_Q * detune) ** 2)
        return clear + BUBBLE_ABSORPTION * METRES_PER_PIXEL * bubble_fraction * (
            1.0 + BUBBLE_RESONANCE_GAIN * peak
        )

    # --- injection ----------------------------------------------------------

    def add_heat(self, x: float, y: float, amount: float) -> None:
        """Absorbed sound becomes heat (§7.2). One cell, no splat kernel: the
        cell is the unit the player can see, and a kernel would smear the
        density boundary that the whole acoustic-mirror trick depends on."""
        row, col = self._cell(x, y)
        if self.solid[row, col]:
            return
        self.temp[row, col] += float(amount)
        self._dirty = True

    def add_channel(self, name: str, diffusivity: float, half_life: float) -> None:
        """Declare a trophic channel. RIGS.md 13.4.

        Two numbers, and they are the channel's whole character: diffusivity
        is how far it can be smelled, half-life is how long a place stays
        worth visiting. A wide slow channel says "the shoal is somewhere that
        way" from across a room; a tight fast one says "it is right here".
        One creature reading the first positively and the second negatively is
        long-range attraction with short-range repulsion, which is the entire
        difference between an aggregation and a smear.

        Idempotent, so a caller can declare the same world twice without
        wiping what is in it.
        """
        if name in self.channels:
            return
        self.channels[name] = np.zeros((self.ny, self.nx))
        self._channel_rates[name] = (float(diffusivity), float(half_life))

    def deposit(self, name: str, x: float, y: float, amount: float) -> None:
        """Leave something behind. One cell, for `add_heat`'s reason."""
        field = self.channels.get(name)
        if field is None or amount <= 0.0:
            return
        row, col = self._cell(x, y)
        if self.solid[row, col]:
            return
        field[row, col] += float(amount)

    def consume(self, name: str, x: float, y: float, amount: float) -> float:
        """Eat. Returns what was actually there to be eaten.

        This is what stops an aggregation collapsing to a point. Attraction
        alone is monotone toward the peak, so every arrival climbs to the same
        cell and stays; letting the arrivals EAT flattens the peak they came
        for, which spreads the crowd out and makes the whole knot travel. It
        is also what makes RIGS.md 13.4's cycle a transfer of something rather
        than five independent sources agreeing to be near each other.
        """
        field = self.channels.get(name)
        if field is None or amount <= 0.0:
            return 0.0
        row, col = self._cell(x, y)
        taken = min(float(field[row, col]), float(amount))
        if taken <= 0.0:
            return 0.0
        field[row, col] -= taken
        return taken

    def channel_at(self, name: str, x: float, y: float) -> float:
        field = self.channels.get(name)
        if field is None:
            return 0.0
        return self._bilinear(field, x, y)

    def add_bubbles(self, x: float, y: float, amount: float, radius: float) -> None:
        row, col = self._cell(x, y)
        if self.solid[row, col] or amount <= 0.0:
            return
        total = self.bubbles[row, col] + amount
        self.bubble_radius[row, col] = (
            self.bubbles[row, col] * self.bubble_radius[row, col] + amount * float(radius)
        ) / total
        self.bubbles[row, col] = min(1.0, total)
        self._dirty = True

    # --- scenario setup -----------------------------------------------------

    def set_temperature_profile(self, fn) -> None:
        """fn(depth_fraction) -> temperature, applied to every row.

        Also re-seeds dissolved gas to GAS_INITIAL_SATURATION of the new local
        capacity. A scenario handing over a profile wants still water, not a
        domain that starts fizzing on step one because the gas field was left
        over from a colder ocean.
        """
        fractions = (np.arange(self.ny) + 0.5) / self.ny
        column = np.array([float(fn(float(f))) for f in fractions]).reshape(-1, 1)
        self.temp[:] = column
        self.gas[:] = GAS_INITIAL_SATURATION * self._gas_capacity()
        self._dirty = True

    def carve(self, x, y, w, h) -> None:
        """Mark a world-space rectangle solid. Rock does not diffuse heat, does
        not exchange with the water beside it, and blocks bubbles rising
        through it -- so an overhang collects a pocket of gas for free."""
        c0 = max(0, int(math.floor(x / self.cell_size)))
        c1 = min(self.nx, int(math.ceil((x + w) / self.cell_size)))
        r0 = max(0, int(math.floor(y / self.cell_size)))
        r1 = min(self.ny, int(math.ceil((y + h) / self.cell_size)))
        if c1 <= c0 or r1 <= r0:
            return
        self.solid[r0:r1, c0:c1] = True
        self.bubbles[r0:r1, c0:c1] = 0.0
        self.gas[r0:r1, c0:c1] = 0.0
        self._dirty = True

    # --- the step -----------------------------------------------------------

    def step(self, dt: float) -> None:
        dt = float(dt)
        if dt <= 0.0:
            return
        self.elapsed += dt
        self._diffuse_heat(dt)
        self._advect_channels(dt)
        self._step_channels(dt)
        self._buoyancy(dt)
        self._shed_gas(dt)
        self._rise_bubbles(dt)
        # The tide moves even when nothing else does, so the flow field is
        # stale after every step regardless of whether a cell changed.
        self._dirty = True

    def _neighbours(self, field):
        """The four neighbours of every cell, with solid cells and the domain
        edge replaced by the cell's own value. That is a zero-flux boundary in
        both cases, which is what makes diffusion conserve exactly: every pair
        of cells either exchanges antisymmetrically or not at all."""
        padded = np.pad(field, 1, mode="edge")
        walls = np.pad(self.solid, 1, mode="edge")
        return [
            np.where(walls[sl_r, sl_c], field, padded[sl_r, sl_c])
            for sl_r, sl_c in (
                (slice(0, -2), slice(1, -1)),
                (slice(2, None), slice(1, -1)),
                (slice(1, -1), slice(0, -2)),
                (slice(1, -1), slice(2, None)),
            )
        ]

    def _diffuse_heat(self, dt: float) -> None:
        alpha = min(HEAT_DIFFUSIVITY * dt / (self.cell_size**2), MAX_DIFFUSION_ALPHA)
        up, down, left, right = self._neighbours(self.temp)
        laplacian = up + down + left + right - 4.0 * self.temp
        self.temp += np.where(self.solid, 0.0, alpha * laplacian)

    def _advect_channels(self, dt: float) -> None:
        """Carry every channel on the current. RIGS.md 13.4, 13.6.

        This is the difference between an ecosystem that can be found and one
        that cannot. Diffusion alone gave a detection range of about 200 px --
        past that the field is under CHANNEL_FLOOR, the gradient is exactly
        zero, and a creature more than a couple of rooms from food freezes in
        place, which in a 1200x800 ocean is nearly everywhere. Measured: a
        decomposer 300 px from a fed patch never arrived.

        Advection fixes it the way the real ocean does. A scent is not spread
        by spreading, it is spread by being carried, so a source streams a long
        thin plume downtide -- findable from far away along the flow and sharp
        across it. Which means the tide of 13.6 decides what you can smell and
        from where, and approaching a thing from downstream is a different
        proposition from approaching it from upstream. Nobody has to write that
        down; it is one flux term.

        Conservative upwind, in flux form, so this moves the channel around
        without creating or destroying any of it -- the same discipline as
        `_neighbours`, and for the same reason. The CFL number here is about
        0.03 at the fastest water the medium can produce, so the scheme is
        nowhere near its stability limit and the clamp below never binds.
        """
        if not self.channels:
            return
        u, v = self.flow_field

        # Face velocities, with a zero-flux wall at every solid boundary.
        ux = 0.5 * (u[:, :-1] + u[:, 1:])
        vy = 0.5 * (v[:-1, :] + v[1:, :])
        ux = np.where(self.solid[:, :-1] | self.solid[:, 1:], 0.0, ux)
        vy = np.where(self.solid[:-1, :] | self.solid[1:, :], 0.0, vy)

        k = dt / self.cell_size
        ux = np.clip(ux * k, -MAX_ADVECT_COURANT, MAX_ADVECT_COURANT)
        vy = np.clip(vy * k, -MAX_ADVECT_COURANT, MAX_ADVECT_COURANT)

        for field in self.channels.values():
            fx = np.where(ux > 0.0, field[:, :-1], field[:, 1:]) * ux
            fy = np.where(vy > 0.0, field[:-1, :], field[1:, :]) * vy
            field[:, :-1] -= fx
            field[:, 1:] += fx
            field[:-1, :] -= fy
            field[1:, :] += fy

    def _step_channels(self, dt: float) -> None:
        """Diffuse and decay every trophic channel. RIGS.md 13.4.

        Identical stencil to `_diffuse_heat`, and deliberately so: it inherits
        the zero-flux boundary from `_neighbours`, which means a channel does
        not leak through walls and does not leak out of the domain. A scent
        that seeps through rock would let a creature climb toward something it
        cannot reach, and a creature stuck against a wall reading a gradient
        that never resolves is the exact failure mode 9's `_band` softness was
        written to avoid.

        Decay is exponential and framerate-independent. A channel steps at the
        medium's rate, not the renderer's (13.7), so this has to be correct for
        any dt rather than tuned for one.
        """
        for name, field in self.channels.items():
            diffusivity, half_life = self._channel_rates[name]
            alpha = min(diffusivity * dt / (self.cell_size**2), MAX_DIFFUSION_ALPHA)
            up, down, left, right = self._neighbours(field)
            laplacian = up + down + left + right - 4.0 * field
            field += np.where(self.solid, 0.0, alpha * laplacian)
            if half_life > 0.0:
                field *= 0.5 ** (dt / half_life)
            field[field < CHANNEL_FLOOR] = 0.0
            field[self.solid] = 0.0

    def _buoyancy(self, dt: float) -> None:
        """Heavy sitting on light is unstable, so the pair partly swaps. Not a
        fluid solver, and never allowed to become one: this is the entirety of
        "heavy sinks, water stratifies into layers" (§7.1).

        The price of having no momentum is that lifting an anomaly also mixes
        it, so a blob climbs a couple of cells and then stalls once it has
        flattened the inversion driving it. Stratification and the layer
        boundaries the mirror needs come out correct; a tall coherent plume
        does not, and would cost a velocity field to buy."""
        density = self._compute_density()
        inversion = density[:-1, :] - density[1:, :]
        exchange = np.clip(BUOYANCY_RATE * dt * inversion, 0.0, MAX_EXCHANGE)
        exchange[self.solid[:-1, :] | self.solid[1:, :]] = 0.0

        # Bubbles are exchanged along with everything else, and leaving them
        # out was a real bug rather than a simplification: `_compute_density`
        # subtracts BUBBLE_LIGHTENING * bubbles, so a bubble cloud makes its
        # own cell permanently lighter than the water above it. If buoyancy
        # cannot move the bubbles, that inversion can never resolve, and the
        # pair grinds against each other forever -- stirring temperature,
        # which warms cells, which sheds more gas (warm water holds less),
        # which makes more bubbles and a stronger inversion. Measured on the
        # unfixed version: a stationary cloud drove a 0.29 C spread to 2.52 C
        # and grew itself from 5.4 to 7.1 units of gas with nothing acting on
        # it. Exchanging bubbles closes the loop, and it is also what §7.2's
        # "bubbles lighten water -> a rising column" actually means.
        for field in (self.temp, self.salinity, self.gas, self.bubbles):
            flux = exchange * (field[1:, :] - field[:-1, :])
            field[:-1, :] += flux
            field[1:, :] -= flux
        np.clip(self.bubbles, 0.0, 1.0, out=self.bubbles)

    def _shed_gas(self, dt: float) -> None:
        """Water holds less gas when it is warm and more when it is deep. What
        it cannot hold becomes bubbles, born at the size pressure allows -- so
        the same spell makes fat lazy bubbles at 50 m and a fine mist at 700 m,
        and the two do not sound alike."""
        excess = np.maximum(self.gas - self._gas_capacity(), 0.0)
        shed = excess * min(OUTGAS_RATE * dt, 1.0)
        shed[self.solid] = 0.0
        total = self.bubbles + shed
        self.bubble_radius = np.where(
            total > 1e-12,
            (self.bubbles * self.bubble_radius + shed * self._nucleation_radius)
            / np.maximum(total, 1e-12),
            self.bubble_radius,
        )
        self.gas -= shed
        self.bubbles = np.clip(total, 0.0, 1.0)

    def _rise_bubbles(self, dt: float) -> None:
        """Bubbles go up at a fixed speed, growing by Boyle's law as the
        pressure above them falls, and vent at the surface. A cell's radius is
        the bubble-weighted mean of what was already there and what arrived,
        which is why a plume's note slides upward as it climbs."""
        rise = min(BUBBLE_RISE_SPEED * dt / self.cell_size, MAX_RISE_FRACTION)
        moved = self.bubbles[1:, :] * rise
        moved[self.solid[:-1, :] | self.solid[1:, :]] = 0.0
        grown = self.bubble_radius[1:, :] * self._rise_expansion
        arrived = self.bubbles[:-1, :] + moved
        self.bubble_radius[:-1, :] = np.where(
            arrived > 1e-12,
            (self.bubbles[:-1, :] * self.bubble_radius[:-1, :] + moved * grown)
            / np.maximum(arrived, 1e-12),
            self.bubble_radius[:-1, :],
        )
        self.bubbles[:-1, :] = arrived
        self.bubbles[1:, :] -= moved
        self.bubbles[0, :] *= 1.0 - rise
        np.clip(self.bubble_radius, MIN_BUBBLE_RADIUS, MAX_BUBBLE_RADIUS, out=self.bubble_radius)
