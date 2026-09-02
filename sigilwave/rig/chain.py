"""A chain of modules, read left to right. RIGS.md 2.2, 7, 8.1.

This is the module that justifies the whole redesign, and it does it by
existing: a chain can be evaluated stage by stage, described in a sentence,
and diffed against another chain. `Assembly.describe` in the old bench gave up
past twelve edges and returned "a tangle" (SUBMERGED 9.6), because a graph has
no reading order and there was nothing else it could honestly say.

Three things live here and nowhere else:

    evaluate()  -- walk the slug down the list, one stage at a time
    describe()  -- say what the machine is, in a sentence with 'then' in it
    fault()     -- which of the four ways to be wrong this one is
"""

from dataclasses import dataclass, field

from . import modules as mod
from .slug import Ambient, Ledger
from .units import (
    BOIL_TEMP,
    ECONOMY_JOULES_PER_UNIT,
    STALL_FLOW,
    ambient_pressure,
    gas_capacity,
)
from ..medium.field import GAS_INITIAL_SATURATION, default_temperature_profile


@dataclass
class Stage:
    """One module's worth of the walk, and the slug as it left.

    The bench draws one of these per module and it is the entire legibility
    claim (RIGS.md 8.2): five properties, five visual channels, and every law
    in the game readable in watching them change.
    """

    index: int
    kind: str
    option: str | None
    line: str
    dead: bool = False
    events: tuple = ()
    # the slug as it LEFT this stage, or None if there was no water
    temp: float | None = None
    pressure: float | None = None
    gas: float | None = None
    speed: float | None = None
    bubbles: float | None = None
    working: float | None = None
    note: float = 0.0


@dataclass
class Fault:
    kind: str
    why: str


@dataclass
class Result:
    stages: list
    ledger: Ledger
    ambient: Ambient
    fault: Fault | None = None
    tore: bool = False
    peak_temp: float = 0.0
    min_pressure: float = 0.0
    flow: float = 1.0
    out_temp: float | None = None
    out_speed: float = 0.0
    out_note: float = 0.0
    out_acoustic: float = 0.0
    out_bubbles: float = 0.0

    @property
    def runs(self) -> bool:
        return self.fault is None

    @property
    def cost(self) -> float:
        """What one pass costs in economy units. RIGS.md 3.3, kept.

        Skill is expressed as one number -- energy per result -- so two chains
        that do the same job are comparable and the better-understood one is
        cheaper. This is that number.
        """
        return self.ledger.net_work / ECONOMY_JOULES_PER_UNIT

    @property
    def delta_temp(self) -> float:
        if self.out_temp is None:
            return 0.0
        return self.out_temp - self.ledger.reference_temp


