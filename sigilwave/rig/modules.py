"""The eleven modules. RIGS.md 5.

Each one is a single sentence, has no knobs, and obeys the architectural rule
from `units.py`:

    **compute the ENERGY moved, then derive the temperature from it.**

Not one function here picks a temperature change. Every `dT` in this file is
`Q / (m * C_P_WATER)` for a `Q` that was already written into the ledger, so
`selftest_conservation` is checking arithmetic rather than intentions.

WHAT WORKING THROUGH THE PHYSICS CHANGED
----------------------------------------
Three things came back different from the design doc, and all three are
recorded here rather than quietly fixed, because in each case the correction
is better than what it replaced.

**NARROW drops pressure, which RIGS.md 5 did not say.** A nozzle is Bernoulli:
it buys speed by spending pressure. That was not designed for, and it hands
the vocabulary a second route to cavitation -- narrow hard enough and the
water tears at the throat, which is exactly why real propellers cavitate. So
NARROW is both the thruster module and the cheap way to make a bang, and
nobody had to write that down.

**A squeeze-expand round trip comes back HOTTER, not level.** RIGS.md 6 calls
the coil-less cooler "nothing at all". It is worse than that: the compressor
puts all of its work into the fluid while the turbine only recovers 78% of
what is there, so the slug ends up a few degrees warm. The lesson is sharper
than the one that was designed -- you did not merely fail to cool it, you
spent energy heating it -- and it is the Second Law teaching itself.

**PUMP barely heats anything, and SQUEEZE costs three thousand times more.**
Moving water is cheap; moving heat is expensive. That is true of real machines
and it means the economy has a shape nobody chose: thermal work is what you
budget for, and thrust and sound are the utilities you spend it on.
"""

import math

from .slug import Ambient, Ledger, Slug
from .units import (
    AREA_RATIO,
    BOIL_TEMP,
    C_P_WATER,
    ETA_COIL,
    ETA_COMPRESSOR,
    ETA_PUMP,
    ETA_RESONATOR,
    ETA_TURBINE,
    MAX_WORKING_FRACTION,
    MIN_WORKING_FRACTION,
    PASCALS_PER_BAR,
    PRESSURE_RATIO,
    PUMP_WORK,
    RESONATOR_WORK,
    RIG_MASS_FLOW,
    RHO_WATER,
    FREEZE_TEMP,
    LATENT_HEAT_FUSION,
    TEAR_PRESSURE,
    VAPOUR_PRESSURE,
    WORKING_NUCLEATION,
    compression_work,
    gas_capacity,
    working_fraction,
)

# The five rungs of SUBMERGED 7.4, kept exactly. A RESONATOR has no knob, so
# the note is chosen when the module is placed and the ladder is the whole
# choice -- five named notes rather than a circumference in pixels, which is
# the entire point of RIGS.md 2.1.
NOTES = {
    "swell": 117.0,
    "groan": 234.0,
    "hum": 469.0,
    "ping": 937.0,
    "chirp": 1875.0,
}
DEFAULT_NOTE = "hum"

# A nozzle cannot pull the water below its own vapour pressure; past that it
# stops being water and the cavity is what carries the difference.
MIN_PRESSURE = VAPOUR_PRESSURE * 0.5

DEFAULT_AREA = 0.02       # m^2, the bore of an unmodified pipe


class Module:
    """One module. Kind, one sentence, and a transform.

    `apply` takes the slug (None before an INTAKE, None after a PORT), the
    ambient water, and the ledger it must write every joule into. It returns
    the new slug and a list of events -- 'tore', 'fizzed' -- that the chain
    turns into failures and the bench turns into animation.
    """

    __slots__ = ("kind", "line", "option")

    def __init__(self, kind, line, option=None):
        self.kind = kind
        self.line = line
        self.option = option

    def __repr__(self):
        if self.option:
            return f"{self.kind}({self.option})"
        return self.kind

    def apply(self, s, amb, led):
        raise NotImplementedError


# --- the pairs ---------------------------------------------------------------


