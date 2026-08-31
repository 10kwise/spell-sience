"""The Belfry: one room, and everything that happens in it.

The old build's arena was a twin-stick shooter that happened to be running a
wave simulation. This one is built the other way round: every verb here is
short, committed and readable, and the simulation decides what each one is
worth rather than whether it happens at all.

Four verbs. That is the entire control surface:

    move        WASD, snappy, no acceleration to fight
    strike      one button - tap tolls, hold swells, release tolls big
    dash        i-frames, cancels anything, the answer to every wind-up
    swap        two bells, instantly

Aiming is gone. A ring is omnidirectional, so what the player is choosing is
*distance*, and distance is exactly what the note ladder means. That single
substitution is what turns "learn the frequency table" into "stand in the
right place", which is a thing hands can learn.
"""

import math
import random

import pygame

from . import audio, notes
from .bell import survived
from .foes import (
    SLAM_SPEED, CONTACT_COOLDOWN, CONTACT_DAMAGE,
    Deadweight, Foe, Glasswing, GreatBell, Husk, Overtone, Twin, make_twins,
)
from .notes import N_NOTES
from .rings import Ring, RING_THICKNESS, cancel

# Drawn canvas px -> world px. The bell is not decoration on the avatar, it
# *is* the avatar: its size is its note, so the ladder has to be readable off
# the player's own body at a glance. A BOURDON is visibly four times a CHIME
# here, because it is.
BELL_WORLD_SCALE = 1.0

PLAYER_RADIUS = 15.0
PLAYER_SPEED = 300.0
PLAYER_ACCEL = 14.0        # high, so the character starts and stops *now*
PLAYER_MAX_HP = 100.0

# The swing. Short enough to feel like a strike rather than a cast, long
# enough that there is a real frame of anticipation to read - the whole
# reason a hit lands with weight is that something happened just before it.
WINDUP = 0.085
RECOVER = 0.15

DASH_SPEED = 980.0
DASH_TIME = 0.155
DASH_COOLDOWN = 0.58
DASH_IFRAMES = 0.19

# Rings the player is standing inside do not shove the player, but hostile
# ones do, and being knocked about by sound is most of what makes the Great
# Bell frightening.
HOSTILE_RING_DAMAGE = 16.0
HOSTILE_RING_SCALE = 5.2


