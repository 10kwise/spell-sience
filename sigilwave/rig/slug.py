"""The parcel of water that travels the pipe, and the books it keeps.

RIGS.md 3.1. The slug is the protagonist (9.4, inherited from SUBMERGED): it
carries five properties, every one of which is drawable, and every rule in the
game is legible in watching it cross a chain.

The Ledger is the other half and it is what makes this design honest. Every
module records what it moved and where it came from, and `Ledger.residual()`
must come back at zero. That is not decoration -- it is the difference between
a system whose behaviour composes and a pile of effects that happen to look
plausible one at a time.
"""

import math
from dataclasses import dataclass, field

from .units import (
    ACOUSTIC_FACE,
    C_P_WATER,
    DEFAULT_AREA,
    PASCALS_PER_BAR,
    RHO_WATER,
    SOUND_SPEED,
    gas_capacity,
)


@dataclass
class Slug:
    """Five numbers and no others (RIGS.md 3.1).

    `area` is not a sixth property of the water -- it is the aperture the
    water is currently being pushed through, which NARROW and WIDEN change and
    which sets speed for a given mass flow. It belongs to the pipe rather than
    to the parcel, and it is here because the parcel is the only thing that
    travels.
    """

    mass: float             # kg
    temp: float             # degC
    pressure: float         # bar absolute
    gas: float              # dissolved gas, in field.py's units
    speed: float = 0.0      # m/s
    area: float = DEFAULT_AREA   # m^2, the aperture it is moving through
    note: float = 0.0       # Hz
    note_amp: float = 0.0   # J of acoustic energy carried
    working: float = 0.0    # compressible fraction, fixed at the intake

    # --- derived, never stored ----------------------------------------------

    @property
    def capacity(self) -> float:
        """The most gas this parcel could hold at its own pressure and heat."""
        return gas_capacity(self.pressure, self.temp)

    @property
    def bubbles(self) -> float:
        """Gas beyond what this pressure and heat can hold.

        RIGS.md 3.1: bubbles are deliberately NOT a sixth number. They are a
        consequence, computed the same way `field.py` computes them, so "why
        did my rig fizz" always has one answer and that answer is a law.
        """
        return max(0.0, self.gas - self.capacity)

    @property
    def kinetic(self) -> float:
        """J. What the port would deliver as thrust."""
        return 0.5 * self.mass * self.speed * self.speed

    @property
    def acoustic_pressure(self) -> float:
        """bar. The swing the note rides on, which is NOT in `pressure`.

        This property is the whole of what made sound stop being decoration.
        A slug at 1 bar carrying a 3 bar note is at minus 2 bar for part of
        every cycle, and water does not hold together through that -- so the
        cavitation check has to read the trough rather than the mean, and once
        it does, every module that touches area or pressure is also a module
        that touches sound.

        Nothing is invented here. Acoustic intensity is power over area, and a
        plane wave's pressure amplitude is `sqrt(2 rho c I)`. `note_amp` is
        joules per pass and a pass is a second (RIG_MASS_FLOW is kg/s), so it
        is already a power. The only chosen quantity is ACOUSTIC_FACE, which
        is how big the projector is, and `units.py` says why it cannot be much
        smaller.

        The area it divides by is the SLUG's, scaled, so NARROW and WIDEN move
        it: halving the aperture multiplies the pressure by root two. A horn
        concentrates and a bell spreads, and that is a real horn and a real
        bell rather than two words in a table.
        """
        if self.note_amp <= 0.0 or self.area <= 0.0:
            return 0.0
        face = ACOUSTIC_FACE * (self.area / DEFAULT_AREA)
        intensity = self.note_amp / face
        return math.sqrt(2.0 * RHO_WATER * SOUND_SPEED * intensity) / PASCALS_PER_BAR

    @property
    def tension(self) -> float:
        """bar. The LOWEST pressure this water actually sees, mean minus swing.

        Every cavitation test in the game reads this rather than `pressure`,
        which is the one-line version of why a RESONATOR is worth placing.
        """
        return self.pressure - self.acoustic_pressure

    def flow_energy(self, reference_pressure: float) -> float:
        """J of pressure energy this parcel is carrying, against ambient.

        This term was missing from the first draft and two separate bugs fell
        out of the omission, which is a good advertisement for keeping books
        that have to balance.

        A nozzle trades pressure for speed, so without a pressure term the
        thruster's kinetic energy came from nowhere and the residual was
        11.5 kJ out. Worse, EXPAND recovered turbine work while dropping the
        pressure BELOW ambient -- which is pulling a vacuum, and pulling a
        vacuum costs work rather than yielding it. The gill and the lamp both
        ran at negative cost: free energy, buildable in four modules.

        Measuring flow energy against ambient fixes both at once, because
        below ambient it goes negative and the ledger correctly reports that
        the rig had to pay to get there.
        """
        return (self.pressure - reference_pressure) * self.volume * PASCALS_PER_BAR

    @property
    def volume(self) -> float:
        return self.mass / RHO_WATER

    def internal(self, reference_temp: float) -> float:
        """J of thermal energy relative to a reference temperature.

        Every ledger term is measured against where the water started, which
        is what makes `residual` a plain sum rather than an argument about
        absolute internal energy.
        """
        return self.mass * C_P_WATER * (self.temp - reference_temp)

    def copy(self) -> "Slug":
        return Slug(self.mass, self.temp, self.pressure, self.gas,
                    self.speed, self.area, self.note, self.note_amp,
                    self.working)


