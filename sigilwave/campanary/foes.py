"""The roster. Six designs, and every one of them exists to make the player
do a specific thing they would not otherwise do.

The rule this file obeys, and the reason it is short: **an enemy is a
question, and the answer is a verb the player already has.** Nothing here is
a stat block with a resistance table. A DEADWEIGHT is not "immune to
resonance" as a balance decision - it is dead metal, it has no note, and the
only thing you can do to something with no note is throw it at something
else. That is the whole design, and it is one sentence.

Health is gone. Everything cracks instead.

That is the single most important change in the rebuild. A health bar makes
every attack partially correct, which is exactly the property that let the
old build be brute-forced: hitting a Ward with the wrong band was *weak*,
and weak is survivable, so a player who never engaged with the system could
grind anything down and every gate in the game was advisory.

A crack meter makes the wrong note **not wrong, but a different verb**. Off
note fills nothing at all - and it shoves, hard, and shoving things into
walls and into each other kills them too. So there is no punishment for
brute force and no glut meter and no surge; there is simply force, which
moves things, and resonance, which breaks them, and the player picks. The
old build needed three interlocking systems to stop players ignoring
resonance. This needs none, because the fast, beautiful kill is the one that
matches, and nobody has to be told that twice.
"""

import math
import random

import pygame

from . import audio, notes
from .notes import N_NOTES, match_curve

# A slam is the force kill. Below this closing speed a collision is a bump.
SLAM_SPEED = 620.0
SLAM_CRACK = 0.34          # at exactly the threshold; scales up from there
SLAM_STAGGER = 0.34

CONTACT_DAMAGE = 13.0
CONTACT_COOLDOWN = 0.8

# Every foe sings what it is weak to, on a slow cycle. This is the game's
# whole scan/identify layer and it costs no UI: the room tells you the
# answer, in the one sense that does not need a legend.
HUM_PERIOD = 2.4


class Foe:
    kind = "foe"
    label = "Foe"
    # One line, shown once, the first time this thing is ever met.
    lesson = ""
    note = 1
    cap = 1.0
    mass = 1.0

    def __init__(self, pos, note=None, cap=None, radius=16.0, speed=140.0):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(0, 0)
        if note is not None:
            self.note = note
        if cap is not None:
            self.cap = cap
        self.curve = match_curve(self.note) if self.note >= 0 else [0.0] * N_NOTES
        self.crack = 0.0
        self.radius = radius
        self.base_speed = speed
        self.dead = False
        self.shattered = False

        self.stagger = 0.0
        self.telegraph = 0.0
        self.flash = 0.0
        self.last_purity = 0.0
        self.spin = random.uniform(0, 360)
        self.hum_t = random.uniform(0, HUM_PERIOD)
        self.aim = pygame.Vector2(1, 0)
        self.wind = 0.0
        self.cooldown = random.uniform(0.8, 2.2)
        self.bond = None

    # ------------------------------------------------------------ readouts

    @property
    def crackable(self) -> bool:
        return self.note >= 0

    @property
    def color(self) -> tuple:
        if not self.crackable:
            return (128, 132, 140)
        return notes.note_color(self.note)

    @property
    def crack_fraction(self) -> float:
        return min(1.0, self.crack / self.cap) if self.cap > 0 else 0.0

    @property
    def speed(self) -> float:
        return self.base_speed

    # ------------------------------------------------------------ lifecycle

    def update(self, dt, arena, player, world):
        self.flash = max(0.0, self.flash - dt * 3.2)
        self.telegraph = max(0.0, self.telegraph - dt * 1.8)
        self.spin += dt * 34.0

        if self.stagger > 0.0:
            self.stagger -= dt
        else:
            self.behave(dt, arena, player, world)

        self.pos += self.vel * dt
        self.vel *= 0.87 ** (dt * 60)

        self.hum_t += dt
        if self.hum_t >= HUM_PERIOD:
            self.hum_t -= HUM_PERIOD
            if self.crackable:
                audio.hum(self.note, world.pan(self.pos), world.hum_volume(self.pos))

        self._bounds(arena, world)

    def _bounds(self, arena, world):
        """Walls are not scenery. Something thrown into one at speed cracks
        against it, which is what makes shoving a kill and not just crowd
        control."""
        r = self.radius
        speed = self.vel.length()
        hit = False
        if self.pos.x < r:
            self.pos.x, self.vel.x, hit = r, abs(self.vel.x) * 0.35, True
        elif self.pos.x > arena.width - r:
            self.pos.x, self.vel.x, hit = arena.width - r, -abs(self.vel.x) * 0.35, True
        if self.pos.y < r:
            self.pos.y, self.vel.y, hit = r, abs(self.vel.y) * 0.35, True
        elif self.pos.y > arena.height - r:
            self.pos.y, self.vel.y, hit = arena.height - r, -abs(self.vel.y) * 0.35, True
        if hit and speed > SLAM_SPEED:
            self.take_slam(speed, world, self.pos)

    def behave(self, dt, arena, player, world):
        self.seek(player.pos, dt)

    def seek(self, target, dt, stand_off=0.0):
        to = target - self.pos
        d = to.length()
        if d < 1e-6:
            return
        self.aim = to / d
        if stand_off and d < stand_off:
            self.vel -= self.aim * self.speed * dt * 2.2
            return
        self.vel += self.aim * self.speed * dt * 3.2

    # ---------------------------------------------------------------- hits

    def take_ring(self, ring, world) -> float:
        """A wavefront crossing this body. Returns how well it matched.

        Both halves of the game happen here and they are kept visibly
        separate: what landed on the note goes into the crack, and *all* of
        it - matched or not - goes into the shove. There is no third path
        and no penalty branch.
        """
        arrived = ring.spectrum_at(self.pos)
        total = sum(arrived)
        if total <= 1e-9:
            return 0.0

        pure = notes.purity(arrived, self.curve) if self.crackable else 0.0
        if self.crackable:
            from .rings import CRACK_SCALE
            gained = notes.strike_value(arrived, self.curve) * CRACK_SCALE * ring.chorus
            if gained > 1e-6:
                self.crack += gained
                self.stagger = max(self.stagger, 0.05 + 0.25 * pure)

        self.vel += ring.shove_at(self.pos) / max(0.35, self.mass)
        self.flash = 1.0
        self.last_purity = pure
        if self.crack >= self.cap:
            self.shatter(world)
        return pure

    def take_slam(self, speed, world, at=None):
        """Force, arriving as an impact. This is the second kill path, and
        it is the only one a DEADWEIGHT has - so a player who has drawn
        nothing useful is never actually stuck."""
        if self.dead:
            return
        over = max(0.0, speed - SLAM_SPEED) / SLAM_SPEED
        self.crack += SLAM_CRACK * (1.0 + over * 1.6)
        self.stagger = max(self.stagger, SLAM_STAGGER)
        self.flash = 1.0
        world.slam(at or self.pos, min(1.0, 0.4 + over))
        if self.crack >= self.cap:
            self.shatter(world)

    def shatter(self, world):
        if self.dead:
            return
        self.dead = True
        self.shattered = True
        world.shatter(self)

    def drop(self):
        return None


