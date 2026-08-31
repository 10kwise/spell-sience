"""The Belfry: one room, and everything that happens in it.

Four verbs, and that is the entire control surface:

    move        WASD, snappy, no acceleration to fight
    strike      one button - tap tolls, hold swells, release tolls big
    dash        i-frames, cancels anything, the answer to every wind-up
    swap        bells, instantly

Aiming is gone. A ring is omnidirectional, so what the player chooses is
*distance*, and distance is exactly what the note ladder means.

The threat model is the part that changed most. The first cut gave the
player 100 health against 13-point contact damage on a 0.8s cooldown, which
means the correct play against every enemy in the game was to stand in it.
Now three or four connected attacks kill - and **shattering something on its
note heals you, while slamming it into a wall does not.**

That pairing is the whole economy. The game pays for the play it wants to
teach instead of punishing the play it wants to discourage: force stays a
real kill path and a real answer to dead metal, but it does not sustain you,
so a player who never learns to tune bleeds out slowly no matter how well
they shove.
"""

import math
import random

import pygame

from . import audio, fx, notes
from .bell import survived
from .foes import (
    SLAM_SPEED, CONTACT_COOLDOWN, CONTACT_DAMAGE,
    Deadweight, Foe, Glasswing, GreatBell, Husk, Overtone, Twin, make_twins,
)
from .notes import N_NOTES
from .rings import Ring, RING_THICKNESS, cancel

# Drawn canvas px -> world px. The bell is not decoration on the avatar, it
# *is* the avatar: its size is its note, so the ladder has to be readable off
# the player's own body at a glance.
BELL_WORLD_SCALE = 1.0

PLAYER_RADIUS = 15.0
PLAYER_SPEED = 310.0
PLAYER_ACCEL = 16.0        # high, so the character starts and stops *now*
PLAYER_MAX_HP = 100.0

# What good play is worth. A resonant shatter is the only thing in the game
# that gives health back, so the sustainable way to play is the correct one -
# and a run of slams, which is always available and always legal, quietly
# costs you the room.
#
# Seven, not eleven. At eleven a competent bot finished nine waves out of
# eleven on exactly full health: the heal was not a reward for good play, it
# was an eraser for the entire threat layer, and the game read as easy for
# precisely the reason it was designed to feel tense. It has to be worth
# chasing and it must not cover a bad room.
SHATTER_HEAL = 7.0

# The swing. Short enough to feel like a strike rather than a cast, long
# enough that there is a real frame of anticipation to read.
WINDUP = 0.075
RECOVER = 0.14

DASH_SPEED = 1020.0
DASH_TIME = 0.15
# The dash has to be a resource, not a stance. At a 0.5s cooldown against
# 0.22s of invulnerability a player is untouchable nearly half the time, and
# every wind-up in the game becomes free to ignore. At 0.75 it covers one
# threat, and choosing *which* one is the decision the telegraphs are for.
DASH_COOLDOWN = 0.75
DASH_IFRAMES = 0.22

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

        self.swing = 0.0
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
        self.chorus = 0
        self.last_beat_error = 0.0
        self.tolls = 0

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
        self.holding = True
        b = self.bell
        if b is None or b.is_empty or self.busy or self.dash_t > 0 or b.cracked:
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
        self.swing = self.recover = 0.0
        self.swinging = self.swelling = False
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
        if self.iframes > 0.0 or self.hit_cd > 0.0:
            return False
        self.hp -= amount
        self.hurt = 1.0
        self.hit_cd = 0.32          # brief mercy so one event cannot double-dip
        self.chorus = 0             # the groove is something you can lose
        return True

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    # -------------------------------------------------------------- update

    def update(self, dt, move, arena):
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.hurt = max(0.0, self.hurt - dt * 2.6)
        self.hit_cd = max(0.0, self.hit_cd - dt)

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
            # Bells you are not holding keep ringing down rather than
            # freezing, so swapping away is not a way to bank a charge.
            if other is not b and not other.is_empty:
                other.advance(dt)


