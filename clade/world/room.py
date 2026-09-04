"""A room: solid geometry, doors, and the water inside it.

Rooms are tile grids because tile grids are honest about collision and
because the thing the player most needs from a pitch-dark game is
*confidence about where the walls are*. A curve you cannot see is
frightening in the wrong way; a wall you bumped once and remember is
frightening in the right way.

Three tile kinds carry the whole level vocabulary:

    ROCK      the world. permanent, uncaring, and the only reliable thing
              down here.
    TISSUE    grown. it is alive, it is a door, and it will not open to
              force. gentleness or rot, nothing else. this single tile is
              the game's entire progression gate, and it works because the
              hard thing about a balanced charge is not finding a key, it
              is *building a body that can be gentle*, which is the exact
              opposite of what combat teaches.
    VENT      a hole in the floor or wall that the room's water comes out
              of. it is why one corner of a room is worth swimming to.

Ice is not a tile. Ice is the heat field being sufficiently negative, which
means the player makes and unmakes walls as a consequence of a chain they
built for another reason, and nobody had to design a wall-making spell.
"""

import math
import random

from .. import config as C
from ..humours import Charge
from .fields import Fields

WATER, ROCK, TISSUE, VENT = 0, 1, 2, 3

NORTH, SOUTH, EAST, WEST = "n", "s", "e", "w"
OPPOSITE = {NORTH: SOUTH, SOUTH: NORTH, EAST: WEST, WEST: EAST}

# Door locks. Each is a *statement about your body*, never an item.
LOCK_NONE = None
LOCK_GENTLE = "gentle"      # only a balanced charge persuades it
LOCK_CAUSTIC = "caustic"    # or rot it, if you are in a hurry and ugly
LOCK_RISE = "rise"          # a sheer shaft: you must be able to make lift
LOCK_COLD = "cold"          # a scald vent: you must be able to chill it
LOCK_FORCE = "force"        # rubble. brute strength, the one honest lock.

LOCK_TEXT = {
    LOCK_GENTLE: "grown shut. it flinches from anything sharp.",
    LOCK_CAUSTIC: "grown shut, and scarred. something ate through here once.",
    LOCK_RISE: "straight up. nothing heavy is getting out this way.",
    LOCK_COLD: "the water here is boiling. it would cook you.",
    LOCK_FORCE: "fallen in. it would take a shove.",
}


class Door:
    __slots__ = ("side", "at", "target", "lock", "open", "seen", "span")

    def __init__(self, side, at, target, lock=LOCK_NONE, span=3):
        self.side = side
        self.at = at            # tile index along the wall
        self.target = target    # room key
        self.lock = lock
        self.span = span
        # A "rise" lock is not a locked door — it is an open door somewhere
        # you cannot reach yet. The gate is your own buoyancy, which means
        # it opens the moment you understand weight rather than the moment
        # you find a key.
        self.open = lock is LOCK_NONE or lock == LOCK_RISE
        self.seen = False

    def tiles(self, w, h):
        out = []
        half = self.span // 2
        for k in range(-half, half + 1):
            if self.side == NORTH:
                out.append((self.at + k, 0))
            elif self.side == SOUTH:
                out.append((self.at + k, h - 1))
            elif self.side == WEST:
                out.append((0, self.at + k))
            else:
                out.append((w - 1, self.at + k))
        return [(x, y) for x, y in out if 0 <= x < w and 0 <= y < h]

    def center_px(self, w, h):
        xs = [t[0] for t in self.tiles(w, h)]
        ys = [t[1] for t in self.tiles(w, h)]
        return ((sum(xs) / len(xs) + 0.5) * C.TILE,
                (sum(ys) / len(ys) + 0.5) * C.TILE)


