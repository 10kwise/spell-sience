"""Everything else that is alive down here.

The rule this file exists to enforce: **creatures are built the way you are
built.** Every one of them has organs, in an order, and fires them through
the same chain executor, resolved by the same effect rules. Nothing has a
hand-written attack.

That is not tidiness. It is the game's only teaching mechanism that scales.
A thing hits you with a bright hot lance; the lance was bright and hot for
exactly one reason, which is that the creature has an Ember Gland in it;
and when you kill it, you get the Ember Gland. The player who notices what
an attack *looked like* can predict what the corpse contains, and a player
who has been paying attention arrives at the deep regions with a body
assembled out of inferences instead of drops.

It also means the bestiary cannot lie. If a Recursor appears to feed on
your attacks, it is because it genuinely has a Knot in it and the damage
rules genuinely turn concentration into food. There is no separate
"absorbs" flag doing the work behind the curtain.

Perception is the other half. Creatures do not have a sight cone onto your
position — they have three senses, and all three are things you control:

    light        your glow, attenuated by silt.
    noise        what your chains have been doing, decayed over time.
    contact      proximity, which no amount of cleverness hides.

Which is why a player who has understood the Muffle can walk past the thing
that killed them nine times.
"""

import math
import random

from . import config as C
from .effects import resolve
from .humours import BRINE, ICHOR, N_HUMOURS, SILT, SPARK, Charge
from .organs import ChainContext, INTAKE, TRANSFORM, VENT, make

IDLE, ALERT, HUNT, STRIKE, FLEE, DEAD = range(6)

STATE_NAMES = ("idle", "alert", "hunting", "striking", "fleeing", "dead")


class CreatureBody:
    """A creature's metabolism: enough of the Body interface for the shared
    chain executor to run against, and nothing more. Creatures do not have
    a grid because they do not rearrange themselves — which is, when you
    think about it, the only real difference between you and them."""

    def __init__(self, reserve: Charge, organ_keys, owner=None):
        self.owner = owner
        self.reserve = reserve
        self.reserve_cap = max(20.0, reserve.magnitude * 1.6)
        self.on_floor = True
        self.organs = [make(k) for k in organ_keys]

    def tap_reserve(self, amount, purify=False, floor_only=False):
        have = self.reserve.magnitude
        if have < 1e-6:
            return Charge()
        take = min(amount, have)
        out = Charge()
        if purify:
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

    def tap_nearby_flesh(self, world, pos, radius):
        if world is None:
            return None
        return world.drain_nearest_flesh(pos, radius, exclude=self.owner)

    def regenerate(self, dt, ambient: Charge, rate):
        m = ambient.magnitude
        if m < 1e-6:
            return
        add = ambient.scaled(rate * dt / m)
        room = max(0.0, self.reserve_cap - self.reserve.magnitude)
        if room <= 0:
            return
        k = min(1.0, room / max(1e-9, add.magnitude))
        for i in range(N_HUMOURS):
            self.reserve.v[i] += add[i] * k


class Species:
    __slots__ = (
        "key", "name", "viability", "radius", "speed", "armour", "resist",
        "organs", "chain", "senses", "behaviour", "drops", "tier",
        "glow", "aggression", "codex", "harvest_note", "peaceful",
    )

    def __init__(self, key, name, viability, radius, speed, organs, chain,
                 behaviour="stalk", resist=None, armour=0.0, senses=1.0,
                 drops=None, tier=0, glow=0.0, aggression=1.0, codex="",
                 harvest_note="", peaceful=False):
        self.key = key
        self.name = name
        self.viability = viability
        self.radius = radius
        self.speed = speed
        self.armour = armour
        self.resist = resist or [0.0, 0.0, 0.0, 0.0]
        self.organs = organs
        self.chain = chain          # indices into organs, in firing order
        self.senses = senses
        self.behaviour = behaviour
        self.drops = drops if drops is not None else organs
        self.tier = tier
        self.glow = glow
        self.aggression = aggression
        self.codex = codex
        self.harvest_note = harvest_note
        self.peaceful = peaceful


