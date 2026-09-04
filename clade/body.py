"""The body: a grid you install organs into, and the chains you route
through it.

Two ideas are load-bearing here and they are worth stating before the code,
because both look like arbitrary UI choices and neither is.

**Chains are spatial.** A chain is a path through *adjacent* cells. You do
not pick organs off a list and order them; you lay them out and walk a line
through them. That makes the ordering problem a placement problem, which
means it has geometry, which means it has the one thing an ordering problem
lacks: a reason for two chains to interfere with each other. They share
cells. They compete for room. A body that wants two good chains has to
solve a packing problem, and packing problems are the good kind of hard.

**Heat is local.** An organ that works gets hot, the heat crawls to its
neighbours, and what does not crawl radiates into the water where it
becomes light and noise. So the geometry is thermal as well as logical: put
the Ember Gland next to the Ganglion and the Ganglion seizes; put it on the
rim and the room can see you. There is no correct layout, only the one you
can live with, and it changes every time you find a new organ.

The composition rule is the third thing and it is deliberately cruel:
**your reserve is also your body.** What you are carrying is what you are
made of. Drink a creature made of fire and you become bright and hot and
easily found. There is no separate stat for "what you are"; there is only
the tank, and the tank is you.
"""

import math

from . import config as C
from .effects import body_modifiers, resolve
from .humours import BRINE, ICHOR, N_HUMOURS, SILT, SPARK, Charge, strain
from .organs import (
    BLADDER, INTAKE, TRANSFORM, VENT, ChainContext, Organ, make,
)

GRID_W, GRID_H = 6, 5

# What you wake up able to use. The rest of the body is there, visibly,
# from the first minute — you can see the empty sockets and you can see how
# many there are, which is a promise the game keeps.
STARTING_CELLS = {(1, 1), (2, 1), (3, 1), (1, 2), (2, 2), (3, 2), (2, 3)}


class Emission:
    """One thing leaving the body. The world turns these into projectiles,
    auras or seeds; the body does not know which."""

    __slots__ = ("charge", "effect", "shape", "origin", "heading", "speed",
                 "trail", "delay", "loudness", "source")

    def __init__(self, charge, shape, origin, heading, speed, trail=False,
                 delay=0.0, loudness=0.0, source=None):
        self.charge = charge
        self.effect = resolve(charge)
        self.shape = shape
        self.origin = origin
        self.heading = heading
        self.speed = speed
        self.trail = trail
        self.delay = delay
        self.loudness = loudness
        self.source = source


class Chain:
    """An ordered path of cells. Stored as coordinates rather than organ
    references so that moving an organ re-plumbs the chain automatically —
    which is what makes rearranging feel like surgery rather than
    bookkeeping."""

    __slots__ = ("cells", "name", "cooldown", "timer")

    def __init__(self, cells=None, name=""):
        self.cells = list(cells or [])
        self.name = name
        self.cooldown = 0.0
        self.timer = 0.0

    def to_dict(self):
        return {"cells": [list(c) for c in self.cells], "name": self.name}

    @staticmethod
    def from_dict(d):
        return Chain([tuple(c) for c in d.get("cells", [])], d.get("name", ""))


