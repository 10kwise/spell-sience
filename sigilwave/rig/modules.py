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

from ..medium.field import GAS_INITIAL_SATURATION
from .slug import Ambient, Ledger, Slug
from .units import (
    ACOUSTIC_COLLAPSE,
    AREA_RATIO,
    BOIL_TEMP,
    C_P_WATER,
    DEFAULT_AREA,
    ETA_COIL,
    ETA_COMPRESSOR,
    ETA_PILE,
    ETA_PUMP,
    ETA_RESONATOR,
    ETA_TURBINE,
    DEGASSED_TENSION,
    K,
    PILE_DRAW,
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
    pipe_loss,
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

        # Expanding frees gas that was in solution, so the working fluid grows
        # -- which is why a chain that expands before it squeezes compresses
        # better than one that does not.
        s.working = min(MAX_WORKING_FRACTION,
                        s.working * WORKING_NUCLEATION)

        # The tear check used to live here. It moved to `cavitate`, called by
        # the chain after every module, the moment sound became a pressure:
        # water can now be torn by a RESONATOR, by a NARROW, or by this, and a
        # check that lives inside one of the three is a check the other two
        # have to remember to copy. Same argument as `freeze_clamp`.
        return s, _gas_events(s)


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
        #
        # `amb.sink` rather than `amb.temp`: a coil is the one part of a rig
        # that can be somewhere else, and `couple.apply` has always let a
        # player run it down a line. In water that is all one temperature the
        # two are identical and this reads exactly as it did before.
        q = (s.temp - amb.sink) * s.mass * C_P_WATER * ETA_COIL
        add_heat(s, -q, led)
        if q >= 0.0:
            led.heat_to_ocean += q
        else:
            led.heat_from_ocean += -q
        return s, _gas_events(s)


class Resonator(Module):
    """The one module that is not half of a pair, and the reason is the point.

    Every other module MOVES one of the five numbers. This one changes what
    the others do to them, which is a different category of thing -- in
    wand-building terms it is a modifier rather than a projectile, and every
    game built on ordered lists has exactly that category.

    The first build did not know that. It wrote `note_amp`, carried it to the
    PORT, and nothing in between ever read it: no ordering involving a
    RESONATOR changed any outcome, so a player looking at it correctly
    concluded it did nothing. It was an output device with a frequency label.

    Now it does three things and all three reach OTHER modules:

    **It tears water.** `Slug.acoustic_pressure` is a real pressure, and the
    cavitation check reads the trough rather than the mean. So a RESONATOR is
    a way to cavitate, NARROW is its amplifier, and five EXPANDs plus one note
    tears water that neither could tear alone.

    **It boils gas out of solution.** An oscillating field pumps gas into
    bubbles over cycles, because a bubble surface is larger during the half of
    the cycle that is pulling. That is rectified diffusion, it is why
    insonated water goes cloudy, and here it means a RESONATOR in front of a
    SQUEEZE hands the compressor more working fluid than it would have had.

    **It decays into heat, at a rate its note chooses.** See `attenuate`.
    """

    def __init__(self, note=DEFAULT_NOTE):
        if note not in NOTES:
            note = DEFAULT_NOTE
        super().__init__(
            "RESONATOR",
            "Makes the water ring -- and a ringing pressure is still a pressure.",
            option=note,
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        led.work_in += RESONATOR_WORK
        acoustic = RESONATOR_WORK * ETA_RESONATOR
        lost = RESONATOR_WORK - acoustic
        # Two resonators do not make a chord. The later note wins and the
        # earlier energy folds into it, which is a simplification and is also
        # an order rule: the note that reaches the water is the last one
        # placed, arriving through however much pipe came after it.
        s.note = NOTES[self.option]
        s.note_amp += acoustic
        add_heat(s, lost, led)
        # Rectified diffusion. The SAME constant EXPAND nucleates with,
        # because it is the same process -- gas coming out of solution because
        # the pressure fell -- and the only difference is that here the
        # pressure fell and came back a thousand times a second.
        s.working = min(MAX_WORKING_FRACTION, s.working * WORKING_NUCLEATION)
        return s, _gas_events(s)


class Turbine(Module):
    """PUMP opposite, and the honest half of the answer to "where is power".

    It GENERATES NOTHING. It takes back the push that is already in the water
    and hands 78% of it to the economy, and since ETA_PUMP * ETA_TURBINE is
    0.55, a pump-turbine loop loses nearly half every time round. That is not
    a balance decision -- it is what two real machines back to back do, and
    the fuzzer checks that no arrangement of them ever comes out ahead.

    What it is actually FOR is that it is the only way to stop. A PORT dumps
    whatever the slug has as a jet, and a jet is a wake and a noise and a
    direction pointing back at you. A TURBINE before the port lands you
    quietly and gives you some of the energy back for having been patient.
    """

    def __init__(self):
        super().__init__(
            "TURBINE", "Takes the push back out of the water, as power."
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []
        # Measured against the ledger OWN datum rather than against ambient,
        # and that is deliberate: `_book_flow` charges pressure energy against
        # `reference_pressure`, so recovering it against the same number makes
        # this the exact inverse of the charge and there is no gap for free
        # energy to live in. With one ambient the two are equal anyway; if a
        # rig ever gets two, this is the one that stays right.
        ref = led.reference_pressure
        flow_before = s.flow_energy(ref)
        kinetic_before = s.kinetic

        available = max(0.0, flow_before) + kinetic_before
        if available <= 0.0:
            return s, []
        recovered = available * ETA_TURBINE

        s.speed = 0.0
        if flow_before > 0.0:
            s.pressure = max(MIN_PRESSURE, min(s.pressure, ref))
        released = (flow_before - s.flow_energy(ref)) + kinetic_before

        led.work_out += recovered
        # The 22% a turbine does not catch does not vanish; it is friction, and
        # friction is heat in the fluid. Same rule as every other efficiency
        # in this file.
        add_heat(s, released - recovered, led)
        return s, ["recovered"]


class Thermopile(Module):
    """COIL opposite, and the actual generator.

    A COIL throws a temperature difference away. This stands in the same heat
    flow and takes a cut of it on the way past, and the size of that cut is
    not a number anybody chose:

        eta <= 1 - Tcold / Thot

    Carnot, in Kelvin, which is why `units.K` exists.

    WHY IT READS THE OCEAN AND NOT THE SLUG
    ---------------------------------------
    The first version took its temperature difference between the SLUG and the
    sink, which is the obvious reading of "a pile sits in the heat flow" and
    is wrong. The fuzzer found it in one run, in four modules:

        INTAKE -> EXPAND -> THERMOPILE -> PORT      +343 kJ from nothing

    EXPAND cools the slug and books the energy as leaving to the water, which
    is correct -- an expanding gas really does deliver that work outward. But
    it means a rig can MANUFACTURE A COLD RESERVOIR at almost no charge, and a
    pile that will run against anything colder than the sink then sells it
    back. Perpetual motion, with books that balance perfectly, which is the
    third time in this project that exact sentence has been true.

    The physics says what the fix is. A reservoir is something whose
    temperature does not change when you take heat out of it. The ocean is
    one. **A 240 kg slug is not**, and the moment it is treated as one, the
    rig can make its own cold end and charge itself for the privilege.

    So the pile is two things stacked, and only one of them generates:

      - a HEAT EXCHANGER, identical to the COIL it is paired with, which
        brings the slug to the sink and generates nothing;
      - an ENGINE across the two temperatures **the ocean is maintaining**,
        whose output is Carnot on those and is capped by the heat one pass of
        the pipe can actually carry between them.

    Three things follow and none were designed:

    **In water that is all one temperature it produces exactly zero.** Not a
    small number -- zero, because the Carnot factor is 1 - T/T. That is
    Kelvin-Planck, it is why no chain can charge by being clever, and it is
    the invariant `selftest_conservation` fuzzes 8000 chains against.

    **Stacking has steep diminishing returns.** The first pile takes 90% of
    the difference and the second gets 10% of what is left, because they are
    heat exchangers and the slug is already there. Nobody wrote a stacking rule.

    **Tapping a vent cools the vent.** `couple.apply` writes `heat_from_ocean`
    back into the medium as cooling, and it always did. So a power station
    depletes what it is standing on, and the depletion needed no depletion rule.
    """

    def __init__(self):
        super().__init__(
            "THERMOPILE",
            "Takes power out of a difference in heat -- and only a difference.",
        )

    def apply(self, s, amb, led):
        if s is None:
            return None, []

        # --- first it is a heat exchanger, and this half generates nothing ---
        q_slug = (s.temp - amb.sink) * s.mass * C_P_WATER * PILE_DRAW
        add_heat(s, -q_slug, led)
        if q_slug >= 0.0:
            led.heat_to_ocean += q_slug
        else:
            led.heat_from_ocean += -q_slug

        # --- then it is an engine, on the gradient the OCEAN maintains -------
        d = amb.sink - amb.temp
        if abs(d) < 1e-9 or q_slug == 0.0:
            return s, []
        hot = K(max(amb.sink, amb.temp))
        cold = K(min(amb.sink, amb.temp))
        if hot <= cold or cold <= 0.0:
            return s, []
        carnot = 1.0 - cold / hot

        # One pass of pipe cannot carry more heat between the two ends than
        # its own mass flow will hold, so that is the ceiling -- and it is the
        # same quantity `Result.carnot_ceiling` reports, which is what makes
        # the check in selftest_conservation a real bound rather than a
        # restatement of this arithmetic.
        #
        # The budget is spent ACROSS THE CHAIN rather than per module, and it
        # has to be: each pile on its own obeys Carnot, so nothing stops five
        # of them from doing five times the work, and a chain that resets the
        # slug between them with FILTER and INJECT reached 185% of what one
        # pass of water can physically ferry. The stream is the bottleneck.
        ceiling = abs(d) * s.mass * C_P_WATER
        q = min(abs(q_slug), max(0.0, ceiling - led.pile_heat))
        w = q * carnot * ETA_PILE
        if w <= 0.0:
            return s, []
        led.pile_heat += q

        led.work_out += w
        led.heat_from_ocean += q
        led.heat_to_ocean += q - w
        return s, ["charged"]


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

    if tore:
        # A CHOKED nozzle, which is this module's own failure and not the
        # general one. The geometry asked for speed the pressure could not pay
        # for, so half of what flow there is goes into the bang instead --
        # both terms are things the ledger already counts as held, so this is
        # a conversion and not a source. SUBMERGED 4.1 got here first from the
        # acoustic side; this is the same water tearing, reached from
        # Bernoulli.
        #
        # The collapse itself is NOT called here. `cavitate` does it, once,
        # for every module -- because since sound became a pressure this is no
        # longer the only way to tear water.
        bang = s.kinetic * 0.5
        s.note_amp += bang
        s.speed = (2.0 * max(0.0, s.kinetic - bang) / s.mass) ** 0.5
        if s.note <= 0.0:
            s.note = NOTES["chirp"]
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
    """The cavity implodes. TWO things drive it and the difference matters.

    No compression heating here, deliberately. Once the water has torn there
    is no working fluid left to compress adiabatically -- the cavity is
    vapour, and its collapse is a mechanical event rather than a thermodynamic
    one. Treating it as a compression was what produced the absurd +143 degC
    charge.

    **Driven by the ocean.** If the slug is below ambient, the ocean's own
    pressure slams the void shut, and a quarter of that leaves as the bang.
    The energy is the ocean's, and the ledger says so.

    **Driven by the note.** If the sound tore it, the sound closes it, and the
    energy is the note's own -- which is why acoustic cavitation is a
    conversion and not a source, and why an over-driven projector goes quiet
    and hot instead of getting louder forever. That self-limiting is real: it
    is the cavitation limit that stops sonar arrays being made louder, and it
    is here for free rather than as a cap.

    Where the note's energy goes is a hot spot in a very small volume, which
    in real water flashes. `the lamp` was named before any of this was written.
    """
    # --- driven by the note --------------------------------------------------
    spent = s.note_amp * ACOUSTIC_COLLAPSE
    if spent > 0.0:
        s.note_amp -= spent
        add_heat(s, spent, led)

    # --- driven by the ocean -------------------------------------------------
    #
    # The inrush that slams the void shut is THE FLOW ITSELF, and the collapse
    # eats it before it asks the ocean for anything. That ordering is not a
    # detail; it is the third free-energy machine this project has had to fix,
    # and the fuzzer found it in six modules:
    #
    #     INTAKE PUMP NARROW NARROW TURBINE PORT        -12.3 kJ
    #
    # A nozzle in a submerged pipe borrows kinetic energy from the local static
    # pressure and gives it back downstream -- you cannot net-extract a jet
    # from ambient water with no pump, because the pressure field is
    # CONSERVATIVE and the loop closes. The old collapse broke that loop: it
    # let the ocean pay to restore a pressure the nozzle had never been charged
    # for lowering, and a turbine downstream then cashed the difference.
    #
    # Taking it out of the flow first closes the loop and says something true
    # at the same time. **A cavitating propeller loses its thrust.** That is
    # thrust breakdown, it is the single most important practical consequence
    # of cavitation in real water, and it means the loudest machine in the
    # game is no longer also the fastest -- which is a better game than the one
    # where the best way to travel happened to be a weapon.
    before = s.flow_energy(led.reference_pressure)
    s.pressure = max(s.pressure, amb.pressure)
    gained = s.flow_energy(led.reference_pressure) - before
    if gained > 0.0:
        take = min(gained, s.kinetic)
        s.speed = (2.0 * max(0.0, s.kinetic - take) / s.mass) ** 0.5
        # Only the part the flow could not supply comes out of the water, and
        # only that part rings.
        short = gained - take
        bang = short * COLLAPSE_RADIATED
        s.note_amp += bang
        led.heat_from_ocean += short + bang

    # --- the cloud, either way -----------------------------------------------
    # A collapse does not tidily re-dissolve. It shatters into a cloud of
    # microbubbles that persists long after the pressure has recovered, which
    # is what a cavitating propeller's wake looks like and why the charge
    # leaves cover behind it.
    #
    # This was missed at first because the collapse restored ambient pressure
    # and the gas went quietly back into solution, so the loudest thing in the
    # vocabulary left no trace in the water at all.
    #
    # It is also what stops an acoustic tear running away. Shedding gas
    # DEGASSES the parcel, and degassed water takes more tension before it
    # lets go (Slug.tear_point) -- so a rig that cavitates itself becomes
    # harder to cavitate. Nobody wrote that; it is Blake's threshold being a
    # property of the nuclei rather than of the water.
    shed = s.gas * COLLAPSE_SHED
    if shed > 0.0:
        led.bubbles_shed += s.mass * shed
        s.gas -= shed
    if s.note <= 0.0:
        # A collapse is broadband. The ladder's top rung is the honest stand-in
        # for "everything at once" until the front propagator takes a spectrum.
        s.note = NOTES["chirp"]


def tear_point(s, amb) -> float:
    """bar. The tension THIS water lets go at. Blake, not a constant.

    A cavity has to start on something. In gassy water it starts on a bubble
    and the threshold is essentially vapour pressure; strip the nuclei out and
    the water holds together well below it -- carefully degassed water sustains
    tens of bar of tension in the laboratory, and this is a conservative
    reading of that.

    The count of nuclei is measured against **what the surrounding water
    holds**, not against what the slug could hold at its own pressure, and
    that distinction is the whole of whether this rule exists at all. Measured
    the second way it never fired once: an expansion collapses the parcel own
    capacity by a factor of hundreds, so every expanded slug reads as wildly
    supersaturated no matter what was filtered out of it beforehand, and
    DEGASSED_TENSION was dead weight in a vocabulary that is not allowed any
    (selftest_density 3).

    Measured the first way it says something true and useful: a FILTER takes
    nuclei out of the water and takes them out for good, so a rig that strips
    its own intake gets harder to cavitate. Six filters is enough to stop a
    chain that would otherwise tear -- at the price of the working fluid the
    compressor needed, because the same module took that too.
    """
    cap = amb.capacity * GAS_INITIAL_SATURATION
    if cap <= 1e-12:
        return TEAR_PRESSURE
    # Normalised against the gas the ocean ACTUALLY delivers rather than
    # against a full saturation nothing in this world reaches. Water as it
    # comes reads exactly 1.0 and tears at TEAR_PRESSURE, which is where every
    # measurement in RIGS.md 9.1 was taken; only water something has taken gas
    # OUT of reads lower. Against full saturation the datum was 0.9 for every
    # parcel in the game, which shifted the threshold 0.16 bar below the
    # pressure floor and quietly made cavitation-by-expansion impossible
    # everywhere -- caught by selftest_density, because IT FREEZES stopped
    # being reachable.
    saturation = min(1.0, s.gas / cap)
    return TEAR_PRESSURE - DEGASSED_TENSION * (1.0 - saturation)


def tearing(s, amb) -> bool:
    """Has the water actually let go. Reads the trough, not the mean."""
    return s.tension <= tear_point(s, amb)


def cavitate(s, amb, led) -> bool:
    """Tear the water if the tension has gone past what it can take. One place.

    Called by the chain after every module for exactly the reason
    `freeze_clamp` is: this is a property of the WATER rather than of any one
    machine, and a module that forgot to check would be a module that could
    quietly not cavitate.

    It had to move out of EXPAND the moment sound became a pressure. There are
    now three ways to tear water -- drop the mean pressure, raise the acoustic
    swing, or narrow the aperture so the swing rises for you -- and the check
    reads `Slug.tension`, which is the only quantity all three move.
    """
    if s is None or not tearing(s, amb):
        return False
    _collapse(s, amb, led)
    return True


def attenuate(s, led):
    """The pipe eats the note, and it eats high notes fastest.

    The only quantity in the rig that DECAYS ALONG THE CHAIN, which is what
    makes distance-from-the-port a thing worth thinking about. A chirp loses
    27% of itself per module and a swell loses 0.3%, so a chirp placed early
    arrives at the port as heat and a swell placed early arrives as sound.

    The frequency law is the ocean's own -- `units.pipe_loss` imports
    field.py's absorption exponent rather than restating it -- so the note
    that carries furthest inside the pipe is the same note that carries
    furthest outside it, and a player only has to learn the rule once.
    """
    if s is None or s.note_amp <= 0.0 or s.note <= 0.0:
        return
    lost = s.note_amp * pipe_loss(s.note)
    if lost <= 0.0:
        return
    s.note_amp -= lost
    add_heat(s, lost, led)


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
    "TURBINE": Turbine,
    "COIL": Coil,
    "THERMOPILE": Thermopile,
    "RESONATOR": Resonator,
}

# The order the bench shows them in: six opposed pairs, then one modifier.
#
# It used to be four pairs and THREE singletons, and that was the shape of a
# real hole rather than a stylistic one. PUMP had no opposite, so there was no
# way to take energy back out of moving water. COIL had no opposite, so there
# was no way to take energy out of a temperature difference -- which meant
# every verb in the vocabulary was a cost and the only decision left to a
# player was how little to run the machine. And RESONATOR was in the list for
# a third reason entirely: it is not half of a pair because it is not the same
# KIND of thing, and calling it a singleton hid that instead of saying it.
#
# The pairing is load-bearing (RIGS.md 5): it teaches two things at once and
# makes "what is the opposite of this" always answerable. One module is
# allowed to have no answer, and it is the one that modifies rather than moves.
PAIRS = (("INTAKE", "PORT"), ("SQUEEZE", "EXPAND"),
         ("NARROW", "WIDEN"), ("FILTER", "INJECT"),
         ("PUMP", "TURBINE"), ("COIL", "THERMOPILE"))
SINGLETONS = ("RESONATOR",)
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