class Creature:
    def __init__(self, species: Species, pos, rng=None):
        self.sp = species
        self.pos = [float(pos[0]), float(pos[1])]
        self.vel = [0.0, 0.0]
        self.rng = rng or random.Random()
        self.viability = species.viability
        self.max_viability = species.viability
        self.state = IDLE
        self.state_time = 0.0
        self.cooldown = self.rng.uniform(0.4, 1.6)
        self.target_memory = None      # last believed player position
        self.memory_age = 99.0
        self.alarm = 0.0               # 0..1 confidence that you are here
        self.facing = [1.0, 0.0]
        self.wander = [self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)]
        self.wander_time = 0.0
        self.stagger = 0.0
        self.body = CreatureBody(
            Charge.of(_reserve_for(species)), species.organs, owner=self
        )
        self.hurt_flash = 0.0
        self.fed_flash = 0.0
        self.dead = False
        self.tag = None                # narrative hook (the Attendant uses it)

    # ---------------------------------------------------------- perception

    def sense(self, world, player, dt):
        """One number: how sure this thing is that you are here. It rises
        from light, noise and nearness, and it falls in the dark and the
        quiet. Everything about the creature's behaviour reads off it, so
        stealth is not a separate system with its own rules — it is the
        same number, lower."""
        px, py = player.pos
        dx, dy = px - self.pos[0], py - self.pos[1]
        dist = math.hypot(dx, dy) + 1e-6

        vis = world.room.fields.visibility_along(self.pos, (px, py))
        # Light you emit, falling off with distance and eaten by silt.
        light = player.body.glow * 520.0 / dist * vis
        # Noise is room-wide but attenuates: a scream two rooms of water
        # away is a rumour, not a fix.
        noise = world.disturbance * 0.9 * (240.0 / (dist * 0.55 + 240.0))
        # Contact: nothing hides a body pressed against you.
        contact = 320.0 / dist if dist < 130.0 else 0.0

        signal = (light + noise + contact) * self.sp.senses
        target = max(0.0, min(1.0, signal / 26.0))

        # Asymmetric: suspicion arrives faster than it leaves. That gap is
        # where the whole stealth game lives — you can be noticed in a
        # second and spend twenty earning the dark back.
        rate = 3.2 if target > self.alarm else 0.55
        self.alarm += (target - self.alarm) * min(1.0, rate * dt)

        if self.alarm > 0.45:
            self.target_memory = (px, py)
            self.memory_age = 0.0
        else:
            self.memory_age += dt
        return self.alarm

    # ------------------------------------------------------------- update

    def update(self, dt, world, player, out_emissions):
        if self.dead:
            return
        self.state_time += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 3.0)
        self.fed_flash = max(0.0, self.fed_flash - dt * 2.0)
        self.stagger = max(0.0, self.stagger - dt)

        amb = world.room.fields.ambient(self.pos)
        self.body.regenerate(dt, amb, 2.2)

        alarm = self.sense(world, player, dt)
        BEHAVIOURS.get(self.sp.behaviour, _b_stalk)(
            self, dt, world, player, out_emissions, alarm
        )

        if self.stagger <= 0.0:
            self._integrate(dt, world)
        self._suffer_world(dt, world)

    def _integrate(self, dt, world):
        cur = world.room.fields.current_at(self.pos)
        self.vel[0] += cur[0] * 0.5 * dt
        self.vel[1] += cur[1] * 0.5 * dt
        drag = math.pow(0.0016, dt)
        self.vel[0] *= drag
        self.vel[1] *= drag
        nx = self.pos[0] + self.vel[0] * dt
        ny = self.pos[1] + self.vel[1] * dt
        room = world.room
        if not room.solid_at(nx, self.pos[1]):
            self.pos[0] = nx
        else:
            self.vel[0] *= -0.35
        if not room.solid_at(self.pos[0], ny):
            self.pos[1] = ny
        else:
            self.vel[1] *= -0.35
        sp = math.hypot(*self.vel)
        if sp > 1e-3:
            self.facing = [self.vel[0] / sp, self.vel[1] / sp]

    def _suffer_world(self, dt, world):
        f = world.room.fields
        h = f.heat_at(self.pos)
        from .world.fields import BURN_AT, FREEZE_AT
        if h > BURN_AT:
            self.hurt(( h - BURN_AT) * 7.0 * dt, world, silent=True)
        elif h < FREEZE_AT * 0.6:
            self.vel[0] *= 0.90
            self.vel[1] *= 0.90
        ch = f.charge_at(self.pos)
        if ch > 0.35:
            self.hurt(ch * 5.0 * dt, world, silent=True)

    # -------------------------------------------------------------- combat

    def take(self, effect, world, from_pos=None):
        """Absorb an incoming effect. Resistance is per humour, so 'what is
        this thing weak to' is a question with a four-part answer the player
        can actually reason about rather than guess."""
        f = effect.charge.fractions()
        passthru = 1.0
        for i in range(N_HUMOURS):
            passthru -= f[i] * self.sp.resist[i]
        passthru = max(0.05, passthru)

        dmg = effect.damage * passthru * max(0.15, 1.0 - self.sp.armour)

        # Feeding. A creature with a Knot in it turns concentration into
        # food — the *more* focused your attack, the more it gains. There
        # is no flag for this: it reads its own organ list.
        if any(o.key == "knot" for o in self.body.organs):
            if effect.divergence > 0.55:
                self.viability = min(self.max_viability,
                                     self.viability + dmg * 0.55)
                self.body.reserve.add(effect.charge.scaled(0.5))
                self.fed_flash = 1.0
                world.note_feed(self)
                return 0.0

        if effect.gentle > 0.5:
            # Gentleness does not hurt anything. On most creatures that is
            # a waste; on a few it is the only thing that works.
            if self.sp.behaviour in ("recursor", "attendant"):
                self.viability -= effect.gentle * 2.4
                self.hurt_flash = 1.0
            return 0.0

        self.viability -= dmg
        if dmg > 0.4:
            self.hurt_flash = 1.0
        if abs(effect.force) > 40.0 and from_pos is not None:
            dx = self.pos[0] - from_pos[0]
            dy = self.pos[1] - from_pos[1]
            d = math.hypot(dx, dy) + 1e-6
            k = effect.force / max(24.0, self.max_viability * 0.5)
            self.vel[0] += dx / d * k
            self.vel[1] += dy / d * k
            self.stagger = max(self.stagger, min(0.5, abs(k) / 260.0))
        if self.viability <= 0:
            self.die(world)
        else:
            # Being hurt is being found.
            self.alarm = 1.0
            if from_pos is not None:
                self.target_memory = tuple(from_pos)
                self.memory_age = 0.0
        return dmg

    def hurt(self, amount, world, silent=False):
        self.viability -= amount
        if not silent:
            self.hurt_flash = 1.0
        if self.viability <= 0:
            self.die(world)

    def die(self, world):
        if self.dead:
            return
        self.dead = True
        self.state = DEAD
        world.on_death(self)

    # --------------------------------------------------------------- fire

    def fire(self, world, aim, out):
        organs = self.body.organs
        order = self.sp.chain
        if not order:
            return
        seq = [organs[i] for i in order]
        if seq[0].role != INTAKE or seq[-1].role != VENT:
            return
        ctx = ChainContext(self.body, world, tuple(self.pos), aim)
        charge = seq[0].apply(Charge(), ctx)
        if ctx.aborted or charge.magnitude < 1e-6:
            return
        for o in seq[1:-1]:
            charge = o.apply(charge, ctx)
            if ctx.aborted:
                return
        vent = seq[-1]
        shape = vent.type.vent
        eff = resolve(charge)
        count = max(1, shape.count * ctx.count)
        spread = shape.spread + ctx.spread
        per = charge.scaled(1.0 / count) if count > 1 else charge
        from .body import Emission, _rotate
        for n in range(count):
            ang = ((n / (count - 1.0)) - 0.5) * spread if count > 1 else 0.0
            out.append(Emission(per.copy(), shape, tuple(self.pos),
                                _rotate(aim, ang), shape.speed * ctx.speed,
                                ctx.trail, ctx.delay, eff.loudness * ctx.quiet,
                                self))
        world.add_disturbance(eff.loudness * ctx.quiet * 0.5, self.pos)

    # -------------------------------------------------------------- helpers

    def aim_at(self, pos):
        dx, dy = pos[0] - self.pos[0], pos[1] - self.pos[1]
        d = math.hypot(dx, dy) + 1e-6
        return (dx / d, dy / d)

    def swim(self, direction, dt, mult=1.0):
        s = self.sp.speed * mult
        self.vel[0] += direction[0] * s * 6.0 * dt
        self.vel[1] += direction[1] * s * 6.0 * dt

    def distance_to(self, pos):
        return math.hypot(pos[0] - self.pos[0], pos[1] - self.pos[1])

    @property
    def composition(self):
        return self.body.reserve