class Room:
    def __init__(self, key, spec, rng=None):
        self.key = key
        self.spec = spec
        self.w = spec.get("w", C.ROOM_W)
        self.h = spec.get("h", C.ROOM_H)
        self.rng = rng or random.Random(hash(key) & 0xFFFFFFFF)
        self.tiles = [[ROCK] * self.w for _ in range(self.h)]
        self.doors = [Door(**d) for d in spec.get("doors", [])]
        self.region = spec.get("region", "nursery")
        self.name = spec.get("name", key)

        base = Charge.of(spec.get("water", [5, 5, 5, 5]))
        self.fields = Fields(self.w * C.TILE, self.h * C.TILE, base)

        self.props = []          # (kind, x, y, data)
        self.spawns = []         # (creature_key, x, y)
        self.visited = False
        self.cleared = False

        _carve(self)
        _place_features(self)

    # ------------------------------------------------------------ queries

    def in_bounds(self, tx, ty):
        return 0 <= tx < self.w and 0 <= ty < self.h

    def tile_at_px(self, x, y):
        tx, ty = int(x / C.TILE), int(y / C.TILE)
        if not self.in_bounds(tx, ty):
            return ROCK
        return self.tiles[ty][tx]

    def solid_at(self, x, y):
        """Rock and tissue stop you. So does frozen water, which is why a
        chill build is a movement tool as much as a weapon."""
        t = self.tile_at_px(x, y)
        if t in (ROCK, TISSUE):
            return True
        return self.fields.frozen_at((x, y))

    def blocks_sight(self, x, y):
        return self.tile_at_px(x, y) in (ROCK, TISSUE)

    def free_cells(self):
        return [(x, y) for y in range(self.h) for x in range(self.w)
                if self.tiles[y][x] == WATER]

    def px_of(self, tx, ty):
        return ((tx + 0.5) * C.TILE, (ty + 0.5) * C.TILE)

    @property
    def pixel_w(self):
        return self.w * C.TILE

    @property
    def pixel_h(self):
        return self.h * C.TILE

    # ----------------------------------------------------------- mutation

    def dissolve(self, x, y, radius):
        """Rot eats tissue and nothing else. Rock is rock."""
        opened = 0
        r = int(radius / C.TILE) + 1
        tx, ty = int(x / C.TILE), int(y / C.TILE)
        for yy in range(ty - r, ty + r + 1):
            for xx in range(tx - r, tx + r + 1):
                if not self.in_bounds(xx, yy):
                    continue
                if self.tiles[yy][xx] != TISSUE:
                    continue
                dx = (xx + 0.5) * C.TILE - x
                dy = (yy + 0.5) * C.TILE - y
                if dx * dx + dy * dy <= radius * radius:
                    self.tiles[yy][xx] = WATER
                    opened += 1
        return opened

    def door_near(self, x, y, radius=52.0):
        for d in self.doors:
            cx, cy = d.center_px(self.w, self.h)
            if (cx - x) ** 2 + (cy - y) ** 2 <= radius * radius:
                return d
        return None

    def update(self, dt):
        self.fields.update(dt)


# ===========================================================================
# Carving
#
# Every room is generated, but nothing is generated *freely*: the spec picks
# a shape grammar and the generator is then obliged to connect every door to
# every other door. A beautiful cave with an unreachable exit is worse than
# a boring corridor, and in a game this dark the player cannot tell the
# difference between "no path" and "I have not found it", which turns a
# generation bug into an hour of wasted fear.
# ===========================================================================

def _carve(room):
    kind = room.spec.get("kind", "cavern")
    rng = room.rng
    w, h = room.w, room.h

    if kind == "cavern":
        _carve_cavern(room, rng, fill=0.50, steps=5)
    elif kind == "hall":
        _carve_cavern(room, rng, fill=0.43, steps=4)
    elif kind == "warren":
        _carve_cavern(room, rng, fill=0.56, steps=6)
    elif kind == "shaft":
        _carve_shaft(room, rng)
    elif kind == "corridor":
        _carve_corridor(room, rng)
    elif kind == "chamber":
        _carve_chamber(room, rng)
    else:
        _carve_cavern(room, rng)

    _connect_doors(room)
    _seal_border(room)
    _open_doors(room)


