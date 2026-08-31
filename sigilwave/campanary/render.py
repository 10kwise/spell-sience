"""Drawing the game, and drawing the invisible.

The old build was legible in the way a diagram is legible: the information
was all present, in bars and readouts, and none of it was where the player's
eyes actually were. This file works on one rule instead -

    **every fact the player needs is expressed as something on the floor.**

Not a meter. A circle they are standing inside, a pulse they can count, a
colour that cools as it travels. The three facts that decide every fight -
what note is that thing, how far does my bell reach, and when is the swell -
are all drawn in world space, at the place they apply, so reading them is
the same act as looking where you are going.

Redundancy is deliberate. A foe's note is its colour *and* its pulse tempo
*and* its hum, so the game is playable with the sound off, playable without
fine colour discrimination, and playable by a player who has only noticed
one of the three.
"""

import math

import pygame

from . import notes
from .bell import survived
from .notes import N_NOTES, NOTE_COLORS, NOTE_NAMES, NOTE_PERIOD

BG = (9, 10, 14)
FLOOR = (19, 22, 30)
FLOOR_LINE = (26, 30, 40)
INK = (196, 208, 224)
DIM = (104, 116, 136)
HOT = (255, 244, 224)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


class Glow:
    """One reusable additive layer. Allocating a surface per glow per frame
    is the difference between this running at 120fps and at 40."""

    def __init__(self, size):
        self.surf = pygame.Surface(size, pygame.SRCALPHA)

    def resize(self, size):
        if self.surf.get_size() != size:
            self.surf = pygame.Surface(size, pygame.SRCALPHA)

    def clear(self):
        self.surf.fill((0, 0, 0, 0))

    def blit_onto(self, target):
        target.blit(self.surf, (0, 0), special_flags=pygame.BLEND_ADD)


# ---------------------------------------------------------------- the floor

def draw_floor(surf, cam, belfry):
    surf.fill(BG)
    w, h = surf.get_size()
    step = 128
    ox = int(cam.pos.x - w / 2)
    oy = int(cam.pos.y - h / 2)
    x0 = -(ox % step)
    y0 = -(oy % step)
    for x in range(x0, w + step, step):
        pygame.draw.line(surf, FLOOR_LINE, (x, 0), (x, h))
    for y in range(y0, h + step, step):
        pygame.draw.line(surf, FLOOR_LINE, (0, y), (w, y))

    # The walls are a real part of the fight - things die against them - so
    # they are drawn as something solid rather than as the edge of the grid.
    tl = cam.world_to_screen(pygame.Vector2(0, 0))
    br = cam.world_to_screen(pygame.Vector2(belfry.width, belfry.height))
    rect = pygame.Rect(tl.x, tl.y, br.x - tl.x, br.y - tl.y)
    pygame.draw.rect(surf, (44, 50, 64), rect, 3)
    pygame.draw.rect(surf, (26, 30, 40), rect.inflate(10, 10), 1)


def draw_stains(surf, cam, belfry):
    """Where rings were struck. Fades out. Purely for the sense that the room
    remembers what you did in it."""
    for pos, color, life in belfry.floor_notes:
        p = cam.world_to_screen(pos)
        r = int(26 + 40 * (1.0 - life))
        if r < 2:
            continue
        pygame.draw.circle(surf, scale(color, 0.10 * life), (int(p.x), int(p.y)), r, 1)


# ------------------------------------------------------------------- rings

def draw_ring(glow, cam, ring):
    """An expanding wavefront, cooling as it goes.

    The cooling is the point. One ring shows the whole range law: the hot
    components have already died by the time the front is a body length out,
    so a ring that leaves white arrives blue, and a player watching it learns
    where they have to stand without being told.
    """
    if ring.r <= 1.0:
        return
    p = cam.world_to_screen(ring.origin)
    col = ring.color_at(ring.r)
    left = sum(survived(ring.bands, ring.r)) / max(1e-9, ring.power)
    if left <= 0.01:
        return

    a = min(1.0, left * 1.5)
    r = int(ring.r)
    pygame.draw.circle(glow.surf, (*scale(col, 0.75 * a), 255), (int(p.x), int(p.y)), r, 5)
    pygame.draw.circle(glow.surf, (*scale(col, 0.30 * a), 255), (int(p.x), int(p.y)),
                       max(1, r - 6), 3)
    pygame.draw.circle(glow.surf, (*scale(HOT, 0.35 * a), 255), (int(p.x), int(p.y)),
                       max(1, r + 3), 1)

    # A leaning bell writes its lean into the front.
    if ring.bias_strength > 1e-3 and ring.bias.length_squared() > 1e-9:
        tip = p + pygame.Vector2(ring.bias) * ring.r
        pygame.draw.circle(glow.surf, (*scale(col, 0.5 * a), 255),
                           (int(tip.x), int(tip.y)), max(3, int(10 * a)))


