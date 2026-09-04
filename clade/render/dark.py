"""Drawing the dark.

The pipeline, once, so the ordering is not a mystery later:

    1. albedo    the room's own colours, cached per room, drawn unlit.
    2. lightmap  a 1/5-scale additive buffer. every light in the world is a
                 pre-rendered radial gradient blitted into it.
    3. multiply   albedo * upscale(lightmap). this is the whole "volumetric"
                 effect and it costs one smoothscale and one BLEND_MULT.
    4. emissive   things that make their own light are drawn *after* the
                 multiply, additively, so they survive being in the dark.
    5. murk       silt as a fog layer, then marine snow, then the vignette.

Two decisions worth defending:

**The ambient is not black.** It is (7,10,13). Pure black makes an empty
room and a solid wall identical, and a player who cannot tell those apart
is not frightened, they are annoyed — they read it as the renderer being
broken rather than as the dark being dark.

**Creatures you cannot see are drawn as holes.** A thing outside your light
but inside your half-light is rendered *darker than the background* — a
disturbance in the water rather than a shape. You do not see the Silt
Mother. You see the place where the water stops telling you anything, and
you watch that place move. Making absence render as information is the
single highest-value thing in this file.
"""

import math
import random

import pygame

from .. import config as C
from ..humours import BRINE, ICHOR, SILT, SPARK
from ..world.fields import FREEZE_AT
from ..world.room import ROCK, TISSUE, WATER

_glow_cache = {}
_albedo_cache = {}


def glow_sprite(radius, color=(255, 255, 255)):
    """A radial falloff disc, cached by (radius, colour). Falloff is
    quadratic-ish rather than linear because linear light looks like a
    stage spot and quadratic looks like something in water."""
    key = (int(radius), color)
    s = _glow_cache.get(key)
    if s is not None:
        return s
    r = max(2, int(radius))
    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    steps = max(10, min(40, r))
    for i in range(steps, 0, -1):
        t = i / steps
        rad = int(r * t)
        k = (1.0 - t)
        a = k * k * 1.35
        a = min(1.0, a)
        col = (int(color[0] * a), int(color[1] * a), int(color[2] * a))
        pygame.draw.circle(surf, col, (r, r), rad)
    _glow_cache[key] = surf
    return surf


def _tint(color, k):
    return (max(0, min(255, int(color[0] * k))),
            max(0, min(255, int(color[1] * k))),
            max(0, min(255, int(color[2] * k))))


def room_albedo(room, region_tint):
    """The room's unlit colours, built once. Rock gets a per-tile jitter so
    a wall reads as stone rather than as a rectangle, and any rock face
    that touches water gets a brighter lip — which is what makes geometry
    legible at the very edge of a lamp, where almost all of this game's
    navigation actually happens."""
    key = (room.key, id(room))
    surf = _albedo_cache.get(key)
    if surf is not None:
        return surf

    w, h = room.pixel_w, room.pixel_h
    surf = pygame.Surface((w, h)).convert()
    rng = random.Random(hash(room.key) & 0xFFFF)
    base = region_tint
    surf.fill(_tint(base, 0.34))

    T = C.TILE
    for ty in range(room.h):
        for tx in range(room.w):
            t = room.tiles[ty][tx]
            if t == WATER:
                continue
            r = pygame.Rect(tx * T, ty * T, T, T)
            if t == TISSUE:
                # Grown. It is the only warm thing on the palette and it is
                # meant to be noticed from across a room: a door that is
                # alive should look alive.
                j = rng.uniform(0.82, 1.18)
                surf.fill(_tint((104, 56, 62), j), r)
            else:
                j = rng.uniform(0.72, 1.30)
                surf.fill(_tint(base, 1.45 * j), r)

    # Lips: the top edge of any rock that has water above it.
    for ty in range(room.h):
        for tx in range(room.w):
            if room.tiles[ty][tx] != ROCK:
                continue
            if ty > 0 and room.tiles[ty - 1][tx] == WATER:
                surf.fill(_tint(base, 1.85),
                          pygame.Rect(tx * T, ty * T, T, 3))
            if ty < room.h - 1 and room.tiles[ty + 1][tx] == WATER:
                surf.fill(_tint(base, 1.15),
                          pygame.Rect(tx * T, (ty + 1) * T - 2, T, 2))
    _albedo_cache[key] = surf
    return surf