@dataclass
class Ledger:
    """Where every joule came from and where it went.

    Sign convention, and it is worth stating because getting it wrong is the
    classic way a conservation test passes while meaning nothing:

        POSITIVE = energy that entered the rig
        NEGATIVE = energy that left it

    So `work_in` is what the energy economy paid, `work_out` is what a turbine
    handed back, and everything in `spent` left through a port or a coil.
    """

    # in
    work_in: float = 0.0            # J drawn from the economy (sources.py)
    heat_from_ocean: float = 0.0    # J the coil took OUT of the water

    # out
    work_out: float = 0.0           # J a turbine recovered
    heat_to_ocean: float = 0.0      # J the coil put INTO the water
    kinetic_out: float = 0.0        # J that left as moving water
    acoustic_out: float = 0.0       # J that left as sound
    heat_out: float = 0.0           # J that left as warm water through a port

    # stored
    tank_heat: float = 0.0          # J held by FILTER, spendable by INJECT
    tank_gas: float = 0.0           # kg of gas held

    # How much gradient heat the thermopiles have already ferried this pass.
    # NOT an energy term -- it never enters `residual`, it is a budget.
    #
    # One pass of pipe can carry at most `m * Cp * dT` between two
    # temperatures, because past that the water would have to leave hotter
    # than the hot end or colder than the cold one. That is a heat exchanger
    # effectiveness bound and it is the only thing standing between this game
    # and a wall of twenty thermopiles: each one on its own obeys Carnot, so
    # stacking them is not a violation, it is just more hardware -- and the
    # fuzzer found a chain that reset the slug with FILTER/INJECT between
    # piles and reached 185% of what one pass can carry.
    pile_heat: float = 0.0

    flow_out: float = 0.0           # J of pressure energy dumped at a port
    latent: float = 0.0             # J the slug gave up freezing instead of cooling
    bubbles_shed: float = 0.0       # kg of gas left behind as a cavitation cloud

    # bookkeeping
    reference_temp: float = 0.0     # degC the intake started at
    reference_pressure: float = 1.0  # bar the intake started at
    gas_from_ocean: float = 0.0     # kg stripped out of the water
    gas_to_ocean: float = 0.0       # kg handed back

    def residual(self, slug: "Slug | None") -> float:
        """What is unaccounted for. Must be zero.

        energy in - energy out - energy still in the slug - energy in the tank

        `selftest_conservation` asserts this is within float noise for every
        chain in the library, at every depth, which is the check that makes
        RIGS.md's claim to be a system rather than a pile of effects real.
        """
        # `latent` is energy that genuinely left the slug but is not visible in
        # its temperature, because it came out of the phase change instead.
        #
        # It is subtracted UNCONDITIONALLY, and that placement is the whole of
        # the bug this comment exists for. Written inside the `slug is not
        # None` branch it silently vanished the moment a PORT consumed the
        # slug, and every chain that froze came back 41 MJ out. Ice does not
        # stop existing because the water left the pipe.
        held = -self.latent
        if slug is not None:
            held += (slug.internal(self.reference_temp)
                     + slug.kinetic
                     + slug.note_amp
                     + slug.flow_energy(self.reference_pressure))
        return (
            (self.work_in + self.heat_from_ocean)
            - (self.work_out + self.heat_to_ocean + self.kinetic_out
               + self.acoustic_out + self.heat_out + self.flow_out)
            - held
            - self.tank_heat
        )

    def gas_residual(self, slug: "Slug | None") -> float:
        """Gas is conserved separately, and by mass.

        Nothing creates gas. FILTER moves it from the water to the tank,
        INJECT moves it back, and a port hands whatever is left to the ocean.
        """
        held = slug.mass * slug.gas if slug is not None else 0.0
        return (self.gas_from_ocean - self.gas_to_ocean - self.tank_gas
                - self.bubbles_shed - held)

    @property
    def net_work(self) -> float:
        """What the rig actually cost to run, in J.

        This is the number `sources.py` bills against, and it is the one place
        understanding is countable: two chains that do the same job differ
        here, and the better-understood one is cheaper.
        """
        return self.work_in - self.work_out

    def add(self, other: "Ledger") -> None:
        self.work_in += other.work_in
        self.work_out += other.work_out
        self.heat_from_ocean += other.heat_from_ocean
        self.heat_to_ocean += other.heat_to_ocean
        self.kinetic_out += other.kinetic_out
        self.acoustic_out += other.acoustic_out
        self.heat_out += other.heat_out
        self.flow_out += other.flow_out
        self.latent += other.latent
        self.bubbles_shed += other.bubbles_shed
        self.tank_heat += other.tank_heat
        self.tank_gas += other.tank_gas
        self.pile_heat += other.pile_heat
        self.gas_from_ocean += other.gas_from_ocean
        self.gas_to_ocean += other.gas_to_ocean


