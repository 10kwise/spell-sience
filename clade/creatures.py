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

# The attack cycle. Every attack in the game passes through all three.
WINDUP, COMMIT, RECOVER = "windup", "commit", "recover"


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
        "attack", "windup", "commit_time", "recover", "reach", "pack",
    )

    def __init__(self, key, name, viability, radius, speed, organs, chain,
                 behaviour="stalk", resist=None, armour=0.0, senses=1.0,
                 drops=None, tier=0, glow=0.0, aggression=1.0, codex="",
                 harvest_note="", peaceful=False, attack="shoot",
                 windup=0.55, commit_time=0.25, recover=0.9, reach=340.0,
                 pack=0.0):
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
        # The attack cycle. windup is the tell, commit is the part that
        # cannot be re-aimed, recover is the part you punish.
        self.attack = attack
        self.windup = windup
        self.commit_time = commit_time
        self.recover = recover
        self.reach = reach
        self.pack = pack        # how loudly it tells its neighbours


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
        # --- the attack cycle
        self.phase = None              # None | WINDUP | COMMIT | RECOVER
        self.phase_t = 0.0
        self.phase_len = 0.0
        self.locked_aim = (1.0, 0.0)
        self.charge_speed = 0.0
        self.grabbed = False           # grapplers: attached to the player
        self.still_time = 0.0
        self.contact_done = False      # charger/grappler: hit landed
        self.search_anchor = None      # apex: the last thing it heard
        self.search_t = 0.0

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
        light = player.body.glow * 700.0 / dist * vis

        # Noise is room-wide but attenuates: a scream two rooms of water
        # away is a rumour, not a fix.
        noise = world.disturbance * 0.9 * (240.0 / (dist * 0.55 + 240.0))

        # Wake. **Moving fast is the loudest thing you can do**, and this
        # single term is the answer to the most damning thing said about
        # the first build: that you could sprint around a room and nothing
        # would react. Now sprinting is a signal, hanging still in the dark
        # is not, and the difference between them is most of the game.
        speed = math.hypot(player.vel[0], player.vel[1])
        wake = (speed / C.PLAYER_MAX_SPEED) * 17.0 * (300.0 / (dist + 300.0))

        # Contact: nothing hides a body pressed against you. Ramped rather
        # than a cliff at 130px — the old form gave a creature swimming
        # straight into you an alarm of about 0.2, so nothing ever engaged
        # and every fight had to be started by the player.
        contact = max(0.0, (230.0 - dist) / 230.0) * 24.0

        # A body that burns and shouts is a body things come and look at.
        # This is the "attract enemies" build, and it is not a flag: it is
        # the same light and the same concentration that give you away
        # everywhere else, turned up on purpose.
        lure = player.body.standing_fx["lure"] * 90.0 / dist

        signal = (light + noise + wake + lure + contact) * self.sp.senses

        # Kinship. You and this creature are both made of humours, and if
        # your composition resembles its own it has much more trouble
        # deciding you are not one of it.
        #
        # This is the game's whole thesis made mechanical: build yourself
        # out of what lives here and what lives here stops minding you. The
        # cost is that you *are* what you resemble, and the deep regions
        # are full of things you would not want to be.
        signal *= 1.0 - self.kinship(player) * 0.6

        target = max(0.0, min(1.0, signal / 24.0))
        if self.hidden:
            # It is not stealthed. It is *motionless*, which in water with
            # no light in it is the same thing.
            target *= 0.25

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

    # -------------------------------------------------------- the cycle

    def begin_attack(self):
        """Start winding up. Nothing else in this class may set `phase`."""
        if self.phase is not None or self.cooldown > 0.0:
            return False
        self.phase = WINDUP
        self.phase_len = self.phase_t = max(0.08, self.sp.windup)
        return True

    @property
    def phase_frac(self):
        if self.phase_len <= 0.0:
            return 0.0
        return 1.0 - (self.phase_t / self.phase_len)

    @property
    def vulnerable(self):
        return self.phase == RECOVER

    def kinship(self, player) -> float:
        """0 = nothing like you, 1 = indistinguishable."""
        a = self.composition.fractions()
        b = player.body.reserve.fractions()
        l1 = sum(abs(a[i] - b[i]) for i in range(N_HUMOURS))
        return max(0.0, 1.0 - l1 / 1.1)

    @property
    def hidden(self):
        """An ambusher that has been perfectly still is not drawn and is
        not sensed. You find it by the hole it makes in the silt, or by
        swimming into it."""
        return self.sp.behaviour == "ambush" and self.still_time > 1.4

    def _advance_phase(self, dt, world, player, out):
        """WINDUP -> COMMIT -> RECOVER, and the reason fights are readable.

        The first build had none of this: creatures fired instantly on a
        cooldown, aimed at wherever you were that frame, so there was
        nothing to see coming and nothing that moving could avoid. You
        could swim in circles forever and never feel in danger, which is
        exactly what the game felt like.

        Now the heading is locked at the *end* of windup and cannot be
        re-aimed, so dodging is real; and recovery is a genuine
        vulnerability window, so committing to an attack is a decision the
        creature can be punished for."""
        if self.phase is None:
            return
        self.phase_t -= dt
        if self.phase == WINDUP:
            # Winding up stirs the water. In a room you cannot see across,
            # this is how something announces itself: you feel the pull
            # before you find the shape.
            if player is not None:
                d = self.aim_at(player.pos)
                world.room.fields.add_current(
                    self.pos, self.sp.radius * 3.4,
                    (-d[0] * C.WINDUP_STIR * dt, -d[1] * C.WINDUP_STIR * dt))
            if self.phase_t <= 0.0:
                self.locked_aim = self.aim_at(player.pos) if player else (1, 0)
                self.phase = COMMIT
                self.phase_len = self.phase_t = max(0.05, self.sp.commit_time)
                COMMITS.get(self.sp.attack, _c_shoot)(self, world, out)
        elif self.phase == COMMIT:
            SUSTAIN.get(self.sp.attack, lambda *a: None)(self, dt, world,
                                                         player, out)
            if self.phase_t <= 0.0:
                self.phase = RECOVER
                self.phase_len = self.phase_t = max(0.05, self.sp.recover)
        elif self.phase == RECOVER:
            if self.phase_t <= 0.0:
                self.phase = None
                self.cooldown = self.rng.uniform(0.5, 1.3) / max(
                    0.4, self.sp.aggression)

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
        self._advance_phase(dt, world, player, out_emissions)

        if self.phase is None:
            BEHAVIOURS.get(self.sp.behaviour, _b_stalk)(
                self, dt, world, player, out_emissions, alarm
            )
        else:
            self.state = STRIKE
            MOVES.get(self.sp.attack, lambda *a: None)(self, dt, world, player)

        # Telling the neighbours. A creature that has found you raises the
        # suspicion of everything nearby, which is where pack behaviour
        # comes from without anybody writing a pack.
        if self.sp.pack > 0.0 and alarm > 0.6:
            for other in world.creatures:
                if other is self or other.dead or other.alarm > 0.55:
                    continue
                if other.distance_to(self.pos) < 300.0:
                    other.alarm = min(0.75, other.alarm + self.sp.pack * dt)
                    if self.target_memory:
                        other.target_memory = self.target_memory
                        other.memory_age = 0.0

        # Ward. A body running rot and live nerve is one nothing wants to
        # be near, so it is not: this pushes things off you without ever
        # touching their behaviour, which means a warded body can still be
        # hunted, just not comfortably.
        ward = player.body.standing_fx["ward"] if player is not None else 0.0
        if ward > 0.2:
            d = self.distance_to(player.pos)
            reach = 60.0 + ward * 46.0
            if d < reach:
                away = ((self.pos[0] - player.pos[0]) / (d + 1e-6),
                        (self.pos[1] - player.pos[1]) / (d + 1e-6))
                push = (reach - d) / reach * ward * 190.0
                self.vel[0] += away[0] * push * dt
                self.vel[1] += away[1] * push * dt

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

        armour = self.sp.armour
        if self.vulnerable:
            # Caught mid-recovery: the plates are open, and hitting it now
            # is worth more than hitting it twice at any other time. This
            # is what turns an armoured creature from a sponge into a
            # rhythm.
            armour *= 0.25
        dmg = effect.damage * passthru * max(0.15, 1.0 - armour)
        if self.vulnerable:
            dmg *= C.RECOVER_VULNERABLE

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
        if self.vulnerable and dmg > 1.0:
            self.phase_t += C.STAGGER_ON_RECOVER_HIT
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
# ATTACKS
#
# Three tables, keyed by the species' archetype:
#
#   COMMITS  fires once, the instant the wind-up ends.
#   SUSTAIN  runs every frame while the attack is committed.
#   MOVES    runs every frame during *any* phase, so a charger accelerates
#            through its own commit while a bulwark plants itself.
#
# Splitting it this way is what lets nine genuinely different attacks share
# one state machine, and it is why a new creature costs a table row rather
# than a subclass.
# ===========================================================================