class Belfry:
    """One room: the floor, the things on it, and the sound in the air."""

    def __init__(self, player, spec, seed=None, on_event=None):
        self.rng = random.Random(seed)
        self.width = spec.get("width", 1700)
        self.height = spec.get("height", 1150)
        self.spec = spec
        self.player = player
        self.player.pos = pygame.Vector2(self.width / 2, self.height - 200)
        self.player.vel = pygame.Vector2(0, 0)

        self.foes = []
        self.rings = []
        self.hostile = []
        self.marks = []
        self.beams = []            # live standing waves (Twins)
        self.waves = []            # expanding damage shockwaves
        self.fx = fx.Fx(self.rng)

        self.time = 0.0
        self.cleared = False
        self.failed = False
        self.shake = 0.0
        self.hitstop = 0.0
        self.banner = spec.get("name", "")
        self.banner_t = 2.4
        self.lesson = ""
        self.lesson_t = 0.0
        self.announce = None
        self.announce_t = 0.0
        self.on_event = on_event or (lambda *a, **k: None)
        self.seen = set()
        self.cracked_bells = set()

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
                    self.foes.append(GreatBell(
                        pygame.Vector2(self.width / 2, 280),
                        spec.get("phrase", [1, 2, 1])))
        # Spread the clocks. Identical foes starting in phase attack as one
        # wall; staggered, they arrive as a pattern, and a pattern is a thing
        # a player can play against.
        by_kind = {}
        for f in self.foes:
            by_kind.setdefault(f.kind, []).append(f)
        for group in by_kind.values():
            for i, f in enumerate(group):
                f.clock = f.period * (i / max(1, len(group)))

    def _spawn_point(self):
        m = 200
        return pygame.Vector2(
            self.rng.uniform(m, self.width - m),
            self.rng.uniform(m, self.height * 0.55),
        )

    # ------------------------------------------------------ world callbacks

    def pan(self, pos) -> float:
        return max(0.0, min(1.0, (pos.x - self.player.pos.x) / 900.0 + 0.5))

    def hum_volume(self, pos) -> float:
        d = (pos - self.player.pos).length()
        return max(0.05, 0.24 * (1.0 - min(1.0, d / 1100.0)))

    def mark(self, kind, pos, color, power=1.0, note=0.0):
        self.marks.append({"kind": kind, "pos": pygame.Vector2(pos), "color": color,
                           "power": power, "t": 0.0, "note": note})

    def say(self, text, seconds=3.6):
        self.lesson = text
        self.lesson_t = seconds

    # --- things foes do to the player ---------------------------------

    def melee(self, foe, damage, reach, duration, kind="lunge"):
        """A committed body attack: it hurts anything it passes through for
        `duration`, so dodging it means not being on the line, not
        out-reacting a single frame."""
        self.beams.append({"foe": foe, "damage": damage, "reach": reach,
                           "t": duration, "kind": kind, "hit": False})
        self.fx.sparks(foe.pos, 10, foe.color, direction=foe.aim, spread=1.0,
                       speed=(160, 420))

    def shockwave(self, pos, radius, damage, color, push=400.0):
        self.waves.append({"pos": pygame.Vector2(pos), "r": 0.0, "max": radius,
                           "damage": damage, "color": color, "push": push,
                           "hit": False})
        self.shake = min(1.5, self.shake + 0.4)
        self.fx.burst(pos, 16, color, speed=(200, 520), life=(0.2, 0.45),
                      size=(2, 5))
        audio.slam(self.pan(pos), 0.7)

    def beam(self, a, b, width, damage, color):
        self.beams.append({"a": pygame.Vector2(a), "b": pygame.Vector2(b),
                           "damage": damage, "reach": width, "t": 0.34,
                           "kind": "beam", "hit": False})
        mid = (pygame.Vector2(a) + pygame.Vector2(b)) * 0.5
        self.fx.burst(mid, 14, color, speed=(120, 380), life=(0.2, 0.5), size=(2, 5))

    def hostile_ring(self, pos, note, power=1.0, announce=None, source=None,
                     damage=22.0):
        bands = [0.0] * N_NOTES
        bands[max(0, min(N_NOTES - 1, int(note)))] = power * HOSTILE_RING_SCALE
        # Hostile rings pull. So a bell wound the ordinary way answers them
        # and a bell wound backwards feeds them - a real consequence for a
        # choice the player makes with the direction of one drag.
        r = Ring(pos, bands, push=-1.0, hostile=True, source=source)
        r.damage = damage
        self.hostile.append(r)
        audio.toll(note, 0.9, self.pan(pos))
        self.fx.glint(pos, notes.NOTE_COLORS[int(note)], 34, 0.3)
        if announce is not None:
            self.announce = announce
            self.announce_t = 1.7

    def boss_opened(self, boss):
        self.mark("open", boss.pos, (255, 240, 210), 1.0)
        self.shake = min(1.6, self.shake + 0.8)
        self.hitstop = max(self.hitstop, 0.12)
        self.fx.glass(boss.pos, 22, boss.color)
        self.announce = None
        self.say("its mouth is open - ring it now")

    # --- things the player does ---------------------------------------

    def slam(self, pos, power):
        self.mark("slam", pos, (255, 236, 200), power)
        self.shake = min(1.4, self.shake + 0.5 * power)
        self.hitstop = max(self.hitstop, 0.05 * power)
        self.fx.burst(pos, int(8 + 14 * power), (255, 232, 190),
                      speed=(180, 620), life=(0.18, 0.45), size=(2, 5))
        self.fx.smoke(pos, 4)
        audio.slam(self.pan(pos), power)

    def shatter(self, foe, resonant=True):
        """The payoff frame. Everything the game builds toward lands here."""
        col = foe.color if foe.crackable else (220, 226, 236)
        self.mark("shatter", foe.pos, col, 1.0)
        self.shake = min(1.9, self.shake + 0.9)
        self.hitstop = max(self.hitstop, 0.13)
        audio.shatter(max(0.0, foe.note), self.pan(foe.pos))
        self.fx.glass(foe.pos, 18 + int(foe.radius), col)
        self.fx.glint(foe.pos, (255, 255, 250), 60, 0.3)
        self.fx.wash((255, 255, 250), 0.5, 0.07)
        if resonant and foe.crackable:
            # Only a shatter on the note heals. Force kills the thing; it
            # does not feed you.
            self.player.heal(SHATTER_HEAL)
            self.fx.implode(self.player.pos, 12, (170, 255, 200), 90.0, 0.3)
        self.on_event("shatter", foe)

    def bell_cracked(self, bell):
        """The player cooked a bell. Anything nearby that eats greed, eats."""
        p = self.player
        self.fx.burst(p.pos, 20, (200, 90, 70), speed=(120, 460), life=(0.3, 0.7),
                      size=(3, 7), kind=fx.SHARD)
        self.fx.smoke(p.pos, 8, (120, 70, 60))
        self.fx.vignette((210, 90, 60), 0.9, 0.6)
        self.shake = min(1.5, self.shake + 0.6)
        audio.crack(0.5)
        self.say("your bell cracked - it will not sound until it cools", 2.6)
        for f in self.foes:
            if isinstance(f, Overtone) and (f.pos - p.pos).length() < f.PULL_RANGE:
                f.feed(self)

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
            self.fx.burst(p.pos, 10, (170, 205, 255), speed=(60, 240),
                          life=(0.15, 0.3), size=(2, 4),
                          direction=-p.dash_dir, spread=1.4)
        if wants_strike:
            p.press()
        if not holding and p.holding:
            p.release()
        p.holding = holding

        p.update(dt, move, self)
        self._watch_bells()
        self._advance_swing(dt)
        self._first_sight()

        if p.dash_t > 0.0:
            self.fx.trail(p.pos, p.vel, (150, 195, 255), 2)
        if p.swelling and p.bell is not None:
            b = p.bell
            if self.rng.random() < 0.5:
                self.fx.implode(p.pos, 1, b.color, 120.0, 0.28)

        for f in self.foes:
            f.update(dt, self, p, self)
            if f.winding and self.rng.random() < 0.25:
                self.fx.implode(f.pos, 1, (255, 208, 150), f.radius + 46, 0.25)

        self._rings(dt)
        self._hazards(dt)
        self._bodies(dt)
        self.fx.update(dt)

        self.marks = [m for m in self.marks if m["t"] < 1.0]
        for m in self.marks:
            m["t"] += dt * 2.6

        self.foes = [f for f in self.foes if not f.dead]
        if not self.foes and not self.cleared:
            self.cleared = True
        if p.hp <= 0.0 and not self.failed:
            self.failed = True

    def _watch_bells(self):
        """Notice the frame a bell goes over the edge, exactly once."""
        for b in self.player.bells:
            key = id(b)
            if b.cracked and key not in self.cracked_bells:
                self.cracked_bells.add(key)
                self.bell_cracked(b)
            elif not b.cracked:
                self.cracked_bells.discard(key)

    def _first_sight(self):
        """Say a thing's lesson the first time it is ever met, once."""
        for f in self.foes:
            if f.kind in self.seen:
                continue
            if (f.pos - self.player.pos).length() < 820.0:
                self.seen.add(f.kind)
                if f.lesson:
                    self.say(f"{f.label.upper()} - {f.lesson}", 4.8)
                self.on_event("met", f)

    def _advance_swing(self, dt):
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
        if not p.busy and p.holding and not p.swelling and p.dash_t <= 0.0:
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
        else:
            p.chorus = 0
            bands = [x * notes.OFF_BEAT_SCALE for x in bands]

        ring = Ring(
            p.pos, bands, push=b.push, hostile=False,
            bias=b.bias, bias_strength=1.0 if b.bias.length_squared() > 1e-6 else 0.0,
            chorus=p.chorus_mult, on_beat=on_beat,
        )
        self.rings.append(ring)
        p.tolls += 1
        self.shake = min(1.2, self.shake + 0.08 + 0.24 * min(1.0, total / 40.0))
        audio.toll(ring.note, min(1.0, 0.25 + total / 45.0), 0.5)
        self.mark("toll", p.pos, ring.color_at(0.0), 1.0 if on_beat else 0.5, ring.note)
        col = ring.color_at(0.0)
        self.fx.burst(p.pos, 12 if on_beat else 5, col, speed=(240, 700),
                      life=(0.12, 0.3), size=(2, 5))
        if on_beat:
            self.fx.glint(p.pos, (255, 250, 240), 30, 0.22)

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
                self.shake = min(1.4, self.shake + 0.3)
                self.hitstop = max(self.hitstop, 0.05)
                audio.tick(True)
                self.fx.burst(pos, 16, (230, 244, 255), speed=(180, 560),
                              life=(0.15, 0.4), size=(2, 5))
                self.fx.glint(pos, (255, 255, 255), 26, 0.2)

        for boss in answered:
            boss.answered_toll(self)

        for r in self.rings:
            if r.spent:
                continue
            for f in self.foes:
                if f.dead or id(f) in r.hit or not r.crosses(f.pos, f.radius):
                    continue
                r.hit.add(id(f))
                before = f.crack
                pure = f.take_ring(r, self)
                self._hit_feedback(f, r, pure, f.crack - before)

        for r in self.hostile:
            if r.spent or id(p) in r.hit or not r.crosses(p.pos, p.radius):
                continue
            r.hit.add(id(p))
            arrived = sum(r.spectrum_at(p.pos))
            if arrived <= 1e-6:
                continue
            if p.take_hit(r.damage):
                p.vel += r.shove_at(p.pos) * 0.5
                self._hurt_fx(r.color_at(r.r))

        self.rings = [r for r in self.rings if not r.spent]
        self.hostile = [r for r in self.hostile if not r.spent]

    def _hit_feedback(self, foe, ring, pure, gained):
        """The most important teaching signal in the game.

        A dull grey puff means the right idea in the wrong octave. A bright
        spray of the target's own colour means they found it. The difference
        is a different *kind* of particle, not a different hue on the same
        circle, so it is readable at a glance and across a room.
        """
        if not foe.crackable:
            self.mark("thud", foe.pos, (150, 155, 165), 0.5)
            self.fx.thud(foe.pos)
            return
        if pure > 0.42:
            self.mark("crack", foe.pos, foe.color, min(1.0, 0.4 + pure), foe.note)
            self.shake = min(1.5, self.shake + 0.2 + 0.32 * pure)
            self.hitstop = max(self.hitstop, 0.025 + 0.055 * pure)
            d = (foe.pos - ring.origin)
            d = d.normalize() if d.length_squared() > 1e-9 else pygame.Vector2(1, 0)
            self.fx.sparks(foe.pos, int(6 + 14 * pure), foe.color, direction=d,
                           spread=2.0)
            self.fx.glint(foe.pos, (255, 250, 240), 18 + 16 * pure, 0.18)
        else:
            self.mark("thud", foe.pos, (140, 148, 160), 0.35 + pure)
            self.fx.thud(foe.pos)

    def _hurt_fx(self, col=(255, 110, 100)):
        self.fx.vignette((230, 52, 44), 0.85, 0.42)
        self.fx.burst(self.player.pos, 14, (255, 120, 100), speed=(120, 420),
                      life=(0.2, 0.45), size=(2, 5))
        self.shake = min(1.6, self.shake + 0.55)
        self.hitstop = max(self.hitstop, 0.06)
        audio.hurt(0.5)

    # -------------------------------------------------------------- hazards

    def _hazards(self, dt):
        """Melee arcs, standing waves and shockwaves - everything a foe does
        that is not a ring."""
        p = self.player
        alive = []
        for b in self.beams:
            b["t"] -= dt
            if b["t"] <= 0.0:
                continue
            alive.append(b)
            if b["hit"]:
                continue
            if b["kind"] == "beam":
                if _near_segment(p.pos, b["a"], b["b"]) < b["reach"] + p.radius:
                    if p.take_hit(b["damage"]):
                        b["hit"] = True
                        self._hurt_fx()
            else:
                foe = b["foe"]
                if foe.dead:
                    continue
                if (p.pos - foe.pos).length() < b["reach"] + p.radius:
                    if p.take_hit(b["damage"]):
                        b["hit"] = True
                        p.vel += foe.aim * 460.0
                        self._hurt_fx()
        self.beams = alive

        live = []
        for w in self.waves:
            w["r"] += 1500.0 * dt
            if w["r"] > w["max"]:
                continue
            live.append(w)
            if w["hit"]:
                continue
            d = (p.pos - w["pos"]).length()
            if abs(d - w["r"]) < 34.0 + p.radius:
                if p.take_hit(w["damage"]):
                    w["hit"] = True
                    off = p.pos - w["pos"]
                    if off.length_squared() > 1e-9:
                        p.vel += off.normalize() * w["push"]
                    self._hurt_fx()
            # It shoves foes too, which is how a Deadweight ends up throwing
            # its own neighbours into walls.
            for f in self.foes:
                if f.dead or (f.pos - w["pos"]).length_squared() < 1.0:
                    continue
                fd = (f.pos - w["pos"]).length()
                if abs(fd - w["r"]) < 30.0 + f.radius and not w.get("f%d" % id(f)):
                    w["f%d" % id(f)] = True
                    f.vel += (f.pos - w["pos"]).normalize() * w["push"] * 0.5 / max(0.4, f.mass)
        self.waves = live

    # --------------------------------------------------------------- bodies

    def _bodies(self, dt):
        """Foes are solid to each other, and hitting each other hard enough
        cracks both. This is what turns a shove into a weapon."""
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
                    if d > 1e-6:
                        p.vel += delta / d * 400.0
                    self.fx.burst(p.pos, 6, (255, 150, 130), speed=(80, 260),
                                  life=(0.14, 0.3), size=(2, 4))
                    self.shake = min(1.2, self.shake + 0.25)
                    audio.hurt(0.5)


def _near_segment(p, a, b) -> float:
    ab = b - a
    L2 = ab.length_squared()
    if L2 < 1e-9:
        return (p - a).length()
    t = max(0.0, min(1.0, (p - a).dot(ab) / L2))
    return (p - (a + ab * t)).length()
