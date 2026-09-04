"""Enemies — each one is a lesson about the system, wearing a hitbox.

The rule for this file: **no enemy has a mechanic that is not already in the
physics.** A Ward does not have "immune to physical"; it has a high
impedance, so low bands reflect off it, because that is what an impedance
mismatch does. A Choir pair does not have "pulsing aura damage"; it has two
loops of slightly different circumference, so it beats, because that is what
detuned oscillators do. Every enemy is a demonstration the player can walk
up to, lose to, understand, and then build.

The casting ones (Drone, Anchor) own real Sigils and drive them through the
identical parse-compile-analyse pipeline the player uses. That is the doc's
strongest pillar and it is close to free here: the Sigil class does not know
or care who is holding it. It also means an Anchor's corpse is a legible
drawing rather than a loot table entry, and reading it teaches something,
because it is the same kind of object the player builds.
"""

import math
import random

import pygame

from sigilwave.ink import Stroke

from .bands import BAND_LOOP_PX, band_color, vulnerability_curve
from .combat import Pulse, emissions_to_pulses, resonance_quality
from .inks import BONEWHITE, CHALK, QUICKSILVER
from .shapes import radius_for_band_px, ring_with_tail

# Enemy sigils are rendered small next to the player's; they are readable
# glyphs orbiting a body, not full-size drawings.
ENEMY_SIGIL_SCALE = 0.42
# Enemy volleys are coarse and slow on purpose. The same energy delivered as
# four fat, slow motes and as two hundred fine fast ones does identical
# damage on paper, but only the first is a thing a player can read, sidestep,
# or cancel with an antiphase shot. The second is a wash that just subtracts
# health, and a wash cannot teach the parry it is supposed to be teaching.
ENEMY_EMIT_SCALE = 18.0

BURN_DPS = 26.0
CHILL_SLOW = 0.55
DECOHERE_THRESHOLD = 0.5
PHASE_DECAY = 0.7
TEMP_DECAY = 0.5

# --- glut: what happens when you hit something with the wrong frequency ----
#
# The single worst property of the first build was that a wrong-band hit was
# merely *weak*. Weak is survivable, so a player who never engaged with the
# system could stand at range and grind anything down with their opening
# sigil, and every gate in the game was advisory. A system you are allowed to
# ignore is a system that does not exist.
#
# So off-band energy is no longer wasted, it is *fed*. A thing tuned to one
# frequency does not shatter when struck at another; it absorbs, and it rings
# louder. Fill the meter and it surges — heals, quickens, and throws out a
# shockwave. Brute force now visibly makes the problem worse, which converts
# "you should match the band" from advice into the rule of the fight.
#
# It is also honest: this is what driving an oscillator off-resonance does.
GLUT_MAX = 1.0
# Per unit of absorbed off-band energy. Calibrated against the real thing
# rather than guessed: a mote that has crossed a room has lost most of itself
# to air decay, so a sustained wrong-band barrage was measured delivering
# 0.022 glut/sec against a 0.16/sec bleed — the meter could never rise and
# the entire anti-brute-force mechanic was inert while looking implemented.
# At this value a wrong-band attacker fills it in about two seconds.
GLUT_GAIN = 1.1               # per unit of absorbed off-band energy
GLUT_BLEED = 0.12             # per second
# A near miss is not a mistake. Anything landing over 62% on-resonance feeds
# nothing at all, so a player who is one band out feels the damage fall off
# but is not punished for it — the punishment is reserved for the player who
# is simply hosing the wrong colour and not looking.
#
# The threshold has to sit above what a *correct* hit actually scores in
# play, and that number is far lower than the bench suggests. A sigil fired
# point-blank at its own band measures ~0.79, but a mote crossing a room
# loses its upper bands to air decay long before it lands, and the surviving
# spectrum matches much worse: measured live, a correctly-matched Shove
# scores a median of 0.194 against the Cinders it is designed to kill.
#
# Set from that measurement rather than from intuition. A wrong-band hit
# scores about 0.02, so 0.16 still separates the two by an order of
# magnitude while leaving correct play entirely unpunished — which it was
# not at 0.5 or 0.62, where the right answer fed the enemy too.
GLUT_FORGIVE = 0.16
SURGE_HEAL = 0.28             # fraction of max hp
SURGE_SPEED = 1.45
SURGE_TIME = 5.0
# Healing stops after this many surges. The signal has landed by then, and an
# unbounded heal loop stops being a lesson and becomes an unwinnable fight
# that the player cannot tell apart from a bug. Speed keeps stacking, so the
# thing still gets worse to be near.
SURGE_HEAL_CAP = 9