# ---------------------------------------------------------------------------

class Husk(Foe):
    """Teaches: the ring reaches further than you think, and a wind-up is a
    question.

    Tuned to TENOR, which is the bell the player starts holding, so the very
    first fight is winnable by someone who has understood nothing. What it
    asks for instead is *reading*: it stalks, commits to a lunge, and cannot
    steer once committed. A telegraph is the cheapest threat in games and the
    only one that makes standing still a decision.
    """

    kind = "husk"
    label = "Husk"
    lesson = "it commits to the lunge - sidestep, then answer"
    note = 1
    cap = 1.0
    mass = 1.0

    LUNGE_RANGE = 330.0
    WINDUP = 0.44
    LUNGE = 830.0

    def __init__(self, pos):
        super().__init__(pos, radius=16.0, speed=150.0)

    def behave(self, dt, arena, player, world):
        to = player.pos - self.pos
        d = to.length()
        if d > 1e-6:
            self.aim = to / d

        if self.wind > 0.0:
            self.wind -= dt
            self.telegraph = 1.0
            self.vel *= 0.82
            if self.wind <= 0.0:
                self.vel = self.aim * self.LUNGE
                self.cooldown = random.uniform(1.3, 2.3)
            return

        self.cooldown -= dt
        if d < self.LUNGE_RANGE and self.cooldown <= 0.0:
            self.wind = self.WINDUP
            return
        self.seek(player.pos, dt)


class Glasswing(Foe):
    """Teaches: a small bell only works nose to nose, and that is fine.

    Tuned to CHIME, whose ring runs out at 185px - about six body lengths.
    So this cannot be answered from safety, at all, by anyone. It circles at
    a distance the player's long bell can reach and their short one cannot,
    then dives *through* them. The dive is the opening: it comes to you, so
    the correct play is to hold the small bell and strike late, which is a
    nerve check rather than an aim check.
    """

    kind = "glasswing"
    label = "Glasswing"
    lesson = "tuned high - a high note has no reach, so let it come to you"
    note = 3
    cap = 0.85
    mass = 0.55

    ORBIT = 360.0
    DIVE_SPEED = 900.0

    def __init__(self, pos):
        super().__init__(pos, radius=13.0, speed=210.0)
        self.turn = random.choice((-1.0, 1.0))
        self.diving = 0.0

    def behave(self, dt, arena, player, world):
        to = player.pos - self.pos
        d = to.length()
        if d > 1e-6:
            self.aim = to / d

        if self.diving > 0.0:
            self.diving -= dt
            return

        if self.wind > 0.0:
            self.wind -= dt
            self.telegraph = 1.0
            self.vel *= 0.7
            if self.wind <= 0.0:
                self.vel = self.aim * self.DIVE_SPEED
                self.diving = 0.42
                self.cooldown = random.uniform(1.1, 1.9)
            return

        self.cooldown -= dt
        if self.cooldown <= 0.0 and d < 620.0:
            self.wind = 0.3
            return

        radial = max(-1.0, min(1.0, (d - self.ORBIT) / 180.0))
        tangent = pygame.Vector2(-self.aim.y, self.aim.x) * self.turn
        move = self.aim * radial + tangent * 0.85
        if move.length_squared() > 1e-9:
            self.vel += move.normalize() * self.speed * dt * 3.4


