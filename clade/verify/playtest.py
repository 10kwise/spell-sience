"""Headless bots, playing the actual game.

Four bots, each knowing exactly one more thing about the systems than the
one before it. They share navigation, aim and reflexes — the only variable
is *understanding*. If a game claims to reward curiosity, then knowing more
must produce better outcomes with no change in reaction time, and that is a
falsifiable statement about a build rather than an opinion about a design.

    flail    fires chain 1 at whatever is nearest. never feeds, never
             re-plumbs, never shuts up. this is a player in their first
             ten minutes.
    feeder   also eats the dead. knows that the reserve is ammunition.
    quiet    also watches the room's attention and stops making noise when
             something is listening. knows that loudness is a resource
             being spent.
    plumber  also picks things up and rebuilds its own body around what it
             finds, ordering amplifiers before converters. knows what the
             game is actually about.

    python -m clade.verify.playtest
    python -m clade.verify.playtest --seeds 5 --minutes 4
"""

import argparse
import collections
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

from .. import config as C
from ..body import Chain, GRID_H, GRID_W
from ..organs import BY_KEY, INTAKE, TRANSFORM, VENT, make
from ..world.room import ROCK, TISSUE

# Amplifiers before the converters that spend what they amplified; quieting
# and evening organs last. This ordering *is* the plumber's knowledge, and
# it is the same conclusion the Assay hands a player in about four shots.
_PREFERENCE = {
    "salt_node": 0, "ember_gland": 0, "spine": 0, "bloom": 0, "swell": 1,
    "kiln": 2, "condenser": 2, "ganglion": 2, "brackish": 2,
    "settling_sac": 3, "fork": 4, "knot": 4, "muffle": 5, "sieve": 6,
    "harmonic": 7,
}