class Chain:
    """An ordered list of modules. The wand.

    Deliberately a plain list with no graph structure at all. Everything the
    design claims about legibility follows from that one property, so it is
    worth being blunt: if a future module ever needs to branch, it breaks the
    reading order and belongs in the withheld set (RIGS.md 5.4).
    """

    def __init__(self, kinds=()):
        self.modules = []
        for k in kinds:
            if isinstance(k, (tuple, list)):
                self.append(k[0], k[1])
            elif isinstance(k, mod.Module):
                self.modules.append(k)
            else:
                self.append(k)

    # --- editing ------------------------------------------------------------

    def append(self, kind, option=None):
        self.modules.append(mod.make(kind, option))
        return self

    def insert(self, i, kind, option=None):
        self.modules.insert(i, mod.make(kind, option))
        return self

    def remove(self, i):
        if 0 <= i < len(self.modules):
            self.modules.pop(i)
        return self

    def copy(self) -> "Chain":
        c = Chain()
        c.modules = [mod.make(m.kind, m.option) for m in self.modules]
        return c

    def kinds(self) -> list:
        return [m.kind for m in self.modules]

    def __len__(self):
        return len(self.modules)

    def __repr__(self):
        return " -> ".join(repr(m) for m in self.modules)

    # --- the walk -----------------------------------------------------------

    def evaluate(self, ambient: Ambient) -> Result:
        """Walk one slug down the list and account for every joule.

        The ledger is written by the modules themselves; nothing is
        reconstructed here. That is what makes `Ledger.residual` a real check
        rather than a restatement of the same arithmetic.
        """
        led = Ledger()
        led.reference_temp = ambient.temp
        s = None
        stages = []
        opened = False
        ported = False
        tore = False
        peak = ambient.temp
        lowest = ambient.pressure
        pumps = 0

        for i, m in enumerate(self.modules):
            dead = False
            events = ()

            if m.kind == "INTAKE" and opened:
                dead = True
            elif m.kind != "INTAKE" and not opened:
                dead = True
            elif ported:
                dead = True
            else:
                s, ev = m.apply(s, ambient, led)
                events = tuple(ev)
                if m.kind == "INTAKE":
                    opened = True
                elif m.kind == "PORT":
                    ported = True
                elif m.kind == "PUMP":
                    pumps += 1
                if "tore" in events:
                    tore = True

            if s is not None:
                peak = max(peak, s.temp)
                lowest = min(lowest, s.pressure)

            stages.append(Stage(
                index=i, kind=m.kind, option=m.option, line=m.line,
                dead=dead, events=events,
                temp=None if s is None else s.temp,
                pressure=None if s is None else s.pressure,
                gas=None if s is None else s.gas,
                speed=None if s is None else s.speed,
                bubbles=None if s is None else s.bubbles,
                working=None if s is None else s.working,
                note=0.0 if s is None else s.note,
            ))

        flow = 1.0 * (1.6 ** pumps)
        r = Result(stages=stages, ledger=led, ambient=ambient,
                   tore=tore, peak_temp=peak, min_pressure=lowest, flow=flow)

        # What left, read off the last live stage rather than the slug, which
        # a PORT has already consumed.
        if opened and ported:
            r.out_temp = led.reference_temp + (
                led.heat_out / (mod.RIG_MASS_FLOW * 4186.0))
            r.out_speed = (2.0 * led.kinetic_out / mod.RIG_MASS_FLOW) ** 0.5
            r.out_acoustic = led.acoustic_out
            for st in reversed(stages):
                if st.temp is not None:
                    r.out_note = st.note
                    r.out_bubbles = st.bubbles or 0.0
                    break

        r.fault = self._fault(opened, ported, peak, flow, led)
        return r

    def _fault(self, opened, ported, peak, flow, led) -> Fault | None:
        """Which of the four (RIGS.md 7). Order matters: the earliest cause wins."""
        if not opened:
            return Fault(
                "IT DOES NOTHING",
                "There is no INTAKE. The pipe is not open at the front, "
                "so no water ever enters.")
        if not ported:
            return Fault(
                "IT DOES NOTHING",
                "There is no PORT. Only a port touches the ocean, so "
                "everything you did stays inside the housing and dies there.")
        if peak > BOIL_TEMP:
            return Fault(
                "IT BOILS",
                f"Peak internal temperature reached {peak:.0f} C with nowhere "
                f"to send it. Heat is moved, never destroyed -- add a COIL, "
                f"or squeeze less.")
        if flow > STALL_FLOW:
            return Fault(
                "IT STALLS",
                f"You asked for {flow:.1f}x the flow one intake supplies. "
                f"The chain runs dry and stutters.")
        return None

    # --- saying what it is --------------------------------------------------

    _PHRASES = {
        "INTAKE": "takes water in",
        "PORT": "and puts it back",
        "SQUEEZE": "squeezes it",
        "EXPAND": "lets it expand",
        "COIL": "dumps the heat outside",
        "NARROW": "forces it through a nozzle",
        "WIDEN": "spreads it wide",
        "FILTER": "strains it into the tank",
        "INJECT": "puts the tank back in",
        "PUMP": "drives it harder",
        "RESONATOR": "rings it",
    }

    def describe(self) -> str:
        """The machine, in one sentence. RIGS.md 8.1.

        If the game can name your machine, you can name it. The failure case
        is not "a tangle" -- it is a sentence that sounds wrong when you read
        it, which is itself the diagnosis.
        """
        if not self.modules:
            return "An empty bench."
        parts = []
        for m in self.modules:
            phrase = self._PHRASES.get(m.kind, m.kind.lower())
            if m.kind == "RESONATOR":
                phrase = f"rings it at a {m.option}"
            elif m.kind == "FILTER" and m.option and m.option != "gas":
                phrase = f"strains the {m.option} into the tank"
            parts.append(phrase)
        s = ", ".join(parts)
        return s[0].upper() + s[1:] + "."

    def name(self, result: Result) -> str:
        """What this machine IS, read off what it did.

        No recipe table. Every name here is a threshold on a measured output,
        so a chain nobody anticipated still gets named by what it does rather
        than falling through to "unknown".
        """
        if result.fault:
            return {"IT BOILS": "It boils",
                    "IT STALLS": "It stalls"}.get(result.fault.kind, "It does nothing")
        led = result.ledger
        dT = result.delta_temp
        if result.tore:
            return "A charge"
        if led.tank_gas > 1e-4:
            return "A gill"
        if result.out_acoustic > 1e3:
            return "Sonar"
        if result.out_speed > 6.0:
            return "A thruster"
        if dT < -1.5:
            return "A cooler"
        if dT > 1.5:
            return "A heater"
        return "It does nothing"


# --- the water a bench sits in ----------------------------------------------


def ambient_at(depth_m: float, world_height_m: float = 800.0) -> Ambient:
    """The ocean at a depth, using field.py's own profile and Henry's law.

    Kept here rather than in the bench so that every selftest, the bench and
    the real coupling all read the same water. When they disagree the bug is
    invisible, because each one looks correct on its own.
    """
    depth_m = float(depth_m)
    fraction = max(0.0, min(1.0, depth_m / max(world_height_m, 1e-6)))
    temp = default_temperature_profile(fraction)
    pressure = ambient_pressure(depth_m)
    gas = GAS_INITIAL_SATURATION * gas_capacity(pressure, temp)
    return Ambient(temp=temp, pressure=pressure, gas=gas, depth=depth_m)