class Deadweight(Foe):
    """Teaches: force is a verb, and a mistuned bell is a tool.

    Dead metal. No note, so no ring will ever crack it, so resonance is
    simply not the answer here and no amount of tuning will make it one. It
    dies thrown into a wall, or thrown into something else - which means the
    energy a player was calling 'wrong' turns out to be the whole solution,
    and the winding direction they never looked at turns out to matter.

    It exists to stop the game from being one idea. Without it, a player who
    tuned correctly would never need to know that rings push at all.
    """

    kind = "deadweight"
    label = "Deadweight"
    lesson = "no note - nothing will ring it. Throw it into something."
    note = -1
    cap = 1.6
    mass = 2.4

    def __init__(self, pos):
        super().__init__(pos, radius=25.0, speed=92.0)

    def behave(self, dt, arena, player, world):
        self.seek(player.pos, dt)


class Twin(Foe):
    """Teaches: two things that nearly agree make something neither has, and
    you have to take them apart before you can take them down.

    A bonded pair, an octave apart. While the bond holds they beat against
    each other, and the beat carries away anything put into either crack -
    so the correct note does *nothing*, which is the one moment in the game
    where matching is not the answer and the player has to notice why. The
    line between them is a live standing wave that hurts to stand in.

    Shove them past the bond length and it breaks. Then they are two ordinary
    things with two ordinary notes. Force first, then resonance: it is the
    only enemy that requires both verbs in order, and it is placed after both
    have been taught separately.
    """

    kind = "twin"
    label = "Twin"
    lesson = "bonded - the beat eats every note you land. Break them apart."
    cap = 0.8
    mass = 0.8

    BOND_BREAK = 470.0
    BOND_PULL = 320.0

    def __init__(self, pos, note=1):
        super().__init__(pos, note=note, radius=14.0, speed=118.0)
        self.beat_t = 0.0

    @property
    def bonded(self) -> bool:
        b = self.bond
        return b is not None and not b.dead and (b.pos - self.pos).length() < self.BOND_BREAK

    def beat_hz(self) -> float:
        """|f1 - f2|, the real thing. An octave apart in the simulation is an
        octave apart here, so the envelope is the difference of the two
        ring frequencies and not a number somebody picked."""
        b = self.bond
        if b is None or b.dead:
            return 0.0
        return abs(notes.NOTE_F0[self.note] - notes.NOTE_F0[b.note]) * 180.0

    def envelope(self) -> float:
        if not self.bonded:
            return 0.0
        return 0.5 - 0.5 * math.cos(2 * math.pi * self.beat_hz() * self.beat_t)

    def take_ring(self, ring, world) -> float:
        if self.bonded:
            # The bond carries it off. The shove still lands - which is the
            # hint, and the solution, and the same action.
            arrived = ring.spectrum_at(self.pos)
            if sum(arrived) > 1e-9:
                self.vel += ring.shove_at(self.pos) / max(0.35, self.mass)
                self.flash = 1.0
                self.last_purity = 0.0
            return 0.0
        return super().take_ring(ring, world)

    def behave(self, dt, arena, player, world):
        self.beat_t += dt
        b = self.bond
        if b is not None and not b.dead:
            gap = b.pos - self.pos
            d = gap.length()
            if d > 1e-6 and d < self.BOND_BREAK:
                # It wants to hold formation, so breaking the pair takes a
                # real shove rather than a nudge.
                stretch = max(-1.0, min(1.0, (d - self.BOND_PULL) / 140.0))
                self.vel += gap.normalize() * stretch * self.speed * dt * 2.6
            mid = (self.pos + b.pos) * 0.5
            to = player.pos - mid
            if to.length_squared() > 1e-9:
                self.vel += to.normalize() * self.speed * dt * 1.5
        else:
            self.seek(player.pos, dt)