def _reserve_for(sp: Species):
    """A creature is made of what it eats, so its reserve is derived from
    its own organs rather than authored — a thing full of Ember Glands is
    full of ichor, and drinking it will make you full of ichor too."""
    c = Charge(2.0, 2.0, 2.0, 2.0)
    for k in sp.organs:
        if k in ("ember_gland", "kiln"):
            c.v[ICHOR] += 6.0
        elif k in ("salt_node", "condenser", "brackish"):
            c.v[BRINE] += 6.0
        elif k in ("bloom", "settling_sac", "root"):
            c.v[SILT] += 6.0
        elif k in ("spine", "ganglion"):
            c.v[SPARK] += 6.0
        else:
            c.v[c.dominant] += 1.0
    # Note this sets what a corpse is *worth*, not what the creature hits
    # for: intakes draw a fixed amount, so a creature's attack is decided
    # by its chain and not by how full it is. The knob for incoming damage
    # is config.HOSTILE_DAMAGE.
    return list(c.scaled(0.4 + sp.tier * 0.35))


# ===========================================================================
# BEHAVIOURS
#
# Each is a lesson wearing a hitbox. Written as plain functions rather than
# subclasses so that a species is entirely describable as data and a new one
# costs a table row.
# ===========================================================================

def _wander(cr, dt, speed=0.35):
    cr.wander_time -= dt
    if cr.wander_time <= 0.0:
        cr.wander_time = cr.rng.uniform(1.2, 3.4)
        a = cr.rng.uniform(0, math.tau)
        cr.wander = [math.cos(a), math.sin(a)]
    cr.swim(cr.wander, dt, speed)


