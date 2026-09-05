"""The game.

State machine, input, and the handful of rules that are about the *run*
rather than about any one system: picking things up, dying, resting, and
the ending.

Death is worth reading. You do not reload and you do not lose the run — you
**regress**. Two installed organs come out of you and stay where you fell,
your reserve empties, and you wake at the last quiet pocket. The organs are
recoverable if you go back for them, and something may have eaten them by
the time you do. The punishment for dying is therefore not lost time, it is
*being less of yourself*, which is the only punishment this game's fiction
can honestly impose.

The ending is eleven lines at the bottom of this file and it does not
announce itself. You will know it when it is in front of you, and what you
do about it is not something the game will offer you a menu for.
"""

import math
import os
import sys

import pygame

from . import bestiary, config as C, save
from .body import Body, starting_body
from .creatures import Creature
from .effects import resolve
from .humours import Charge
from .lore import Codex, FRAGMENTS
from .organs import BY_KEY, make
from .player import Player
from .render.dark import DarkRenderer
from .render.hud import draw_hud, font, text
from .screens.bench import BenchScreen, _wrapped
from .world.atlas import ATLAS, REGIONS
from .world.live import World

TITLE, PLAY, BENCH, CODEX, MAPS, DEAD, ENDING = range(7)

FIRE_KEYS = {pygame.K_q: 2, pygame.K_e: 3}