def draw_hostile_ring(glow, cam, ring):
    if ring.r <= 1.0:
        return
    p = cam.world_to_screen(ring.origin)
    col = notes.note_color(ring.note)
    left = sum(survived(ring.bands, ring.r)) / max(1e-9, ring.power)
    if left <= 0.01:
        return
    r = int(ring.r)
    a = min(1.0, left * 1.6)
    # Hostile fronts are drawn dashed, so they never read as your own even
    # for a frame - the one thing that must never be ambiguous.
    steps = max(12, int(r / 9))
    for i in range(steps):
        if i % 2:
            continue
        a0 = math.tau * i / steps
        a1 = math.tau * (i + 0.9) / steps
        pygame.draw.arc(glow.surf, (*scale(col, 0.9 * a), 255),
                        pygame.Rect(p.x - r, p.y - r, r * 2, r * 2), a0, a1, 6)


# ------------------------------------------------------------------- foes

def draw_foe(surf, glow, cam, foe, t):
    p = cam.world_to_screen(foe.pos)
    x, y = int(p.x), int(p.y)
    col = foe.color
    body = lerp(col, HOT, foe.flash * 0.7)

    if foe.telegraph > 0.02:
        # A wind-up is the cheapest fair threat there is, so it gets to be
        # loud: a closing bracket that says exactly when.
        k = 1.0 - foe.telegraph
        rr = int(foe.radius + 46 * foe.telegraph)
        pygame.draw.circle(glow.surf, (*scale((255, 210, 150), 0.8 * foe.telegraph), 255),
                           (x, y), rr, 3)

    _draw_note_pulse(glow, foe, x, y, t)

    r = int(foe.radius)
    pygame.draw.circle(surf, scale(body, 0.34), (x, y), r)
    pygame.draw.circle(surf, body, (x, y), r, 3)
    pygame.draw.circle(glow.surf, (*scale(body, 0.30 + 0.6 * foe.flash), 255), (x, y), r, 2)

    # Three states, and they have to be three *looks*, not one look and two
    # absences. The first cut drew "cannot be cracked right now" the same way
    # for both cases, so the act boss - which has a note and is merely sealed
    # until you answer its phrase - rendered as dead metal, which is the one
    # thing in the game that says "no note will ever work on this".
    if foe.crackable:
        _draw_cracks(surf, foe, x, y, body)
    elif foe.note < 0:
        # Dead metal: hatched, colourless, obviously not a thing with a note.
        for i in range(-r, r, 6):
            h = int(math.sqrt(max(0.0, r * r - i * i)))
            pygame.draw.line(surf, scale(body, 0.5), (x + i, y - h), (x + i, y + h), 1)
    else:
        _draw_sealed(surf, glow, foe, x, y, r, t)

    if foe.stagger > 0.0:
        pygame.draw.circle(glow.surf, (*scale(HOT, 0.35), 255), (x, y), r + 5, 1)


def _draw_note_pulse(glow, foe, x, y, t):
    """A foe's note, as a pulse you can count.

    This is the identify layer, and it costs no UI at all. The ring expands
    on exactly the period a bell of that note would toll at, so a player who
    has played a TENOR for two minutes recognises a TENOR-tuned thing across
    the room by its *tempo*, not by reading a colour off a legend. Colour and
    hum say the same thing at the same time; any one of the three is enough.
    """
    if not foe.crackable:
        return
    period = NOTE_PERIOD[max(0, min(N_NOTES - 1, foe.note))]
    phase = ((t + foe.hum_t) % period) / period
    rr = int(foe.radius + 4 + phase * 40)
    a = (1.0 - phase) ** 1.6
    if a <= 0.02:
        return
    pygame.draw.circle(glow.surf, (*scale(foe.color, 0.72 * a), 255), (x, y), rr, 2)


