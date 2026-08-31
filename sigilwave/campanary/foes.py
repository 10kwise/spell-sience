"""The roster. Six designs, and every one exists to punish a specific habit.

The first cut of this file was polite. Everything telegraphed, everything
dodged, and nothing actually happened if you ignored all of it: contact did
13 damage against 100 health on a 0.8s cooldown, so the correct play against
every enemy in the game was to walk into it and keep tolling. They were
busywork with a colour.

Two changes fix that, and they are the same change:

**1. The pulse is the attack clock.** Every foe already showed a ring
expanding on its own note's tempo, as an identify cue. Now that ring *closes
inward* and the foe attacks the instant it lands. So the thing that tells you
which bell to bring is the same thing that tells you when to move, a TENOR
enemy threatens on a slow 0.8s swing while a CHIME one comes at you twice as
fast, and reading the room is one act instead of two.

**2. Everything hits hard enough to matter.** Three or four connected
attacks kill. That is not difficulty for its own sake - it is what makes a
telegraph worth reading. A wind-up you can afford to eat is not a wind-up,
it is an animation.

The counterweight is that **shattering something on its note heals you** and
slamming it into a wall does not. So the game pays for the play it is trying
to teach, rather than punishing the play it is trying to discourage. Every
enemy below is a question; the answer is always a verb the player already
has, and answering correctly is how you stay alive.
"""

import math
import random

import pygame

from . import audio, notes
from .notes import N_NOTES, NOTE_PERIOD, match_curve

# A slam is the force kill. Below this closing speed a collision is a bump.
#
# Measured before this value moved: a TENOR ring at point-blank range threw a
# Deadweight at 543px/s against a 560 threshold, so the *only* kill the game's
# unshatterable enemy has could not be triggered by the bell the player
# starts holding. It was not hard, it was off by three percent, and the
# symptom was a foe that simply never died.
SLAM_SPEED = 430.0
SLAM_CRACK = 0.40
# How much of a slam a thing that *has* a note actually takes.
#
# Force is supposed to be the answer to dead metal and a bonus everywhere
# else. When it was a full-strength kill against everything, a bot playing
# one bell on the beat and shoving cleared the note gates outright - three
# Glasswings and an Overtone, the two rooms that exist to require specific
# pitches, went from 0/3 to 3/3 without a single matched hit. That is the
# exact hole the crack meter was built to close, re-opened from the other
# side.
#
# A resonant thing breaks at its note. Throwing it into a wall rattles it.
SLAM_RESONANT = 0.28
SLAM_STAGGER = 0.34

# Touching something is a nudge; being *hit* by something is the threat. The
# separation matters - if brushing past a body cost as much as eating a
# lunge, the game would be about not being touched rather than about reading
# what things do.
CONTACT_DAMAGE = 11.0
CONTACT_COOLDOWN = 0.7

# Every foe sings what it is weak to on its own clock. This is the entire
# scan/identify layer and it costs no UI: the room tells you the answer, in
# the one sense that needs no legend.
HUM_EVERY = 2