@dataclass
class Ambient:
    """The water the rig is standing in. Read-only, per evaluation.

    A rig reads ambient at its intake and at every coil, which is what makes
    RIGS.md 9.1 -- depth flips the sign on almost everything -- true without a
    single depth-dependent branch anywhere in `modules.py`.
    """

    temp: float          # degC
    pressure: float      # bar absolute
    gas: float           # dissolved gas fraction in the surrounding water
    depth: float = 0.0   # m, for reporting only

    # The water the COIL and the THERMOPILE are exchanging with, which is not
    # necessarily the water the INTAKE is standing in.
    #
    # This is the second-smallest change in the whole redesign and it is what
    # makes a generator possible. `couple.apply` already let a player put the
    # coil somewhere else -- "one who runs the coil down a line has built a
    # radiator" -- and a radiator with something standing in the heat flow is
    # a power station. Kelvin-Planck says you cannot get work out of ONE
    # temperature, so a rig that can only see one temperature can only ever
    # spend. Giving it a second is the entire difference.
    #
    # None means "the same water", so every call site that does not care is
    # unchanged and reads exactly as it did before.
    sink_temp: float | None = None

    @property
    def sink(self) -> float:
        """degC of whatever the coil is dumping into. Defaults to right here."""
        return self.temp if self.sink_temp is None else float(self.sink_temp)

    @property
    def gradient(self) -> float:
        """degC the ocean is maintaining across this rig, for free.

        Zero in ordinary water. This is the only quantity a THERMOPILE can
        actually charge against, and it is a property of WHERE THE PLAYER IS
        STANDING rather than of anything they built.
        """
        return self.sink - self.temp

    @property
    def capacity(self) -> float:
        return gas_capacity(self.pressure, self.temp)