class Player:
    def __init__(self, pos, bells):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(0, 0)
        self.radius = PLAYER_RADIUS
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.bells = bells
        self.active = 0
        self.face = pygame.Vector2(1, 0)

        self.swing = 0.0          # >0 winding up
        self.recover = 0.0
        self.swinging = False
        self.pending_beat = False
        self.holding = False
        self.swelling = False

        self.dash_t = 0.0
        self.dash_cd = 0.0
        self.dash_dir = pygame.Vector2(1, 0)
        self.iframes = 0.0

        self.hurt = 0.0
        self.hit_cd = 0.0
        # Consecutive on-beat strikes. The mastery curve, and the only number
        # in the game that goes up because of *timing* rather than because of
        # what was drawn.
        self.chorus = 0
        self.chorus_t = 0.0
        self.last_beat_error = 0.0

    @property
    def bell(self):
        return self.bells[self.active] if self.bells else None

    @property
    def chorus_mult(self) -> float:
        steps = notes.CHORUS_STEPS
        return steps[min(len(steps) - 1, self.chorus)]

    @property
    def busy(self) -> bool:
        return self.swing > 0.0 or self.recover > 0.0

    # --------------------------------------------------------------- verbs

    def press(self) -> bool:
        """Hammer down. Returns whether the strike actually started."""
        self.holding = True
        b = self.bell
        if b is None or b.is_empty or self.busy or self.dash_t > 0:
            return False
        if b.cracked:
            return False
        self.pending_beat = b.on_beat()
        self.last_beat_error = b.beat_offset()
        b.strike()
        self.swing = WINDUP
        self.swinging = True
        return True

    def release(self):
        self.holding = False
        if self.swelling:
            self.swelling = False
            b = self.bell
            if b is not None:
                b.set_swell(False)
                # Letting go is itself a strike: everything the swell built
                # up leaves at once, as one ring.
                if not self.busy and not b.cracked:
                    self.pending_beat = True
                    b.strike()
                    self.swing = WINDUP
                    self.swinging = True

    def try_dash(self, move) -> bool:
        if self.dash_cd > 0.0:
            return False
        d = pygame.Vector2(move)
        if d.length_squared() < 1e-6:
            d = pygame.Vector2(self.face)
        self.dash_dir = d.normalize()
        self.dash_t = DASH_TIME
        self.dash_cd = DASH_COOLDOWN
        self.iframes = DASH_IFRAMES
        # A dash cancels everything, which is what makes it the universal
        # answer and why every wind-up in the game is fair.
        self.swing = 0.0
        self.recover = 0.0
        self.swinging = False
        self.swelling = False
        if self.bell is not None:
            self.bell.set_swell(False)
        return True

    def swap(self, index):
        if not (0 <= index < len(self.bells)) or index == self.active:
            return False
        if self.bell is not None:
            self.bell.set_swell(False)
            self.bell.silence()
        self.swelling = False
        self.active = index
        return True

    def take_hit(self, amount):
        if self.iframes > 0.0:
            return False
        self.hp -= amount
        self.hurt = 1.0
        self.chorus = 0          # the groove is something you can lose
        return True

    # -------------------------------------------------------------- update

    def update(self, dt, move, arena):
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.hurt = max(0.0, self.hurt - dt * 2.6)
        self.hit_cd = max(0.0, self.hit_cd - dt)
        self.chorus_t = max(0.0, self.chorus_t - dt)

        if self.dash_t > 0.0:
            self.dash_t -= dt
            self.pos += self.dash_dir * DASH_SPEED * dt
        else:
            target = move.normalize() * PLAYER_SPEED if move.length_squared() > 1e-9 else pygame.Vector2(0, 0)
            self.vel += (target - self.vel) * min(1.0, PLAYER_ACCEL * dt)
            self.pos += self.vel * dt

        if move.length_squared() > 1e-9:
            self.face = move.normalize()

        self.pos.x = max(self.radius, min(arena.width - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(arena.height - self.radius, self.pos.y))

        b = self.bell
        if b is not None and not b.is_empty:
            b.advance(dt)
            if b.cracked and self.swelling:
                self.swelling = False
                b.set_swell(False)
        for other in self.bells:
            # The bells you are not holding keep ringing down rather than
            # freezing, so swapping away is not a way to bank a charge.
            if other is not b and not other.is_empty:
                other.advance(dt)


class Belfry:
    """One room: the floor, the things on it, and the sound in the air."""

    def __init__(self, player, spec, seed=None, on_event=None):
        self.rng = random.Random(seed)
        self.width = spec.get("width", 1500)
        self.height = spec.get("height", 1000)
        self.spec = spec
        self.player = player
        self.player.pos = pygame.Vector2(self.width / 2, self.height - 190)
        self.player.vel = pygame.Vector2(0, 0)

        self.foes = []
        self.rings = []
        self.hostile = []
        self.shards = []
        self.marks = []            # transient visual events for the renderer
        self.floor_notes = []      # note-coloured stains where rings landed

        self.time = 0.0
        self.cleared = False
        self.failed = False
        self.shake = 0.0
        self.hitstop = 0.0
        self.banner = spec.get("name", "")
        self.banner_t = 2.6
        self.lesson = ""
        self.lesson_t = 0.0
        self.announce = None
        self.announce_t = 0.0
        self.on_event = on_event or (lambda *a, **k: None)
        self.seen = set()

        self._spawn(spec)

    # ------------------------------------------------------------ spawning

    def _spawn(self, spec):
        for kind, count in spec.get("foes", {}).items():
            for _ in range(count):
                pos = self._spawn_point()
                if kind == "husk":
                    self.foes.append(Husk(pos))
                elif kind == "glasswing":
                    self.foes.append(Glasswing(pos))
                elif kind == "deadweight":
                    self.foes.append(Deadweight(pos))
                elif kind == "overtone":
                    self.foes.append(Overtone(pos))
                elif kind == "twin":
                    self.foes.extend(make_twins(pos))
                elif kind == "greatbell":
                    self.foes.append(GreatBell(pygame.Vector2(self.width / 2, 260),
                                               spec.get("phrase", [1, 2, 1])))

    def _spawn_point(self):
        m = 190
        return pygame.Vector2(
            self.rng.uniform(m, self.width - m),
            self.rng.uniform(m, self.height * 0.55),
        )

    # ------------------------------------------------------ world callbacks

    def pan(self, pos) -> float:
        return max(0.0, min(1.0, (pos.x - self.player.pos.x) / 900.0 + 0.5))

    def hum_volume(self, pos) -> float:
        d = (pos - self.player.pos).length()
        return max(0.05, 0.26 * (1.0 - min(1.0, d / 1100.0)))

    def slam(self, pos, power):
        self.mark("slam", pos, (255, 236, 200), power)
        self.shake = min(1.4, self.shake + 0.5 * power)
        self.hitstop = max(self.hitstop, 0.05 * power)
        audio.slam(self.pan(pos), power)

    def shatter(self, foe):
        """The payoff frame. Everything the game has been building toward
        lands here, so it gets the freeze, the shake and the brightest thing
        on screen."""
        self.mark("shatter", foe.pos, foe.color if foe.crackable else (220, 226, 236), 1.0)
        self.shake = min(1.8, self.shake + 0.85)
        self.hitstop = max(self.hitstop, 0.115)
        audio.shatter(max(0.0, foe.note), self.pan(foe.pos))
        for _ in range(16 + int(foe.radius)):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(160.0, 640.0)
            self.shards.append([
                pygame.Vector2(foe.pos), pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                self.rng.uniform(0.45, 0.95), foe.color if foe.crackable else (215, 220, 230),
            ])
        self.on_event("shatter", foe)

    def hostile_ring(self, pos, note, power=1.0, announce=None, source=None):
        bands = [0.0] * N_NOTES
        bands[max(0, min(N_NOTES - 1, int(note)))] = power * HOSTILE_RING_SCALE
        # Hostile rings pull. So a bell wound the ordinary way answers them
        # and a bell wound backwards feeds them - a real consequence for a
        # choice the player makes with the direction of one drag.
        self.hostile.append(Ring(pos, bands, push=-1.0, hostile=True, source=source))
        audio.toll(note, 0.9, self.pan(pos))
        if announce is not None:
            self.announce = announce
            self.announce_t = 1.6

    def boss_opened(self, boss):
        self.mark("open", boss.pos, (255, 240, 210), 1.0)
        self.shake = min(1.6, self.shake + 0.7)
        self.hitstop = max(self.hitstop, 0.1)
        self.announce = None
        self.say("its mouth is open - ring it now")

    def mark(self, kind, pos, color, power=1.0, note=0.0):
        self.marks.append({"kind": kind, "pos": pygame.Vector2(pos), "color": color,
                           "power": power, "t": 0.0, "note": note})

    def say(self, text, seconds=3.4):
        self.lesson = text
        self.lesson_t = seconds

    # --------------------------------------------------------------- update

    def update(self, dt, move, wants_strike, holding, wants_dash, swap_to):
        self.time += dt
        self.banner_t = max(0.0, self.banner_t - dt)
        self.lesson_t = max(0.0, self.lesson_t - dt)
        self.announce_t = max(0.0, self.announce_t - dt)
        self.shake = max(0.0, self.shake - dt * 3.4)

        p = self.player

        if swap_to is not None and p.swap(swap_to):
            audio.ui(swap_to > 0)
        if wants_dash and p.try_dash(move):
            audio.dash(0.5)
            self.mark("dash", p.pos, (180, 210, 255), 1.0)
        if wants_strike:
            p.press()
        if not holding and p.holding:
            p.release()
        p.holding = holding

        p.update(dt, move, self)
        self._advance_swing(dt)
        self._first_sight()

        for f in self.foes:
            f.update(dt, self, p, self)

        self._rings(dt)
        self._bodies(dt)
        self._shards(dt)
        self.marks = [m for m in self.marks if m["t"] < 1.0]
        for m in self.marks:
            m["t"] += dt * 2.6
        self.floor_notes = [s for s in self.floor_notes if s[2] > 0.0]
        for s in self.floor_notes:
            s[2] -= dt * 0.5

        self.foes = [f for f in self.foes if not f.dead]
        if not self.foes and not self.cleared:
            self.cleared = True
        if p.hp <= 0.0 and not self.failed:
            self.failed = True

    def _first_sight(self):
        """Say a thing's lesson the first time it is ever met, once, and
        never again. Everything else the game teaches, it teaches by being
        played."""
        for f in self.foes:
            if f.kind in self.seen:
                continue
            if (f.pos - self.player.pos).length() < 780.0:
                self.seen.add(f.kind)
                if f.lesson:
                    self.say(f"{f.label.upper()} - {f.lesson}", 4.6)
                self.on_event("met", f)

    def _advance_swing(self, dt):
        """The swing state machine, and the one frame where the ring is
        born."""
        p = self.player
        if p.swing > 0.0:
            p.swing -= dt
            if p.swing <= 0.0:
                self._contact()
                p.recover = RECOVER
                p.swinging = False
        elif p.recover > 0.0:
            p.recover -= dt

        # Keeping the hammer on the metal past the recovery is the swell.
        #
        # Written as its own condition rather than as a tail of the recovery
        # branch, which is what it was first: that version only ever started
        # a swell in the frame a recovery ended, so holding the button
        # through a dash - or holding it without an initial tap at all -
        # silently did nothing, and the one enemy that requires the swell was
        # unbeatable while the meter sat at zero looking fine.
        if (not p.busy and p.holding and not p.swelling and p.dash_t <= 0.0):
            b = p.bell
            if b is not None and not b.cracked and not b.is_empty:
                p.swelling = True
                b.set_swell(True)

    def _contact(self):
        """Hammer meets metal. Take everything the bell has radiated since
        the last strike and throw it as one ring."""
        p = self.player
        b = p.bell
        if b is None or b.is_empty:
            return
        bands, total = b.take_output()
        if total <= 1e-6:
            return

        on_beat = p.pending_beat
        if on_beat:
            p.chorus = min(len(notes.CHORUS_STEPS) - 1, p.chorus + 1)
            p.chorus_t = 1.2
        else:
            p.chorus = 0
            bands = [x * notes.OFF_BEAT_SCALE for x in bands]

        ring = Ring(
            p.pos, bands, push=b.push, hostile=False,
            bias=b.bias, bias_strength=1.0 if b.bias.length_squared() > 1e-6 else 0.0,
            chorus=p.chorus_mult, on_beat=on_beat,
        )
        self.rings.append(ring)
        self.shake = min(1.2, self.shake + 0.1 + 0.22 * min(1.0, total / 40.0))
        audio.toll(ring.note, min(1.0, 0.25 + total / 45.0), 0.5)
        self.mark("toll", p.pos, ring.color_at(0.0), 1.0 if on_beat else 0.5, ring.note)
        self.floor_notes.append([pygame.Vector2(p.pos), ring.color_at(0.0), 1.0])

    # ---------------------------------------------------------------- rings

    def _rings(self, dt):
        p = self.player
        for r in self.rings:
            r.update(dt)
        for r in self.hostile:
            r.update(dt)

        answered = []
        for pos, amount, opposed in cancel(self.rings, self.hostile, answered):
            self.mark("cancel", pos, (226, 240, 255) if opposed else (255, 168, 92),
                      min(1.0, amount * 0.3))
            if opposed:
                self.shake = min(1.4, self.shake + 0.24)
                self.hitstop = max(self.hitstop, 0.045)
                audio.tick(True)

        for boss in answered:
            # Only a phrase note the boss itself called counts as an answer.
            # Crediting any cancellation would let an Overtone's tolls open
            # the boss, which reads as the game losing track of its own rules.
            boss.answered_toll(self)

        for r in self.rings:
            if r.spent:
                continue
            for f in self.foes:
                if f.dead or id(f) in r.hit:
                    continue
                if not r.crosses(f.pos, f.radius):
                    continue
                r.hit.add(id(f))
                before = f.crack
                pure = f.take_ring(r, self)
                gained = f.crack - before
                self._hit_feedback(f, r, pure, gained)

        for r in self.hostile:
            if r.spent or id(p) in r.hit:
                continue
            if not r.crosses(p.pos, p.radius):
                continue
            r.hit.add(id(p))
            arrived = sum(r.spectrum_at(p.pos))
            if arrived <= 1e-6:
                continue
            if p.take_hit(HOSTILE_RING_DAMAGE * min(2.0, arrived / 3.0)):
                p.vel += r.shove_at(p.pos) * 0.5
                audio.hurt(0.5)
                self.shake = min(1.5, self.shake + 0.5)

        self.rings = [r for r in self.rings if not r.spent]
        self.hostile = [r for r in self.hostile if not r.spent]

    def _hit_feedback(self, foe, ring, pure, gained):
        """The single most important teaching signal in the game.

        A dull, low thud means the right idea in the wrong octave. A bright
        crack means they found it. The player is told which of those just
        happened in three senses at once - the flash, the freeze, and the
        pitch - so nobody has to read a number to know whether that worked.
        """
        if not foe.crackable:
            self.mark("thud", foe.pos, (150, 155, 165), 0.5)
            return
        if pure > 0.42:
            self.mark("crack", foe.pos, foe.color, min(1.0, 0.4 + pure), foe.note)
            self.shake = min(1.5, self.shake + 0.18 + 0.3 * pure)
            self.hitstop = max(self.hitstop, 0.02 + 0.05 * pure)
        else:
            self.mark("thud", foe.pos, (140, 148, 160), 0.35 + pure)

    # --------------------------------------------------------------- bodies

    def _bodies(self, dt):
        """Foes are solid to each other, and hitting each other hard enough
        cracks both. This is what turns a shove into a weapon rather than a
        way to buy a second and a half."""
        p = self.player
        n = len(self.foes)
        for i in range(n):
            a = self.foes[i]
            if a.dead:
                continue
            for j in range(i + 1, n):
                b = self.foes[j]
                if b.dead:
                    continue
                delta = b.pos - a.pos
                d = delta.length()
                overlap = a.radius + b.radius - d
                if overlap <= 0.0 or d < 1e-6:
                    continue
                nrm = delta / d
                closing = (a.vel - b.vel).dot(nrm)
                total_mass = a.mass + b.mass
                a.pos -= nrm * overlap * (b.mass / total_mass)
                b.pos += nrm * overlap * (a.mass / total_mass)
                a.vel -= nrm * closing * (b.mass / total_mass) * 1.3
                b.vel += nrm * closing * (a.mass / total_mass) * 1.3
                if closing > SLAM_SPEED:
                    at = a.pos + nrm * a.radius
                    a.take_slam(closing, self, at)
                    b.take_slam(closing, self, at)

            delta = p.pos - a.pos
            d = delta.length()
            if d < a.radius + p.radius and p.hit_cd <= 0.0:
                if p.take_hit(CONTACT_DAMAGE):
                    p.hit_cd = CONTACT_COOLDOWN
                    if d > 1e-6:
                        p.vel += delta / d * 380.0
                    audio.hurt(0.5)
                    self.shake = min(1.4, self.shake + 0.4)

    def _shards(self, dt):
        alive = []
        for s in self.shards:
            s[2] -= dt
            if s[2] <= 0.0:
                continue
            s[0] += s[1] * dt
            s[1] *= 0.90 ** (dt * 60)
            alive.append(s)
        self.shards = alive