def _b_drift(cr, dt, world, player, out, alarm):
    """The Coelenter. It does not care. It has never cared. Killing it is
    free and the codex will remember that you did."""
    cr.state = IDLE
    _wander(cr, dt, 0.22)


def _b_attendant(cr, dt, world, player, out, alarm):
    """It follows. It keeps its distance. It has never once attacked you.

    This is the most important creature in the game and it has eleven lines
    of code. It is the ending, rehearsed, in the first hour, silently — and
    the reason it works is that the game never says a word about it, gives a
    genuinely excellent organ for killing it, and does not react when you
    do."""
    cr.state = IDLE
    d = cr.distance_to(player.pos)
    if d > 260.0:
        cr.swim(cr.aim_at(player.pos), dt, 0.75)
    elif d < 130.0:
        cr.swim([-x for x in cr.aim_at(player.pos)], dt, 0.5)
    else:
        _wander(cr, dt, 0.15)
    # It tidies. Silt settles where it has been.
    world.room.fields.add_silt(cr.pos, 40.0, -0.55 * dt)


def _b_swarm(cr, dt, world, player, out, alarm):
    """Gullet-fry. Individually trivial, collectively a drain. They take
    your reserve rather than your viability, which is worse: they do not
    kill you, they make you unable to do anything about what does."""
    if alarm < 0.25:
        cr.state = IDLE
        _wander(cr, dt, 0.4)
        return
    cr.state = HUNT
    d = cr.distance_to(player.pos)
    cr.swim(cr.aim_at(player.pos), dt, 1.15)
    if d < 34.0 and cr.cooldown <= 0.0:
        cr.cooldown = 0.85
        stolen = player.body.tap_reserve(4.5)
        cr.body.reserve.add(stolen)
        player.body.viability -= 1.6
        player.shake = max(player.shake, 3.0)
        cr.fed_flash = 1.0


