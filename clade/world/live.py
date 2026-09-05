"""The live world: one room at a time, everything in it, and the attention
economy that ties them together.

This is the orchestration layer, and it holds exactly one opinion of its
own — **disturbance** — because that is the only quantity in the game that
belongs to the room rather than to anything in it.

Disturbance is the sum of every loud thing that has happened here lately,
decaying slowly. It does three jobs at once and it is the same number for
all three, which is why the game's stealth reads as coherent rather than as
three overlapping systems:

  * it is what the Apex homes on,
  * it is a term in every creature's perception,
  * and it is what the screen edge is doing when you feel watched.

Emissions become Motes here. A Mote does not know what it is — it carries a
resolved Effect and a shape, and the collision code applies the effect to
whatever it hit and to the water it hit it in. That is why a chain you
built to freeze a door also freezes a creature, and why the fire you set to
kill something is still burning when you have to come back through.
"""

import math
import random

from .. import config as C
from ..effects import resolve
from ..humours import BRINE, ICHOR, N_HUMOURS, SILT, SPARK, Charge
from .. import bestiary
from ..creatures import Creature
from .room import (
    LOCK_CAUSTIC, LOCK_COLD, LOCK_FORCE, LOCK_GENTLE, LOCK_RISE, Room, TISSUE,
)


class Mote:
    """Loose effect, in flight."""

    __slots__ = ("pos", "vel", "effect", "shape", "life", "hostile", "spent",
                 "trail", "radius", "delay", "source", "hit")

    def __init__(self, em, hostile=False):
        self.pos = [float(em.origin[0]), float(em.origin[1])]
        h = em.heading
        self.vel = [h[0] * em.speed, h[1] * em.speed]
        self.effect = em.effect
        self.shape = em.shape
        self.life = em.shape.life
        self.hostile = hostile
        self.spent = False
        self.trail = em.trail
        self.radius = em.shape.radius
        self.delay = em.delay
        self.source = em.source
        self.hit = set()

    def update(self, dt, room):
        if self.delay > 0.0:
            self.delay -= dt
            return
        if self.shape.kind == "seed" and self.life < self.shape.life - 0.35:
            # A seed stops and waits. It is a decoy, a trap, and the only
            # way to make a noise somewhere you are not.
            self.vel[0] *= 0.02
            self.vel[1] *= 0.02
        if self.shape.kind == "lob":
            self.vel[1] += 210.0 * dt
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.life -= dt
        if self.trail:
            room.fields.apply_effect(self.effect, self.pos, self.radius * 1.4)
        if self.life <= 0.0:
            self.spent = True
        elif room.solid_at(self.pos[0], self.pos[1]):
            self.spent = True


class Corpse:
    """A dead thing, and what is left in it. It rots on a clock and the
    scavengers know the clock better than you do."""

    __slots__ = ("pos", "charge", "organs", "age", "life", "species",
                 "spent", "claimed", "harvested")

    def __init__(self, pos, charge, organs, species):
        self.pos = [float(pos[0]), float(pos[1])]
        self.charge = charge
        self.organs = list(organs)
        self.species = species
        self.age = 0.0
        self.life = 42.0
        self.spent = False
        self.claimed = False
        self.harvested = 0.0

    def update(self, dt, room):
        self.age += dt
        # It leaks. What it was made of goes into the water around it, which
        # is why a fresh kill is a temporarily different room.
        if self.charge.magnitude > 0.2:
            room.fields.apply_effect(resolve(self.charge.scaled(0.02 * dt)),
                                     self.pos, 46.0)
        if self.age > self.life:
            self.spent = True

    def drain(self, amount):
        m = self.charge.magnitude
        if m < 1e-4:
            self.spent = True
            return Charge()
        take = min(amount, m)
        out = self.charge.scaled(take / m)
        self.charge.scale_in_place(1.0 - take / m)
        self.harvested += take
        if self.charge.magnitude < 0.4:
            self.spent = True
        return out