class Foe:
    kind = "foe"
    label = "Foe"
    lesson = ""
    punishes = ""
    note = 1
    cap = 1.0
    mass = 1.0
    # Fraction of the beat spent winding up. Long enough to read, short
    # enough that the attack still feels like it lands *on* the beat.
    telegraph_frac = 0.42
    # Attack on every Nth beat, rather than every one.
    #
    # This exists because the clock and the note have to stay the same fact -
    # the pulse tempo is how you identify a thing - but a SPARROW-tuned enemy
    # ticks five times a second, and a room-covering shockwave five times a
    # second is not a fight, it is weather. Measured, the Overtone at every
    # beat was unwinnable for every bot at every seed while the swell it
    # exists to teach takes 1.4 seconds to land.
    #
    # So the identity pulse keeps ticking at the note's own tempo and the
    # wind-up bracket only appears on the beats it will actually act on. The
    # threat stays perfectly readable and the cadence becomes tunable.
    attack_every = 1

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
        self.flash = 0.0
        self.last_purity = 0.0
        self.spin = random.uniform(0, 360)
        self.aim = pygame.Vector2(1, 0)
        self.bond = None

        # The clock. Its period is the note's own tempo, so a foe's pitch,
        # its colour, its hum and its threat cadence are one fact.
        self.period = NOTE_PERIOD[self.note] if self.note >= 0 else NOTE_PERIOD[1]
        self.clock = random.uniform(0.0, self.period)
        self.beats = 0
        self.committed = 0.0     # >0 while an attack is actually happening

    # ------------------------------------------------------------ readouts

    @property
    def crackable(self) -> bool:
        return self.note >= 0

    @property
    def flying(self) -> bool:
        """Moving fast enough that hitting something will crack it. Drawn, so
        "this is now a projectile" is a thing the player can see rather than
        infer."""
        return self.vel.length_squared() > SLAM_SPEED * SLAM_SPEED

    @property
    def color(self) -> tuple:
        return notes.note_color(self.note) if self.crackable else (132, 136, 146)

    @property
    def crack_fraction(self) -> float:
        return min(1.0, self.crack / self.cap) if self.cap > 0 else 0.0

    @property
    def speed(self) -> float:
        return self.base_speed

    @property
    def arming(self) -> bool:
        """Is the beat now approaching one this thing will act on?"""
        return (self.beats + 1) % self.attack_every == 0

    @property
    def wind(self) -> float:
        """0..1 across the wind-up window, 0 outside it. The renderer draws
        the closing bracket from this, so what the player sees is literally
        the variable the attack fires on."""
        if self.committed > 0.0:
            return 1.0
        if not self.arming:
            return 0.0
        t = self.clock / self.period
        start = 1.0 - self.telegraph_frac
        return 0.0 if t < start else (t - start) / self.telegraph_frac

    @property
    def winding(self) -> bool:
        return self.wind > 0.0 and self.committed <= 0.0

    # ----------------------------------------------------------- lifecycle

    def update(self, dt, arena, player, world):
        self.flash = max(0.0, self.flash - dt * 3.2)
        self.spin += dt * 34.0
        self.committed = max(0.0, self.committed - dt)

        if self.stagger > 0.0:
            # Staggered things do not attack, and their clock does not run.
            # Staggering something is therefore a real tempo change in the
            # fight, not just a pause on one body.
            self.stagger -= dt
        else:
            self.clock += dt
            if self.clock >= self.period:
                self.clock -= self.period
                self.beats += 1
                if self.crackable and self.beats % HUM_EVERY == 0:
                    audio.hum(self.note, world.pan(self.pos), world.hum_volume(self.pos))
                if self.beats % self.attack_every == 0:
                    self.on_beat(dt, arena, player, world)
            self.behave(dt, arena, player, world)

        self.pos += self.vel * dt
        self.vel *= 0.87 ** (dt * 60)
        self._bounds(arena, world)

    def _bounds(self, arena, world):
        """Walls are not scenery. Something thrown into one at speed cracks
        against it, which is what makes shoving a kill rather than crowd
        control."""
        r = self.radius
        speed = self.vel.length()
        hit = False
        # Bouncy, so one hard shove can carom off a wall into a second
        # impact - or into whatever else is standing there.
        k = 0.55
        if self.pos.x < r:
            self.pos.x, self.vel.x, hit = r, abs(self.vel.x) * k, True
        elif self.pos.x > arena.width - r:
            self.pos.x, self.vel.x, hit = arena.width - r, -abs(self.vel.x) * k, True
        if self.pos.y < r:
            self.pos.y, self.vel.y, hit = r, abs(self.vel.y) * k, True
        elif self.pos.y > arena.height - r:
            self.pos.y, self.vel.y, hit = arena.height - r, -abs(self.vel.y) * k, True
        if hit and speed > SLAM_SPEED:
            self.take_slam(speed, world, self.pos)

    def behave(self, dt, arena, player, world):
        self.seek(player.pos, dt)

    def on_beat(self, dt, arena, player, world):
        """Fired the instant the closing ring lands. Override to attack."""

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

    def face(self, target):
        to = target - self.pos
        if to.length_squared() > 1e-9:
            self.aim = to.normalize()

    # ---------------------------------------------------------------- hits

    def take_ring(self, ring, world) -> float:
        """A wavefront crossing this body.

        Both halves of the game happen here and are kept visibly separate:
        what landed on the note goes into the crack, and *all* of it goes
        into the shove. No third path, no penalty branch.
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
                # A solid hit interrupts. That is the reward loop closing:
                # correct notes buy you time as well as progress, so playing
                # well is also how you stop being hit.
                self.stagger = max(self.stagger, 0.06 + 0.42 * pure)

        self.vel += ring.shove_at(self.pos) / max(0.35, self.mass)
        self.flash = 1.0
        self.last_purity = pure
        if self.crack >= self.cap:
            self.shatter(world, resonant=pure > 0.3)
        return pure

    def take_slam(self, speed, world, at=None):
        """Force, arriving as an impact. The only kill a DEADWEIGHT has - so
        a player holding nothing useful is never actually stuck."""
        if self.dead:
            return
        over = max(0.0, speed - SLAM_SPEED) / SLAM_SPEED
        bite = SLAM_CRACK * (1.0 + over * 1.6)
        if self.crackable or self.note >= 0:
            bite *= SLAM_RESONANT
        self.crack += bite
        self.stagger = max(self.stagger, SLAM_STAGGER)
        self.flash = 1.0
        world.slam(at or self.pos, min(1.0, 0.4 + over))
        if self.crack >= self.cap:
            self.shatter(world, resonant=False)

    def shatter(self, world, resonant=True):
        if self.dead:
            return
        self.dead = True
        self.shattered = True
        world.shatter(self, resonant)

    def drop(self):
        return None


# ---------------------------------------------------------------------------

class Husk(Foe):
    """Punishes standing still.

    TENOR, which is the bell the player starts holding, so the opening fight
    is winnable by somebody who has understood nothing. What it asks for
    instead is *reading*: it commits to a lunge on its own beat and cannot
    steer once it has, so sidestepping is a real answer rather than a stat
    check - and the lunge takes a third of your health, so declining to
    sidestep is not.

    Three of them in a room is a rhythm section. Their clocks are seeded
    apart, so the lunges arrive as a pattern rather than a wall.
    """

    kind = "husk"
    label = "Husk"
    lesson = "it commits to the lunge - sidestep, then answer"
    punishes = "standing still"
    note = 1
    cap = 1.0
    mass = 1.0
    telegraph_frac = 0.46
    attack_every = 1          # TENOR clock: a lunge every 0.8s

    LUNGE_RANGE = 420.0
    LUNGE_SPEED = 1080.0
    LUNGE_DAMAGE = 26.0

    def __init__(self, pos):
        super().__init__(pos, radius=16.0, speed=165.0)

    def behave(self, dt, arena, player, world):
        self.face(player.pos)
        if self.committed > 0.0:
            return                      # mid-lunge: cannot steer
        if self.winding:
            self.vel *= 0.80 ** (dt * 60)
            return
        self.seek(player.pos, dt)

    def on_beat(self, dt, arena, player, world):
        if (player.pos - self.pos).length() > self.LUNGE_RANGE:
            return
        self.vel = self.aim * self.LUNGE_SPEED
        self.committed = 0.34
        world.melee(self, self.LUNGE_DAMAGE, reach=self.radius + 20.0,
                    duration=0.30, kind="lunge")


class Glasswing(Foe):
    """Punishes fighting at range.

    CHIME, whose ring runs out at 155px - about five body lengths - so this
    cannot be answered from safety by anyone, ever. And its clock is a CHIME
    clock, twice a Husk's, so it comes at you twice as often.

    The dive is the opening: it brings itself to you, which means the correct
    play is to hold the short bell and strike late. That is a nerve check
    rather than an aim check, which is the only kind of check a game with no
    aiming can make.
    """

    kind = "glasswing"
    label = "Glasswing"
    lesson = "tuned high - a high note has no reach, so let it come to you"
    punishes = "keeping your distance"
    note = 3
    cap = 0.85
    mass = 0.5
    telegraph_frac = 0.38
    attack_every = 2          # CHIME clock ticks at 0.4s; it dives every 0.8s

    ORBIT = 330.0
    DIVE_SPEED = 1140.0
    DIVE_DAMAGE = 19.0

    def __init__(self, pos):
        super().__init__(pos, radius=13.0, speed=250.0)
        self.turn = random.choice((-1.0, 1.0))

    def behave(self, dt, arena, player, world):
        to = player.pos - self.pos
        d = to.length()
        if d > 1e-6:
            self.aim = to / d
        if self.committed > 0.0:
            return
        if self.winding:
            self.vel *= 0.86 ** (dt * 60)
            return
        radial = max(-1.0, min(1.0, (d - self.ORBIT) / 170.0))
        tangent = pygame.Vector2(-self.aim.y, self.aim.x) * self.turn
        move = self.aim * radial + tangent * 0.95
        if move.length_squared() > 1e-9:
            self.vel += move.normalize() * self.speed * dt * 3.6

    def on_beat(self, dt, arena, player, world):
        if (player.pos - self.pos).length() > 620.0:
            return
        self.vel = self.aim * self.DIVE_SPEED
        self.committed = 0.30
        self.turn *= -1.0
        world.melee(self, self.DIVE_DAMAGE, reach=self.radius + 16.0,
                    duration=0.28, kind="dive")


class Deadweight(Foe):
    """Punishes tunnel vision.

    Dead metal. No note, so no ring will ever crack it and no amount of
    tuning will make one. It dies thrown into a wall or into something else -
    which means the energy a player was calling 'wrong' turns out to be the
    whole solution, and the winding direction they never looked at turns out
    to matter.

    It also refuses to be ignored: on its beat it stomps, and the shockwave
    takes a third of your health and throws you. So it is not a slow thing
    you deal with later. It is a thing that owns the ground it is standing
    on, and the room gets smaller while you are busy with something else.
    """

    kind = "deadweight"
    label = "Deadweight"
    lesson = "no note - nothing will ring it. Throw it into something."
    punishes = "forgetting where it is"
    note = -1
    cap = 1.1      # about two good wall slams
    mass = 2.6
    telegraph_frac = 0.5
    attack_every = 1          # on the deepest clock already: 1.6s

    STOMP_RANGE = 300.0
    STOMP_RADIUS = 210.0
    STOMP_DAMAGE = 22.0

    def __init__(self, pos):
        super().__init__(pos, radius=25.0, speed=104.0)
        self.period = NOTE_PERIOD[0]     # slow, heavy, on the deepest clock

    def behave(self, dt, arena, player, world):
        self.face(player.pos)
        if self.winding:
            self.vel *= 0.9 ** (dt * 60)
            return
        self.seek(player.pos, dt)

    def on_beat(self, dt, arena, player, world):
        if (player.pos - self.pos).length() > self.STOMP_RANGE:
            return
        self.committed = 0.2
        world.shockwave(self.pos, self.STOMP_RADIUS, self.STOMP_DAMAGE,
                        (238, 226, 200), push=560.0)


class Twin(Foe):
    """Punishes dithering, and standing in the wrong place.

    A bonded pair an octave apart. While the bond holds they beat against
    each other, and the beat carries away anything put into either crack - so
    the correct note does *nothing*, which is the one moment in the game
    where matching is not the answer and the player has to notice why.

    The line between them is a live standing wave that hurts, and they
    actively try to *straddle* you - moving to opposite sides so the line
    crosses where you are. Ignoring them while you deal with something else
    is how the line ends up through your chest.

    Shove them past the bond length and it breaks. Force first, then
    resonance: the only enemy that needs both verbs in order.
    """

    kind = "twin"
    label = "Twin"
    lesson = "bonded - the beat eats every note you land. Break them apart."
    punishes = "standing between things"
    cap = 0.8
    mass = 0.8
    attack_every = 2          # the beam sweeps every 1.6s

    BOND_BREAK = 470.0
    BOND_HOLD = 330.0
    BEAT_DAMAGE = 15.0
    BEAT_WIDTH = 46.0

    def __init__(self, pos, note=1):
        super().__init__(pos, note=note, radius=14.0, speed=150.0)
        self.beat_t = 0.0
        self.lead = False
        self.broken = False

    @property
    def bonded(self) -> bool:
        """Bonded until it is broken, and then broken for good.

        This used to be recomputed from the current distance every frame,
        which meant a pair shoved apart snapped straight back together and
        was immune again a third of a second later - so the correct play
        produced a window too short to use and the harness could not clear
        the wave at any seed. "Break them apart" has to mean broken.
        """
        b = self.bond
        if self.broken or b is None or b.dead:
            return False
        if (b.pos - self.pos).length() >= self.BOND_BREAK:
            self.broken = True
            b.broken = True
            return False
        return True

    def beat_hz(self) -> float:
        """|f1 - f2|, the real thing. An octave apart in the simulation is an
        octave apart here, so the envelope is the difference of the two ring
        frequencies and not a number somebody picked."""
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
                world.mark("bonded", self.pos, (232, 200, 255), 0.7)
            return 0.0
        return super().take_ring(ring, world)

    def behave(self, dt, arena, player, world):
        self.beat_t += dt
        b = self.bond
        if not self.bonded:
            self.seek(player.pos, dt)
            return

        gap = b.pos - self.pos
        d = gap.length()
        if d > 1e-6 and d < self.BOND_BREAK:
            stretch = max(-1.0, min(1.0, (d - self.BOND_HOLD) / 140.0))
            self.vel += gap.normalize() * stretch * self.speed * dt * 2.6

        # Straddle: aim for the point opposite the partner, through the
        # player. Two of these will walk the killing line onto you.
        to_player = player.pos - b.pos
        if to_player.length_squared() > 1e-9:
            want = player.pos + to_player.normalize() * (self.BOND_HOLD * 0.5)
            self.seek(want, dt)

    def on_beat(self, dt, arena, player, world):
        b = self.bond
        if b is None or b.dead or not self.bonded or not self.lead:
            return
        if self.envelope() < 0.45:
            return
        world.beam(self.pos, b.pos, self.BEAT_WIDTH, self.BEAT_DAMAGE,
                   (236, 198, 255))


class Overtone(Foe):
    """Punishes over-swelling.

    SPARROW - one octave above the smallest ring a hand can hold steady, so
    it cannot be answered by drawing better. The only way to that note is to
    swell a CHIME until its junctions fold, and the only way to land it is to
    be standing next to the thing, because a SPARROW ring dies at arm's
    length.

    So it drags you in rather than keeping you out. Being close is not the
    challenge. Being close on a 0.4s clock, holding a swell, and letting go
    before your own bell cracks is the challenge - and if you *do* crack it
    in reach of this thing, it feeds: it heals and quickens, because greed is
    the specific mistake this enemy is here to teach.
    """

    kind = "overtone"
    label = "Overtone"
    lesson = "an octave above any bell you can draw. Swell one until it climbs."
    punishes = "greed - crack your bell near it and it feeds"
    note = 4
    cap = 2.0      # about two full swells
    mass = 3.4
    telegraph_frac = 0.4
    # SPARROW ticks five times a second. It tolls on every fourth, which is
    # 1.6s - long enough to hold a swell in, short enough to make holding it
    # a decision.
    attack_every = 4

    PULL_RANGE = 620.0
    PULL = 210.0
    TOLL_RADIUS = 200.0
    TOLL_DAMAGE = 20.0

    def __init__(self, pos):
        super().__init__(pos, radius=32.0, speed=78.0)
        self.fed = 0

    def behave(self, dt, arena, player, world):
        self.seek(player.pos, dt, stand_off=210.0)
        to = self.pos - player.pos
        d = to.length()
        if 1e-6 < d < self.PULL_RANGE and player.dash_t <= 0.0:
            # It hauls you in. The fight it wants is the fight you need.
            player.vel += to.normalize() * self.PULL * dt

    def on_beat(self, dt, arena, player, world):
        if (player.pos - self.pos).length() > self.TOLL_RADIUS * 1.4:
            return
        self.committed = 0.18
        world.shockwave(self.pos, self.TOLL_RADIUS, self.TOLL_DAMAGE,
                        notes.NOTE_COLORS[4], push=300.0)

    def feed(self, world):
        """Somebody cracked a bell inside its reach."""
        self.fed += 1
        self.crack = max(0.0, self.crack - 0.5)
        self.base_speed *= 1.16
        self.flash = 1.0
        world.mark("feed", self.pos, (255, 150, 120), 1.0)
        world.shake = min(1.6, world.shake + 0.6)


class GreatBell(Foe):
    """Punishes not knowing your own bells.

    It tolls a phrase - notes, announced one at a time, each launching a ring
    at the arena. Every ring can be dashed, and every ring can also be
    *answered*: put out the same note and the two fronts delete each other,
    which is the simulation's own antiphase cancellation doing exactly what
    it does in the physics package's selftests.

    Answer the whole phrase and it staggers with its mouth open, which is the
    only window in which it can be cracked. A call and response where the
    call is pitch, and there is no way to fake knowing the answer.
    """

    kind = "greatbell"
    label = "The Great Bell"
    lesson = "answer its phrase in the same note - matched fronts cancel"
    punishes = "carrying only one bell"
    note = 2
    cap = 3.6
    mass = 9.0
    telegraph_frac = 0.55
    attack_every = 2          # on the BOURDON clock: a toll every 3.2s

    TOLL_DAMAGE = 26.0

    def __init__(self, pos, phrase=None):
        super().__init__(pos, radius=52.0, speed=52.0)
        self.phrase = list(phrase or [1, 2, 1])
        self.step = 0
        self.answered = 0
        self.open_t = 0.0
        self.period = NOTE_PERIOD[0]      # it is a great bell; it tolls slow

    @property
    def crackable(self) -> bool:
        # Sealed until the phrase is answered. Not a resistance stat - it is
        # a closed shell, and a closed shell does not ring.
        return self.open_t > 0.0

    @property
    def next_note(self) -> int:
        return self.phrase[self.step % len(self.phrase)]

    def behave(self, dt, arena, player, world):
        self.open_t = max(0.0, self.open_t - dt)
        self.seek(player.pos, dt, stand_off=360.0)

    def on_beat(self, dt, arena, player, world):
        if self.open_t > 0.0:
            return
        n = self.next_note
        world.hostile_ring(self.pos, n, 1.0, announce=n, source=self,
                           damage=self.TOLL_DAMAGE)
        self.step += 1

    def answered_toll(self, world):
        self.answered += 1
        if self.answered >= len(self.phrase):
            self.answered = 0
            self.step = 0
            self.open_t = 4.4
            self.stagger = 1.1
            world.boss_opened(self)


def make_twins(pos, spread=300.0):
    a = Twin(pygame.Vector2(pos) + pygame.Vector2(-spread / 2, 0), note=1)
    b = Twin(pygame.Vector2(pos) + pygame.Vector2(spread / 2, 0), note=2)
    a.bond, b.bond = b, a
    a.lead = True      # only one of the pair fires the beam, so it fires once
    return [a, b]


FOE_TYPES = {
    "husk": Husk,
    "glasswing": Glasswing,
    "deadweight": Deadweight,
    "twin": Twin,
    "overtone": Overtone,
    "greatbell": GreatBell,
}