def _c_shoot(cr, world, out):
    cr.fire(world, cr.locked_aim, out)


def _c_charge(cr, world, out):
    cr.charge_speed = cr.sp.speed * 5.0
    cr.contact_done = False


def _c_grab(cr, world, out):
    cr.charge_speed = cr.sp.speed * 3.4
    cr.contact_done = False


def _c_scream(cr, world, out):
    world.add_disturbance(38.0, cr.pos)
    world.alert_all(cr.pos)
    world.flash_event("something has told the room about you", cr.pos)


def _c_erupt(cr, world, out):
    cr.fire(world, cr.locked_aim, out)
    world.room.fields.add_silt(cr.pos, 170.0, 2.6)
    world.room.fields.add_current(cr.pos, 150.0, (0.0, -220.0))


def _c_lob(cr, world, out):
    """Leads the target. Artillery that fires at where you *are* is
    artillery you can walk away from at any speed."""
    p = world.player
    aim = cr.locked_aim
    if p is not None:
        lead = 0.45
        px = p.pos[0] + p.vel[0] * lead
        py = p.pos[1] + p.vel[1] * lead
        dx, dy = px - cr.pos[0], py - cr.pos[1]
        d = math.hypot(dx, dy) + 1e-6
        aim = (dx / d, dy / d)
    cr.fire(world, aim, out)