def _carve_cavern(room, rng, fill=0.50, steps=5):
    """Cellular-automaton caves, with two corrections that are the whole
    difference between "cave" and "empty box".

    Out-of-bounds counts as rock. Without that, the border cells see only
    five neighbours instead of eight, never reach the rock threshold, and
    the automaton eats the room inward from every edge until nothing is
    left — which is exactly the failure that made a 44%-fill cavern come
    out 88% open.

    And the rule has a dead band: >=5 becomes rock, <=3 becomes water, and
    4 is left alone. The strict two-way form flips every marginal cell
    every step and the grid oscillates instead of settling, so structures
    never consolidate into anything worth swimming around."""
    w, h = room.w, room.h
    grid = [[ROCK if rng.random() < fill else WATER for _ in range(w)]
            for _ in range(h)]
    for _ in range(steps):
        nxt = [row[:] for row in grid]
        for y in range(h):
            for x in range(w):
                n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w:
                            if grid[yy][xx] == ROCK:
                                n += 1
                        else:
                            n += 1
                if n >= 5:
                    nxt[y][x] = ROCK
                elif n <= 3:
                    nxt[y][x] = WATER
        grid = nxt
    room.tiles = grid


def _carve_shaft(room, rng):
    """A vertical throat. Wide enough to swim, narrow enough that falling
    is a real outcome and rising is a real capability."""
    w, h = room.w, room.h
    room.tiles = [[ROCK] * w for _ in range(h)]
    cx = w // 2
    for y in range(h):
        t = y / max(1, h - 1)
        width = 5 + int(4 * math.sin(t * math.pi * 1.6) ** 2) + rng.randint(0, 2)
        drift = int(3 * math.sin(t * math.pi * 2.1))
        for x in range(cx + drift - width, cx + drift + width + 1):
            if 0 <= x < w:
                room.tiles[y][x] = WATER
    # Ledges, so a shaft is a climb and not a tube.
    for _ in range(rng.randint(3, 6)):
        y = rng.randint(3, h - 4)
        x0 = rng.randint(2, w - 8)
        for x in range(x0, min(w - 1, x0 + rng.randint(3, 6))):
            room.tiles[y][x] = ROCK


def _carve_corridor(room, rng):
    w, h = room.w, room.h
    room.tiles = [[ROCK] * w for _ in range(h)]
    cy = h // 2
    y = cy
    for x in range(w):
        if rng.random() < 0.20:
            y += rng.choice((-1, 1))
            y = max(3, min(h - 4, y))
        thick = rng.randint(3, 5)
        for k in range(-thick, thick + 1):
            if 0 <= y + k < h:
                room.tiles[y + k][x] = WATER


def _carve_chamber(room, rng):
    """A deliberate room: a big open middle with structure in it. Used for
    anything the level wants the player to *look at* rather than pass
    through."""
    w, h = room.w, room.h
    room.tiles = [[ROCK] * w for _ in range(h)]
    m = 4
    for y in range(m, h - m):
        for x in range(m, w - m):
            room.tiles[y][x] = WATER
    for _ in range(rng.randint(3, 7)):
        px = rng.randint(m + 2, w - m - 4)
        py = rng.randint(m + 2, h - m - 4)
        pw = rng.randint(2, 5)
        ph = rng.randint(2, 5)
        for y in range(py, min(h - m, py + ph)):
            for x in range(px, min(w - m, px + pw)):
                room.tiles[y][x] = ROCK