def _sigil_for_band(band: int, ink=CHALK, clockwise=True, tail=44.0):
    """A ring sized to ring at `band`, with an open end so it radiates.

    An enemy's weakness is therefore visible in its silhouette: the ring you
    can see orbiting it is literally the resonator that decides what kills
    it, and a player who has drawn a few of their own can size it by eye
    before they ever scan it."""
    from .sigil import Sigil

    # Band 5 has no drawable ring — its circumference falls under the
    # parser's minimum edge, which is exactly why it is the harmonics-only
    # band. Authored casters clamp to 4; nothing casts a band-5 fundamental
    # because nothing can.
    band = max(0, min(4, band))
    r = radius_for_band_px(BAND_LOOP_PX[band])
    pts = ring_with_tail((0, 0), r, tail, attach_deg=0.0, clockwise=clockwise)
    sig = Sigil(f"band{band}", [Stroke(points=pts, ink_type=ink)])
    sig.emit_scale = ENEMY_EMIT_SCALE
    return sig


class Enemy:
    kind = "enemy"
    label = "Enemy"
    lesson = ""

    def __init__(self, pos, resonance=1.0, hp=100.0, radius=15.0, speed=80.0):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(0, 0)
        self.resonance = resonance
        self.vuln = vulnerability_curve(resonance)
        self.hp = hp
        self.max_hp = hp
        self.radius = radius
        self.base_speed = speed
        self.dead = False

        self.temperature = 0.0     # + burning, - chilled
        self.phase = 0.0           # decoherence; see take_pulse
        self.hit_flash = 0.0
        self.last_quality = 0.0
        self.spin = random.uniform(0, 360)
        self.sigil = None
        self.aim = pygame.Vector2(1, 0)
        self.glut = 0.0            # absorbed off-band energy
        self.surge_t = 0.0         # time left in a surge
        self.surges = 0
        self.telegraph = 0.0       # 0..1 wind-up on a committed attack
        self.lunge_cd = random.uniform(1.0, 2.6)
        self.shock = None          # (pos, radius) to hand to the field

    # ------------------------------------------------------------- lifecycle

    @property
    def color(self) -> tuple:
        return band_color(self.resonance)

    @property
    def speed(self) -> float:
        chill = 1.0 - CHILL_SLOW * min(1.0, max(0.0, -self.temperature))
        surge = SURGE_SPEED if self.surge_t > 0 else 1.0
        return self.base_speed * chill * surge

    @property
    def decohered(self) -> bool:
        return self.phase > DECOHERE_THRESHOLD

    def update(self, dt, arena, player, out_pulses):
        self.temperature *= max(0.0, 1.0 - TEMP_DECAY * dt)
        self.phase = max(0.0, self.phase - PHASE_DECAY * dt)
        self.hit_flash = max(0.0, self.hit_flash - dt * 3.0)
        self.spin += dt * 40.0
        self.glut = max(0.0, self.glut - GLUT_BLEED * dt)
        self.surge_t = max(0.0, self.surge_t - dt)
        self.telegraph = max(0.0, self.telegraph - dt * 1.6)

        if self.temperature > 0.02:
            # Burning is damage over time, and it is the reason a hot sigil
            # is worth building even though it cannot reach: you leave.
            self.hp -= BURN_DPS * self.temperature * dt
            if self.hp <= 0:
                self.dead = True

        self._behave(dt, arena, player, out_pulses)

        self.pos += self.vel * dt
        self.vel *= 0.86 ** (dt * 60)
        self.pos = arena.clamp(self.pos, self.radius)

        if self.sigil is not None:
            emissions = self.sigil.advance(dt)
            if emissions:
                out_pulses.extend(
                    emissions_to_pulses(
                        emissions,
                        self.pos,
                        self.aim.angle_to(pygame.Vector2(1, 0)) * -1.0,
                        ENEMY_SIGIL_SCALE,
                        hostile=True,
                        speed=255.0,
                    )
                )

    def _behave(self, dt, arena, player, out_pulses):
        self._seek(player.pos, dt)

    def _seek(self, target, dt, stop_at=0.0):
        to = target - self.pos
        d = to.length()
        if d < 1e-6:
            return
        if stop_at and d < stop_at:
            self.vel -= to.normalize() * self.speed * dt * 2.0
            return
        self.vel += to.normalize() * self.speed * dt * 3.0
        self.aim = to.normalize()

    # ----------------------------------------------------------------- hits

    def take_pulse(self, pulse, out_pulses) -> float:
        """Returns the resonance quality of the hit, for feedback."""
        quality = resonance_quality(pulse.bands, self.vuln)
        dmg = pulse.damage_against(self.vuln)

        # Whatever did not land on resonance is absorbed rather than wasted.
        # Measured against the incoming pulse, not against what survived the
        # target's own defences — a Ward that reflects most of a wrong-band
        # shot was ending up with almost no glut from it, which exempted the
        # one enemy the mechanic exists for from the mechanic.
        off = max(0.0, 1.0 - quality / GLUT_FORGIVE) * pulse.total
        if off > 1e-6:
            self.glut = min(GLUT_MAX, self.glut + off * GLUT_GAIN)
            if self.glut >= GLUT_MAX:
                self._surge()

        thermal = pulse.thermal()
        if self.decohered:
            # Decohered matter has stopped interacting mechanically, so a
            # shove passes straight through it — but its structure is open,
            # and heat bites twice as hard. Phase is not a pure buff; using
            # it wrong throws away your knockback.
            thermal *= 2.0
            dmg *= 1.6
        else:
            self.vel += pulse.kinetic() / max(20.0, self.max_hp * 0.35)

        self.temperature += thermal
        self.phase = min(1.0, self.phase + pulse.phase())
        self.hp -= dmg
        self.hit_flash = 1.0
        self.last_quality = quality
        if self.hp <= 0:
            self.dead = True
        return quality

    def _surge(self):
        """It ate enough of the wrong note and got louder."""
        self.glut = 0.0
        self.surges += 1
        if self.surges <= SURGE_HEAL_CAP:
            self.hp = min(self.max_hp, self.hp + self.max_hp * SURGE_HEAL)
        self.surge_t = SURGE_TIME
        self.hit_flash = 1.0
        self.shock = (pygame.Vector2(self.pos), 150.0 + 18.0 * self.surges)

    def take_shock(self):
        """Hand off and clear the pending shockwave, if any."""
        s, self.shock = self.shock, None
        return s

    def drop(self):
        """What reading this thing's corpse gives you. None for the trash."""
        return None