COMMITS = {
    "shoot": _c_shoot, "charge": _c_charge, "grab": _c_grab,
    "scream": _c_scream, "erupt": _c_erupt, "lob": _c_lob,
    "cone": _c_shoot, "sweep": _c_shoot,
}


def _rush(cr, dt, world, player, out, on_touch):
    d = cr.locked_aim
    cr.vel[0] += d[0] * cr.charge_speed * dt * 9.0
    cr.vel[1] += d[1] * cr.charge_speed * dt * 9.0
    ahead = (cr.pos[0] + cr.vel[0] * dt * 2.2,
             cr.pos[1] + cr.vel[1] * dt * 2.2)
    if world.room.solid_at(*ahead):
        # It committed and it was wrong. A charger that hits a wall is
        # stunned for much longer than one that hits you, which is the
        # entire counterplay: stand in front of something solid and move
        # late.
        cr.phase = RECOVER
        cr.phase_len = cr.phase_t = cr.sp.recover * 2.6
        cr.hurt(7.0, world)
        cr.vel[0] *= -0.25
        cr.vel[1] *= -0.25
        world.flash_event("it went past you and into the rock", cr.pos)
        return
    if player is not None and not cr.contact_done:
        if cr.distance_to(player.pos) < cr.sp.radius + 13.0:
            cr.contact_done = True
            on_touch(cr, world, player)


def _touch_slam(cr, world, player):
    player.take_damage(cr.max_viability * 0.10 * C.HOSTILE_DAMAGE, world,
                       cr.pos, cause=cr.sp.name + ", ramming you")
    d = cr.locked_aim
    player.vel[0] += d[0] * 420.0
    player.vel[1] += d[1] * 420.0
    player.shake = max(player.shake, 8.0)


def _touch_latch(cr, world, player):
    cr.grabbed = True
    world.flash_event("it is on you")


def _s_charge(cr, dt, world, player, out):
    _rush(cr, dt, world, player, out, _touch_slam)


def _s_grab(cr, dt, world, player, out):
    _rush(cr, dt, world, player, out, _touch_latch)


SUSTAIN = {"charge": _s_charge, "grab": _s_grab}