def _connect_doors(room):
    """Guarantee every door reaches the room's centre of mass. Dumb, direct
    L-shaped tunnels — the cavern noise around them makes them read as
    natural, and correctness beats elegance for something this load-bearing."""
    w, h = room.w, room.h
    free = room.free_cells()
    if free:
        cx = sum(c[0] for c in free) // len(free)
        cy = sum(c[1] for c in free) // len(free)
    else:
        cx, cy = w // 2, h // 2
    _bore(room, cx, cy, 3)


    for d in room.doors:
        for (tx, ty) in d.tiles(w, h):
            x, y = tx, ty
            # L-shaped bore, alternating which leg goes first per door so
            # the room does not end up with a visible plus-sign of tunnels
            # radiating from its centre.
            if (d.side in (NORTH, SOUTH)):
                while y != cy:
                    _bore(room, x, y, 2)
                    y += 1 if cy > y else -1
                while x != cx:
                    _bore(room, x, y, 2)
                    x += 1 if cx > x else -1
            else:
                while x != cx:
                    _bore(room, x, y, 2)
                    x += 1 if cx > x else -1
                while y != cy:
                    _bore(room, x, y, 2)
                    y += 1 if cy > y else -1
            break


def _bore(room, x, y, r):
    for yy in range(y - r, y + r + 1):
        for xx in range(x - r, x + r + 1):
            if room.in_bounds(xx, yy):
                if (xx - x) ** 2 + (yy - y) ** 2 <= r * r + 1:
                    room.tiles[yy][xx] = WATER


def _seal_border(room):
    w, h = room.w, room.h
    for x in range(w):
        room.tiles[0][x] = ROCK
        room.tiles[h - 1][x] = ROCK
    for y in range(h):
        room.tiles[y][0] = ROCK
        room.tiles[y][w - 1] = ROCK


def _open_doors(room):
    """Doors are carved last so nothing can wall them back up. A locked door
    is TISSUE (grown shut) or ROCK (fallen in) depending on its lock, which
    means the lock is *visible from across the room* — you can see that the
    way on is alive before you can see anything else about it."""
    w, h = room.w, room.h
    for d in room.doors:
        for (tx, ty) in d.tiles(w, h):
            if d.open:
                room.tiles[ty][tx] = WATER
            elif d.lock in (LOCK_GENTLE, LOCK_CAUSTIC):
                room.tiles[ty][tx] = TISSUE
            else:
                room.tiles[ty][tx] = ROCK
            # A pocket inside the door so it is enterable once opened.
            ix = tx + (1 if tx == 0 else (-1 if tx == w - 1 else 0))
            iy = ty + (1 if ty == 0 else (-1 if ty == h - 1 else 0))
            if room.in_bounds(ix, iy) and room.tiles[iy][ix] == ROCK:
                room.tiles[iy][ix] = WATER


def _place_features(room):
    """Seeps, vents and spawn points. Seeps are placed *away from doors*, so
    the good water is never on the route you were taking anyway — you go and
    get it or you do without."""
    rng = room.rng
    free = room.free_cells()
    if not free:
        return
    door_px = [d.center_px(room.w, room.h) for d in room.doors]

    def far_from_doors(cell, min_d=260.0):
        px = room.px_of(*cell)
        return all((px[0] - dx) ** 2 + (px[1] - dy) ** 2 > min_d * min_d
                   for dx, dy in door_px)

    candidates = [c for c in free if far_from_doors(c)] or free

    for seep in room.spec.get("seeps", []):
        cell = rng.choice(candidates)
        px = room.px_of(*cell)
        room.fields.seeps.append(
            (px[0], px[1], seep.get("radius", 170.0), Charge.of(seep["water"]))
        )
        room.props.append(("vent", px[0], px[1], seep))

    for entry in room.spec.get("spawns", []):
        n = entry.get("n", 1)
        for _ in range(n):
            cell = rng.choice(free)
            px = room.px_of(*cell)
            room.spawns.append((entry["kind"], px[0], px[1]))

    for entry in room.spec.get("props", []):
        cell = rng.choice(candidates if entry.get("hidden") else free)
        px = room.px_of(*cell)
        room.props.append((entry["kind"], px[0], px[1], entry))