class Cinder(Enemy):
    """Lesson zero: something big and slow kills it, and you can shove it.

    Tuned to band 1 — a 263px ring, comfortably the first loop anybody draws
    — so a player who has understood nothing still wins here. But it does not
    drift at you politely: it stalks, winds up, and commits to a lunge. The
    wind-up is the whole design. A telegraph is what turns an enemy from a
    moving obstacle into something you have to *answer*, and it is the
    cheapest threat there is."""

    kind = "cinder"
    label = "Cinder"
    lesson = "big ring, low band - and it lunges, so watch the wind-up"

    LUNGE_RANGE = 300.0
    LUNGE_WINDUP = 0.42
    LUNGE_SPEED = 780.0

    def __init__(self, pos):
        super().__init__(pos, resonance=1.0, hp=62.0, radius=13.0, speed=142.0)
        self.winding = 0.0

    def _behave(self, dt, arena, player, out_pulses):
        to = player.pos - self.pos
        d = to.length()
        if d > 1e-6:
            self.aim = to.normalize()

        if self.winding > 0:
            # Committed. It cannot steer once it has decided, which is what
            # makes sidestepping a real answer rather than a stat check.
            self.winding -= dt
            self.telegraph = 1.0
            if self.winding <= 0:
                self.vel = self.aim * self.LUNGE_SPEED
                self.lunge_cd = random.uniform(1.4, 2.5)
            return

        self.lunge_cd -= dt
        if d < self.LUNGE_RANGE and self.lunge_cd <= 0:
            self.winding = self.LUNGE_WINDUP
            self.vel *= 0.25
            return
        self._seek(player.pos, dt)