def _m_plant(cr, dt, world, player):
    """Bulwarks and artillery stop moving to attack. Being rooted for a
    second and a half is what makes their wind-up worth watching."""
    cr.vel[0] *= 0.90
    cr.vel[1] *= 0.90


def _m_coil(cr, dt, world, player):
    """Chargers draw back before they commit — a visible, physical tell
    that is also a real disadvantage if you read it."""
    if cr.phase == WINDUP and player is not None:
        d = cr.aim_at(player.pos)
        cr.swim((-d[0], -d[1]), dt, 0.55)


MOVES = {
    "shoot": _m_plant, "cone": _m_plant, "lob": _m_plant,
    "scream": _m_plant, "erupt": _m_plant, "sweep": _m_plant,
    "charge": _m_coil, "grab": _m_coil,
}


# ===========================================================================
# BEHAVIOURS
#
# What a creature does when it is *not* mid-attack: where it goes, what it
# is watching, and when it decides to commit. Each is a lesson wearing a
# hitbox, and each is a plain function so that a species is describable as
# data.
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

    The most important creature in the game, and it has eleven lines of
    code. It is the ending, rehearsed in the first hour, silently — and it
    works because the game never says a word about it, gives a genuinely
    excellent organ for killing it, and does not react when you do."""
    cr.state = IDLE
    d = cr.distance_to(player.pos)
    if d > 260.0:
        cr.swim(cr.aim_at(player.pos), dt, 0.75)
    elif d < 130.0:
        cr.swim([-x for x in cr.aim_at(player.pos)], dt, 0.5)
    else:
        _wander(cr, dt, 0.15)
    world.room.fields.add_silt(cr.pos, 40.0, -0.55 * dt)


def _b_swarm(cr, dt, world, player, out, alarm):
    """Gullet-fry. They do not take your viability, they take your
    *reserve* — and now that reserve is what keeps you alive, a swarm is no
    longer a nuisance. It is a thing that empties the tank you were going
    to spend on getting out.

    They also surround rather than converge, so you cannot solve them by
    backing into a corner."""
    if alarm < 0.25:
        cr.state = IDLE
        _wander(cr, dt, 0.4)
        return
    cr.state = HUNT
    d = cr.distance_to(player.pos)
    to = cr.aim_at(player.pos)
    if d > 120.0:
        cr.swim(to, dt, 1.25)
    else:
        # Orbit, so the shoal spreads around you instead of stacking.
        side = 1.0 if (id(cr) & 1) else -1.0
        cr.swim((-to[1] * side + to[0] * 0.35,
                 to[0] * side + to[1] * 0.35), dt, 1.1)
    if d < 36.0 and cr.cooldown <= 0.0:
        cr.cooldown = 0.7
        stolen = player.body.tap_reserve(6.5)
        cr.body.reserve.add(stolen)
        player.body.hurt(1.2, cr.sp.name)
        player.shake = max(player.shake, 3.0)
        cr.fed_flash = 1.0


def _b_sounder(cr, dt, world, player, out, alarm):
    """It does not fight. It tells."""
    cr.state = ALERT if alarm > 0.3 else IDLE
    _wander(cr, dt, 0.08)
    if alarm > 0.6:
        cr.begin_attack()


def _b_stalk(cr, dt, world, player, out, alarm):
    """The default predator: close to its reach, then commit."""
    if alarm < 0.22 and cr.memory_age > 5.0:
        cr.state = IDLE
        _wander(cr, dt, 0.3)
        return
    goal = cr.target_memory or player.pos
    d = cr.distance_to(goal)
    cr.state = HUNT if alarm > 0.5 else ALERT
    _press(cr, dt, goal, cr.sp.reach)
    if alarm > 0.42 and cr.distance_to(player.pos) < cr.sp.reach:
        cr.begin_attack()


def _press(cr, dt, goal, reach):
    """Close to about two thirds of reach, then hold and circle. Creatures
    that walk all the way into your face have no spacing, and spacing is
    most of what makes a fight legible."""
    d = cr.distance_to(goal)
    to = cr.aim_at(goal)
    want = reach * 0.62
    if d > want * 1.15:
        cr.swim(to, dt, 1.0)
    elif d < want * 0.6:
        cr.swim((-to[0], -to[1]), dt, 0.7)
    else:
        cr.swim((-to[1], to[0]), dt, 0.45)


def _b_charger(cr, dt, world, player, out, alarm):
    """It commits to a straight line and it cannot turn once it has.

    Bait it into rock. That is the whole creature, and it takes one death
    to learn and never stops working."""
    if alarm < 0.3 and cr.memory_age > 4.0:
        cr.state = IDLE
        _wander(cr, dt, 0.45)
        return
    goal = cr.target_memory or player.pos
    cr.state = HUNT
    d = cr.distance_to(goal)
    if d > cr.sp.reach:
        cr.swim(cr.aim_at(goal), dt, 1.1)
    else:
        to = cr.aim_at(goal)
        cr.swim((-to[1] * 0.8, to[0] * 0.8), dt, 0.6)
    if alarm > 0.42 and d < cr.sp.reach:
        cr.begin_attack()


def _b_bulwark(cr, dt, world, player, out, alarm):
    """Armoured everywhere except where it has to let the heat out — and it
    lets the heat out while it recovers. Slow, unhurried, and only worth
    hitting on the beat."""
    if alarm < 0.25 and cr.memory_age > 6.0:
        cr.state = IDLE
        _wander(cr, dt, 0.15)
        return
    goal = cr.target_memory or player.pos
    cr.state = HUNT
    _press(cr, dt, goal, cr.sp.reach)
    world.room.fields.add_heat(cr.pos, 44.0, 0.9 * dt)
    cr.tag = "venting" if cr.vulnerable else None
    if alarm > 0.42 and cr.distance_to(player.pos) < cr.sp.reach:
        cr.begin_attack()


def _b_artillery(cr, dt, world, player, out, alarm):
    """Dangerous at range and helpless up close. It backs away from you the
    whole time, which means the counter is to be rude about it."""
    if alarm < 0.25 and cr.memory_age > 5.0:
        cr.state = IDLE
        _wander(cr, dt, 0.3)
        return
    goal = cr.target_memory or player.pos
    d = cr.distance_to(player.pos)
    cr.state = HUNT
    to = cr.aim_at(goal)
    if d < cr.sp.reach * 0.55:
        cr.swim((-to[0], -to[1]), dt, 1.2)
    elif d > cr.sp.reach:
        cr.swim(to, dt, 0.8)
    else:
        cr.swim((-to[1], to[0]), dt, 0.4)
    if alarm > 0.42 and d < cr.sp.reach:
        cr.begin_attack()


def _b_grappler(cr, dt, world, player, out, alarm):
    """It latches on and drains you until you shake it off.

    Surging breaks it — which costs brine, which is the reserve it is
    currently eating. The whole creature is a bill you have to pay to stop
    paying it."""
    if cr.grabbed:
        cr.state = STRIKE
        cr.pos[0] += (player.pos[0] - cr.pos[0]) * min(1.0, dt * 9.0)
        cr.pos[1] += (player.pos[1] - cr.pos[1]) * min(1.0, dt * 9.0)
        cr.vel[0] = cr.vel[1] = 0.0
        stolen = player.body.tap_reserve(9.0 * dt)
        cr.body.reserve.add(stolen)
        player.body.hurt(3.4 * dt, cr.sp.name + ", attached to you")
        player.shake = max(player.shake, 2.0)
        cr.fed_flash = 1.0
        return
    if alarm < 0.3 and cr.memory_age > 4.0:
        cr.state = IDLE
        _wander(cr, dt, 0.4)
        return
    cr.state = HUNT
    goal = cr.target_memory or player.pos
    d = cr.distance_to(goal)
    if d > cr.sp.reach:
        cr.swim(cr.aim_at(goal), dt, 1.2)
    else:
        to = cr.aim_at(goal)
        cr.swim((-to[1], to[0]), dt, 0.7)
    if alarm > 0.42 and d < cr.sp.reach:
        cr.begin_attack()


def _b_recursor(cr, dt, world, player, out, alarm):
    """It has a Knot. Every focused thing you throw at it becomes part of
    it. Not a puzzle boss — it runs the same rules you do, and the rules
    say concentration is food.

    Two answers, and the game states neither: starve it, or hand it
    something with no concentration in it at all."""
    _b_stalk(cr, dt, world, player, out, alarm)
    cr.viability -= 1.15 * dt
    if cr.viability <= 0:
        cr.die(world)


def _b_ambush(cr, dt, world, player, out, alarm):
    """The Silt Mother. She carries her own dark, and — this is the part
    that matters — **while she is completely still you cannot detect her at
    all.** No glow, no disturbance, no silhouette. You find her by the
    shape of the hole she makes, or by swimming into her."""
    world.room.fields.add_silt(cr.pos, 130.0, 2.6 * dt)
    d = cr.distance_to(player.pos)
    if d > 200.0 and alarm < 0.75:
        cr.state = IDLE
        cr.still_time += dt
        cr.vel[0] *= 0.82
        cr.vel[1] *= 0.82
        return
    cr.still_time = 0.0
    cr.state = HUNT
    if d > 90.0:
        cr.swim(cr.aim_at(player.pos), dt, 1.4)
    if d < 230.0:
        cr.begin_attack()


def _b_carrion(cr, dt, world, player, out, alarm):
    """It eats the dead, including the ones you were saving.

    This is the pressure that stops harvesting from being a leisurely
    post-combat chore: a corpse is a clock, and the thing that comes to eat
    it is also a thing you have to deal with while you are empty."""
    corpse = world.nearest_corpse(cr.pos, 900.0)
    if corpse is not None:
        d = math.hypot(corpse.pos[0] - cr.pos[0], corpse.pos[1] - cr.pos[1])
        cr.state = HUNT
        if d > 30.0:
            cr.swim(cr.aim_at(corpse.pos), dt, 1.2)
        else:
            taken = corpse.drain(11.0 * dt)
            cr.body.reserve.add(taken)
            cr.fed_flash = 1.0
        return
    _b_artillery(cr, dt, world, player, out, alarm)


def _b_apex(cr, dt, world, player, out, alarm):
    """The thing you do not fight.

    It wakes on disturbance and sleeps on quiet, it is faster than you, and
    killing it is a project rather than a fight. It is not invulnerable —
    the game should never lie about that — but it is *not worth it*.

    It also actually hunts: it goes to the loudest thing it heard, and when
    it gets there and finds nothing it sweeps outward from that point
    rather than standing still. Losing it means putting distance and
    quiet between you and the last noise you made, which is a skill."""
    hunting = cr.state in (HUNT, STRIKE)
    if world.disturbance > C.DISTURB_APEX_WAKE:
        hunting = True
    elif world.disturbance < C.DISTURB_APEX_SLEEP and alarm < 0.35:
        hunting = False

    if not hunting:
        cr.state = IDLE
        _wander(cr, dt, 0.20)
        cr.search_anchor = None
        return

    cr.state = HUNT
    if alarm > 0.5:
        goal = player.pos
        cr.search_anchor = None
    else:
        anchor = getattr(cr, "search_anchor", None)
        if anchor is None:
            anchor = world.loudest_point or cr.target_memory or player.pos
            cr.search_anchor = (float(anchor[0]), float(anchor[1]))
            cr.search_t = 0.0
        cr.search_t = getattr(cr, "search_t", 0.0) + dt
        if cr.distance_to(cr.search_anchor) < 90.0 or cr.search_t > 7.0:
            # Sweep outward from the last thing it heard.
            a = cr.search_t * 1.1
            r = 150.0 + cr.search_t * 40.0
            goal = (cr.search_anchor[0] + math.cos(a) * r,
                    cr.search_anchor[1] + math.sin(a) * r)
            if cr.search_t > 14.0:
                cr.search_anchor = None
        else:
            goal = cr.search_anchor

    d = cr.distance_to(goal)
    cr.swim(cr.aim_at(goal), dt, 1.0 if d > 120 else 0.4)
    if alarm > 0.6 and cr.distance_to(player.pos) < cr.sp.reach:
        cr.begin_attack()


def _b_conspecific(cr, dt, world, player, out, alarm):
    """It does not run and it does not attack. It waits."""
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
    "charger": _b_charger,
    "bulwark": _b_bulwark,
    "artillery": _b_artillery,
    "grappler": _b_grappler,
    "recursor": _b_recursor,
    "ambush": _b_ambush,
    "carrion": _b_carrion,
    "apex": _b_apex,
    "conspecific": _b_conspecific,
}