class Bot:
    name = "bot"
    feeds = False
    minds_noise = False
    rebuilds = False

    def __init__(self, game, rng):
        self.game = game
        self.rng = rng
        self.path = []
        self.repath = 0.0
        self.goal = None
        self.fire_timer = 0.0
        self.bite_timer = 0.0
        self.stuck = 0.0
        self.last_pos = (0.0, 0.0)

    # -------------------------------------------------------- navigation

    def _walkable(self, room, t):
        x, y = t
        if not room.in_bounds(x, y):
            return False
        return room.tiles[y][x] not in (ROCK, TISSUE)

    def _bfs(self, room, start, goals):
        if not goals:
            return []
        goalset = set(goals)
        seen = {start: None}
        q = collections.deque([start])
        found = None
        while q:
            cur = q.popleft()
            if cur in goalset:
                found = cur
                break
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cur[0] + d[0], cur[1] + d[1])
                if n in seen or not self._walkable(room, n):
                    continue
                seen[n] = cur
                q.append(n)
        if found is None:
            return []
        path = []
        while found is not None:
            path.append(found)
            found = seen[found]
        path.reverse()
        return path[1:]

    def _pick_goal(self, world, player):
        room = world.room
        tiles = []
        # A corpse is a clock — the Carrion Drift is on its way and the
        # thing rots on its own. A bot that feeds has to actually go to the
        # body, which is the exposed, stationary, frightening part of the
        # loop and the part worth measuring.
        if self.feeds:
            for cp in world.corpses:
                if not cp.spent:
                    tiles.append((int(cp.pos[0] / C.TILE),
                                  int(cp.pos[1] / C.TILE)))
            if tiles:
                return tiles
        # Anything worth having, next.
        for (kind, x, y, data) in room.props:
            if kind in ("fragment", "organ", "nerve") \
                    and data.get("id") not in world.picked_up:
                tiles.append((int(x / C.TILE), int(y / C.TILE)))
        if tiles:
            return tiles
        # Then the door that leads toward the nearest room still worth
        # visiting — computed over the whole atlas, not just this room.
        #
        # The local version ("any door to somewhere undiscovered, else any
        # door at all") deadlocks the moment a room's neighbours are all
        # explored: the bot picks an arbitrary exit, arrives, picks an
        # arbitrary exit back, and shuttles between two rooms until the run
        # ends. A player has a map. So does this.
        want = self._route(world)
        doors = []
        for d in room.doors:
            if not d.open:
                continue
            if want is not None and d.target != want:
                continue
            cx, cy = d.center_px(room.w, room.h)
            doors.append((int(cx / C.TILE), int(cy / C.TILE)))
        if doors:
            return doors
        return [(int(d.center_px(room.w, room.h)[0] / C.TILE),
                 int(d.center_px(room.w, room.h)[1] / C.TILE))
                for d in room.doors if d.open]

    @staticmethod
    def _interesting(world, key):
        if key not in world.discovered:
            return True
        for p in world.atlas.rooms[key]["props"]:
            if p["kind"] in ("fragment", "organ", "nerve") \
                    and p["id"] not in world.picked_up:
                return True
        return False

    def _route(self, world):
        """First hop toward the nearest room that still has something in
        it. Returns None when the reachable world is exhausted."""
        start = world.room_key
        atlas = world.atlas
        seen = {start: None}
        q = collections.deque([start])
        goal = None
        while q:
            cur = q.popleft()
            if cur != start and self._interesting(world, cur):
                goal = cur
                break
            for d in atlas.rooms[cur]["doors"]:
                t = d["target"]
                if t in seen or t not in atlas.rooms:
                    continue
                if not world.passable(cur, d):
                    continue
                seen[t] = cur
                q.append(t)
        if goal is None:
            return None
        cur = goal
        while seen[cur] != start:
            cur = seen[cur]
        return cur

    def move(self, dt, world, player):
        room = world.room
        here = (int(player.pos[0] / C.TILE), int(player.pos[1] / C.TILE))
        self.repath -= dt
        if not self.path or self.repath <= 0.0:
            self.repath = 1.4
            self.path = self._bfs(room, here, self._pick_goal(world, player))
        if not self.path:
            a = self.rng.uniform(0, math.tau)
            return (math.cos(a), math.sin(a))
        tx, ty = self.path[0]
        target = room.px_of(tx, ty)
        dx = target[0] - player.pos[0]
        dy = target[1] - player.pos[1]
        if dx * dx + dy * dy < (C.TILE * 0.75) ** 2:
            self.path.pop(0)
        d = math.hypot(dx, dy) + 1e-6
        return (dx / d, dy / d)

    # ------------------------------------------------------------ acting

    def act(self, dt, game):
        world, player = game.world, game.player
        move = self.move(dt, world, player)

        # Unstick: a bot wedged in geometry produces a run that measures
        # the pathfinder rather than the game.
        p = (round(player.pos[0]), round(player.pos[1]))
        if p == self.last_pos:
            self.stuck += dt
        else:
            self.stuck = 0.0
        self.last_pos = p
        if self.stuck > 1.5:
            a = self.rng.uniform(0, math.tau)
            move = (math.cos(a), math.sin(a))
            player.surge(world)
            self.stuck = 0.0
            self.path = []

        target = self._nearest_threat(world, player)

        # Keeping away from things is most of being quiet.
        if self.minds_noise and target is not None \
                and not target.sp.peaceful:
            dx = player.pos[0] - target.pos[0]
            dy = player.pos[1] - target.pos[1]
            d = math.hypot(dx, dy) + 1e-6
            if d < 190.0:
                push = (190.0 - d) / 190.0
                move = (move[0] + dx / d * push * 1.6,
                        move[1] + dy / d * push * 1.6)
                n = math.hypot(*move) + 1e-6
                move = (move[0] / n, move[1] / n)

        if target is not None:
            dx = target.pos[0] - player.pos[0]
            dy = target.pos[1] - player.pos[1]
            d = math.hypot(dx, dy) + 1e-6
            player.aim = [dx / d, dy / d]
        else:
            player.aim = [move[0], move[1]] if any(move) else [1.0, 0.0]

        player.update(dt, world, move)
        world.update(dt, player)

        self.fire_timer -= dt
        if target is not None and self.fire_timer <= 0.0 \
                and self._may_fire(world, target, player):
            self.fire_timer = 0.18
            game._fire(0)

        if self.feeds:
            got = player.bite(world, dt)
            if got is not None:
                game._on_harvest(got)
        game._pickups()
        game._quiet_pockets(dt)
        moved = world.try_transition()
        if moved:
            self.path = []
        if self.rebuilds:
            self.replumb(game)
        else:
            self.repair(game)

    def repair(self, game):
        """Re-route chain 1 if it has stopped being a chain.

        Every bot does this, including the stupidest one, because the body
        screen paints a dead slot in red and reconnecting two things is not
        an insight. Only the *ordering* is knowledge, and that is the
        plumber's job alone."""
        body = game.body
        ok, _ = body.validate(body.chains[0])
        if ok:
            return
        installed = [(c, o) for c, o in body.cells.items() if o is not None]
        intakes = [c for c, o in installed if o.role == INTAKE]
        vents = [c for c, o in installed if o.role == VENT]
        for start in intakes:
            for end in vents:
                path = self._grid_path(body, start, end)
                if path is None:
                    continue
                ch = Chain(path)
                good, _ = body.validate(ch)
                if good:
                    body.chains[0] = ch
                    return

    def _may_fire(self, world, target, player):
        """A bot that understands noise does not merely shoot less — it
        stops picking fights.

        Holding fire while standing in the same room is *worse* than
        shooting: the creature lives, keeps attacking, and its attacks are
        loud too. Measured, the first version of this bot ended up noisier
        than the one that shot everything. Understanding noise means
        engaging only what is already on top of you and leaving the rest
        behind, which is a movement decision and not a trigger decision."""
        if not self.minds_noise:
            return True
        if world.disturbance > C.DISTURB_APEX_WAKE * 0.8:
            return False
        if target is None:
            return False
        d = math.hypot(target.pos[0] - player.pos[0],
                       target.pos[1] - player.pos[1])
        return d < 210.0

    def _nearest_threat(self, world, player):
        """Hostiles at range; failing that, anything alive and close.

        The second clause matters more than it looks. The Nursery's early
        rooms are full of Coelenters, which are peaceful — a bot that only
        shoots things that shoot back never kills anything there, never
        makes a corpse, and so never exercises the harvest loop that the
        whole game is built on. Which is also, uncomfortably, an accurate
        model of what a real player does: they shoot the harmless drifting
        thing because it is made of parts."""
        best, bd = None, 460.0 ** 2
        for c in world.creatures:
            if c.dead or c.sp.peaceful:
                continue
            d = ((c.pos[0] - player.pos[0]) ** 2
                 + (c.pos[1] - player.pos[1]) ** 2)
            if d < bd:
                best, bd = c, d
        if best is not None:
            return best
        bd = 300.0 ** 2
        for c in world.creatures:
            if c.dead or c.sp.key == "conspecific":
                continue
            d = ((c.pos[0] - player.pos[0]) ** 2
                 + (c.pos[1] - player.pos[1]) ** 2)
            if d < bd:
                best, bd = c, d
        return best

    # ---------------------------------------------------------- surgery

    def replumb(self, game):
        """Install anything carried into any free socket, then rebuild
        chain 1 as intake -> amplifiers -> converters -> vent along a real
        path through the grid. Deliberately not clever: it is the plan a
        player arrives at in their second hour, not an optimiser."""
        body = game.body
        if not body.pack:
            ok, _ = body.validate(body.chains[0])
            if ok:
                return
        free = [c for c in sorted(body.cells) if body.organ_at(c) is None]
        while body.pack and free:
            body.install(free.pop(0), body.pack[0])

        installed = [(c, o) for c, o in body.cells.items() if o is not None]
        intakes = [c for c, o in installed if o.role == INTAKE]
        vents = [c for c, o in installed if o.role == VENT]
        if not intakes or not vents:
            return

        best = None
        for start in intakes:
            for end in vents:
                path = self._grid_path(body, start, end)
                if path is None:
                    continue
                mids = path[1:-1]
                if any(body.organ_at(c).role != TRANSFORM for c in mids):
                    continue
                score = len(mids) - 0.35 * sum(
                    _PREFERENCE.get(body.organ_at(c).key, 3) for c in mids)
                if best is None or score > best[0]:
                    best = (score, path)
        if best is not None:
            ch = Chain(best[1])
            ok, _ = body.validate(ch)
            if ok:
                body.chains[0] = ch

    @staticmethod
    def _grid_path(body, start, end):
        """Any occupied-cell path from an intake to a vent, preferring the
        organs the bot rates highest and putting them in preference order
        along the way."""
        seen = {start: None}
        q = collections.deque([start])
        while q:
            cur = q.popleft()
            if cur == end:
                break
            nbrs = [(cur[0] + 1, cur[1]), (cur[0] - 1, cur[1]),
                    (cur[0], cur[1] + 1), (cur[0], cur[1] - 1)]
            nbrs.sort(key=lambda n: _PREFERENCE.get(
                body.organ_at(n).key if body.organ_at(n) else "", 9))
            for n in nbrs:
                if n in seen or body.organ_at(n) is None:
                    continue
                if n != end and body.organ_at(n).role != TRANSFORM:
                    continue
                seen[n] = cur
                q.append(n)
        if end not in seen:
            return None
        path, cur = [], end
        while cur is not None:
            path.append(cur)
            cur = seen[cur]
        path.reverse()
        return path if len(path) >= 2 else None


