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

# Four chains you fire, two you *run*. The second number is the entire
# answer to "the Bench is only a weapon designer": a standing chain is not
# an attack, it is a thing your body does continuously — burning to stay
# warm, hazing to stay hidden, tending itself, or hauling its own weight
# upward — and every one of them costs a socket an attack could have used
# and reserve you have to go and kill something for.
N_ACTIVE = 4
N_STANDING = 2

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
        self.chains = [Chain() for _ in range(N_ACTIVE)]
        self.standing = [Chain() for _ in range(N_STANDING)]
        self.standing_fx = _EMPTY_STANDING.copy()
        self._standing_timer = 0.0
        self.upkeep = C.BASE_UPKEEP
        self.clog = 0.0        # region hazard: fraction of intake lost
        self._sense_dom = None
        self._sense_mag = 0.0
        # Pressure. Set by the region you are in, and it multiplies
        # everything your body costs to run.
        #
        # Without it the game has no escalation at all: a competent player
        # who feeds sits at a full tank forever, in every region, so the
        # scarcity that is supposed to drive the whole loop stops existing
        # about twenty minutes in. Depth is the thing that makes the same
        # body progressively unaffordable, which is what turns "hunt when
        # you feel like it" into "you cannot stay down here for free".
        self.pressure = 1.0
        # Everything that has hurt you lately, and how much. There is
        # exactly one entry point for losing viability (hurt(), below) so
        # this cannot go stale or miss a source — which matters because
        # "I just keep seeing you come apart" is what happens when a game
        # kills you without ever saying what did it.
        self.damage_log = {}
        self.recent_cause = None
        self.recent_cause_t = 0.0
        self.reserve = Charge(6.0, 22.0, 8.0, 4.0)
        self.reserve_cap = C.RESERVE_CAP
        self.viability = C.VIABILITY_MAX
        self.pack = []               # organs you own but have not installed
        # Ambient uptake, per second. It is *deliberately* less than the
        # cost of a body that is actually doing anything: it covers the
        # base rate of existing and nothing beyond it, so every standing
        # chain you run has to be paid for out of something that was alive.
        #
        # This was left at 3.4 while the whole upkeep economy was written
        # around it, which meant ambient water out-earned a working body
        # four to one and none of the scarcity existed. Nothing about the
        # game looked wrong; it was just free.
        self.absorb_rate = C.AMBIENT_ABSORB
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

    def validate(self, chain: Chain, standing=False):
        """Returns (ok, reason). The reasons are written to be read by a
        player mid-surgery, so they name the missing thing rather than the
        rule that was broken.

        A standing chain has no vent, and that is the whole distinction
        between the two kinds: a chain that ends in a vent throws what it
        made at the world, and a chain that does not ends in *you*."""
        organs = self.chain_organs(chain)
        if not organs:
            return False, "nothing routed"
        if len(organs) < 2:
            return False, ("a standing chain needs an intake and at least "
                           "one thing to do with it" if standing else
                           "a chain needs a way in and a way out")
        for a, b in zip(chain.cells, chain.cells[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                return False, "the path breaks between two cells"
        if organs[0].role != INTAKE:
            return False, "it has to start with something that takes in"
        if standing:
            for o in organs[1:]:
                if o.role != TRANSFORM:
                    return False, ("a standing chain cannot have a vent in "
                                   "it — it feeds you, not the water")
            return True, "running"
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

    def peek_reserve(self, amount, purify=False, floor_only=False) -> Charge:
        """What tap_reserve *would* return, without taking it."""
        if floor_only and not self.on_floor:
            amount *= 0.25
        have = self.reserve.magnitude
        if have < 1e-6:
            return Charge()
        take = min(amount, have)
        out = Charge()
        if purify:
            d = self.reserve.dominant
            out.v[d] = min(take, self.reserve[d])
        else:
            f = self.reserve.fractions()
            for i in range(N_HUMOURS):
                out.v[i] = take * f[i]
        return out

    def tap_reserve(self, amount, purify=False, floor_only=False) -> Charge:
        """Withdraw from the tank. Composition of the withdrawal follows the
        composition of the tank, so what you are is what you fire — which is
        why eating things changes your weapons and not just your total."""
        if floor_only and not self.on_floor:
            amount *= 0.25
        if self.clog > 0.0:
            amount *= max(0.15, 1.0 - self.clog)
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
        self.hurt(ctx.viability_cost + eff.recoil * 0.35,
                  "the chain you fired")

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

    # ----------------------------------------------------------- damage

    def hurt(self, amount, cause="something"):
        """The only way viability goes down. Everything else calls this."""
        if amount <= 0.0:
            return 0.0
        self.viability -= amount
        self.damage_log[cause] = self.damage_log.get(cause, 0.0) + amount
        if amount > self.recent_cause_t or self.recent_cause is None:
            self.recent_cause = cause
            self.recent_cause_t = amount
        return amount

    def decay_cause(self, dt):
        self.recent_cause_t = max(0.0, self.recent_cause_t - dt * 6.0)
        if self.recent_cause_t <= 0.0:
            self.recent_cause = None

    def worst_causes(self, n=3):
        return sorted(self.damage_log.items(), key=lambda kv: -kv[1])[:n]

    # --------------------------------------------------------- standing

    def recompute_standing(self):
        """What your standing chains are doing to you, and what they cost.

        Run dry — the chains are measured, not fired — and the result is
        the *sum* of their resolved effects, applied continuously in
        update(). Every channel is read straight off the existing effect
        rules, so a standing chain does exactly what the same chain would
        do to something you shot with it, only to you and slowly.

            heat    you burn. it keeps the cold out and it lights you up.
            murk    you trail sediment. it hides you and it grounds you.
            gentle  you tend yourself. slow, real regeneration.
            brine   you get heavier, or — inverted — you rise.
            jolt    everything about you cycles faster, and hurts more.
            caustic you dissolve what you touch.
        """
        fx = _EMPTY_STANDING.copy()
        cost = 0.0
        best_mag, best_dom = 0.0, None
        for ch in self.standing:
            ok, _ = self.validate(ch, standing=True)
            if not ok:
                continue
            organs = self.chain_organs(ch)
            if any(o.seized for o in organs):
                continue
            ctx = ChainContext(self, None, None, None)
            ctx.dry = True
            ctx.heat_scale = 0.0     # charged separately, below
            charge = organs[0].apply(Charge(), ctx)
            if ctx.aborted or charge.magnitude < 1e-9:
                continue
            # organs[1:], not organs[1:-1]. A standing chain has no vent,
            # so its last organ is a transform that has to run — slicing it
            # off (copied from the active-chain path, where the last organ
            # really is the vent) silently dropped the final stage of every
            # standing chain in the game. The symptom was subtle and
            # miserable: a chain whose last organ was the Harmonic produced
            # no gentleness at all, so the Cisterns had a correct answer
            # that did not work and no way to tell why.
            for o in organs[1:]:
                if o.type is BLADDER:
                    continue
                charge = o.apply(charge, ctx)
                if ctx.aborted:
                    break
            if ctx.aborted:
                continue
            eff = resolve(charge)
            fx["heat"] += eff.heat
            fx["murk"] += eff.murk
            fx["gentle"] += eff.gentle
            fx["jolt"] += eff.jolt
            fx["caustic"] += eff.caustic
            fx["lift"] += eff.lift
            fx["light"] += eff.light
            fx["magnitude"] += charge.magnitude
            fx["divergence"] = max(fx["divergence"], eff.divergence)
            if charge.magnitude > best_mag:
                best_mag = charge.magnitude
                best_dom = charge.dominant
            cost += charge.magnitude * C.STANDING_UPKEEP_PER_MAGNITUDE

        # --- what all of that adds up to, for the body wearing it.
        #
        # Every line below is the same humour doing the same thing it does
        # when you throw it at something, only pointed at yourself.

        # Nerve quickens you; weight slows you. This is the "swim faster"
        # upgrade, and it is not a stat you bought — it is what carrying
        # nerve does.
        fx["speed"] = min(0.55, fx["jolt"] * 0.085) - min(
            0.35, max(0.0, -fx["lift"]) * 0.035)

        # A body that burns and shouts is a body things come to look at.
        # Derived from exactly the two channels that already give you away
        # everywhere else: light, and concentration.
        fx["lure"] = fx["light"] * 0.55 + fx["magnitude"] * fx["divergence"] * 0.5

        # And a body that is caustic and live is one they would rather not
        # touch. Rot and shock, which are already the two things that hurt
        # on contact.
        fx["ward"] = fx["caustic"] * 0.7 + fx["jolt"] * 0.45

        self.standing_fx = fx
        self._sense_dom = best_dom
        self._sense_mag = best_mag
        self.upkeep = (C.BASE_UPKEEP + cost) * self.pressure
        return fx

    def _run_standing(self, dt):
        """Pay for the standing chains and take what they give.

        Upkeep comes out first and comes out whatever happens: a body that
        cannot afford what it is running starves while running it, which is
        the correct and unpleasant answer."""
        fx = self.standing_fx
        if self.upkeep > 0.0:
            self.tap_reserve(self.upkeep * dt)
        if fx["gentle"] > 0.0:
            self.viability += fx["gentle"] * 0.55 * dt
        # Running hot is not free: the organs doing it warm up like any
        # others, which is what stops a permanent furnace from being
        # strictly better than a switchable one.
        if fx["magnitude"] > 0.0:
            for ch in self.standing:
                for cell in ch.cells:
                    o = self.cells.get(cell)
                    if o is not None:
                        o.heat += o.type.heat * 0.22 * dt

    # ------------------------------------------------------------- update

    def update(self, dt, world=None, pos=None):
        self._mods = body_modifiers(self.reserve)

        for ch in self.chains:
            if ch.timer > 0.0:
                ch.timer = max(0.0, ch.timer - dt)

        self._standing_timer -= dt
        if self._standing_timer <= 0.0:
            self._standing_timer = 0.5
            self.recompute_standing()
        self._run_standing(dt)

        self._thermal(dt, world, pos)

        # Strain: holding a spiked composition costs you. Squared, so being
        # a bit specialised is nearly free and being entirely one thing is
        # a slow suicide with excellent damage numbers.
        st = strain(self.reserve) * (self.reserve.magnitude / self.reserve_cap)
        if st > 0.01:
            self.hurt(st * C.IMBALANCE_RATE * dt,
                      "being too much one thing")

        if self.reserve.magnitude < 1.0:
            self.hurt(C.STARVE_RATE * dt, "an empty tank")
        self.decay_cause(dt)

        if world is not None and pos is not None:
            # Ambient uptake covers the base rate and nothing beyond it.
            # Everything else has to come out of something that was alive.
            rate = self.absorb_rate * max(0.15, 1.0 - self.clog)
            got = world.ambient_draw(pos, rate * dt)
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
                self.hurt(2.0 * dt, "your own organs cooking")
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
        return (f[ICHOR] * (self.reserve.magnitude / self.reserve_cap)
                + min(1.0, self.total_heat / (ORGAN_SEIZE * 3.0)) * 0.6
                # A body that is burning to stay warm is a body that can be
                # seen from across a room. There is no way to have the one
                # without the other, and in the Sill you need the one.
                + max(0.0, self.standing_fx["light"]) * 0.10)

    @property
    def sight(self):
        return min(C.MAX_SIGHT, C.BASE_SIGHT + self.glow * 240.0)

    # ---------------------------------------------------------- the senses

    @property
    def sense_mode(self):
        """(key, blurb, strength) for whatever your standing chains have
        turned you into. None if you are running nothing."""
        if self._sense_dom is None or self._sense_mag < 0.8:
            return None
        name, blurb = SENSE_MODES[self._sense_dom]
        return name, blurb, min(1.0, self._sense_mag / 5.0)

    def senses(self):
        """How far you perceive, split by *what*.

        Sight is one number in most games. Here it is three, because the
        four humours disagree about what perception even is: weight feels
        the shape of a room and nothing alive in it, nerve finds living
        things straight through rock, sediment reports only what moves, and
        heat simply lights the place up and tells everyone where you are."""
        base = self.sight
        out = {"geometry": base, "creature": base, "moving_only": False,
               "mode": None}
        mode = self.sense_mode
        if mode is None:
            return out
        key, _blurb, k = mode
        out["mode"] = key
        if key == "pressure":
            out["geometry"] = min(1100.0, base + 240.0 + k * 620.0)
        elif key == "nerve":
            out["creature"] = min(1200.0, base + 260.0 + k * 700.0)
        elif key == "displacement":
            out["creature"] = min(1000.0, base + 200.0 + k * 520.0)
            out["moving_only"] = True
        elif key == "light":
            out["geometry"] = base + k * 180.0
            out["creature"] = base + k * 180.0
        return out

    def to_dict(self):
        return {
            "standing": [c.to_dict() for c in self.standing],
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
        while len(b.chains) < N_ACTIVE:
            b.chains.append(Chain())
        b.standing = [Chain.from_dict(c) for c in d.get("standing", [])]
        while len(b.standing) < N_STANDING:
            b.standing.append(Chain())
        b.reserve = Charge.of(d.get("reserve", [10, 10, 10, 10]))
        b.viability = d.get("viability", C.VIABILITY_MAX)
        b.pack = [make(o["key"]) for o in d.get("pack", [])]
        return b


_EMPTY_STANDING = {"heat": 0.0, "murk": 0.0, "gentle": 0.0, "jolt": 0.0,
                   "caustic": 0.0, "lift": 0.0, "light": 0.0,
                   "magnitude": 0.0, "speed": 0.0, "lure": 0.0, "ward": 0.0,
                   "reach": 0.0, "divergence": 0.0}

# What a standing chain lets you perceive, by which humour it is mostly
# made of. Four chains, four different games, and not one new rule — each
# is the same humour doing the same thing it does everywhere else, pointed
# inward instead of outward.
SENSE_MODES = {
    SPARK: ("nerve", "living things shine through rock. the rock does not."),
    BRINE: ("pressure", "you feel the shape of the room. nothing that lives "
                        "in it."),
    SILT: ("displacement", "what moves is bright. what holds still is not "
                           "there at all."),
    ICHOR: ("light", "you burn, so you can see, so you can be seen."),
}

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
        ((2, 3), "siphon"),
    ]
    for cell, key in layout:
        b.install(cell, make(key))
    b.chains[0] = Chain([(1, 1), (2, 1), (3, 1)], "sting")
    # And one standing chain, wired badly on purpose. It does something
    # mild and faintly useful (a haze you trail), it is visibly costing you
    # upkeep from the first second, and it is the worst use of those two
    # sockets in the game. A player who never opens the Bench survives the
    # Nursery on it and nothing below.
    b.standing[0] = Chain([(2, 3), (2, 2)], "haze")
    b.recompute_standing()
    return b