class Intake(Module):
    def __init__(self):
        super().__init__(
            "INTAKE",
            "Water enters here, at the temperature and pressure of wherever it is.",
        )

    def apply(self, s, amb, led):
        if s is not None:
            return s, ["already open"]
        led.reference_temp = amb.temp
        led.reference_pressure = amb.pressure
        fresh = Slug(
            mass=RIG_MASS_FLOW,
            temp=amb.temp,
            pressure=amb.pressure,
            gas=amb.gas,
            speed=0.0,
            area=DEFAULT_AREA,
            # Fixed here and only here. How well this rig compresses is a
            # property of the water it took in -- see units.working_fraction.
            working=working_fraction(amb.gas, amb.pressure, amb.temp),
        )
        # The water brings its dissolved gas in with it; a PORT hands it back.
        led.gas_from_ocean += fresh.mass * fresh.gas
        return fresh, []


class Port(Module):
    def __init__(self):
        super().__init__(
            "PORT",
            "Water leaves here, carrying everything it has, in the direction it faces.",
        )

    def apply(self, s, amb, led):
        """Hand the water back -- which means handing it back AT AMBIENT.

        The density search found the bug this fixes, and it was a bad one. A
        bare EXPAND was reported as a cooler: one module, -5.1 degC, 0.17
        units. The proper refrigerator -- SQUEEZE, COIL, EXPAND -- cost 6.03
        units and cooled LESS. So the cheapest way to cool was to skip the
        entire cycle, and the central lesson of RIGS.md 4.1 was not merely
        unrewarded, it was actively punished.

        The cause was that a port simply released whatever it was holding,
        including a slug still sitting at a third of ambient pressure. Water
        cannot leave into the ocean at a third of ambient; the ocean pushes
        back in. It has to be brought up to ambient first, and compressing it
        back up RE-HEATS it -- undoing precisely the cooling the expansion
        bought.

        With the recompression in place a bare expand-and-release nets to
        nothing, and the only way to keep the cold is to get rid of the heat
        while the water is still compressed, which is what the COIL is for.
        That is the actual refrigeration cycle, and it is now the only thing
        that works.
        """
        if s is None:
            return None, []

        # The ocean's own pressure, not the intake's: a rig can port into
        # different water than it drew from, and that difference is a thing a
        # player can build around.
        _equalise(s, amb.pressure, led)

        # Everything the slug still holds leaves the rig. This is the only
        # module that touches the ocean (RIGS.md 5.3), so it is also the only
        # place the ledger's outward terms are written.
        led.kinetic_out += s.kinetic
        led.acoustic_out += s.note_amp
        led.heat_out += s.internal(led.reference_temp)
        led.flow_out += s.flow_energy(led.reference_pressure)
        led.gas_to_ocean += s.mass * s.gas
        return None, ["ported"]


class Squeeze(Module):
    def __init__(self):
        super().__init__("SQUEEZE", "Raises pressure, and heats it.")

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        p2 = s.pressure * PRESSURE_RATIO
        ideal = compression_work(s.mass, s.working, s.temp, s.pressure, p2)
        # A compressor puts ALL of its work into the fluid. Being inefficient
        # means less pressure per joule, not less heat -- which is why eta
        # divides the requirement and does not scale the heating.
        work = ideal / ETA_COMPRESSOR
        led.work_in += work
        add_heat(s, work, led)
        before = s.flow_energy(led.reference_pressure)
        s.pressure = p2
        _book_flow(s, before, led)
        # Compression drives gas back into solution -- the exact inverse of
        # EXPAND's nucleation, and it must use the same factor or the pair
        # stops being a pair.
        s.working = max(MIN_WORKING_FRACTION, s.working / WORKING_NUCLEATION)
        return s, _gas_events(s)