class World:
    def __init__(self, atlas, body, start_key=None, seed=0):
        self.atlas = atlas
        self.rng = random.Random(seed)
        self.rooms = {}
        self.body = body
        self.disturbance = 0.0
        self.loudest_point = None
        self.loudest_at = 0.0
        self.creatures = []
        self.corpses = []
        self.motes = []
        self.hostile_motes = []
        self.events = []            # (text, pos, age)
        self.time = 0.0
        self.player = None
        self.apex = None
        # Persistent, world-wide state. Declared before the first get_room()
        # because get_room re-applies `opened` to any room it builds — a
        # room constructed before that set exists would silently re-lock
        # every door the player had already forced.
        self.picked_up = set()      # prop ids already taken, world-wide
        self.opened = set()         # (room_key, side, at) doors forced open
        self.flags = set()          # narrative flags
        self.kill_counts = {}
        # Seconds after arriving during which doors do not trigger. Without
        # it, arriving next to a door and drifting one pixel sends you
        # straight back through it, and because the return trip also lands
        # you next to a door the two rooms swap forever at frame rate. A
        # bot did this ten thousand times in a row; a player would have
        # done it once and stopped playing.
        self.transition_lock = 0.0
        self.hazard_bite = 0.0
        self._hazard_warn = 0.0
        self.room_key = start_key or atlas.start
        self.discovered = {self.room_key}
        self.room = self.get_room(self.room_key)
        self.enter_room(self.room_key, first=True)

    # ------------------------------------------------------------- rooms

    def get_room(self, key):
        r = self.rooms.get(key)
        if r is None:
            r = Room(key, self.atlas.spec(key), random.Random(
                (hash(key) ^ 0x9E3779B9) & 0xFFFFFFFF))
            self.rooms[key] = r
            for (rk, side, at) in self.opened:
                if rk == key:
                    for d in r.doors:
                        if d.side == side and d.at == at:
                            self._force_open(r, d)
        return r

    def enter_room(self, key, first=False, from_side=None):
        self.room_key = key
        self.room = self.get_room(key)
        self.room.visited = True
        self.discovered.add(key)
        self.creatures = []
        self.corpses = []
        self.motes = []
        self.hostile_motes = []
        self.disturbance *= 0.35    # a new room has not heard you yet
        self.apex = None
        self.transition_lock = 0.85

        for (kind, x, y) in self.room.spawns:
            if kind not in bestiary.SPECIES:
                continue
            sp = bestiary.get(kind)
            cr = Creature(sp, (x, y), self.rng)
            if sp.behaviour == "apex":
                self.apex = cr
            self.creatures.append(cr)

        if from_side is not None and self.player is not None:
            self._place_at_door(from_side)

    def _place_at_door(self, entered_from):
        from .room import OPPOSITE
        want = OPPOSITE[entered_from]
        for d in self.room.doors:
            if d.side == want:
                cx, cy = d.center_px(self.room.w, self.room.h)
                # Well clear of the door's own trigger radius, and nudged
                # along a tile so you never land inside geometry.
                inset = 104.0
                dx = {"n": (0, inset), "s": (0, -inset),
                      "w": (inset, 0), "e": (-inset, 0)}[d.side]
                self.player.pos = [cx + dx[0], cy + dx[1]]
                self.player.vel = [dx[0] * 1.4, dx[1] * 1.4]
                return
        free = self.room.free_cells()
        if free:
            c = free[len(free) // 2]
            self.player.pos = list(self.room.px_of(*c))

    def try_transition(self):
        """Walk into an open door and you leave. No prompt — a prompt would
        be one more thing between the player and the dark."""
        if self.transition_lock > 0.0:
            return None
        p = self.player
        d = self.room.door_near(p.pos[0], p.pos[1], 44.0)
        if d is None or not d.open or d.target not in self.atlas.rooms:
            return None
        side = d.side
        self.enter_room(d.target, from_side=side)
        return d.target

    # --------------------------------------------------------- disturbance

    def add_disturbance(self, amount, pos=None):
        if amount <= 0.0:
            return
        self.disturbance = min(C.DISTURB_CAP, self.disturbance + amount)
        if pos is not None and amount > 2.0:
            if amount >= self.loudest_at * 0.6 or self.time - self.loudest_at > 4.0:
                self.loudest_point = (float(pos[0]), float(pos[1]))
                self.loudest_at = amount

    def alert_all(self, pos):
        for c in self.creatures:
            if not c.dead:
                c.alarm = max(c.alarm, 0.85)
                c.target_memory = (float(pos[0]), float(pos[1]))
                c.memory_age = 0.0

    def flash_event(self, text, pos=None):
        self.events.append([text, pos, 0.0])
        if len(self.events) > 6:
            self.events.pop(0)

    def note_feed(self, creature):
        self.flash_event("it took that and got bigger", creature.pos)

    # ------------------------------------------------- the Body's hooks

    def ambient_draw(self, pos, amount):
        if amount <= 0.0:
            return None
        return self.room.fields.draw_from(pos, amount)

    def shed_body_heat(self, pos, amount):
        """Waste heat from your organs goes into the water. It lights you,
        it warms the water you are about to drink, and it is a trail. One
        number, three consequences, no special cases."""
        self.room.fields.add_heat(pos, 34.0, amount * 0.05)
        self.add_disturbance(amount * 0.008, pos)

    def drain_nearest_flesh(self, pos, radius, exclude=None):
        """What a Leech reaches. Corpses first, then anything living —
        **including you**.

        That last clause is not symmetry for its own sake. A Lamprey's whole
        attack is a Leech, so without it the Lamprey has no intake, aborts
        its chain every time, and is a fast harmless fish. With it, the
        thing draining your reserve is doing it with an organ you can take
        off its body and use the same way, which is the rule this entire
        game is built on and which would be a lie if the creature version
        quietly ran on something else."""
        best, bd = None, radius * radius
        for c in self.corpses:
            if c.spent:
                continue
            d = (c.pos[0] - pos[0]) ** 2 + (c.pos[1] - pos[1]) ** 2
            if d < bd:
                best, bd = c, d
        if best is not None:
            return best.drain(5.5)

        living = None
        for c in self.creatures:
            if c.dead or c is exclude:
                continue
            d = (c.pos[0] - pos[0]) ** 2 + (c.pos[1] - pos[1]) ** 2
            if d < bd:
                living, bd = c, d
        if self.player is not None and self.player is not exclude:
            d = ((self.player.pos[0] - pos[0]) ** 2
                 + (self.player.pos[1] - pos[1]) ** 2)
            if d < bd:
                got = self.player.body.tap_reserve(5.0)
                self.player.take_damage(2.0, self, pos)
                return got
        if living is None:
            return None
        got = living.body.tap_reserve(5.0)
        living.hurt(3.0, self)
        return got

    def bite_target(self, pos, radius):
        best, bd = None, radius * radius
        for c in self.corpses:
            if c.spent:
                continue
            d = (c.pos[0] - pos[0]) ** 2 + (c.pos[1] - pos[1]) ** 2
            if d < bd:
                best, bd = c, d
        return best

    def nearest_corpse(self, pos, radius):
        return self.bite_target(pos, radius)

    # ------------------------------------------------------------- deaths

    def on_death(self, creature):
        sp = creature.sp
        self.kill_counts[sp.key] = self.kill_counts.get(sp.key, 0) + 1
        comp = creature.composition.copy()
        comp.clamp_nonneg()
        # A corpse is worth roughly what the thing was carrying plus a
        # dividend for the trouble. Tuned so that clearing a room refills
        # you but does not fill you: you always leave a room slightly
        # hungrier than you would like.
        comp.scale_in_place(C.CORPSE_YIELD)
        drops = list(sp.drops)
        self.corpses.append(Corpse(creature.pos, comp, drops, sp.key))
        self.add_disturbance(6.0, creature.pos)

    # ------------------------------------------------------------ emitting

    def emit(self, emissions, hostile=False):
        for em in emissions:
            shape = em.shape
            if shape.kind == "aura":
                self._apply_aura(em, hostile)
            else:
                m = Mote(em, hostile)
                (self.hostile_motes if hostile else self.motes).append(m)
            self.add_disturbance(em.loudness * 0.55, em.origin)

    def _apply_aura(self, em, hostile):
        """A near field. It has no projectile: it happens to the water
        around the caster and to everything standing in it, including the
        caster. Your own aura is a room you are inside."""
        eff = em.effect
        pos = em.origin
        r = em.shape.radius
        self.room.fields.apply_effect(eff, pos, r)
        for c in self.creatures:
            if c.dead:
                continue
            if c.distance_to(pos) <= r + c.sp.radius:
                if not hostile:
                    self._resolve_on_creature(c, eff, pos)
        if self.player is not None:
            d = math.hypot(self.player.pos[0] - pos[0], self.player.pos[1] - pos[1])
            if d <= r + 12.0:
                if hostile:
                    src = getattr(em.source, "sp", None)
                    self.player.take_damage(
                        eff.damage * C.HOSTILE_DAMAGE, self, pos,
                        cause=src.name if src else "something")
                elif eff.gentle > 0.4:
                    self.body.viability = min(
                        C.VIABILITY_MAX, self.body.viability + eff.gentle * 0.9)

    def _resolve_on_creature(self, c, eff, from_pos):
        dealt = c.take(eff, self, from_pos)
        return dealt

    # ------------------------------------------------------------- update

    def apply_hazard(self, player, dt):
        """The region, working on you.

        Below the Nursery you cannot simply survive being somewhere. Each
        region applies a continuous pressure that exactly one *standing*
        chain answers, so the question "what should I build" stops being
        "what kills fastest" and starts being "what can I live in".

        The deficit is proportional, not a switch: half the warmth you need
        takes half the cold, so a partial answer is a partial answer and
        the player can feel themselves getting closer."""
        region = self.atlas.rooms[self.room_key]["region"]
        hz = C.HAZARD.get(region, {})
        body = player.body
        body.pressure = C.PRESSURE.get(region, 1.0)
        body.clog = 0.0
        if not hz:
            self.hazard_bite = 0.0
            return

        fx = body.standing_fx
        have = fx.get(hz["answer"], 0.0)
        need = hz["need"]
        deficit = max(0.0, min(1.0, 1.0 - have / max(1e-6, need)))
        self.hazard_bite = deficit

        if deficit > 0.02:
            if "chill" in hz:
                player.take_damage(hz["chill"] * deficit * dt, self,
                                   cause="the cold")
                player.vel[0] *= (1.0 - (1.0 - hz["slow"]) * deficit * dt * 4)
                player.vel[1] *= (1.0 - (1.0 - hz["slow"]) * deficit * dt * 4)
            if "shock" in hz:
                player.take_damage(hz["shock"] * deficit * dt, self,
                                   cause="the live water")
            if "clog" in hz:
                body.clog = hz["clog"] * deficit

            self._hazard_warn -= dt
            if self._hazard_warn <= 0.0 and deficit > 0.35:
                self._hazard_warn = 14.0
                self.flash_event(hz["note"])

    def update(self, dt, player):
        self.player = player
        self.time += dt
        self.room.update(dt)
        self.apply_hazard(player, dt)

        self.transition_lock = max(0.0, self.transition_lock - dt)
        self.disturbance = max(0.0, self.disturbance - C.DISTURB_DECAY * dt)
        if self.time - self.loudest_at > 12.0:
            self.loudest_point = None

        out = []
        for c in self.creatures:
            c.update(dt, self, player, out)
        if out:
            self.emit(out, hostile=True)

        for c in self.corpses:
            c.update(dt, self.room)
        self.corpses = [c for c in self.corpses if not c.spent]
        self.creatures = [c for c in self.creatures
                          if not c.dead or c.state_time < 1.0]

        self._update_motes(dt)

        for e in self.events:
            e[2] += dt
        self.events = [e for e in self.events if e[2] < 4.5]

    def _update_motes(self, dt):
        room = self.room
        for m in self.motes:
            m.update(dt, room)
            if m.spent:
                self._burst(m, hostile=False)
        for m in self.hostile_motes:
            m.update(dt, room)
            if m.spent:
                self._burst(m, hostile=True)

        self._collide()

        self.motes = [m for m in self.motes if not m.spent]
        self.hostile_motes = [m for m in self.hostile_motes if not m.spent]

    def _burst(self, mote, hostile):
        """What a mote leaves behind when it stops. Every mote deposits into
        the water — that is not a special 'explosion', it is the same
        apply_effect the trail uses, at the point it died."""
        self.room.fields.apply_effect(mote.effect, mote.pos, mote.radius * 2.2)
        if mote.effect.caustic > 1.2:
            opened = self.room.dissolve(mote.pos[0], mote.pos[1],
                                        mote.radius * 2.0 + mote.effect.caustic * 4.0)
            if opened:
                self._check_door_dissolve(mote.pos)

    def _collide(self):
        p = self.player
        for m in self.motes:
            if m.spent or m.delay > 0.0:
                continue
            for c in self.creatures:
                if c.dead or c in m.hit:
                    continue
                r = m.radius + c.sp.radius
                dx = c.pos[0] - m.pos[0]
                dy = c.pos[1] - m.pos[1]
                if dx * dx + dy * dy <= r * r:
                    m.hit.add(c)
                    self._resolve_on_creature(c, m.effect, m.pos)
                    if m.shape.kind not in ("beam", "cone"):
                        m.spent = True
                        self._burst(m, False)
                    break

        if p is None:
            return
        for m in self.hostile_motes:
            if m.spent or m.delay > 0.0:
                continue
            r = m.radius + 11.0
            dx = p.pos[0] - m.pos[0]
            dy = p.pos[1] - m.pos[1]
            if dx * dx + dy * dy <= r * r:
                src = getattr(m.source, "sp", None)
                p.take_damage(m.effect.damage * C.HOSTILE_DAMAGE, self, m.pos,
                              cause=src.name if src else "something")
                if abs(m.effect.force) > 30.0:
                    d = math.hypot(dx, dy) + 1e-6
                    k = m.effect.force / 90.0
                    p.vel[0] += dx / d * k
                    p.vel[1] += dy / d * k
                m.spent = True
                self._burst(m, True)

    # -------------------------------------------------------------- doors

    def _check_door_dissolve(self, pos):
        d = self.room.door_near(pos[0], pos[1], 96.0)
        if d is not None and not d.open and d.lock in (LOCK_GENTLE, LOCK_CAUSTIC):
            self._force_open(self.room, d)
            self.flash_event("it has stopped holding itself shut")

    def try_open_door(self, effect, pos):
        """Doors answer to statements about your body, not to keys. Each
        lock names one capability, and every one of them is a thing you can
        only do by understanding the humour rules well enough to build for
        it on purpose."""
        d = self.room.door_near(pos[0], pos[1], 120.0)
        if d is None or d.open:
            return False
        ok = False
        if d.lock == LOCK_GENTLE:
            ok = effect.gentle > 1.2
        elif d.lock == LOCK_CAUSTIC:
            ok = effect.caustic > 2.4 or effect.gentle > 1.6
        elif d.lock == LOCK_COLD:
            ok = effect.freezes
        elif d.lock == LOCK_FORCE:
            ok = abs(effect.force) > 900.0
        elif d.lock == LOCK_RISE:
            ok = False      # opened by getting there, not by shooting it
        if ok:
            self._force_open(self.room, d)
            self.flash_event("it has opened")
            return True
        return False

    def _force_open(self, room, door):
        from .room import WATER
        door.open = True
        for (tx, ty) in door.tiles(room.w, room.h):
            room.tiles[ty][tx] = WATER
        self.opened.add((room.key, door.side, door.at))

    # -------------------------------------------------------------- intel

    def passable(self, room_key, door_spec):
        """Whether a door in the atlas can currently be walked through.
        Shared by the map screen and the playtest bots so that neither can
        disagree with the world about where you can actually go."""
        lock = door_spec["lock"]
        if lock is None or lock == "rise":
            return True
        return (room_key, door_spec["side"], door_spec["at"]) in self.opened

    def threat_level(self):
        """What the screen edge is doing. 0..1."""
        base = self.disturbance / C.DISTURB_CAP
        if self.apex is not None and not self.apex.dead:
            from ..creatures import HUNT, STRIKE
            if self.apex.state in (HUNT, STRIKE):
                base = max(base, 0.55 + 0.45 * self.apex.alarm)
        return min(1.0, base)

    def visible_creatures(self, sight):
        out = []
        p = self.player
        for c in self.creatures:
            d = c.distance_to(p.pos)
            vis = self.room.fields.visibility_along(p.pos, c.pos)
            lit = (sight + c.sp.glow * 220.0) * vis
            if d < lit:
                out.append((c, min(1.0, (lit - d) / max(1.0, lit) * 2.0)))
        return out