def _b_sounder(cr, dt, world, player, out, alarm):
    """It does not fight. It tells. A Sounder that sees you converts your
    careful hour into a room full of things that know where you are, and
    the only counterplay is to have killed it before it noticed — quietly,
    which means weakly, which means early."""
    cr.state = ALERT if alarm > 0.3 else IDLE
    _wander(cr, dt, 0.08)
    if alarm > 0.62 and cr.cooldown <= 0.0:
        cr.cooldown = 3.0
        cr.state = STRIKE
        world.add_disturbance(34.0, cr.pos)
        world.alert_all(cr.pos)
        world.flash_event("something has told the room about you", cr.pos)


def _b_stalk(cr, dt, world, player, out, alarm):
    """The default predator: close, strike, back off, close again."""
    if alarm < 0.22 and cr.memory_age > 5.0:
        cr.state = IDLE
        _wander(cr, dt, 0.3)
        return
    goal = cr.target_memory or player.pos
    d = cr.distance_to(goal)
    if alarm > 0.5:
        cr.state = HUNT
    else:
        cr.state = ALERT

    if d > 210.0:
        cr.swim(cr.aim_at(goal), dt, 1.0)
    elif d < 90.0:
        cr.swim([-x for x in cr.aim_at(goal)], dt, 0.55)
    else:
        perp = cr.aim_at(goal)
        cr.swim([-perp[1], perp[0]], dt, 0.5)

    if alarm > 0.55 and d < 340.0 and cr.cooldown <= 0.0:
        cr.cooldown = cr.rng.uniform(1.5, 2.6) / max(0.4, cr.sp.aggression)
        cr.state = STRIKE
        cr.fire(world, cr.aim_at(goal), out)


def _b_ossuary(cr, dt, world, player, out, alarm):
    """Armoured, slow, and vulnerable only when it is venting heat — which
    it does for two seconds after every attack, visibly, in a colour you
    have been trained to read since the first room."""
    _b_stalk(cr, dt, world, player, out, alarm)
    if cr.state == STRIKE:
        cr.tag = "venting"
    if cr.cooldown < 0.6:
        cr.tag = None
    world.room.fields.add_heat(cr.pos, 46.0, 1.1 * dt)


def _b_recursor(cr, dt, world, player, out, alarm):
    """It has a Knot. Every focused thing you throw at it becomes part of
    it. It is not immune and it is not a puzzle boss — it simply runs the
    same rules you do, and the rules say concentration is food.

    Two answers, and the game states neither: starve it (it dies on its own
    if it cannot feed, and it feeds on *your* attacks), or hand it something
    with no concentration in it at all."""
    _b_stalk(cr, dt, world, player, out, alarm)
    cr.viability -= 1.15 * dt          # it burns itself constantly
    if cr.viability <= 0:
        cr.die(world)