class Flail(Bot):
    name = "flail"


class Feeder(Bot):
    name = "feeder"
    feeds = True


class Quiet(Bot):
    name = "quiet"
    feeds = True
    minds_noise = True


class Plumber(Bot):
    name = "plumber"
    feeds = True
    minds_noise = True
    rebuilds = True


BOTS = [Flail, Feeder, Quiet, Plumber]


def run_one(bot_cls, seed, seconds, verbose=False):
    from ..app import Game, PLAY
    screen = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    game = Game(screen, seed=seed, headless=True)
    game.state = PLAY
    rng = random.Random(seed * 977 + 13)
    bot = bot_cls(game, rng)

    dt = 1.0 / 30.0
    steps = int(seconds / dt)
    deaths = 0
    peak_disturb = 0.0
    for i in range(steps):
        if game.state == PLAY:
            bot.act(dt, game)
            game.playtime += dt
            peak_disturb = max(peak_disturb, game.world.disturbance)
            if game.player.dead:
                deaths += 1
                game.player.dead = False
                game.player.deaths += 1
                game._regress()
                bot.path = []
        elif game.state in (3, 4):        # ending states
            break
        else:
            game.state = PLAY

    w = game.world
    return {
        "rooms": len(w.discovered),
        "deaths": deaths,
        "organs": len(game.body.installed()) + len(game.body.pack),
        "fragments": len(game.codex.fragments),
        "kills": sum(w.kill_counts.values()),
        "harvests": game.player.harvests,
        "peak_noise": peak_disturb,
        "viability": max(0.0, game.body.viability),
        "region": w.atlas.rooms[w.room_key]["region"],
        "deepest": max(w.atlas.rooms[k]["map"][1] for k in w.discovered),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--minutes", type=float, default=3.0)
    args = ap.parse_args(argv)
    seconds = args.minutes * 60.0

    print("CLADE — headless playtest")
    print("%d seeds x %.0f simulated minutes per bot\n" % (args.seeds, args.minutes))
    header = ("bot", "rooms", "deep", "deaths", "organs", "frags", "kills",
              "harv", "noise")
    print("%-9s %6s %5s %7s %7s %6s %6s %5s %7s" % header)

    table = {}
    for cls in BOTS:
        runs = [run_one(cls, s, seconds) for s in range(args.seeds)]
        avg = {k: sum(r[k] for r in runs) / len(runs)
               for k in runs[0] if isinstance(runs[0][k], (int, float))}
        table[cls.name] = avg
        print("%-9s %6.1f %5.1f %7.1f %7.1f %6.1f %6.1f %5.1f %7.1f" % (
            cls.name, avg["rooms"], avg["deepest"], avg["deaths"],
            avg["organs"], avg["fragments"], avg["kills"], avg["harvests"],
            avg["peak_noise"]))

    print()
    problems = []
    if table["feeder"]["organs"] <= table["flail"]["organs"]:
        problems.append("feeding does not get you more parts")
    if table["quiet"]["peak_noise"] >= table["flail"]["peak_noise"]:
        problems.append("minding the noise does not make you quieter")
    if table["plumber"]["deepest"] < table["flail"]["deepest"]:
        problems.append("understanding the body does not get you deeper")
    if table["plumber"]["rooms"] < table["flail"]["rooms"]:
        problems.append("understanding does not open more of the map")

    ladder = [table[c.name]["rooms"] for c in BOTS]
    print("map opened, by how much the bot understands: %s"
          % " -> ".join("%.1f" % v for v in ladder))
    if problems:
        for p in problems:
            print("  REGRESSION: %s" % p)
        return 1
    print("knowing more is worth more. no regressions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