class Body:
    def __init__(self):
        self.cells = {c: None for c in STARTING_CELLS}
        self.chains = [Chain(), Chain(), Chain(), Chain()]
        self.reserve = Charge(6.0, 22.0, 8.0, 4.0)
        self.reserve_cap = C.RESERVE_CAP
        self.viability = C.VIABILITY_MAX
        self.pack = []               # organs you own but have not installed
        self.absorb_rate = 3.4       # ambient uptake, per second
        self.nerve = len(STARTING_CELLS)
        self._mods = body_modifiers(self.reserve)
        self.last_fire_log = []      # for the Assay
        self.on_floor = False

    # ------------------------------------------------------------- sockets

    def unlocked(self):
        return set(self.cells.keys())

    def unlock(self, cell):
        if cell not in self.cells and 0 <= cell[0] < GRID_W and 0 <= cell[1] < GRID_H:
            self.cells[cell] = None
            self.nerve += 1
            return True
        return False

    def organ_at(self, cell):
        return self.cells.get(cell)

    def install(self, cell, organ: Organ) -> bool:
        if cell not in self.cells or self.cells[cell] is not None:
            return False
        if organ.type.unique and any(
            o is not None and o.key == organ.key for o in self.cells.values()
        ):
            return False
        self.cells[cell] = organ
        if organ in self.pack:
            self.pack.remove(organ)
        return True

    def uninstall(self, cell):
        org = self.cells.get(cell)
        if org is not None:
            self.cells[cell] = None
            self.pack.append(org)
        return org

    def installed(self):
        return [o for o in self.cells.values() if o is not None]

    # -------------------------------------------------------------- chains

    def chain_organs(self, chain: Chain):
        out = []
        for c in chain.cells:
            o = self.cells.get(c)
            if o is None:
                return None
            out.append(o)
        return out

    def validate(self, chain: Chain):
        """Returns (ok, reason). The reasons are written to be read by a
        player mid-surgery, so they name the missing thing rather than the
        rule that was broken."""
        organs = self.chain_organs(chain)
        if not organs:
            return False, "nothing routed"
        if len(organs) < 2:
            return False, "a chain needs a way in and a way out"
        for a, b in zip(chain.cells, chain.cells[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                return False, "the path breaks between two cells"
        if organs[0].role != INTAKE:
            return False, "it has to start with something that takes in"
        if organs[-1].role != VENT:
            return False, "it has to end with something that lets out"
        for o in organs[1:-1]:
            if o.role != TRANSFORM:
                return False, "%s cannot sit in the middle" % o.name
        return True, "ready"

    def chain_ready(self, i):
        ch = self.chains[i]
        ok, _ = self.validate(ch)
        if not ok or ch.timer > 0.0:
            return False
        organs = self.chain_organs(ch)
        return not any(o.seized for o in organs)

    # ------------------------------------------------------------- reserve

    def tap_reserve(self, amount, purify=False, floor_only=False) -> Charge:
        """Withdraw from the tank. Composition of the withdrawal follows the
        composition of the tank, so what you are is what you fire — which is
        why eating things changes your weapons and not just your total."""
        if floor_only and not self.on_floor:
            amount *= 0.25
        have = self.reserve.magnitude
        if have < 1e-6:
            return Charge()
        take = min(amount, have)
        out = Charge()
        if purify:
            # Only the largest humour, and it comes out pure. That both
            # spikes divergence (damage, noise) and *rebalances what is
            # left behind*, which is a second-order effect no organ
            # description mentions and which good players use on purpose.
            d = self.reserve.dominant
            got = min(take, self.reserve[d])
            self.reserve.v[d] -= got
            out.v[d] = got
        else:
            f = self.reserve.fractions()
            for i in range(N_HUMOURS):
                got = take * f[i]
                self.reserve.v[i] = max(0.0, self.reserve.v[i] - got)
                out.v[i] = got
        return out

    def feed(self, charge: Charge, efficiency=1.0):
        """Take humour in. Overflow is discarded rather than wasted-with-a-
        message: a full body simply cannot hold more, and the player finds
        that out by watching the number stop."""
        room = max(0.0, self.reserve_cap - self.reserve.magnitude)
        incoming = charge.magnitude * efficiency
        if incoming <= 1e-9:
            return 0.0
        k = min(1.0, room / incoming) * efficiency
        for i in range(N_HUMOURS):
            self.reserve.v[i] += max(0.0, charge[i]) * k
        return incoming * min(1.0, room / max(1e-9, incoming))

    def tap_nearby_flesh(self, world, pos, radius_cells):
        if world is None or pos is None:
            return None
        # exclude=player: a Leech that can reach its own owner is a body
        # that eats itself for free, forever.
        return world.drain_nearest_flesh(
            pos, radius_cells * C.FIELD_CELL,
            exclude=getattr(world, "player", None))

    # ------------------------------------------------------------- firing

    def fire(self, index, world, pos, aim, dt_scale=1.0):
        """Run a chain and hand back its emissions. Returns [] for any
        reason a chain cannot fire; the caller does not need to know which,
        because the body screen already told the player."""
        ch = self.chains[index]
        ok, _ = self.validate(ch)
        if not ok or ch.timer > 0.0:
            return []
        organs = self.chain_organs(ch)
        if any(o.seized for o in organs):
            return []

        ctx = ChainContext(self, world, pos, aim)
        intake, vent = organs[0], organs[-1]
        middle = organs[1:-1]

        charge = intake.apply(Charge(), ctx)
        if ctx.aborted or charge.magnitude < 1e-6:
            return []

        charge = self._run_middle(charge, middle, ctx)
        if ctx.aborted:
            self._settle(organs, ctx, fired=False)
            return []

        # Re-entry: a Knot upstream runs the whole middle again on its own
        # output. Everything that was true the first time is true again,
        # including the heat, which is the entire risk.
        passes = ctx.recursions
        for _ in range(passes):
            ctx.heat_scale = 1.35        # re-entry costs more than it earns
            charge = self._run_middle(charge, middle, ctx, reentry=True)
            ctx.heat_scale = 1.0
            if ctx.aborted:
                self._settle(organs, ctx, fired=False)
                return []

        vent.heat += vent.type.heat * (1.0 + charge.magnitude * 0.5
                                       * Organ.WORK_HEAT)
        shape = vent.type.vent

        eff = resolve(charge)
        self.viability -= ctx.viability_cost + eff.recoil * 0.35

        count = max(1, shape.count * ctx.count)
        spread = shape.spread + ctx.spread
        per = charge.scaled(1.0 / count) if count > 1 else charge

        emissions = []
        base = aim
        for n in range(count):
            if count > 1:
                t = (n / (count - 1.0)) - 0.5
                ang = t * spread
            else:
                ang = 0.0
            emissions.append(Emission(
                per.copy(), shape, pos, _rotate(base, ang),
                shape.speed * ctx.speed, ctx.trail, ctx.delay,
                eff.loudness * ctx.quiet, self,
            ))

        self._settle(organs, ctx, fired=True)
        self.last_fire_log = list(ctx.log)
        ch.cooldown = 0.42 * (1.0 + 0.10 * len(organs))
        ch.timer = ch.cooldown * self._mods["cycle"]
        return emissions

    def _run_middle(self, charge, middle, ctx, reentry=False):
        for o in middle:
            if o.seized:
                continue
            if o.type is BLADDER:
                charge = self._bladder(o, charge, ctx)
                if ctx.aborted:
                    return charge
                continue
            charge = o.apply(charge, ctx)
            if ctx.aborted:
                return charge
        return charge

    @staticmethod
    def _bladder(organ, charge, ctx):
        """Accumulate until it is worth releasing. The threshold is a real
        number the player can find at the Assay in about four shots, and
        finding it turns the Bladder from junk into the front half of every
        burst build in the game."""
        if organ.stored is None:
            organ.stored = Charge()
        organ.stored.add(charge)
        organ.heat += organ.type.heat
        if organ.stored.magnitude < 22.0:
            ctx.aborted = True
            return charge
        out = organ.stored
        organ.stored = Charge()
        return out

    def _settle(self, organs, ctx, fired):
        for o in organs:
            if fired:
                o.integrity = max(0.0, o.integrity - 0.00035)

    # ------------------------------------------------------------- update

    def update(self, dt, world=None, pos=None):
        self._mods = body_modifiers(self.reserve)

        for ch in self.chains:
            if ch.timer > 0.0:
                ch.timer = max(0.0, ch.timer - dt)

        self._thermal(dt, world, pos)

        # Strain: holding a spiked composition costs you. Squared, so being
        # a bit specialised is nearly free and being entirely one thing is
        # a slow suicide with excellent damage numbers.
        st = strain(self.reserve) * (self.reserve.magnitude / self.reserve_cap)
        self.viability -= st * C.IMBALANCE_RATE * dt

        if self.reserve.magnitude < 1.0:
            self.viability -= C.STARVE_RATE * dt

        if world is not None and pos is not None:
            got = world.ambient_draw(pos, self.absorb_rate * dt)
            if got is not None:
                self.feed(got)

        self.viability = min(C.VIABILITY_MAX, self.viability)

    def _thermal(self, dt, world, pos):
        """Conduction between grid neighbours, then radiation into the
        water. Written as an explicit two-phase pass (gather, then apply)
        because doing it in one pass makes the result depend on dictionary
        iteration order, and a body that behaves differently depending on
        the order you installed things in is a bug nobody will ever
        report clearly."""
        cells = self.cells
        deltas = {}
        for cell, org in cells.items():
            if org is None:
                continue
            cx, cy = cell
            for nb in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                other = cells.get(nb)
                if other is None:
                    continue
                diff = org.heat - other.heat
                if diff <= 0.0:
                    continue
                move = diff * C.ORGAN_CONDUCT * dt * 0.5
                deltas[cell] = deltas.get(cell, 0.0) - move
                deltas[nb] = deltas.get(nb, 0.0) + move

        shed = 0.0
        for cell, org in cells.items():
            if org is None:
                continue
            org.heat += deltas.get(cell, 0.0)
            rad = org.heat * C.ORGAN_RADIATE * dt
            org.heat -= rad
            shed += rad
            if org.heat > ORGAN_SEIZE:
                org.seized = True
            elif org.seized and org.heat < ORGAN_COOL:
                org.seized = False
            if org.heat > ORGAN_SEIZE * 1.25:
                # Cooking. The organ is being destroyed, slowly and
                # visibly, and the player has plenty of time to stop.
                org.integrity = max(0.0, org.integrity - 0.09 * dt)
                self.viability -= 2.0 * dt
            org.heat = max(0.0, org.heat)

        if world is not None and pos is not None and shed > 0.0:
            world.shed_body_heat(pos, shed)

    # -------------------------------------------------------------- stats

    @property
    def mods(self):
        return self._mods

    @property
    def total_heat(self):
        return sum(o.heat for o in self.installed())

    @property
    def glow(self):
        """How brightly you burn. Ichor in the tank plus waste heat from
        the organs. This is the number that decides whether you are a thing
        in the dark or a lamp with legs."""
        f = self.reserve.fractions()
        return f[ICHOR] * (self.reserve.magnitude / self.reserve_cap) + \
            min(1.0, self.total_heat / (ORGAN_SEIZE * 3.0)) * 0.6

    @property
    def sight(self):
        return min(C.MAX_SIGHT, C.BASE_SIGHT + self.glow * 240.0)

    def to_dict(self):
        return {
            "cells": [
                {"c": list(k), "organ": (v.to_dict() if v else None)}
                for k, v in self.cells.items()
            ],
            "chains": [c.to_dict() for c in self.chains],
            "reserve": list(self.reserve),
            "viability": self.viability,
            "pack": [o.to_dict() for o in self.pack],
        }

    @staticmethod
    def from_dict(d):
        b = Body()
        b.cells = {}
        for entry in d.get("cells", []):
            cell = tuple(entry["c"])
            od = entry.get("organ")
            org = None
            if od:
                org = make(od["key"])
                org.integrity = od.get("integrity", 1.0)
                org.uses = od.get("uses", 0)
            b.cells[cell] = org
        b.nerve = len(b.cells)
        b.chains = [Chain.from_dict(c) for c in d.get("chains", [])] or b.chains
        while len(b.chains) < 4:
            b.chains.append(Chain())
        b.reserve = Charge.of(d.get("reserve", [10, 10, 10, 10]))
        b.viability = d.get("viability", C.VIABILITY_MAX)
        b.pack = [make(o["key"]) for o in d.get("pack", [])]
        return b


ORGAN_SEIZE = C.ORGAN_SEIZE_AT
ORGAN_COOL = C.ORGAN_COOL_AT


def _rotate(vec, degrees):
    if abs(degrees) < 1e-9:
        return (vec[0], vec[1])
    r = math.radians(degrees)
    ca, sa = math.cos(r), math.sin(r)
    return (vec[0] * ca - vec[1] * sa, vec[0] * sa + vec[1] * ca)


def starting_body() -> Body:
    """A working, boring animal. Every organ in it is tier 0 and the chain
    it comes wired with is the most obvious possible arrangement, so that
    the first improvement a player makes is one they thought of."""
    b = Body()
    layout = [
        ((1, 1), "siphon"),
        ((2, 1), "kiln"),
        ((3, 1), "spiracle"),
        ((1, 2), "salt_node"),
        ((2, 2), "settling_sac"),
    ]
    for cell, key in layout:
        b.install(cell, make(key))
    b.chains[0] = Chain([(1, 1), (2, 1), (3, 1)], "sting")
    return b
