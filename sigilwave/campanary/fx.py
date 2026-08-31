"""Particles, sparks, trails and flashes.

The old build had a shake, a hitstop and seven kinds of expanding circle, and
that is genuinely all it had. Circles are good at saying *where* and terrible
at saying *what*: a wrong-note thud and a correct-note crack were two circles
of different colours, so the single most important teaching signal in the
game arrived as a hue change on a shape you had already seen a hundred times.

This is a plain, cheap particle layer, and its job is to make the three
things that matter feel physically different:

    a matched hit    throws bright shards of the target's own colour
    a wrong note     puffs dull grey and dies immediately
    a shatter        empties the thing into the room

One flat list, one update, one draw. Every particle is a list rather than an
object because there can be a couple of thousand of them and attribute
lookup on a class instance is the difference between this being free and
this being the frame budget.
"""

import math
import random

import pygame

# index layout of a particle
P_POS, P_VEL, P_LIFE, P_MAX, P_COL, P_SIZE, P_KIND, P_DRAG = range(8)

SPARK = 0      # a short streak along its own velocity
MOTE = 1       # a dot that fades
SHARD = 2      # a spinning line segment - glass
SMOKE = 3      # grows and dims
GLINT = 4      # a bright cross that shrinks fast

MAX_PARTICLES = 1400