class Ward(Enemy):
    """Lesson: bands are not a damage bonus, they are a gate.

    High impedance, so low bands *reflect* rather than land — the player's
    reliable opening sigil comes straight back at them. The fix is heat,
    heat is a small ring, and a small ring's output dies in about two body
    lengths of air, so the same enemy also teaches that the counter to it
    has to be delivered up close. Two lessons, one body, no text."""

    kind = "ward"
    label = "Ward"
    lesson = "reflects low bands - bring heat, and bring it close"

    def __init__(self, pos):
        super().__init__(pos, resonance=4.0, hp=120.0, radius=19.0, speed=74.0)

    def _behave(self, dt, arena, player, out_pulses):
        # No stand-off. It walks at you forever, so the reflected shot you
        # just ate is arriving while the thing that made it is still coming.
        self._seek(player.pos, dt)

    def take_pulse(self, pulse, out_pulses) -> float:
        reflected = [0.0] * len(pulse.bands)
        kept = list(pulse.bands)
        # The lower the band, the more of it bounces. Continuous, so a
        # mid-band sigil partially works and the player can feel the edge
        # of the mechanic instead of hitting a wall.
        for i in range(len(pulse.bands)):
            # Steeper and deeper than it was. At 0.85 falling off over three
            # bands, a low-band sigil still leaked ~15% through and could
            # grind a Ward down in half a minute — which is exactly the
            # "just force it" outcome the resonance system exists to remove.
            # The counter is in the player's starting kit from the first
            # room, so closing this path costs them nothing but a keypress.
            bounce = max(0.0, 1.0 - i / 4.0) * 0.96
            reflected[i] = pulse.bands[i] * bounce
            kept[i] = pulse.bands[i] - reflected[i]

        if sum(reflected) > 1e-7 and not pulse.hostile:
            back = Pulse(
                self.pos,
                -pulse.vel * 0.8,
                reflected,
                pulse.kinetic_sign,
                pulse.thermal_sign,
                hostile=True,
            )
            out_pulses.append(back)

        # Reflected energy still rang it on the way past. Without this the
        # Ward is the only enemy that cannot be over-fed, which is precisely
        # backwards: it is the one whose gate the player is most likely to
        # try to bludgeon.
        bounced = sum(reflected)
        if bounced > 1e-6:
            self.glut = min(GLUT_MAX, self.glut + bounced * GLUT_GAIN * 0.8)
            if self.glut >= GLUT_MAX:
                self._surge()

        pulse.bands = kept
        pulse._refresh()
        return super().take_pulse(pulse, out_pulses)


class Drone(Enemy):
    """Lesson: incoming energy is the same stuff as outgoing energy.

    It runs a real sigil and shoots real pulses, which means its shots
    superpose with yours. A player who fires an opposite-chirality mote into
    an incoming one watches both vanish, and has just parried by arithmetic
    rather than by pressing a parry button."""

    kind = "drone"
    label = "Drone"
    lesson = "shoots back - its motes cancel against opposite chirality"

    def __init__(self, pos):
        super().__init__(pos, resonance=2.0, hp=78.0, radius=14.0, speed=132.0)
        self.sigil = _sigil_for_band(2, ink=QUICKSILVER, clockwise=True, tail=52.0)
        self.cooldown = random.uniform(1.2, 2.6)
        self.orbit_dir = random.choice((-1.0, 1.0))
        self.winding = 0.0

    def _behave(self, dt, arena, player, out_pulses):
        to = player.pos - self.pos
        d = to.length()
        if d > 1e-6:
            self.aim = to.normalize()
            ideal = 320.0
            radial = (d - ideal) / 160.0
            tangent = pygame.Vector2(-self.aim.y, self.aim.x) * self.orbit_dir
            move = self.aim * max(-1.0, min(1.0, radial)) + tangent * 0.7
            if move.length_squared() > 1e-9:
                self.vel += move.normalize() * self.speed * dt * 3.0

        if self.winding > 0:
            self.winding -= dt
            self.telegraph = 1.0
            self.vel *= 0.55
            if self.winding <= 0:
                self.sigil.tap(1.0)
            return

        self.cooldown -= dt
        if self.cooldown <= 0 and d < 620.0:
            # Wind up visibly before firing. An unannounced volley is just
            # damage; an announced one is a decision about where to stand.
            self.winding = 0.34
            self.cooldown = random.uniform(1.7, 2.6)