class Snow:
    """Marine snow. Dead things falling, forever, which is what the deep
    ocean actually looks like and which happens to be the cheapest possible
    way to make water feel like a volume rather than a backdrop."""

    def __init__(self, n=340, w=1600, h=1000, seed=1):
        rng = random.Random(seed)
        self.pts = [[rng.uniform(0, w), rng.uniform(0, h),
                     rng.uniform(0.25, 1.0)] for _ in range(n)]
        self.w, self.h = w, h

    def update(self, dt, current):
        for p in self.pts:
            p[0] += (current[0] * 0.12 + 3.0 * p[2]) * dt
            p[1] += (current[1] * 0.12 + 11.0 * p[2]) * dt
            if p[1] > self.h:
                p[1] -= self.h
            if p[0] > self.w:
                p[0] -= self.w
            elif p[0] < 0:
                p[0] += self.w


class Camera:
    def __init__(self, w, h):
        self.x = 0.0
        self.y = 0.0
        self.w = w
        self.h = h
        self.shake = 0.0

    def follow(self, target, room, dt, lead=(0.0, 0.0)):
        want_x = target[0] - self.w * 0.5 + lead[0]
        want_y = target[1] - self.h * 0.5 + lead[1]
        k = min(1.0, dt * 4.4)
        self.x += (want_x - self.x) * k
        self.y += (want_y - self.y) * k
        self.x = max(0.0, min(max(0.0, room.pixel_w - self.w), self.x))
        self.y = max(0.0, min(max(0.0, room.pixel_h - self.h), self.y))

    def offset(self):
        if self.shake > 0.1:
            return (int(self.x + random.uniform(-self.shake, self.shake)),
                    int(self.y + random.uniform(-self.shake, self.shake)))
        return (int(self.x), int(self.y))

    def to_screen(self, p, off=None):
        o = off or self.offset()
        return (int(p[0] - o[0]), int(p[1] - o[1]))