class Fx:
    def __init__(self, rng=None):
        self.p = []
        self.rng = rng or random.Random()
        # Full-screen flashes and edge vignettes, kept separate because there
        # are never more than a couple and they are drawn differently.
        self.washes = []
        self.vignettes = []

    def clear(self):
        self.p.clear()
        self.washes.clear()

    # ------------------------------------------------------------- spawning

    def _add(self, pos, vel, life, col, size, kind, drag=0.90):
        if len(self.p) >= MAX_PARTICLES:
            return
        self.p.append([pygame.Vector2(pos), pygame.Vector2(vel), life, life,
                       col, size, kind, drag])

    def burst(self, pos, n, col, speed=(120, 420), life=(0.18, 0.5),
              size=(2, 4), kind=SPARK, drag=0.90, direction=None, spread=math.tau):
        """A radial spray. `direction` + `spread` narrow it into a cone."""
        r = self.rng
        base = r.uniform(0, math.tau) if direction is None else math.atan2(direction.y, direction.x)
        for _ in range(n):
            a = base + r.uniform(-spread / 2, spread / 2)
            s = r.uniform(*speed)
            self._add(pos, (math.cos(a) * s, math.sin(a) * s),
                      r.uniform(*life), col, r.uniform(*size), kind, drag)

    def glass(self, pos, n, col, speed=(200, 720)):
        """Something resonant coming apart. Shards, not dots."""
        self.burst(pos, n, col, speed=speed, life=(0.4, 0.95), size=(6, 16),
                   kind=SHARD, drag=0.93)
        self.burst(pos, n // 2, (255, 252, 246), speed=(140, 500), life=(0.2, 0.5),
                   size=(2, 4), kind=SPARK, drag=0.88)

    def thud(self, pos, col=(126, 132, 146)):
        """A wrong-note hit. Deliberately, visibly nothing much."""
        self.burst(pos, 5, col, speed=(40, 130), life=(0.12, 0.24),
                   size=(2, 3), kind=MOTE, drag=0.80)

    def sparks(self, pos, n, col, direction=None, spread=1.6, speed=(200, 620)):
        self.burst(pos, n, col, speed=speed, life=(0.14, 0.36), size=(2, 5),
                   kind=SPARK, drag=0.86, direction=direction, spread=spread)

    def smoke(self, pos, n, col=(96, 92, 96), speed=(20, 90)):
        self.burst(pos, n, col, speed=speed, life=(0.5, 1.2), size=(6, 14),
                   kind=SMOKE, drag=0.94)

    def glint(self, pos, col, size=14.0, life=0.22):
        self._add(pos, (0, 0), life, col, size, GLINT, 1.0)

    def trail(self, pos, vel, col, n=2):
        for _ in range(n):
            jitter = pygame.Vector2(self.rng.uniform(-6, 6), self.rng.uniform(-6, 6))
            self._add(pos + jitter, -pygame.Vector2(vel) * 0.12,
                      self.rng.uniform(0.12, 0.26), col,
                      self.rng.uniform(2, 4), MOTE, 0.88)

    def implode(self, pos, n, col, radius=90.0, life=0.32):
        """Particles falling *inward*: a swell drawing the room into the bell.
        Spawned out at `radius` with velocity pointing home."""
        r = self.rng
        for _ in range(n):
            a = r.uniform(0, math.tau)
            d = pygame.Vector2(math.cos(a), math.sin(a))
            start = pygame.Vector2(pos) + d * r.uniform(radius * 0.6, radius)
            self._add(start, -d * (radius / max(0.05, life)) * 0.9,
                      r.uniform(life * 0.6, life), col, r.uniform(2, 4), SPARK, 1.0)

    # Total screen tint allowed at once, however many things are happening.
    # Without a cap these stack: at a busy moment - two shatters and a hit
    # inside a third of a second - the arena came out flat olive with the
    # fight somewhere underneath it. A wash is punctuation, and punctuation
    # does not get to be the loudest thing on the page.
    WASH_CAP = 0.085

    def wash(self, color, strength=0.4, life=0.3):
        """A full-screen flash. Short and weak on purpose: this game is drawn
        on near-black, so a tint that lasts a quarter of a second and covers
        everything does not punctuate the moment, it hides the next one."""
        self.washes.append([color, strength, life, life])

    def vignette(self, color, strength=0.5, life=0.35):
        """Colour crowding in from the edges.

        Where damage feedback belongs. A full-screen wash for taking a hit
        washed out the arena at exactly the moment the player most needed to
        see it; an edge vignette is unmissable in peripheral vision and
        leaves the middle of the screen alone.
        """
        self.vignettes.append([color, strength, life, life])

    # --------------------------------------------------------------- update

    def update(self, dt):
        alive = []
        for q in self.p:
            q[P_LIFE] -= dt
            if q[P_LIFE] <= 0.0:
                continue
            q[P_POS] += q[P_VEL] * dt
            if q[P_DRAG] < 1.0:
                q[P_VEL] *= q[P_DRAG] ** (dt * 60)
            alive.append(q)
        self.p = alive

        washes = []
        for w in self.washes:
            w[2] -= dt
            if w[2] > 0.0:
                washes.append(w)
        self.washes = washes

        vs = []
        for v in self.vignettes:
            v[2] -= dt
            if v[2] > 0.0:
                vs.append(v)
        self.vignettes = vs

    # ----------------------------------------------------------------- draw

    def draw(self, surf, glow, cam):
        for q in self.p:
            t = q[P_LIFE] / max(1e-6, q[P_MAX])
            p = cam.world_to_screen(q[P_POS])
            x, y = int(p.x), int(p.y)
            col = q[P_COL]
            kind = q[P_KIND]
            k = q[P_SIZE]

            if kind == SPARK:
                v = q[P_VEL]
                tail = p - v * 0.016
                _line(glow, col, t, (int(tail.x), int(tail.y)), (x, y),
                      max(1, int(k * t)))
            elif kind == MOTE:
                _dot(glow, col, t, x, y, max(1, int(k * t)))
            elif kind == SHARD:
                v = q[P_VEL]
                if v.length_squared() < 1e-6:
                    continue
                d = v.normalize() * k * (0.4 + 0.6 * t)
                _line(surf, col, t, (int(p.x - d.x), int(p.y - d.y)),
                      (int(p.x + d.x), int(p.y + d.y)), 2)
                _dot(glow, col, t * 0.6, x, y, 2)
            elif kind == SMOKE:
                r = int(k * (1.6 - t))
                if r > 0:
                    _dot(surf, col, t * 0.35, x, y, r)
            elif kind == GLINT:
                r = int(k * t)
                if r > 0:
                    _line(glow, col, t, (x - r, y), (x + r, y), 2)
                    _line(glow, col, t, (x, y - r), (x, y + r), 2)

    def draw_washes(self, surf):
        """One blit, whatever is going on.

        Blitting each wash separately meant N events tinted the screen N
        times over, so the cost of a good moment was not being able to see
        the next one. The active washes are averaged into a single colour by
        weight and their strengths summed under a cap.
        """
        if not self.washes:
            return False
        total = 0.0
        r = g = b = 0.0
        for color, strength, life, mx in self.washes:
            a = strength * (life / max(1e-6, mx))
            if a <= 0.004:
                continue
            total += a
            r += color[0] * a
            g += color[1] * a
            b += color[2] * a
        if total <= 0.004:
            return False
        col = (int(r / total), int(g / total), int(b / total))
        alpha = int(255 * min(self.WASH_CAP, total))
        if alpha <= 1:
            return False
        w, h = surf.get_size()
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((*col, alpha))
        surf.blit(veil, (0, 0))
        return True

    def draw_vignettes(self, surf):
        if not self.vignettes:
            return False
        total = 0.0
        r = g = b = 0.0
        for color, strength, life, mx in self.vignettes:
            a = strength * (life / max(1e-6, mx)) ** 0.7
            if a <= 0.004:
                continue
            total += a
            r += color[0] * a
            g += color[1] * a
            b += color[2] * a
        if total <= 0.004:
            return False
        col = (int(r / total), int(g / total), int(b / total))
        k = min(1.0, total)
        w, h = surf.get_size()
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        steps = 16
        depth = int(min(w, h) * 0.22)
        for i in range(steps):
            t = i / steps
            a = int(190 * k * (1.0 - t) ** 2)
            if a <= 1:
                continue
            inset = int(depth * t)
            pygame.draw.rect(band, (*col, a),
                             (inset, inset, w - inset * 2, h - inset * 2),
                             max(1, depth // steps + 1))
        surf.blit(band, (0, 0))
        return True


def _scale(col, k):
    k = max(0.0, min(1.0, k))
    return (int(col[0] * k), int(col[1] * k), int(col[2] * k))


def _dot(target, col, t, x, y, r):
    if r <= 0:
        return
    is_glow = hasattr(target, "surf")
    dest = target.surf if is_glow else target
    pygame.draw.circle(dest, (*_scale(col, t), 255) if is_glow else _scale(col, t),
                       (x, y), r)


def _line(target, col, t, a, b, w):
    is_glow = hasattr(target, "surf")
    dest = target.surf if is_glow else target
    pygame.draw.line(dest, (*_scale(col, t), 255) if is_glow else _scale(col, t),
                     a, b, max(1, w))