def _draw_sealed(surf, glow, foe, x, y, r, t):
    """A closed shell. It has a note - you can see its colour and hear its
    hum - and it will not ring until it is open, which is a different
    statement from "nothing rings this" and has to look different."""
    col = foe.color
    for i, k in enumerate((0.86, 0.66, 0.44)):
        pygame.draw.circle(surf, scale(col, 0.45 - 0.1 * i), (x, y), int(r * k), 2)
    # The seam: a band across the mouth that will part when it opens.
    pygame.draw.line(surf, scale(col, 0.8), (x - r, y + int(r * 0.42)),
                     (x + r, y + int(r * 0.42)), 3)
    if getattr(foe, "answered", 0):
        # Show how much of the phrase has been answered, on the thing itself.
        need = len(getattr(foe, "phrase", [1]))
        for i in range(need):
            px = x - (need - 1) * 9 + i * 18
            lit = i < foe.answered
            pygame.draw.circle(glow.surf if lit else surf,
                               (*scale(col, 1.0), 255) if lit else scale(col, 0.25),
                               (px, y - r - 16), 5, 0 if lit else 1)


def _draw_cracks(surf, foe, x, y, body):
    """Damage is drawn on the thing, not on a bar over it. A foe about to
    shatter is visibly about to shatter."""
    frac = foe.crack_fraction
    if frac <= 0.02:
        return
    n = 1 + int(frac * 7)
    r = foe.radius
    for i in range(n):
        a = foe.spin * 0.017 + i * 2.399
        d = pygame.Vector2(math.cos(a), math.sin(a))
        inner = d * r * (0.15 + 0.2 * ((i * 7) % 3))
        outer = d * r * (0.6 + 0.4 * frac)
        mid = inner.rotate(18) * 0.6 + outer * 0.4
        pygame.draw.lines(
            surf, lerp(body, HOT, 0.35 + 0.6 * frac), False,
            [(x + inner.x, y + inner.y), (x + mid.x, y + mid.y), (x + outer.x, y + outer.y)],
            1 + int(frac * 2),
        )


def draw_bond(glow, cam, a, b):
    """The Twins' standing wave: a live envelope between two bodies, not a
    line with a pulsing alpha."""
    pa = cam.world_to_screen(a.pos)
    pb = cam.world_to_screen(b.pos)
    env = a.envelope()
    seg = 26
    for i in range(seg + 1):
        t = i / seg
        q = pa.lerp(pb, t)
        wob = math.sin(t * math.pi) * (10 + 26 * env)
        nrm = (pb - pa)
        if nrm.length_squared() < 1e-6:
            continue
        nrm = pygame.Vector2(-nrm.y, nrm.x).normalize()
        q += nrm * wob * math.sin(t * math.pi * 5 + a.beat_t * 7)
        rr = int(2 + 5 * env)
        pygame.draw.circle(glow.surf, (*scale((240, 200, 255), 0.30 + 0.6 * env), 255),
                           (int(q.x), int(q.y)), rr)


# ----------------------------------------------------------------- player