class Choir(Enemy):
    """Lesson: two loops that nearly agree produce something neither has.

    A Choir spawns as a bonded pair with slightly different resonances.
    While both live, the beat between them — a real |f1 - f2| envelope, not
    a timer — swings a damaging standing wave across the line between them.
    Kill either and the beat has nothing to beat against. It is the cheapest
    possible demonstration that interference is a thing that happens to
    *you*, not just a thing you do."""

    kind = "choir"
    label = "Choir"
    lesson = "a bonded pair beats against itself - break the pair"

    def __init__(self, pos, resonance=2.0):
        super().__init__(pos, resonance=resonance, hp=60.0, radius=12.0, speed=70.0)
        self.partner = None
        self.beat_t = 0.0

    def beat_frequency(self) -> float:
        if self.partner is None or self.partner.dead:
            return 0.0
        f1 = BAND_LOOP_PX[int(round(self.resonance))]
        f2 = BAND_LOOP_PX[int(round(self.partner.resonance))]
        return abs(1.0 / max(f1, 1e-6) - 1.0 / max(f2, 1e-6)) * 400.0

    def beat_envelope(self) -> float:
        if self.partner is None or self.partner.dead:
            return 0.0
        return 0.5 - 0.5 * math.cos(2 * math.pi * self.beat_frequency() * self.beat_t)

    def _behave(self, dt, arena, player, out_pulses):
        self.beat_t += dt
        if self.partner is not None and not self.partner.dead:
            # Hold formation: the pair wants to keep a working baseline.
            mid = (self.pos + self.partner.pos) * 0.5
            to_partner = self.partner.pos - self.pos
            d = to_partner.length()
            if d > 1e-6:
                stretch = (d - 210.0) / 120.0
                self.vel += to_partner.normalize() * max(-1.0, min(1.0, stretch)) * self.speed * dt * 2.2
            to_player = player.pos - mid
            if to_player.length_squared() > 1e-9:
                self.vel += to_player.normalize() * self.speed * dt * 1.4
        else:
            self._seek(player.pos, dt)


class Anchor(Enemy):
    """Elite. Lesson: the top of the spectrum is a different kind of tool.

    Phase-locked — nearly immune until it has been decohered, and the phase
    field only responds to the very top band, which cannot be reached by
    drawing a small enough ring (the parser floor stops you) and can only be
    reached by driving a ring hard enough to fold its junction into
    harmonics. So the Anchor is a lock whose key is the overdrive mechanic,
    and the only way through is to have understood nonlinearity.

    Its corpse is its sigil, and its sigil is a real one."""

    kind = "anchor"
    label = "Anchor"
    lesson = "phase-locked - decohere it first, which means overdrive"

    def __init__(self, pos):
        super().__init__(pos, resonance=3.0, hp=380.0, radius=28.0, speed=78.0)
        self.sigil = _sigil_for_band(3, ink=BONEWHITE, clockwise=False, tail=66.0)
        self.cooldown = 2.8

    def _behave(self, dt, arena, player, out_pulses):
        self._seek(player.pos, dt, stop_at=150.0)
        self.cooldown -= dt
        if self.cooldown <= 0:
            self.sigil.tap(1.15)
            self.cooldown = random.uniform(2.4, 3.4)

    def take_pulse(self, pulse, out_pulses) -> float:
        # Phase arrives from the same pulse that carries the damage, so a
        # single sufficiently hot mote both unlocks and hurts. The lock is
        # steep but not absolute — chipping it down is legal, just slow
        # enough that finding the real answer is obviously better.
        #
        # It has to refuse *heat* as well as impact. Refunding only the
        # direct damage left a hole big enough to drive the whole fight
        # through: burn is applied from the accumulated temperature during
        # update() rather than at the moment of the hit, so it skipped the
        # refund entirely, and a player who simply kept tapping their opening
        # sigil cooked a locked Anchor to death without ever discovering that
        # it had a lock. A gate with a silent bypass is worse than no gate —
        # it teaches that the mechanic it was built to teach does not matter.
        locked = not self.decohered
        temp_before = self.temperature
        quality = super().take_pulse(pulse, out_pulses)
        if locked:
            self.hp += pulse.damage_against(self.vuln) * 0.94
            self.temperature = temp_before + (self.temperature - temp_before) * 0.08
        return quality

    def drop(self):
        from .sigil import Sigil

        clone = Sigil.from_dict(self.sigil.to_dict())
        clone.name = "Anchor's Ring"
        return clone


def make_choir_pair(pos, spread=180.0):
    a = Choir(pygame.Vector2(pos) + pygame.Vector2(-spread / 2, 0), resonance=2.0)
    b = Choir(pygame.Vector2(pos) + pygame.Vector2(spread / 2, 0), resonance=3.0)
    a.partner, b.partner = b, a
    return [a, b]


ENEMY_TYPES = {
    "cinder": Cinder,
    "ward": Ward,
    "drone": Drone,
    "choir": Choir,
    "anchor": Anchor,
}