class Overtone(Foe):
    """Elite. Teaches: there is a note above every bell you can draw.

    Tuned to SPARROW, which sits one octave above the smallest ring a hand
    can hold steady - so it cannot be answered by drawing better. The only
    way to that note is to swell a CHIME until its junctions fold and the
    loop starts sounding its second mode, and the only way to survive doing
    that is to be standing next to the thing while you do it, because a
    SPARROW ring dies at arm's length.

    So it drags you in rather than keeping you out. Being close is not the
    challenge; being close, holding the swell, and letting go before your own
    bell cracks - that is the challenge, and all three are things the player
    already knows how to do separately.
    """

    kind = "overtone"
    label = "Overtone"
    lesson = "sits an octave above any bell you can draw. Swell one until it climbs."
    note = 4
    cap = 2.6      # about three full swells
    mass = 3.2

    PULL_RANGE = 620.0
    PULL = 210.0

    def __init__(self, pos):
        super().__init__(pos, radius=32.0, speed=66.0)
        self.toll_cd = 3.0

    def behave(self, dt, arena, player, world):
        self.seek(player.pos, dt, stand_off=190.0)

        to = self.pos - player.pos
        d = to.length()
        if 1e-6 < d < self.PULL_RANGE:
            # It hauls you in. The fight it wants is the fight you need.
            player.vel += to.normalize() * self.PULL * dt

        self.toll_cd -= dt
        if self.toll_cd <= 0.0:
            if self.wind <= 0.0:
                self.wind = 0.5
                self.telegraph = 1.0
            self.wind -= dt
            if self.wind <= 0.0:
                world.hostile_ring(self.pos, self.note, 0.7)
                self.toll_cd = random.uniform(2.6, 3.8)


class GreatBell(Foe):
    """The act boss. Teaches: carry two bells and know which is which.

    It tolls a phrase - three notes, announced one at a time, each launching
    a ring at the arena. Every ring can be dashed, and every ring can also be
    *answered*: put out the same note wound the other way and the two fronts
    delete each other, which is the simulation's own antiphase cancellation
    doing exactly what it does in the physics package's selftests.

    Answer the whole phrase and it staggers with its mouth open, which is the
    only window in which it can be cracked. So the boss is a call and
    response, the call is pitch, and there is no way to fake knowing the
    answer.
    """

    kind = "greatbell"
    label = "The Great Bell"
    lesson = "answer its phrase in the same note - matched fronts cancel"
    # TREBLE, not BOURDON. Thematically it wants to be the deepest thing in
    # the game, but a BOURDON is a 640px ring and costs an entire starting
    # metal budget, so tuning to it would make the act-one boss a wall for
    # anyone who had not happened to spend everything on one bell. TREBLE is
    # cheap to cast, is *not* what the player starts holding, and is called
    # out on the anvil before the fight - so the gate is "make one new bell",
    # which is exactly the thing the act was teaching.
    note = 2
    cap = 3.6
    mass = 9.0

    def __init__(self, pos, phrase=None):
        super().__init__(pos, radius=52.0, speed=44.0)
        self.phrase = list(phrase or [1, 2, 1])
        self.step = 0
        self.answered = 0
        self.open_t = 0.0
        self.toll_cd = 2.2
        self.calling = 0.0

    @property
    def crackable(self) -> bool:
        # Sealed until the phrase is answered. Not a resistance stat - the
        # thing is a closed shell, and a closed shell does not ring.
        return self.open_t > 0.0

    @property
    def next_note(self) -> int:
        return self.phrase[self.step % len(self.phrase)]

    def behave(self, dt, arena, player, world):
        self.open_t = max(0.0, self.open_t - dt)
        self.seek(player.pos, dt, stand_off=340.0)

        if self.open_t > 0.0:
            return

        if self.calling > 0.0:
            self.calling -= dt
            self.telegraph = 1.0
            if self.calling <= 0.0:
                n = self.next_note
                world.hostile_ring(self.pos, n, 1.0, announce=n, source=self)
                self.step += 1
                self.toll_cd = 1.5
            return

        self.toll_cd -= dt
        if self.toll_cd <= 0.0:
            self.calling = 0.62

    def answered_toll(self, world):
        """A phrase note deleted by a matching ring."""
        self.answered += 1
        if self.answered >= len(self.phrase):
            self.answered = 0
            self.step = 0
            self.open_t = 4.2
            self.stagger = 1.1
            self.telegraph = 0.0
            world.boss_opened(self)


def make_twins(pos, spread=300.0):
    a = Twin(pygame.Vector2(pos) + pygame.Vector2(-spread / 2, 0), note=1)
    b = Twin(pygame.Vector2(pos) + pygame.Vector2(spread / 2, 0), note=2)
    a.bond, b.bond = b, a
    return [a, b]


FOE_TYPES = {
    "husk": Husk,
    "glasswing": Glasswing,
    "deadweight": Deadweight,
    "twin": Twin,
    "overtone": Overtone,
    "greatbell": GreatBell,
}