def draw_reach(surf, glow, cam, player, bell):
    """The pool of sound the player is standing in the middle of.

    The single most important thing on screen, and the thing the old build
    had no equivalent of: it answers "will this reach?" *before* the swing,
    which is the only moment at which the answer is useful.

    Drawn as a filled pool rather than as a hairline circle, because a
    hairline reads as an annotation and a pool reads as a place. The player
    is not looking at a range indicator, they are standing somewhere, and
    the thing they need to know is whether the foe is standing there too.
    """
    if bell is None or bell.is_empty:
        return
    p = cam.world_to_screen(player.pos)
    r = int(bell.reach)
    if r < 4:
        return
    col = bell.color
    lit = 0.10 + 0.16 * bell.charge
    if bell.cracked:
        col, lit = (150, 116, 116), 0.05

    pool = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    c = r + 2
    # Two steps rather than a gradient: full strength out to the shoulder of
    # the falloff, thinner past it. Where a ring stops being lethal and
    # starts being a nudge is a place the player can now see.
    #
    # The intensity lives in the RGB, not in the alpha, and that is not a
    # style choice - BLEND_ADD adds the colour channels outright and ignores
    # the alpha of what it is adding. Dimming these fills by their alpha did
    # exactly nothing, and the arena came out as one flat cyan disc with the
    # fight somewhere underneath it. A pool has to be something you notice
    # you are standing in, not something you have to see past.
    pygame.draw.circle(pool, (*scale(col, 0.030 + 0.05 * lit), 255), (c, c), r)
    pygame.draw.circle(pool, (*scale(col, 0.028 + 0.05 * lit), 255), (c, c), int(r * 0.62))
    surf.blit(pool, (p.x - c, p.y - c), special_flags=pygame.BLEND_ADD)

    # A dashed rim, so the edge is a definite line you can stand on.
    steps = max(24, r // 12)
    for i in range(steps):
        if i % 2:
            continue
        a0 = math.tau * i / steps
        a1 = math.tau * (i + 0.85) / steps
        pygame.draw.arc(glow.surf, (*scale(col, 0.40 + 0.35 * bell.charge), 255),
                        pygame.Rect(p.x - r, p.y - r, r * 2, r * 2), a0, a1, 2)


def draw_beat(glow, cam, player, bell):
    """The swell, drawn as something closing.

    A metronome is a thing you count. A ring collapsing onto the bell is a
    thing you *catch*, which is why this is a circle shrinking to the body
    rather than a bar filling up: the moment to act is the moment the two
    shapes touch, and hands understand that without being taught.
    """
    if bell is None or bell.is_empty or bell.period <= 1e-6:
        return
    p = cam.world_to_screen(player.pos)
    phase = bell.beat_phase
    # Count *toward* the swell: the ring falls in over the beat and snaps.
    closing = 1.0 - phase
    rr = int(player.radius + 6 + closing * 62)
    near = abs(bell.beat_offset()) <= notes.BEAT_WINDOW
    col = HOT if near else (140, 158, 186)
    a = 0.9 if near else 0.34
    pygame.draw.circle(glow.surf, (*scale(col, a), 255), (int(p.x), int(p.y)), rr, 2 if near else 1)


def draw_player(surf, glow, cam, player, bell, t):
    p = cam.world_to_screen(player.pos)
    x, y = int(p.x), int(p.y)

    if player.iframes > 0.0:
        pygame.draw.circle(glow.surf, (*scale((170, 210, 255), 0.55), 255),
                           (x, y), int(player.radius + 10), 2)

    if bell is not None and not bell.is_empty:
        _draw_bell(surf, glow, cam, bell, p, player)

    col = (232, 238, 248)
    if player.hurt > 0.0:
        col = lerp(col, (255, 110, 100), player.hurt)
    r = int(player.radius)
    pygame.draw.circle(surf, scale(col, 0.45), (x, y), r)
    pygame.draw.circle(surf, col, (x, y), r, 3)
    face = p + pygame.Vector2(player.face) * (r + 7)
    pygame.draw.line(surf, scale(col, 0.8), (x, y), (int(face.x), int(face.y)), 2)

    # The hammer: a short bar that cocks back on the wind-up and snaps
    # through on contact. It is the only animation in the game and it is
    # doing all the work of making a strike feel like a strike.
    if player.swing > 0.0 or player.recover > 0.0:
        from .arena import RECOVER, WINDUP
        if player.swing > 0.0:
            k = -0.9 * (player.swing / WINDUP)
        else:
            k = 0.85 * (player.recover / RECOVER)
        d = pygame.Vector2(player.face).rotate(k * 70)
        tip = p + d * (player.radius + 20 + 14 * (1.0 - abs(k)))
        pygame.draw.line(surf, HOT, (x, y), (int(tip.x), int(tip.y)), 3)


def _draw_bell(surf, glow, cam, bell, p, player):
    """The drawn bell, hanging around its owner, at the size it actually is.

    Rendered from the same stroke data the physics compiled, at world scale,
    so a BOURDON is visibly four times a CHIME on the player's own body. This
    is not decoration on the avatar - it *is* the avatar, and the first cut
    of it drew far too faintly and far too small, which quietly deleted the
    game's whole readable statement about itself. If the ladder is not
    obvious from looking at the character, nothing else will teach it.
    """
    from .arena import BELL_WORLD_SCALE
    k = BELL_WORLD_SCALE
    charge = min(1.0, bell.charge * 1.5)
    col = bell.color
    if bell.cracked:
        col = (186, 96, 92)

    for stroke in bell.strokes:
        pts = stroke.points
        if len(pts) < 2:
            continue
        screen = [(p.x + q.x * k, p.y + q.y * k) for q in pts]
        metal = stroke.ink_type.color
        # The metal is always visible; the note's colour rides on top of it
        # and brightens with what the bell is holding.
        pygame.draw.lines(surf, lerp(scale(metal, 0.55), col, 0.35 + 0.5 * charge),
                          False, screen, 3)
        pygame.draw.lines(glow.surf,
                          (*scale(col, 0.35 + 0.6 * charge), 255), False, screen, 3)
        if charge > 0.08:
            pygame.draw.lines(glow.surf, (*scale(col, 0.45 * charge), 255), False,
                              screen, 9)

    if bell.swelling:
        # A swelling bell is visibly being worked: the glow pulses at the
        # rate the drive is climbing, and the colour is already shifting up
        # the ladder because the analyser says it is.
        for stroke in bell.strokes:
            pts = stroke.points
            if len(pts) < 2:
                continue
            screen = [(p.x + q.x * k, p.y + q.y * k) for q in pts]
            pygame.draw.lines(glow.surf, (*scale(HOT, 0.25 + 0.5 * bell.climb_drive), 255),
                              False, screen, 2)

    if bell.char > 0.12:
        # Char is the bell going dark and pitted, not a third meter. You
        # should be able to see that you are cooking it.
        c = min(1.0, bell.char)
        for stroke in bell.strokes:
            pts = stroke.points
            if len(pts) < 6:
                continue
            step = max(2, int(len(pts) / (5 + 16 * c)))
            for i in range(0, len(pts) - 1, step):
                q = pts[i]
                pygame.draw.circle(surf, scale((188, 72, 56), 0.4 + 0.6 * c),
                                   (int(p.x + q.x * k), int(p.y + q.y * k)),
                                   1 + int(c * 2))


# ------------------------------------------------------------------- marks

def draw_marks(surf, glow, cam, belfry, font=None):
    for m in belfry.marks:
        p = cam.world_to_screen(m["pos"])
        x, y = int(p.x), int(p.y)
        # Clamped, because marks are culled at t >= 1 *before* being
        # advanced, so a mark can be drawn one frame past the end - and a
        # negative base with a fractional exponent is a complex number in
        # Python, not a small one.
        t = max(0.0, min(1.0, m["t"]))
        k = m["kind"]
        a = (1.0 - t) ** 1.5
        if a <= 0.01:
            continue
        col = m["color"]
        power = m["power"]

        if k == "shatter":
            # The payoff. Two expanding rings and a flash - short, bright,
            # and unmistakably different from every other event.
            r = int(18 + 190 * t)
            pygame.draw.circle(glow.surf, (*scale(col, a), 255), (x, y), r, max(1, int(7 * a)))
            pygame.draw.circle(glow.surf, (*scale(HOT, a * 0.9), 255), (x, y),
                               int(r * 0.55), max(1, int(4 * a)))
        elif k == "crack":
            r = int(10 + 66 * t * power)
            pygame.draw.circle(glow.surf, (*scale(col, a * 0.9), 255), (x, y), r, 3)
            pygame.draw.circle(glow.surf, (*scale(HOT, a * 0.6), 255), (x, y), int(r * 0.4), 2)
        elif k == "thud":
            # A dull hit looks dull. This is the teaching signal: the player
            # should be able to tell "wrong octave" from "right octave" from
            # across the room, with the sound off.
            r = int(8 + 22 * t)
            pygame.draw.circle(surf, scale((120, 128, 142), a * 0.7), (x, y), r, 2)
        elif k == "slam":
            r = int(12 + 90 * t * power)
            pygame.draw.circle(glow.surf, (*scale((255, 232, 190), a), 255), (x, y), r,
                               max(1, int(5 * a)))
        elif k == "cancel":
            r = int(6 + 74 * t)
            pygame.draw.circle(glow.surf, (*scale(col, a), 255), (x, y), r, 3)
        elif k == "toll":
            r = int(6 + 40 * t)
            pygame.draw.circle(glow.surf, (*scale(col, a * power), 255), (x, y), r, 2)
        elif k == "dash":
            r = int(4 + 34 * t)
            pygame.draw.circle(glow.surf, (*scale(col, a * 0.5), 255), (x, y), r, 1)
        elif k == "open":
            r = int(30 + 250 * t)
            pygame.draw.circle(glow.surf, (*scale(col, a), 255), (x, y), r, max(1, int(9 * a)))


def draw_shards(surf, cam, belfry):
    for pos, vel, life, col in belfry.shards:
        p = cam.world_to_screen(pos)
        a = min(1.0, life * 1.6)
        tail = p - vel * 0.018
        pygame.draw.line(surf, scale(col, a), (int(tail.x), int(tail.y)),
                         (int(p.x), int(p.y)), 2)