class Expand(Module):
    def __init__(self):
        super().__init__(
            "EXPAND",
            "Lowers pressure, and cools it -- gas above capacity comes out as bubbles.",
        )

    def apply(self, s, amb, led):
        """An expansion VALVE, not a turbine, and the difference is the Second Law.

        The first version recovered the expansion work into `work_out`, and
        the gill and the lamp came out at NEGATIVE cost -- four modules that
        generate energy. The cause was not a sign error. Expanding cools the
        slug, the slug then re-warms from the ocean at the port, and the cycle
        was quietly converting ambient heat into work at 100% efficiency with
        no cold sink anywhere. That is a Kelvin-Planck violation, and it is
        exactly the kind of thing a ledger that has to balance is for: the
        books balanced perfectly while the machine was impossible.

        Real refrigerators use a valve rather than a turbine for precisely
        this reason -- the work is not worth recovering -- so the energy the
        slug gives up is REJECTED to the water instead of returned to the
        economy. The cooling is unaffected, which is the effect anybody
        actually wanted.

        And dropping below ambient is pulling a vacuum, which costs work to
        shove the surrounding water aside. That cost is what makes the lamp
        expensive, and it is what makes it get more expensive with depth.
        """
        if s is None:
            return None, []
        ref_p = led.reference_pressure
        p1 = s.pressure
        p2 = max(MIN_PRESSURE, s.pressure / PRESSURE_RATIO)

        held_before = s.internal(led.reference_temp) + s.flow_energy(ref_p)
        ideal = compression_work(s.mass, s.working, s.temp, p1, p2)
        s.temp -= (-ideal * ETA_TURBINE) / (s.mass * C_P_WATER)
        s.pressure = p2
        held_after = s.internal(led.reference_temp) + s.flow_energy(ref_p)

        released = held_before - held_after
        # The vacuum work: what it costs to hold the water open below ambient.
        vac = (max(0.0, ref_p - p2) - max(0.0, ref_p - p1)) * s.volume * PASCALS_PER_BAR
        vac = max(0.0, vac)
        led.work_in += vac
        led.heat_to_ocean += released + vac

        events = []
        # Expanding frees gas that was in solution, so the working fluid grows
        # -- which is why a chain that expands before it squeezes compresses
        # better than one that does not.
        s.working = min(MAX_WORKING_FRACTION,
                        s.working * WORKING_NUCLEATION)

        if s.pressure <= TEAR_PRESSURE:
            events.append("tore")
            _collapse(s, amb, led)
        events.extend(_gas_events(s))
        return s, events


