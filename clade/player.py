"""You.

Not much of a class, because almost everything that would normally live in
a player object lives in the Body instead — your health, your resources,
your weapons, your light and your weight are all the same object, and that
is the point. There is no "player stats" here to drift out of sync with
what you built, because there are no player stats.

Two verbs are defined here and nowhere else:

**BITE.** You put your mouth on a dead thing and take what it was made of.
This is the only fast way to refill, it is how organs are recovered, and it
is the single action the entire ending turns on. It is bound to a key from
the first minute and the game never comments on it.

**SURGE.** A shove out of your own back. It costs reserve and it is loud,
because a dash that is free is a dash that deletes every threat system in
the game.
"""

import math

from . import config as C
from .humours import BRINE, ICHOR, N_HUMOURS, SILT, SPARK, Charge
from .world.fields import BURN_AT, FREEZE_AT


class Player:
    def __init__(self, body, pos):
        self.body = body
        self.pos = [float(pos[0]), float(pos[1])]
        self.vel = [0.0, 0.0]
        self.aim = [1.0, 0.0]
        self.shake = 0.0
        self.surge_timer = 0.0
        self.biting = None
        self.bite_time = 0.0
        self.invuln = 0.0
        self.hurt_flash = 0.0
        self.dead = False
        self.deaths = 0
        self.harvests = 0
        self.peaceful_harvests = 0     # the number the ending reads
        self.spared = 0
        self.facing = [1.0, 0.0]
        self.last_safe = list(pos)

    # ------------------------------------------------------------ movement

    def update(self, dt, world, move):
        self.shake = max(0.0, self.shake - dt * 6.0)
        self.invuln = max(0.0, self.invuln - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 3.0)
        self.surge_timer = max(0.0, self.surge_timer - dt)

        mods = self.body.mods
        room = world.room

        # Thrust. Heavy bodies are slow to start and hard to stop, which is
        # the whole physical argument for keeping your composition light
        # when you are somewhere frightening.
        accel = (C.PLAYER_ACCEL * mods["speed"]
                 * (1.0 + min(0.45, self.body.standing_fx["jolt"] * 0.09))
                 / max(0.6, mods["weight"]))
        ml = math.hypot(move[0], move[1])
        if ml > 1e-4:
            self.vel[0] += move[0] / ml * accel * dt
            self.vel[1] += move[1] / ml * accel * dt
            self.facing = [move[0] / ml, move[1] / ml]

        # Buoyancy. Your brine fraction against neutral, minus whatever a
        # standing chain is doing about it. This is traversal: a body full
        # of salt walks the floor, and a body running an inverted brine
        # chain climbs — which means the game's "double jump" is something
        # you designed at the Bench rather than something you found.
        f = self.body.reserve.fractions()
        fill = self.body.reserve.magnitude / self.body.reserve_cap
        heaviness = (f[BRINE] + f[SILT] * 0.7 - C.NEUTRAL_BRINE) * (0.35 + fill)
        heaviness -= self.body.standing_fx["lift"] * 0.055
        self.vel[1] += heaviness * C.GRAVITY * dt

        cur = room.fields.current_at(self.pos)
        self.vel[0] += cur[0] * dt
        self.vel[1] += cur[1] * dt

        drag = math.pow(0.0009, dt) if ml > 1e-4 else math.pow(0.00025, dt)
        self.vel[0] *= drag
        self.vel[1] *= drag

        # Nerve makes everything about you quicker, including the parts
        # you would rather were not.
        quick = 1.0 + min(0.45, self.body.standing_fx["jolt"] * 0.09)
        cap = C.PLAYER_MAX_SPEED * mods["speed"] * quick
        sp = math.hypot(*self.vel)
        if sp > cap:
            k = cap / sp
            self.vel[0] *= k
            self.vel[1] *= k

        self._move(dt, room)
        self.body.on_floor = room.solid_at(self.pos[0], self.pos[1] + 22.0)

        # Your own wake. Fast water off your flank is both a real current
        # other things drift in and a thing that can be followed.
        speed = math.hypot(self.vel[0], self.vel[1])
        if speed > C.PLAYER_MAX_SPEED * 0.45:
            k = speed / C.PLAYER_MAX_SPEED
            world.room.fields.add_current(
                self.pos, 30.0,
                (-self.vel[0] * 0.22 * dt, -self.vel[1] * 0.22 * dt))
            # Cubed, not squared. Disturbance bleeds off at 2.4/s, so a
            # squared curve made *cruising* louder than the room could
            # forget and every journey ended with the Apex awake. Cubed
            # puts the crossover right at the top of the speed range:
            # travelling is quiet, fleeing is not.
            world.add_disturbance(k * k * k * 3.4 * dt, self.pos)

        self._suffer(dt, world)
        self.body.update(dt, world, tuple(self.pos))

        if self.body.viability <= 0.0 and not self.dead:
            self.dead = True

    def _move(self, dt, room):
        nx = self.pos[0] + self.vel[0] * dt
        ny = self.pos[1] + self.vel[1] * dt
        r = 10.0
        if not (room.solid_at(nx - r, self.pos[1]) or room.solid_at(nx + r, self.pos[1])):
            self.pos[0] = nx
        else:
            self.vel[0] *= -0.18
        if not (room.solid_at(self.pos[0], ny - r) or room.solid_at(self.pos[0], ny + r)):
            self.pos[1] = ny
        else:
            self.vel[1] *= -0.18
        self.pos[0] = max(8.0, min(room.pixel_w - 8.0, self.pos[0]))
        self.pos[1] = max(8.0, min(room.pixel_h - 8.0, self.pos[1]))

    def _suffer(self, dt, world):
        f = world.room.fields
        h = f.heat_at(self.pos)
        mods = self.body.mods
        if h > BURN_AT:
            self.take_damage((h - BURN_AT) * 6.0 * dt * mods["fragility"], world)
        elif h < FREEZE_AT * 0.6:
            # Cold does not damage you. It slows you, which down here is
            # worse and takes longer to notice.
            self.vel[0] *= 0.94
            self.vel[1] *= 0.94
        ch = f.charge_at(self.pos)
        if ch > 0.35:
            self.take_damage(ch * 4.5 * dt * mods["fragility"], world)

    # -------------------------------------------------------------- verbs

    def surge(self, world):
        """A shove out of your own back. Costs brine specifically — you are
        pushing water — so surging repeatedly makes you lighter, faster and
        eventually unable to sink, which is a movement tech nobody wrote
        down."""
        if self.surge_timer > 0.0:
            return False
        take = self.body.tap_reserve(6.0)
        if take.magnitude < 3.0:
            self.body.feed(take)
            return False
        self.surge_timer = 0.55
        torn = 0
        for c in world.creatures:
            if getattr(c, "grabbed", False):
                c.grabbed = False
                c.phase = None
                c.cooldown = 1.8
                c.vel[0] -= self.facing[0] * 260.0
                c.vel[1] -= self.facing[1] * 260.0
                torn += 1
        if torn:
            world.flash_event("you tore it off")
        d = self.facing
        power = 340.0 + take[BRINE] * 26.0
        self.vel[0] += d[0] * power
        self.vel[1] += d[1] * power
        world.room.fields.add_current(
            (self.pos[0] - d[0] * 20, self.pos[1] - d[1] * 20), 40.0,
            (-d[0] * 180, -d[1] * 180))
        world.add_disturbance(take.magnitude * 0.5, self.pos)
        return True

    def bite(self, world, dt):
        """Hold to drain. Deliberately not instant: standing still with your
        mouth in a corpse while a room you just made noise in decides what
        to do about it is the most exposed you are ever asked to be, and it
        is the price of everything you own."""
        target = world.bite_target(self.pos, 58.0)
        if target is None:
            self.biting = None
            self.bite_time = 0.0
            return None
        self.biting = target
        self.bite_time += dt
        got = target.drain(C.BITE_RATE * dt)
        if got is not None and got.magnitude > 0.0:
            self.body.feed(got)
        if target.spent and not target.claimed:
            target.claimed = True
            return target
        return None

    def take_damage(self, amount, world, from_pos=None):
        if self.invuln > 0.0 or amount <= 0.0:
            return
        amount *= self.body.mods["fragility"] / self.body.mods["toughness"]
        self.body.viability -= amount
        self.hurt_flash = 1.0
        self.shake = max(self.shake, min(9.0, amount * 0.6))
        if amount > 3.0:
            self.invuln = 0.22
        if self.body.viability <= 0.0:
            self.dead = True

    # -------------------------------------------------------------- state

    @property
    def viability(self):
        return self.body.viability

    @property
    def sight(self):
        return self.body.sight

    def aim_at(self, world_point):
        dx = world_point[0] - self.pos[0]
        dy = world_point[1] - self.pos[1]
        d = math.hypot(dx, dy)
        if d > 1e-4:
            self.aim = [dx / d, dy / d]