class Game:
    def __init__(self, screen, seed=0, headless=False):
        self.screen = screen
        self.headless = headless
        self.state = TITLE
        self.seed = seed
        self.renderer = DarkRenderer(screen.get_size())
        self.bench = BenchScreen(self)
        self.notices = []
        self.playtime = 0.0
        self.ending = None
        self.ending_time = 0.0
        self.conspecific_hold = 0.0
        self.codex_page = 0
        self.title_index = 0
        self.running = True
        self.new_run()

    # ------------------------------------------------------------ lifecycle

    def new_run(self, data=None):
        self.body = starting_body()
        self.codex = Codex()
        self.checkpoint = ATLAS.start
        self.playtime = 0.0
        self.ending = None
        self.conspecific_hold = 0.0

        if data:
            self.body = Body.from_dict(data["body"])
            self.codex = Codex.from_dict(data["codex"])
            self.checkpoint = data.get("checkpoint", ATLAS.start)
            self.playtime = data.get("stats", {}).get("time", 0.0)

        start = (data or {}).get("room", ATLAS.start)
        self.world = World(ATLAS, self.body, start, seed=self.seed)
        spawn = self._spawn_point()
        self.player = Player(self.body, spawn)
        self.world.player = self.player

        if data:
            self.world.discovered = set(data.get("discovered", [start]))
            self.world.picked_up = set(data.get("picked_up", []))
            self.world.opened = {tuple(o) for o in data.get("opened", [])}
            self.world.flags = set(data.get("flags", []))
            st = data.get("stats", {})
            self.player.deaths = st.get("deaths", 0)
            self.player.harvests = st.get("harvests", 0)
            self.player.peaceful_harvests = st.get("peaceful_harvests", 0)
            self.player.spared = st.get("spared", 0)
            # Re-enter so doors already forced open stay open.
            self.world.enter_room(start, first=True)
            self.player.pos = list(self._spawn_point())

    def _spawn_point(self):
        room = self.world.room
        free = room.free_cells()
        if not free:
            return (room.pixel_w * 0.5, room.pixel_h * 0.5)
        cx, cy = room.w // 2, room.h // 2
        free.sort(key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        return room.px_of(*free[0])

    def enter_bench(self):
        self.state = BENCH
        self.bench._run_assay()

    def leave_bench(self):
        """Back to the water. Chains that stopped being chains during
        surgery are left broken on purpose — the slot shows red and fixing
        it is the player's problem, not a silent auto-repair."""
        self.state = PLAY

    def notice(self, msg):
        self.notices.append([msg, 0.0])
        if len(self.notices) > 5:
            self.notices.pop(0)

    # --------------------------------------------------------------- input

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.running = False
            return
        if self.state == TITLE:
            self._title_key(e)
        elif self.state == PLAY:
            self._play_key(e)
        elif self.state == BENCH:
            self.bench.handle(e)
        elif self.state in (CODEX, MAPS):
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_c, pygame.K_m,
                             pygame.K_TAB):
                    self.state = PLAY
                elif e.key == pygame.K_LEFT:
                    self.codex_page = max(0, self.codex_page - 1)
                elif e.key == pygame.K_RIGHT:
                    self.codex_page += 1
        elif self.state == DEAD:
            if e.type == pygame.KEYDOWN and self.ending_time > 1.2:
                self._regress()
        elif self.state == ENDING:
            if e.type == pygame.KEYDOWN and self.ending_time > 3.0:
                self.running = False

    def _title_key(self, e):
        if e.type != pygame.KEYDOWN:
            return
        opts = self._title_options()
        if e.key in (pygame.K_UP, pygame.K_w):
            self.title_index = (self.title_index - 1) % len(opts)
        elif e.key in (pygame.K_DOWN, pygame.K_s):
            self.title_index = (self.title_index + 1) % len(opts)
        elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
            choice = opts[self.title_index]
            if choice == "continue":
                data = save.read()
                if data:
                    self.new_run(data)
            elif choice == "begin":
                save.clear()
                self.new_run()
            elif choice == "leave":
                self.running = False
                return
            self.state = PLAY
        elif e.key == pygame.K_ESCAPE:
            self.running = False

    def _title_options(self):
        return (["continue", "begin", "leave"] if save.exists()
                else ["begin", "leave"])

    def _play_key(self, e):
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.state = TITLE
                self.title_index = 0
            elif k == pygame.K_TAB:
                self.enter_bench()
            elif k == pygame.K_c:
                self.state = CODEX
                self.codex_page = 0
            elif k == pygame.K_m:
                self.state = MAPS
            elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_SPACE):
                self.player.surge(self.world)
            elif k in FIRE_KEYS:
                self._fire(FIRE_KEYS[k])
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                self._fire(0)
            elif e.button == 3:
                self._fire(1)

    def _fire(self, index):
        p = self.player
        ems = self.body.fire(index, self.world, tuple(p.pos), tuple(p.aim))
        if not ems:
            return
        self.world.emit(ems, hostile=False)
        eff = ems[0].effect
        for o in self.body.chain_organs(self.body.chains[index]) or []:
            self.codex.use_organ(o.key)
        if self.codex.see_blend(eff.blend):
            from .humours import BLEND_NOTES
            self.notice("%s — %s" % (eff.blend, BLEND_NOTES.get(eff.blend, "")))
        # Doors answer to what you point at them.
        self.world.try_open_door(eff, p.pos)
        if eff.recoil > 0.5:
            self.notice("that cost you something")

    # -------------------------------------------------------------- update

    def update(self, dt):
        for n in self.notices:
            n[1] += dt
        self.notices = [n for n in self.notices if n[1] < 5.0]

        if self.state == BENCH:
            self.bench.update(dt)
            self.body.update(dt)
            return
        if self.state in (TITLE, CODEX, MAPS):
            return
        if self.state in (DEAD, ENDING):
            self.ending_time += dt
            return

        self.playtime += dt
        keys = pygame.key.get_pressed()
        move = [0.0, 0.0]
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move[0] -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move[0] += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move[1] -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move[1] += 1

        if not self.headless:
            mx, my = pygame.mouse.get_pos()
            off = self.renderer.camera.offset()
            self.player.aim_at((mx + off[0], my + off[1]))

        self.player.update(dt, self.world, move)
        self.world.update(dt, self.player)

        if keys[pygame.K_f]:
            done = self.player.bite(self.world, dt)
            if done is not None:
                self._on_harvest(done)
        else:
            self.player.biting = None
            self.player.bite_time = 0.0

        self._pickups()
        self._quiet_pockets(dt)
        self._ending_check(dt)

        moved = self.world.try_transition()
        if moved:
            self.notice(self.world.atlas.rooms[moved]["name"])

        for c in self.world.creatures:
            if c.alarm > 0.2 or c.distance_to(self.player.pos) < 400:
                self.codex.see_species(c.sp.key)

        if self.player.dead:
            self.state = DEAD
            self.ending_time = 0.0
            self.player.deaths += 1

    def _pickups(self):
        p = self.player
        room = self.world.room
        for (kind, x, y, data) in room.props:
            pid = data.get("id")
            if kind not in ("fragment", "organ", "nerve"):
                continue
            if pid in self.world.picked_up:
                continue
            if (p.pos[0] - x) ** 2 + (p.pos[1] - y) ** 2 > 34 * 34:
                continue
            self.world.picked_up.add(pid)
            if kind == "fragment":
                fr = self.codex.find_fragment(pid)
                if fr:
                    self.notice("[ %s ]  — press C" % fr.title)
            elif kind == "organ":
                org = make(pid)
                self.body.pack.append(org)
                self.codex.see_organ(pid)
                self.notice("recovered: %s" % org.name)
            elif kind == "nerve":
                cell = self._next_socket()
                if cell:
                    self.body.unlock(cell)
                    self.notice("you have room for one more thing")

    def _next_socket(self):
        from .body import GRID_H, GRID_W
        have = self.body.cells
        best = None
        for cy in range(GRID_H):
            for cx in range(GRID_W):
                if (cx, cy) in have:
                    continue
                adj = sum(1 for n in ((cx+1, cy), (cx-1, cy), (cx, cy+1),
                                      (cx, cy-1)) if n in have)
                if adj == 0:
                    continue
                score = (-adj, abs(cx - 2.5) + abs(cy - 2))
                if best is None or score < best[0]:
                    best = (score, (cx, cy))
        return best[1] if best else None

    def _quiet_pockets(self, dt):
        p = self.player
        for (kind, x, y, data) in self.world.room.props:
            if kind != "quiet":
                continue
            if (p.pos[0] - x) ** 2 + (p.pos[1] - y) ** 2 > 90 * 90:
                continue
            # Rest. It is not free healing — it is slow, and it is the only
            # place the world stops moving, and it saves.
            self.body.viability = min(
                C.VIABILITY_MAX, self.body.viability + 16.0 * dt)
            self.world.disturbance = max(0.0, self.world.disturbance - 22.0 * dt)
            for o in self.body.installed():
                o.heat = max(0.0, o.heat - 40.0 * dt)
            if self.checkpoint != self.world.room_key:
                self.checkpoint = self.world.room_key
                self.notice("you could stop here")
            if not self.headless and int(self.playtime * 2) % 8 == 0:
                save.write(self)

    def _on_harvest(self, corpse):
        self.player.harvests += 1
        sp = bestiary.SPECIES.get(corpse.species)
        for key in corpse.organs:
            if key in BY_KEY and len(self.body.pack) < 24:
                self.body.pack.append(make(key))
                self.codex.see_organ(key)
        self.codex.kill_species(corpse.species)
        if sp is not None:
            if sp.peaceful:
                self.player.peaceful_harvests += 1
            if sp.harvest_note:
                self.notice(sp.harvest_note)
            else:
                self.notice("recovered from %s" % sp.name.lower())

    # ------------------------------------------------------------ regress

    def _regress(self):
        """Not a reload. You come back smaller."""
        lost = []
        cells = [c for c, o in self.body.cells.items() if o is not None]
        # The outermost first: whatever is furthest from the middle of you.
        cells.sort(key=lambda c: -(abs(c[0] - 2.5) + abs(c[1] - 2.0)))

        def _count(role):
            return sum(1 for o in self.body.installed() if o.role == role)

        for cell in cells:
            if len(lost) >= 2:
                break
            org = self.body.organ_at(cell)
            if org is None:
                continue
            # It takes what it can spare. Never the last way in and never
            # the last way out: the starting body's outermost organs are
            # its Siphon and its Spiracle, so the naive version of this
            # rule left a first-time player permanently unable to do
            # anything at all, with no explanation and nothing to go and
            # recover it with.
            from .organs import INTAKE, VENT
            if org.role == INTAKE and _count(INTAKE) <= 1:
                continue
            if org.role == VENT and _count(VENT) <= 1:
                continue
            org = self.body.uninstall(cell)
            if org is not None and org in self.body.pack:
                self.body.pack.remove(org)
                lost.append(org)
        self.body.reserve = Charge(3, 3, 3, 3)
        self.body.viability = C.VIABILITY_MAX * 0.55
        for o in self.body.installed():
            o.heat = 0.0
            o.seized = False
        for ch in self.body.chains:
            ok, _ = self.body.validate(ch)
            if not ok:
                ch.cells = []

        if lost:
            from .world.live import Corpse
            husk = Corpse(self.player.pos, Charge(4, 4, 4, 4),
                          [o.key for o in lost], "husk")
            husk.life = 1e9
            self.world.get_room(self.world.room_key)
            self._husks = getattr(self, "_husks", [])
            self._husks.append((self.world.room_key, husk))

        self.player.dead = False
        self.world.enter_room(self.checkpoint)
        self.player.pos = list(self._spawn_point())
        self.player.vel = [0.0, 0.0]
        if lost:
            self.notice("you left %s behind" %
                        " and ".join(o.name.lower() for o in lost))
        self.state = PLAY

    # ------------------------------------------------------------- ending

    def _ending_check(self, dt):
        if not self.world.atlas.rooms[self.world.room_key].get("ending"):
            self.conspecific_hold = 0.0
            return
        other = next((c for c in self.world.creatures
                      if c.sp.key == "conspecific"), None)
        if other is None:
            # It is gone, and there is exactly one way that happens.
            if "ate_conspecific" in self.world.flags:
                self._finish("harvest")
            return
        if other.dead:
            self.world.flags.add("ate_conspecific")
            return
        d = other.distance_to(self.player.pos)
        if other.viability < other.max_viability - 0.5:
            self.conspecific_hold = 0.0
            return
        if d < 150.0:
            self.conspecific_hold += dt
            if self.conspecific_hold > 6.0:
                self.player.spared += 1
                self._finish("abstain")
        else:
            self.conspecific_hold = max(0.0, self.conspecific_hold - dt * 0.5)

    def _finish(self, which):
        self.ending = which
        self.state = ENDING
        self.ending_time = 0.0
        save.clear()

    # ---------------------------------------------------------------- draw

    def draw(self):
        s = self.screen
        if self.state == TITLE:
            self._draw_title(s)
        elif self.state == BENCH:
            self.bench.draw(s)
        elif self.state == CODEX:
            self._draw_codex(s)
        elif self.state == MAPS:
            self._draw_map(s)
        elif self.state == ENDING:
            self._draw_ending(s)
        else:
            self.renderer.draw(s, self.world, self.player, self._dt)
            draw_hud(s, self.world, self.player, self.notices)
            if self.state == DEAD:
                self._draw_dead(s)

    _dt = 1 / 60.0

    def _draw_title(self, s):
        w, h = s.get_size()
        s.fill((8, 10, 13))
        for i in range(90):
            y = int((i * 137 + self.playtime * 6) % h)
            x = int((i * 311) % w)
            v = 20 + (i % 5) * 8
            s.set_at((x, y), (v, v, v + 4))
        text(s, "CLADE", (w // 2, h // 2 - 130), 96, (206, 214, 222),
             bold=True, center=True)
        text(s, "a clade of one", (w // 2, h // 2 - 66), 26, (110, 122, 132),
             center=True)
        opts = self._title_options()
        for i, o in enumerate(opts):
            col = (215, 225, 235) if i == self.title_index else (100, 110, 120)
            pre = "> " if i == self.title_index else "  "
            text(s, pre + o, (w // 2, h // 2 + 10 + i * 34), 28, col,
                 center=True)
        text(s, "wasd swim · mouse aim · lmb rmb q e · shift surge · "
                "hold f to feed · tab bench · c codex · m map",
             (w // 2, h - 54), 18, (74, 82, 90), center=True)

    def _draw_dead(self, s):
        w, h = s.get_size()
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        a = int(min(215, self.ending_time * 190))
        veil.fill((6, 7, 9, a))
        s.blit(veil, (0, 0))
        if self.ending_time > 0.7:
            text(s, "you come apart", (w // 2, h // 2 - 30), 46,
                 (200, 190, 190), center=True)
            text(s, "not all of you is going to be there when you wake",
                 (w // 2, h // 2 + 22), 22, (130, 130, 135), center=True)
        if self.ending_time > 1.6:
            text(s, "press anything", (w // 2, h // 2 + 76), 20,
                 (90, 94, 100), center=True)

    def _draw_map(self, s):
        """The map, fitted to whatever the atlas actually is.

        Hard-coded cell sizes worked until the world grew past nine rows,
        at which point the bottom region drew straight through the legend
        and off the screen — so the cell size is derived from the atlas
        extents every time. Add a region and the map still fits."""
        w, h = s.get_size()
        s.fill((9, 11, 14))
        text(s, "WHERE YOU HAVE BEEN", (60, 44), 34, (190, 200, 210),
             bold=True)
        text(s, "?  something written    o  tissue    +  room to grow    "
                "~  somewhere to stop", (620, 50), 17, (120, 132, 142))

        rooms = self.world.atlas.rooms
        cols = max(spec["map"][0] for spec in rooms.values()) + 1
        rows = max(spec["map"][1] for spec in rooms.values()) + 1
        left, top = 70, 96
        avail_w, avail_h = 660, h - top - 40
        gap = 7
        cw = int(avail_w / cols) - gap
        ch = int(avail_h / rows) - gap

        for key, spec in rooms.items():
            mx, my = spec["map"]
            r = pygame.Rect(left + mx * (cw + gap), top + my * (ch + gap),
                            cw, ch)
            known = key in self.world.discovered
            if not known:
                pygame.draw.rect(s, (16, 18, 21), r, border_radius=3)
                continue
            tint = REGIONS[spec["region"]]["tint"]
            pygame.draw.rect(s, tuple(min(255, int(v * 1.6)) for v in tint), r,
                             border_radius=3)
            here = key == self.world.room_key
            pygame.draw.rect(s, (235, 242, 250) if here else (66, 76, 86), r,
                             2 if here else 1, border_radius=3)
            text(s, spec["name"], (r.x + 7, r.y + 5), 17,
                 (215, 226, 236) if here else (176, 188, 198))

            marks = []
            for prop in spec["props"]:
                if prop["kind"] in ("fragment", "organ", "nerve") \
                        and prop["id"] not in self.world.picked_up:
                    marks.append({"fragment": "?", "organ": "o",
                                  "nerve": "+"}[prop["kind"]])
                elif prop["kind"] == "quiet":
                    marks.append("~")
                elif prop["kind"] == "ending":
                    marks.append("=")
            if marks:
                text(s, " ".join(sorted(set(marks))),
                     (r.x + 7, r.bottom - 20), 18, (156, 178, 188))

            for d in spec["doors"]:
                if d["target"] not in self.world.discovered:
                    continue
                shut = d["lock"] and not self.world.passable(key, d)
                col = (214, 118, 106) if shut else (96, 116, 128)
                at = {"n": (r.centerx, r.top), "s": (r.centerx, r.bottom),
                      "w": (r.left, r.centery),
                      "e": (r.right, r.centery)}[d["side"]]
                pygame.draw.circle(s, col, at, 4 if shut else 3)

        x = left + cols * (cw + gap) + 40
        y = top + 10
        text(s, "WHERE YOU ARE", (x, y), 24, (170, 182, 192), bold=True)
        y += 36
        for reg, meta in REGIONS.items():
            seen = sum(1 for k, sp in rooms.items()
                       if sp["region"] == reg and k in self.world.discovered)
            total_n = sum(1 for sp in rooms.values() if sp["region"] == reg)
            col = tuple(min(255, int(v * 3.4)) for v in meta["tint"])
            text(s, meta["name"].lower(), (x, y), 22, col)
            text(s, "%d/%d" % (seen, total_n), (x + 250, y + 2), 18,
                 (110, 120, 130))
            y += 24
            y = _wrapped(s, meta["blurb"], (x + 12, y), 330, 18,
                         (118, 128, 136)) + 14

        y += 10
        text(s, "%d of %d rooms" % (len(self.world.discovered), len(rooms)),
             (x, y), 20, (150, 162, 172))
        text(s, "shut doors are marked in red", (x, y + 26), 18,
             (130, 96, 92))

    def _draw_codex(self, s):
        w, h = s.get_size()
        s.fill((9, 11, 14))
        pages = ["fragments", "tissue", "the others"]
        page = self.codex_page % len(pages)
        text(s, "WHAT YOU KNOW", (60, 40), 34, (190, 200, 210), bold=True)
        for i, p in enumerate(pages):
            col = (215, 225, 235) if i == page else (90, 100, 110)
            text(s, p, (420 + i * 190, 48), 24, col)
        text(s, "left / right    esc to go back", (60, 82), 18, (86, 94, 102))

        if page == 0:
            self._codex_fragments(s)
        elif page == 1:
            self._codex_organs(s)
        else:
            self._codex_species(s)

    def _codex_fragments(self, s):
        w, h = s.get_size()
        if not self.codex.fragments:
            text(s, "nothing yet.", (60, 140), 22, (100, 110, 120))
            return
        x, y = 60, 130
        col = 0
        for key in self.codex.fragments:
            fr = FRAGMENTS[key]
            if y > h - 150:
                col += 1
                x, y = 60 + col * 620, 130
                if col > 1:
                    break
            kindcol = {"log": (150, 172, 186), "mark": (196, 150, 130),
                       "memory": (170, 160, 200)}[fr.kind]
            text(s, fr.title, (x, y), 23, kindcol, bold=True)
            y += 26
            y = _wrapped(s, fr.text.replace("\n\n", "  /  ").replace("\n", " "),
                         (x, y), 560, 18, (140, 148, 156)) + 14

    def _codex_organs(self, s):
        from .lore import organ_line
        x, y = 60, 130
        cols = 0
        for key in sorted(self.codex.organ_seen):
            t = BY_KEY.get(key)
            if t is None:
                continue
            if y > s.get_height() - 120:
                cols += 1
                x, y = 60 + cols * 620, 130
                if cols > 1:
                    break
            conf = self.codex.organ_confidence(key)
            text(s, "%s  %s" % (t.glyph, t.name), (x, y), 22, (200, 210, 220))
            text(s, "%d uses" % self.codex.organ_uses.get(key, 0),
                 (x + 300, y + 2), 17, (90, 100, 110))
            y += 24
            line = organ_line(key, conf)
            y = _wrapped(s, line or t.blurb, (x + 14, y), 540, 18,
                         (150, 170, 165) if line else (110, 118, 126)) + 12

    def _codex_species(self, s):
        x, y = 60, 130
        for key, n in sorted(self.codex.species_seen.items(),
                             key=lambda kv: -kv[1]):
            sp = bestiary.SPECIES.get(key)
            if sp is None or not sp.codex:
                continue
            if y > s.get_height() - 130:
                break
            killed = self.codex.species_killed.get(key, 0)
            text(s, sp.name, (x, y), 24, (205, 200, 195), bold=True)
            text(s, "seen %d · taken %d" % (n, killed), (x + 320, y + 3), 17,
                 (100, 108, 116))
            y += 26
            y = _wrapped(s, sp.codex, (x, y), 900, 19, (145, 152, 160)) + 16

    def _draw_ending(self, s):
        """Lines fade in one at a time and the block rises once it runs out
        of screen, so an ending can be as long as it needs to be without
        anyone having to count lines against a resolution. The deep version
        of the abstain ending is twenty-four lines and the first draft of
        this method simply drew ten of them off the bottom."""
        w, h = s.get_size()
        s.fill((6, 7, 9))
        t = self.ending_time
        lines = ENDINGS[self.ending](self)

        heights = [(34 if i == 0 else 22) + 16 if line else 20
                   for i, line in enumerate(lines)]
        shown = 0
        for i in range(len(lines)):
            if t >= 0.55 + i * 0.85:
                shown = i + 1
        revealed_h = sum(heights[:shown])

        top, bottom = 140, h - 90
        overflow = max(0.0, revealed_h - (bottom - top))
        y = top - overflow

        for i, line in enumerate(lines):
            appear = 0.55 + i * 0.85
            if t < appear:
                break
            if not line:
                y += 20
                continue
            a = int(min(255, (t - appear) * 300))
            size = 34 if i == 0 else 22
            col = (215, 220, 226) if i == 0 else (160, 168, 176)
            if y > -40 and y < h:
                img = font(size).render(line, True, col)
                img.set_alpha(a)
                s.blit(img, (w // 2 - img.get_width() // 2, int(y)))
            y += size + 16

        if t > 0.55 + len(lines) * 0.85 + 1.5:
            text(s, "\u2014", (w // 2, h - 44), 24, (80, 86, 92), center=True)

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            dt = min(0.05, clock.tick(C.FPS) / 1000.0)
            self._dt = dt
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()


# ---------------------------------------------------------------------------
# The endings.
#
# There are two, they are three metres apart, and the game does not tell you
# which one you are standing in front of. A player who found the criterion
# will recognise the room; a player who did not will do what the last twelve
# hours have taught them to do, which is the point, and which is why the
# harvest ending is written without a single word of reproach in it.
# ---------------------------------------------------------------------------

def _ending_harvest(game):
    depth = game.codex.depth
    out = [
        "you fed",
        "",
        "it did not resist. you had already worked out that it would not.",
        "",
        "you are heavier now, and warmer, and there is a great deal of you.",
        "the water here goes down further than the building and there is",
        "nothing in it that you have not already learned how to open.",
        "",
    ]
    if depth >= 3:
        out += [
            "somewhere above you a condition is evaluated, the way it has",
            "been evaluated four hundred thousand times, and comes back the",
            "way it always comes back.",
            "",
            "the doors do not open.",
            "",
            "they were only ever on the one thing.",
        ]
    else:
        out += [
            "you wait for a while to see whether anything happens.",
            "",
            "nothing happens.",
            "",
            "you have been the last one for some time now. you simply did",
            "not have the second one to measure it against until today.",
        ]
    out += ["", "CANDIDATE %s — persisted." % _number(game),
            "did not meet criterion."]
    return out


def _ending_abstain(game):
    depth = game.codex.depth
    out = [
        "you did not",
        "",
        "it is smaller than you. it is made of worse things than you are",
        "made of, and you have taken apart nine hundred of them, and this",
        "one is looking at you.",
        "",
        "you stay where you are.",
        "",
    ]
    if depth >= 4:
        out += [
            "above and behind you, something that has been counting for a",
            "very long time stops counting.",
            "",
            "the sill opens. it was never a door. it was a held breath.",
            "",
            "nobody is left to tell you that this was the whole of it — that",
            "everything else was conditions, and this was the criterion, and",
            "they wrote it down once and then went away to die of the world",
            "they had made.",
            "",
            "you go out into the water that has no ceiling.",
            "you are not alone. that is a promise and it is also a threat",
            "and it turns out those were always the same sentence.",
        ]
    else:
        out += [
            "you do not know why you stay. there is no reason in you that",
            "you can find. it is simply that there are two of you now and",
            "there has never been two of anything.",
            "",
            "after a while the water at the sill changes. something that was",
            "shut is not shut.",
            "",
            "you never find out what decided that. you go anyway, and the",
            "small one comes with you, and the dark ahead is a different",
            "dark: it is the kind that has a top.",
        ]
    out += ["", "CANDIDATE %s — persisted." % _number(game),
            "criterion met."]
    return out


def _number(game):
    """Your number. Derived from the run so it is *yours*, and enormous so
    that it lands the way it should: you are not the first, you are not the
    hundredth, and nobody has been keeping the list for a long time."""
    n = 400000 + int(game.playtime * 7) + game.player.harvests * 13 \
        + len(game.codex.fragments) * 101 + game.player.deaths * 37
    return "{:,}".format(n)


ENDINGS = {"harvest": _ending_harvest, "abstain": _ending_abstain}


def main():
    pygame.init()
    pygame.display.set_caption("CLADE")
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    Game(screen).run()
    pygame.quit()


if __name__ == "__main__":
    main()