class Narrow(Module):
    def __init__(self):
        super().__init__(
            "NARROW",
            "The same water through less opening: faster, harder, tighter.",
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        return _bernoulli(s, 1.0 / AREA_RATIO, led, amb)


class Widen(Module):
    def __init__(self):
        super().__init__(
            "WIDEN",
            "The same water through more opening: slower, softer, spread.",
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        return _bernoulli(s, AREA_RATIO, led, amb)


class Filter(Module):
    def __init__(self, what="gas"):
        super().__init__(
            "FILTER",
            "Takes gas and heat out of the water and keeps them in a tank.",
            option=what,
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        events = []
        if self.option in ("gas", "both"):
            # A filter can only catch gas that is actually free. Water that is
            # under-saturated has nothing to give, which is why the gill in
            # the library expands FIRST -- it has to make the bubbles before
            # it can catch them.
            free = s.bubbles
            caught = free * 0.85 if free > 0.0 else s.gas * 0.10
            caught = min(caught, s.gas)
            removed = caught / max(s.gas, 1e-12)
            led.tank_gas += s.mass * caught
            s.gas -= caught
            # Stripping the water takes the compressor's working fluid with it,
            # in proportion to what was actually caught.
            #
            # The first version re-derived `working` from the gas that was
            # LEFT, which barely moved: heavily supersaturated water stays
            # supersaturated after a filter, so the compressor lost 2% and the
            # claim in RIGS.md 5.3 was not true. Taking the working fluid in
            # proportion to the gas removed is both what a filter physically
            # does and what makes "strip a room and disable your own rig" a
            # thing a player can actually do.
            s.working = min(s.working * (1.0 - removed),
                            working_fraction(s.gas, s.pressure, s.temp))
            if caught > 1e-9:
                events.append("caught gas")
        if self.option in ("heat", "both"):
            q = (s.temp - led.reference_temp) * s.mass * C_P_WATER * 0.5
            if q > 0.0:
                led.tank_heat += q
                s.temp -= q / (s.mass * C_P_WATER)
                events.append("caught heat")
        return s, events


class Inject(Module):
    def __init__(self):
        super().__init__("INJECT", "Puts what is in the tank back into the water.")

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        events = []
        if led.tank_heat > 0.0:
            add_heat(s, led.tank_heat, led)
            led.tank_heat = 0.0
            events.append("released heat")
        if led.tank_gas > 0.0:
            s.gas += led.tank_gas / s.mass
            led.tank_gas = 0.0
            s.working = working_fraction(s.gas, s.pressure, s.temp)
            events.append("released gas")
        events.extend(_gas_events(s))
        return s, events


# --- the singletons ----------------------------------------------------------


class Pump(Module):
    def __init__(self):
        super().__init__("PUMP", "Drives the flow. More flow costs more work.")

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        led.work_in += PUMP_WORK
        gained = PUMP_WORK * ETA_PUMP
        lost = PUMP_WORK - gained
        s.speed = math.sqrt(max(0.0, 2.0 * (s.kinetic + gained) / s.mass))
        add_heat(s, lost, led)
        return s, []


class Coil(Module):
    def __init__(self):
        super().__init__(
            "COIL",
            "Moves heat between the water inside it and the water outside.",
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        # Toward equal, never past it. A heat exchanger cannot cool below what
        # it is exchanging with, which is what makes RIGS.md 9.1 true: cold
        # deep water is a better sink, so coolers get stronger with depth.
        q = (s.temp - amb.temp) * s.mass * C_P_WATER * ETA_COIL
        add_heat(s, -q, led)
        if q >= 0.0:
            led.heat_to_ocean += q
        else:
            led.heat_from_ocean += -q
        return s, _gas_events(s)


class Resonator(Module):
    def __init__(self, note=DEFAULT_NOTE):
        if note not in NOTES:
            note = DEFAULT_NOTE
        super().__init__(
            "RESONATOR", "Makes the water ring at one of five notes.", option=note
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        led.work_in += RESONATOR_WORK
        acoustic = RESONATOR_WORK * ETA_RESONATOR
        lost = RESONATOR_WORK - acoustic
        s.note = NOTES[self.option]
        s.note_amp += acoustic
        add_heat(s, lost, led)
        return s, []


# --- shared machinery --------------------------------------------------------


def _bernoulli(s, area_scale, led, amb):
    """Speed for pressure, at constant energy. No work in, no work out.

    A nozzle converts pressure energy into kinetic energy and a diffuser does
    the reverse. Both are conservative here, so neither shows up in the ledger
    at all -- which is the correct answer and also a useful check: if either
    of them ever appears in `residual`, something has been written twice.
    """
    new_area = s.area * area_scale
    ideal_speed = s.speed * (s.area / new_area)
    kinetic_before = s.kinetic
    d_kinetic = 0.5 * s.mass * (ideal_speed * ideal_speed) - kinetic_before

    # A nozzle can only spend the pressure it actually has. Past that the
    # throat cavitates and CHOKES -- it stops delivering speed, because there
    # is nothing left to push with.
    #
    # The first version clamped the pressure and kept the speed, which quietly
    # created 120 kJ out of nothing in the charge. The energy has to come from
    # somewhere and the honest somewhere is: it does not, the flow simply
    # fails to reach the speed the geometry asked for.
    available = (s.pressure - MIN_PRESSURE) * s.volume * PASCALS_PER_BAR
    events = []
    tore = False
    if d_kinetic > available:
        d_kinetic = max(0.0, available)
        tore = True

    d_pressure = -(d_kinetic / max(s.volume, 1e-9)) / PASCALS_PER_BAR
    s.area = new_area
    s.speed = (2.0 * max(0.0, kinetic_before + d_kinetic) / s.mass) ** 0.5
    s.pressure = max(MIN_PRESSURE, s.pressure + d_pressure)

    if tore or s.pressure <= TEAR_PRESSURE:
        # The cavity collapses, and a collapse is broadband and loud. Half the
        # flow's energy goes into the bang -- both terms are things the ledger
        # already counts as held, so this is a conversion and not a source.
        # SUBMERGED 4.1 got here first, from the acoustic side; this is the
        # same effect reached from Bernoulli, and it is the same water tearing.
        bang = s.kinetic * 0.5
        s.note_amp += bang
        s.speed = (2.0 * max(0.0, s.kinetic - bang) / s.mass) ** 0.5
        if s.note <= 0.0:
            s.note = NOTES["chirp"]
        _collapse(s, amb, led)
        events.append("tore")
    events.extend(_gas_events(s))
    return s, events


def _equalise(s, target, led):
    """Bring the slug to a pressure in the same steps it left it by.

    This is stepwise rather than one jump, and the reason is a bug worth
    recording. Compression work scales with absolute temperature, so five
    small expansions and one big recompression are NOT inverses: the charge
    came back at +143 degC and the lamp at +201 degC, because the return leg
    computed its work at a temperature the outbound leg never visited.

    Walking back in the same PRESSURE_RATIO steps makes the two paths
    comparable, and what is left over is exactly the efficiency asymmetry --
    which is the Second Law and is supposed to be there.
    """
    if target <= 0.0:
        return
    guard = 0
    while abs(s.pressure - target) > 1e-9 and guard < 64:
        guard += 1
        if s.pressure < target:
            step = min(target, s.pressure * PRESSURE_RATIO)
            ideal = compression_work(s.mass, s.working, s.temp, s.pressure, step)
            work = max(0.0, ideal) / ETA_COMPRESSOR
            led.work_in += work
            add_heat(s, work, led)
            s.working = max(MIN_WORKING_FRACTION,
                            s.working / WORKING_NUCLEATION)
        else:
            step = max(target, s.pressure / PRESSURE_RATIO)
            ideal = compression_work(s.mass, s.working, s.temp, s.pressure, step)
            released = max(0.0, -ideal) * ETA_TURBINE
            s.temp -= released / (s.mass * C_P_WATER)
            led.heat_to_ocean += released
            s.working = min(MAX_WORKING_FRACTION,
                            s.working * WORKING_NUCLEATION)
        before = s.flow_energy(led.reference_pressure)
        s.pressure = step
        _book_flow(s, before, led)


# How much of a collapsing cavity's energy leaves as sound. A collapse is
# broadband and violent -- it is the pistol shrimp, and SUBMERGED 4.1 already
# uses the same effect as a logic gate -- so a quarter radiated is a
# conservative reading of an event that is mostly noise.
COLLAPSE_RADIATED = 0.25

# How much of the slug's gas the collapse leaves behind as a cloud.
COLLAPSE_SHED = 0.45


def _collapse(s, amb, led):
    """The cavity implodes, and ambient pressure is what drives it.

    No compression heating here, deliberately. Once the water has torn there
    is no working fluid left to compress adiabatically -- the cavity is
    vapour, and its collapse is a mechanical event rather than a thermodynamic
    one. Treating it as a compression was what produced the absurd +143 degC
    charge.

    The energy comes from the ocean, because it is the ocean's own pressure
    doing the collapsing, and a quarter of it leaves as the bang.
    """
    before = s.flow_energy(led.reference_pressure)
    s.pressure = max(s.pressure, amb.pressure)
    gained = s.flow_energy(led.reference_pressure) - before
    if gained <= 0.0:
        return
    bang = gained * COLLAPSE_RADIATED
    s.note_amp += bang

    # A collapse does not tidily re-dissolve. It shatters into a cloud of
    # microbubbles that persists long after the pressure has recovered, which
    # is what a cavitating propeller's wake looks like and why the charge
    # leaves cover behind it.
    #
    # This was missed at first because the collapse restored ambient pressure
    # and the gas went quietly back into solution, so the loudest thing in the
    # vocabulary left no trace in the water at all.
    shed = s.gas * COLLAPSE_SHED
    led.bubbles_shed += s.mass * shed
    s.gas -= shed
    if s.note <= 0.0:
        # A collapse is broadband. The ladder's top rung is the honest stand-in
        # for "everything at once" until the front propagator takes a spectrum.
        s.note = NOTES["chirp"]
    led.heat_from_ocean += gained + bang


def _book_flow(s, before, led):
    """Book the pressure energy a module stored in, or took out of, the slug.

    NARROW and WIDEN deliberately do NOT call this: they move energy between
    two things the ledger already counts as held, so booking it would count it
    twice. SQUEEZE and EXPAND do, because they change the pressure without a
    matching change in speed, and that energy has to come from or go to the
    economy.

    Below ambient the term goes negative, which is how pulling a vacuum ends
    up costing work instead of yielding it -- the bug that let a four-module
    lamp run at negative cost.
    """
    delta = s.flow_energy(led.reference_pressure) - before
    if delta >= 0.0:
        led.work_in += delta
    else:
        led.work_out += -delta


def add_heat(s, q, led):
    """Put q joules of heat into the slug -- melting any ice first.

    The exact inverse of `freeze_clamp`, and it has to exist or the pair is
    not a pair. Without it the cold side was capped at freezing while the warm
    side still charged full price, and the asymmetry produced output that
    swung +78.91, -9.98, +16.56 degC as EXPANDs were added ONE AT A TIME.

    That is precisely the unlearnable non-monotonicity RIGS.md 2.1 condemns:
    a player adding one module cannot be shown a result that lurches. Melting
    before warming makes freeze and thaw cancel exactly, and the sequence goes
    monotone.
    """
    if q <= 0.0:
        s.temp += q / (s.mass * C_P_WATER)
        return
    if led.latent > 0.0:
        melt = min(led.latent, q)
        led.latent -= melt
        q -= melt
    s.temp += q / (s.mass * C_P_WATER)


def freeze_clamp(s, led):
    """Water cannot be cooled below freezing; it turns to ice instead.

    Called by the chain after every module rather than inside the ones that
    cool, so there is exactly one place the floor lives and no module can
    forget it. The energy that would have gone into lowering the temperature
    goes into the phase change, which is where a real refrigerator's cold side
    stops too.
    """
    if s is None or s.temp >= FREEZE_TEMP:
        return
    led.latent += (FREEZE_TEMP - s.temp) * s.mass * C_P_WATER
    s.temp = FREEZE_TEMP


def frozen_fraction(s, led) -> float:
    """How much of the slug has turned to ice. 1.0 means the pipe is blocked."""
    if s is None or s.mass <= 0.0:
        return 0.0
    return led.latent / (s.mass * LATENT_HEAT_FUSION)


def _gas_events(s):
    return ["fizzed"] if s.bubbles > 1e-9 else []


# --- the vocabulary ----------------------------------------------------------

KINDS = {
    "INTAKE": Intake,
    "PORT": Port,
    "SQUEEZE": Squeeze,
    "EXPAND": Expand,
    "NARROW": Narrow,
    "WIDEN": Widen,
    "FILTER": Filter,
    "INJECT": Inject,
    "PUMP": Pump,
    "COIL": Coil,
    "RESONATOR": Resonator,
}

# The order the bench shows them in: four opposed pairs, then three
# singletons. The pairing is load-bearing (RIGS.md 5) -- it teaches two things
# at once and makes "what is the opposite of this" always answerable.
PAIRS = (("INTAKE", "PORT"), ("SQUEEZE", "EXPAND"),
         ("NARROW", "WIDEN"), ("FILTER", "INJECT"))
SINGLETONS = ("PUMP", "COIL", "RESONATOR")
ORDER = tuple(k for pair in PAIRS for k in pair) + SINGLETONS


def make(kind, option=None):
    """Build a module by name. The only way a chain is constructed."""
    kind = kind.upper()
    if kind not in KINDS:
        raise KeyError(f"no such module: {kind}")
    cls = KINDS[kind]
    if option is not None and kind in ("RESONATOR", "FILTER"):
        return cls(option)
    return cls()