def _b_ambush(cr, dt, world, player, out, alarm):
    """The Silt Mother. She carries her own dark with her, which means the
    thing that hides her also hides where she is not — you find her by the
    shape of the hole she makes."""
    world.room.fields.add_silt(cr.pos, 120.0, 2.4 * dt)
    if alarm < 0.4:
        cr.state = IDLE
        _wander(cr, dt, 0.12)
        return
    cr.state = HUNT
    d = cr.distance_to(player.pos)
    cr.swim(cr.aim_at(player.pos), dt, 1.35 if d > 150 else 0.6)
    if d < 260.0 and cr.cooldown <= 0.0:
        cr.cooldown = 2.1
        cr.state = STRIKE
        cr.fire(world, cr.aim_at(player.pos), out)


def _b_carrion(cr, dt, world, player, out, alarm):
    """It eats the dead. Including the ones you were saving.

    This is the pressure that stops harvesting from being a leisurely
    post-combat chore: a corpse is a clock, and the thing that comes to eat
    it is also a thing you now have to deal with while you are empty."""
    corpse = world.nearest_corpse(cr.pos, 900.0)
    if corpse is not None:
        d = math.hypot(corpse.pos[0] - cr.pos[0], corpse.pos[1] - cr.pos[1])
        cr.state = HUNT
        if d > 30.0:
            cr.swim(cr.aim_at(corpse.pos), dt, 1.1)
        else:
            taken = corpse.drain(9.0 * dt)
            cr.body.reserve.add(taken)
            cr.fed_flash = 1.0
        return
    _b_stalk(cr, dt, world, player, out, alarm)


def _b_apex(cr, dt, world, player, out, alarm):
    """The thing you do not fight.

    It wakes on disturbance and sleeps on quiet, it is faster than you, and
    its viability is high enough that killing it is a project rather than a
    fight. It is not invulnerable — the game should never lie about that —
    but it is *not worth it*, and a player who works that out has learned
    the actual lesson of the region."""
    thresh_wake = C.DISTURB_APEX_WAKE
    thresh_sleep = C.DISTURB_APEX_SLEEP
    hunting = cr.state in (HUNT, STRIKE)
    if world.disturbance > thresh_wake:
        hunting = True
    elif world.disturbance < thresh_sleep and alarm < 0.35:
        hunting = False

    if not hunting:
        cr.state = IDLE
        _wander(cr, dt, 0.20)
        return

    goal = world.loudest_point or cr.target_memory or player.pos
    if alarm > 0.5:
        goal = player.pos
    cr.state = HUNT
    d = cr.distance_to(goal)
    cr.swim(cr.aim_at(goal), dt, 1.0 if d > 120 else 0.4)
    if alarm > 0.6 and cr.distance_to(player.pos) < 300.0 and cr.cooldown <= 0.0:
        cr.cooldown = 1.7
        cr.state = STRIKE
        cr.fire(world, cr.aim_at(player.pos), out)


def _b_conspecific(cr, dt, world, player, out, alarm):
    """It does not run and it does not attack. It waits.

    Everything the ending needs is already true by the time this function
    runs; it does not have to do anything except be there and be
    unmistakably the same kind of thing as you."""
    cr.state = IDLE
    d = cr.distance_to(player.pos)
    if d > 200.0:
        cr.swim(cr.aim_at(player.pos), dt, 0.35)
    else:
        _wander(cr, dt, 0.06)
    world.room.fields.add_heat(cr.pos, 90.0, 0.30 * dt)


BEHAVIOURS = {
    "drift": _b_drift,
    "attendant": _b_attendant,
    "swarm": _b_swarm,
    "sounder": _b_sounder,
    "stalk": _b_stalk,
    "ossuary": _b_ossuary,
    "recursor": _b_recursor,
    "ambush": _b_ambush,
    "carrion": _b_carrion,
    "apex": _b_apex,
    "conspecific": _b_conspecific,
}