class DarkRenderer:
    def __init__(self, size):
        self.w, self.h = size
        self.lw = self.w // C.LIGHT_SCALE
        self.lh = self.h // C.LIGHT_SCALE
        self.light = pygame.Surface((self.lw, self.lh))
        self.scratch = pygame.Surface((self.w, self.h))
        self.fog = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.snow = Snow(w=self.w + 200, h=self.h + 200)
        self.camera = Camera(self.w, self.h)
        self.time = 0.0

    # ------------------------------------------------------------- lights

    def _add_light(self, pos, radius, color, off, strength=1.0):
        if radius < 2.0 or strength <= 0.01:
            return
        sx = (pos[0] - off[0]) / C.LIGHT_SCALE
        sy = (pos[1] - off[1]) / C.LIGHT_SCALE
        r = radius / C.LIGHT_SCALE
        if sx + r < 0 or sx - r > self.lw or sy + r < 0 or sy - r > self.lh:
            return
        c = (max(0, min(255, int(color[0] * strength))),
             max(0, min(255, int(color[1] * strength))),
             max(0, min(255, int(color[2] * strength))))
        g = glow_sprite(r, c)
        self.light.blit(g, (int(sx - r), int(sy - r)),
                        special_flags=pygame.BLEND_ADD)

    # -------------------------------------------------------------- draw

    def draw(self, screen, world, player, dt):
        self.time += dt
        room = world.room
        region = _region_tint(world)
        cam = self.camera
        cam.shake = player.shake
        cam.follow(player.pos, room, dt,
                   lead=(player.aim[0] * 60.0, player.aim[1] * 60.0))
        off = cam.offset()

        # 1. albedo
        albedo = room_albedo(room, region)
        self.scratch.fill(C.AMBIENT)
        self.scratch.blit(albedo, (-off[0], -off[1]))

        # 2. lights
        self.light.fill(C.LIGHT_FLOOR)
        self._light_pass(world, player, off)

        # 3. multiply
        big = pygame.transform.smoothscale(self.light, (self.w, self.h))
        self.scratch.blit(big, (0, 0), special_flags=pygame.BLEND_MULT)

        # 4. emissive
        self._heat_pass(room, off)
        self._entities(world, player, off)

        # 5. murk, snow, vignette
        self._murk_pass(room, off)
        self._snow_pass(room, off, dt)

        screen.blit(self.scratch, (0, 0))
        return off

    def _light_pass(self, world, player, off):
        room = world.room
        b = player.body

        # You. Colour comes from your own composition, so a body full of
        # heat burns orange and a body full of sediment barely burns at all
        # — your light is a readout of what you are carrying, and every
        # creature in the room is reading it too.
        col = b.reserve.color()
        self._add_light(player.pos, player.sight, col, off, 0.95)
        self._add_light(player.pos, player.sight * 0.35, (255, 250, 240), off,
                        0.55)

        for c in world.creatures:
            if c.dead or c.sp.glow <= 0.01:
                continue
            pulse = 0.85 + 0.15 * math.sin(self.time * 2.2 + c.pos[0] * 0.01)
            self._add_light(c.pos, 60.0 + c.sp.glow * 200.0,
                            c.composition.color(), off, c.sp.glow * pulse)

        for m in world.motes + world.hostile_motes:
            lit = m.effect.light
            if lit > 0.05:
                self._add_light(m.pos, 30.0 + lit * 16.0, m.effect.color, off,
                                min(1.2, 0.35 + lit * 0.12))

        for cp in world.corpses:
            self._add_light(cp.pos, 34.0, cp.charge.color(), off, 0.18)

        self._heat_lights(room, off)

        for (kind, x, y, data) in room.props:
            if kind == "vent":
                self._add_light((x, y), 92.0, (120, 190, 200), off, 0.30)
            elif kind == "quiet":
                self._add_light((x, y), 130.0, (150, 200, 190), off, 0.42)
            elif kind in ("fragment", "organ", "nerve"):
                pid = data.get("id")
                if pid in world.picked_up:
                    continue
                pulse = 0.5 + 0.32 * math.sin(self.time * 1.7 + x * 0.02)
                self._add_light((x, y), 58.0, (210, 220, 235), off, pulse)

    def _visible_cells(self, f, off):
        cell = C.FIELD_CELL
        return (max(0, int(off[1] / cell) - 1),
                min(f.h, int((off[1] + self.h) / cell) + 2),
                max(0, int(off[0] / cell) - 1),
                min(f.w, int((off[0] + self.w) / cell) + 2))

    def _heat_lights(self, room, off):
        """Fire is a light, not a decal.

        Drawing hot water only as an additive overlay after the lightmap
        multiply gives you a bright orange shape floating in front of a
        room that is still pitch dark — the fire is visible and the wall
        two metres from it is not, which reads as a sticker rather than as
        a fire. Putting the hot cells into the lightmap first means a blaze
        genuinely lights the geometry around it, and that is what makes
        setting one a tactical decision instead of a cosmetic one.

        Sampled every other cell: at this radius the gradients overlap
        heavily and the halved count is invisible in the result."""
        f = room.fields
        r0, r1, c0, c1 = self._visible_cells(f, off)
        cell = C.FIELD_CELL
        heat = f.heat
        for r in range(r0, r1, 2):
            for c in range(c0, c1, 2):
                h = float(heat[r, c])
                if h <= 0.30:
                    continue
                a = min(1.0, h / 3.0)
                self._add_light((c * cell + cell * 0.5, r * cell + cell * 0.5),
                                62.0 + a * 105.0,
                                (255, 150, 70), off, 0.30 + a * 0.75)

    def _heat_pass(self, room, off):
        """The body of the fire itself, and ice. Drawn after the multiply so
        burning water stays bright regardless of what is lighting it."""
        f = room.fields
        cell = C.FIELD_CELL
        r0, r1, c0, c1 = self._visible_cells(f, off)
        heat = f.heat
        for r in range(r0, r1):
            for c in range(c0, c1):
                h = float(heat[r, c])
                if h > 0.28:
                    # Jittered by cell so a burning region reads as churn
                    # rather than as the square grid it is stored on.
                    j = ((r * 73856093) ^ (c * 19349663)) & 0xFF
                    ox = (j & 15) - 7
                    oy = ((j >> 4) & 15) - 7
                    x = int(c * cell - off[0]) + ox
                    y = int(r * cell - off[1]) + oy
                    a = min(1.0, h / 3.4)
                    wob = 0.82 + 0.18 * math.sin(self.time * 5.0 + j)
                    col = (int(190 * a * wob + 30), int(84 * a * wob + 10),
                           int(30 * a))
                    rad = cell * (0.85 + 0.5 * a)
                    g = glow_sprite(rad, col)
                    self.scratch.blit(
                        g, (x - int(rad), y - int(rad)),
                        special_flags=pygame.BLEND_ADD)
                elif h < FREEZE_AT:
                    x = int(c * cell - off[0])
                    y = int(r * cell - off[1])
                    pygame.draw.rect(
                        self.scratch, (108, 140, 168),
                        pygame.Rect(x, y, int(cell) + 1, int(cell) + 1))
                    pygame.draw.rect(
                        self.scratch, (162, 196, 220),
                        pygame.Rect(x, y, int(cell) + 1, int(cell) + 1), 1)
                elif h < FREEZE_AT * 0.55:
                    x = int(c * cell - off[0])
                    y = int(r * cell - off[1])
                    s = pygame.Surface((int(cell) + 1, int(cell) + 1),
                                       pygame.SRCALPHA)
                    s.fill((70, 100, 130, 60))
                    self.scratch.blit(s, (x, y))

    def _murk_pass(self, room, off):
        f = room.fields
        if f.silt.max() < 0.06:
            return
        cell = C.FIELD_CELL
        self.fog.fill((0, 0, 0, 0))
        c0 = max(0, int(off[0] / cell) - 1)
        r0 = max(0, int(off[1] / cell) - 1)
        c1 = min(f.w, int((off[0] + self.w) / cell) + 2)
        r1 = min(f.h, int((off[1] + self.h) / cell) + 2)
        silt = f.silt
        step = int(cell) + 1
        for r in range(r0, r1):
            for c in range(c0, c1):
                s = float(silt[r, c])
                if s < 0.08:
                    continue
                a = int(min(224, s * 150))
                self.fog.fill(
                    (46, 42, 36, a),
                    pygame.Rect(int(c * cell - off[0]), int(r * cell - off[1]),
                                step, step))
        blurred = pygame.transform.smoothscale(
            pygame.transform.smoothscale(self.fog, (self.w // 6, self.h // 6)),
            (self.w, self.h))
        self.scratch.blit(blurred, (0, 0))

    def _snow_pass(self, room, off, dt):
        cur = room.fields.current_at(
            (off[0] + self.w * 0.5, off[1] + self.h * 0.5))
        self.snow.update(dt, cur)
        surf = self.scratch
        px = off[0] % self.snow.w
        py = off[1] % self.snow.h
        for p in self.snow.pts:
            x = int(p[0] - px)
            y = int(p[1] - py)
            if x < 0: x += self.snow.w
            if y < 0: y += self.snow.h
            if 0 <= x < self.w and 0 <= y < self.h:
                v = int(38 + 74 * p[2])
                surf.set_at((x, y), (v, v, int(v * 1.05)))

    # ---------------------------------------------------------- entities

    def _entities(self, world, player, off):
        surf = self.scratch
        sight = player.sight

        for cp in world.corpses:
            p = (int(cp.pos[0] - off[0]), int(cp.pos[1] - off[1]))
            fade = max(0.15, 1.0 - cp.age / cp.life)
            col = _tint(cp.charge.color(), 0.30 + 0.4 * fade)
            pygame.draw.circle(surf, col, p, 9)
            pygame.draw.circle(surf, _tint(col, 0.5), p, 13, 1)

        for (kind, x, y, data) in world.room.props:
            self._prop(surf, kind, x, y, data, world, off)

        for m in world.motes:
            self._mote(surf, m, off, friendly=True)
        for m in world.hostile_motes:
            self._mote(surf, m, off, friendly=False)

        for c in world.creatures:
            if c.dead:
                continue
            self._creature(surf, c, player, world, off, sight)

        self._player(surf, player, world, off)

    def _prop(self, surf, kind, x, y, data, world, off):
        pid = data.get("id")
        if kind in ("fragment", "organ", "nerve") and pid in world.picked_up:
            return
        p = (int(x - off[0]), int(y - off[1]))
        if p[0] < -40 or p[0] > self.w + 40 or p[1] < -40 or p[1] > self.h + 40:
            return
        t = self.time
        if kind == "fragment":
            pygame.draw.circle(surf, (196, 206, 224), p, 5)
            pygame.draw.circle(surf, (120, 132, 152), p,
                               int(9 + 3 * math.sin(t * 2.0)), 1)
        elif kind == "organ":
            pygame.draw.circle(surf, (228, 176, 140), p, 6)
            pygame.draw.circle(surf, (150, 96, 84), p,
                               int(11 + 3 * math.sin(t * 1.6)), 1)
        elif kind == "nerve":
            pygame.draw.circle(surf, (206, 168, 240), p, 5)
            pygame.draw.circle(surf, (140, 108, 176), p,
                               int(10 + 3 * math.sin(t * 2.4)), 1)
        elif kind == "quiet":
            pygame.draw.circle(surf, (110, 160, 150), p,
                               int(26 + 4 * math.sin(t * 0.9)), 2)
            pygame.draw.circle(surf, (150, 200, 186), p, 4)
        elif kind == "vent":
            for i in range(3):
                a = t * 0.6 + i * 2.1
                r = 14 + i * 9
                pygame.draw.circle(surf, (70, 110, 118),
                                   (p[0] + int(math.cos(a) * 3), p[1] - i * 7),
                                   r, 1)
        elif kind == "ending":
            pygame.draw.circle(surf, (200, 190, 170), p,
                               int(40 + 8 * math.sin(t * 0.6)), 1)

    def _mote(self, surf, m, off, friendly):
        if m.delay > 0.0:
            return
        p = (int(m.pos[0] - off[0]), int(m.pos[1] - off[1]))
        col = m.effect.color
        r = max(2, int(m.radius * 0.7))
        if m.shape.kind == "beam":
            tail = (int(p[0] - m.vel[0] * 0.035), int(p[1] - m.vel[1] * 0.035))
            pygame.draw.line(surf, col, tail, p, max(2, r // 2))
        else:
            pygame.draw.circle(surf, col, p, r)
            pygame.draw.circle(surf, _tint(col, 0.45), p, r + 3, 1)
        if not friendly:
            pygame.draw.circle(surf, (255, 210, 210), p, max(1, r // 2))

    def _creature(self, surf, c, player, world, off, sight):
        p = (int(c.pos[0] - off[0]), int(c.pos[1] - off[1]))
        if p[0] < -80 or p[0] > self.w + 80 or p[1] < -80 or p[1] > self.h + 80:
            return
        d = c.distance_to(player.pos)
        vis = world.room.fields.visibility_along(player.pos, c.pos)
        lit = (sight + c.sp.glow * 240.0) * vis
        r = int(c.sp.radius)

        if d > lit:
            # Outside your light. You do not see it — you see the water not
            # behaving. Drawn darker than the ground so it reads as a hole.
            if d < lit * 1.75:
                k = 1.0 - (d - lit) / max(1.0, lit * 0.75)
                s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
                pygame.draw.circle(s, (0, 0, 0, int(150 * k)),
                                   (r * 2, r * 2), int(r * 1.5))
                surf.blit(s, (p[0] - r * 2, p[1] - r * 2))
            return

        base = c.composition.color()
        if c.hurt_flash > 0.05:
            base = (255, 236, 226)
        elif c.fed_flash > 0.05:
            base = (255, 200, 120)
        k = 0.35 + 0.65 * min(1.0, (lit - d) / max(1.0, lit * 0.5))
        col = _tint(base, k)

        pygame.draw.circle(surf, col, p, r)
        pygame.draw.circle(surf, _tint(base, k * 0.5), p, r + 4, 1)

        # A wedge showing where it is facing. In a game where most of what
        # you know about a creature is which way it is pointed, this is not
        # decoration.
        f = c.facing
        tip = (p[0] + int(f[0] * (r + 8)), p[1] + int(f[1] * (r + 8)))
        pygame.draw.line(surf, _tint(base, k * 0.8), p, tip, 2)

        from ..creatures import ALERT, HUNT, STRIKE
        if c.state == STRIKE:
            pygame.draw.circle(surf, (255, 190, 170), p, r + 9, 2)
        elif c.state == HUNT:
            pygame.draw.circle(surf, (220, 140, 130), p, r + 7, 1)
        elif c.state == ALERT or c.alarm > 0.3:
            n = int(6 + c.alarm * 10)
            pygame.draw.arc(surf, (200, 190, 120),
                            pygame.Rect(p[0] - r - 8, p[1] - r - 8,
                                        (r + 8) * 2, (r + 8) * 2),
                            0, c.alarm * math.tau, 1)
        if c.tag == "venting":
            pygame.draw.circle(surf, (255, 150, 90), p, r + 3, 3)

        # Viability, but only as a thinning ring — a number would break the
        # fiction and a bar would break the dark.
        if c.viability < c.max_viability - 0.5:
            frac = max(0.0, c.viability / c.max_viability)
            pygame.draw.arc(surf, (230, 230, 240),
                            pygame.Rect(p[0] - r - 5, p[1] - r - 5,
                                        (r + 5) * 2, (r + 5) * 2),
                            -math.pi / 2, -math.pi / 2 + frac * math.tau, 2)

    def _player(self, surf, player, world, off):
        p = (int(player.pos[0] - off[0]), int(player.pos[1] - off[1]))
        b = player.body
        col = b.reserve.color()
        if player.hurt_flash > 0.05:
            col = (255, 230, 230)
        pygame.draw.circle(surf, col, p, 9)
        pygame.draw.circle(surf, _tint(col, 0.55), p, 13, 1)
        a = player.aim
        pygame.draw.line(surf, _tint(col, 0.85), p,
                         (p[0] + int(a[0] * 22), p[1] + int(a[1] * 22)), 2)
        if player.biting is not None:
            t = min(1.0, player.bite_time * 1.4)
            pygame.draw.arc(surf, (240, 200, 190),
                            pygame.Rect(p[0] - 18, p[1] - 18, 36, 36),
                            -math.pi / 2, -math.pi / 2 + t * math.tau, 3)
        # Waste heat. When you are running hot you are a lamp, and you
        # should be able to see that on your own body before something else
        # sees it from across the room.
        heat = min(1.0, b.total_heat / (C.ORGAN_SEIZE_AT * 2.6))
        if heat > 0.12:
            pygame.draw.circle(surf, (int(210 * heat), int(90 * heat),
                                      int(40 * heat)), p, 15, 2)


def _region_tint(world):
    from ..world.atlas import REGIONS
    reg = world.atlas.rooms[world.room_key]["region"]
    return REGIONS[reg]["tint"]
