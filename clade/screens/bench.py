"""The Bench: surgery, the Assay, the Shelf, and a tutorial.

Rewritten after playtesting, because the first version had a modal editor
with an invisible mode and it made the most important screen in the game
feel broken. The specific failure, in the code that was there:

    def _click(self, e):
        if self.routing is not None:
            self._route_click(cell); return   # <- swallowed every click

Pressing a slot number silently armed routing, and from then on left-click
could not select and **right-click could not remove**. Clicking a socket
already in the path was an error ("the path cannot cross itself") instead
of simply stepping back to it. So the reports — "I left-click to remove and
then I switch to the second slot and now I can't", "making connections
works sometimes and sometimes it doesn't" — were all one bug wearing three
hats.

The rules now, and they hold everywhere with no exceptions:

    right-click a socket      always removes it. always.
    left-click a socket       always selects it, and *also* extends the
                              chain you are editing, if you are editing one
    left-click a route socket steps the path back to there, rather than
                              refusing
    the status line           always says what you are doing and what to
                              press next

There is no state you can get into where a button stops meaning what it
meant a second ago. That is the whole design of this file.
"""

import math

import pygame

from .. import config as C
from ..assay import bias_of, effect_summary, function_of
from ..body import Chain, GRID_H, GRID_W, N_ACTIVE, N_STANDING
from ..effects import resolve
from ..humours import (
    BLEND_NOTES, COLORS, GLYPHS, N_HUMOURS, NAMES, Charge, blend_of,
)
from ..lore import organ_line
from ..organs import (
    BY_KEY, ChainContext, INTAKE, TRANSFORM, VENT, can_fuse, fuse_key, make)
from ..render.hud import font, text
from ..shelf import FIRED, SHELF, STANDING, missing_for

CELL = 68
PAD = 7
GRID_X, GRID_Y = 56, 128
SLOT_X = GRID_X + GRID_W * (CELL + PAD) + 34
PACK_X = 952

ROLE_COLORS = {
    INTAKE: (110, 170, 200),
    TRANSFORM: (190, 175, 140),
    VENT: (205, 130, 120),
}
ROLE_WORD = {INTAKE: "way in", TRANSFORM: "changes it", VENT: "way out"}


class Tutorial:
    """Nine steps, each of which advances when the player actually does the
    thing. Never blocks input and never takes the mouse — you can ignore it
    completely and it will still be right about what you did."""

    STEPS = [
        ("this is your body",
         "every square is a socket. the ones with something in them are "
         "organs you are carrying inside you right now.",
         "press SPACE", lambda b, s: s.tut_key),
        ("take something out",
         "RIGHT-CLICK the Kiln (the ^ in the top row). right-click always "
         "removes, in every mode, with no exceptions.",
         "right-click any organ", lambda b, s: s.tut_removed),
        ("put it back",
         "left-click it in CARRIED on the right, then left-click an empty "
         "socket.",
         "install anything", lambda b, s: s.tut_installed),
        ("a chain is a path",
         "press 1 to edit your first fired chain. a chain starts at a way "
         "in, runs through things that change it, and ends at a way out.",
         "press 1", lambda b, s: s.editing == 0 and not s.standing_edit),
        ("click sockets in order",
         "each one must touch the last. click a socket already in the path "
         "to step back to it. ENTER keeps it, ESC throws it away.",
         "keep a chain with ENTER", lambda b, s: s.tut_committed),
        ("assay it",
         "SPACE fires the chain into nothing and shows you the mixture "
         "after every single organ. it is free and you can do it forever.",
         "press SPACE", lambda b, s: s.tut_assayed),
        ("chains you run, not fire",
         "press 5. slots 5 and 6 are STANDING chains: no way out, always "
         "on, and what they make happens to YOU. warmth, cover, healing, "
         "buoyancy. this is how you survive the deep regions.",
         "press 5", lambda b, s: s.editing == 0 and s.standing_edit),
        ("the shelf",
         "press L for a rack of prebuilt chains that work. load LANCE and "
         "FIZZLE and assay both — they are the same five organs in a "
         "different order.",
         "press L", lambda b, s: s.shelf_open or s.tut_shelf),
        ("two into one",
         "hold an organ from CARRIED, click one in your body, and press G. "
         "they grow together into one socket that does what both did, in "
         "that order. V holds an assay so you can compare two builds.",
         "press G, or any key to move on", lambda b, s: s.tut_late),
        ("that is all of it",
         "everything else is yours to find out. the Assay never lies and "
         "never costs anything. H, out in the water, explains every bar "
         "on the screen and what is currently killing you.",
         "press ESC to go back to the water", lambda b, s: False),
    ]

    def __init__(self):
        self.step = 0
        self.done = False

    def advance(self, body, screen):
        if self.done:
            return
        while self.step < len(self.STEPS):
            cond = self.STEPS[self.step][3]
            if cond(body, screen):
                self.step += 1
            else:
                break
        if self.step >= len(self.STEPS):
            self.step = len(self.STEPS) - 1


class BenchScreen:
    def __init__(self, game):
        self.game = game
        self.sel_cell = None
        self.sel_pack = None
        self.held = None             # organ picked up from CARRIED
        self.editing = None          # slot index being edited
        self.standing_edit = False
        self.route = []
        self.assay = None
        self.assay_chain = 0
        self.assay_standing = False
        self.message = ""
        self.msg_time = 99.0
        self.hover = None
        self.hover_pack = None
        self.shelf_open = False
        self.shelf_index = 0
        self.tutorial = Tutorial()
        self.show_tutorial = True
        # tutorial observations
        self.tut_key = False
        self.tut_removed = False
        self.tut_installed = False
        self.tut_committed = False
        self.tut_assayed = False
        self.tut_shelf = False
        self.pinned = None           # a second assay, held for comparison
        self.tut_late = False

    # ------------------------------------------------------------- helpers

    @property
    def body(self):
        return self.game.body

    def say(self, msg):
        self.message = msg
        self.msg_time = 0.0

    def cell_rect(self, cx, cy):
        return pygame.Rect(GRID_X + cx * (CELL + PAD),
                           GRID_Y + cy * (CELL + PAD), CELL, CELL)

    def cell_at(self, pos):
        for cy in range(GRID_H):
            for cx in range(GRID_W):
                if self.cell_rect(cx, cy).collidepoint(pos):
                    return (cx, cy)
        return None

    # Column budget, so nothing draws over anything else:
    #   left   56  grid, then the selected organ
    #   middle 530 FIRED / RUNNING / upkeep, then the Assay stages
    #   right  952 CARRIED, then what the chain would do
    # Everything below LOWER_Y belongs to the second half of its column.
    LOWER_Y = 556
    PACK_ROWS = 12

    def pack_rect(self, i):
        return pygame.Rect(PACK_X, 160 + i * 30, 296, 27)

    def slot_rect(self, i, standing=False):
        y = 148 + i * 44 + (N_ACTIVE * 44 + 62 if standing else 0)
        return pygame.Rect(SLOT_X, y, 330, 40)

    def pool(self, standing=None):
        st = self.standing_edit if standing is None else standing
        return self.body.standing if st else self.body.chains

    # -------------------------------------------------------------- events

    def handle(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.cell_at(e.pos)
            self.hover_pack = None
            for i in range(len(self.body.pack)):
                if self.pack_rect(i).collidepoint(e.pos):
                    self.hover_pack = i
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self._click(e)
        elif e.type == pygame.KEYDOWN:
            self._key(e)

    # --- clicking ---------------------------------------------------------

    def _click(self, e):
        if self.shelf_open:
            self._shelf_click(e)
            return

        cell = self.cell_at(e.pos)
        if cell is not None:
            self._click_cell(cell, e.button)
            return

        for i in range(len(self.body.pack)):
            if self.pack_rect(i).collidepoint(e.pos):
                if e.button == 3:
                    self.say("right-click removes organs from your body, "
                             "not from your pack")
                    return
                self.held = self.body.pack[i]
                self.sel_pack = self.held
                self.sel_cell = None
                self.say("holding %s — click an empty socket to fit it"
                         % self.held.name)
                return

        for standing in (False, True):
            for i in range(N_STANDING if standing else N_ACTIVE):
                if self.slot_rect(i, standing).collidepoint(e.pos):
                    self._arm(i, standing)
                    return

        # Clicking nothing puts down whatever you were holding.
        if self.held is not None:
            self.held = None
            self.say("")

    def _click_cell(self, cell, button):
        body = self.body

        # RIGHT-CLICK ALWAYS REMOVES. No mode, no exception, no ordering.
        if button == 3:
            if cell not in body.cells:
                return
            org = body.uninstall(cell)
            if org is None:
                self.say("nothing in that socket")
                return
            self.tut_removed = True
            self._prune(cell)
            self.say("took out %s — it is in CARRIED" % org.name)
            self._run_assay()
            return

        if cell not in body.cells:
            self.say("that socket has not grown yet")
            return

        # Holding something and clicked an empty socket: fit it.
        if self.held is not None and body.organ_at(cell) is None:
            if body.install(cell, self.held):
                self.tut_installed = True
                self.say("fitted %s" % self.held.name)
                self.sel_cell = cell
                self.held = None
                self.sel_pack = None
                self.body.recompute_standing()
                self._run_assay()
            else:
                self.say("it will not sit there")
            return

        # Always select. This is what makes the screen non-modal: inspecting
        # never stops working, whatever else you are in the middle of.
        self.sel_cell = cell
        self.sel_pack = None

        if self.editing is not None:
            self._extend(cell)

    def _extend(self, cell):
        """Add to the path, or step back to a socket already in it."""
        if self.body.organ_at(cell) is None:
            self.say("nothing in that socket to run through")
            return
        if cell in self.route:
            # Forgiving: clicking back up the path truncates to there,
            # rather than refusing with 'the path cannot cross itself'.
            i = self.route.index(cell)
            self.route = self.route[:i + 1]
            return
        if self.route:
            a = self.route[-1]
            if abs(a[0] - cell[0]) + abs(a[1] - cell[1]) != 1:
                self.say("that socket does not touch the last one — the "
                         "path has to be unbroken")
                return
        self.route.append(cell)

    def _arm(self, i, standing):
        if self.editing == i and self.standing_edit == standing:
            self._commit()
            return
        self.editing = i
        self.standing_edit = standing
        self.route = list(self.pool(standing)[i].cells)
        self.assay_chain = i
        self.assay_standing = standing
        self._run_assay()

    def _commit(self):
        i, standing = self.editing, self.standing_edit
        ch = Chain(list(self.route))
        ok, why = self.body.validate(ch, standing=standing)
        if not ok:
            self.say("cannot keep it: %s" % why)
            return
        self.pool(standing)[i] = ch
        self.editing = None
        self.route = []
        self.body.recompute_standing()
        self.tut_committed = True
        self.say("%s %d set" % ("standing chain" if standing else "chain",
                                i + (5 if standing else 1)))
        self._run_assay()

    def _prune(self, cell):
        for ch in list(self.body.chains) + list(self.body.standing):
            if cell in ch.cells:
                ch.cells = []
        if cell in self.route:
            self.route = self.route[:self.route.index(cell)]
        self.body.recompute_standing()

    # --- keys -------------------------------------------------------------

    def _key(self, e):
        k = e.key
        self.tut_key = True
        if self.tutorial.step >= len(Tutorial.STEPS) - 2:
            self.tut_late = True

        if self.shelf_open:
            self._shelf_key(k)
            return

        if k == pygame.K_ESCAPE:
            if self.held is not None:
                self.held = None
                self.say("")
            elif self.editing is not None:
                self.editing = None
                self.route = []
                self.say("left it as it was")
            else:
                self.game.leave_bench()
        elif pygame.K_1 <= k <= pygame.K_6:
            i = k - pygame.K_1
            self._arm(i - N_ACTIVE if i >= N_ACTIVE else i, i >= N_ACTIVE)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.editing is not None:
                self._commit()
        elif k == pygame.K_BACKSPACE:
            if self.editing is not None and self.route:
                self.route.pop()
        elif k == pygame.K_SPACE:
            self._run_assay()
            self.tut_assayed = True
        elif k == pygame.K_TAB:
            n = N_ACTIVE + N_STANDING
            cur = self.assay_chain + (N_ACTIVE if self.assay_standing else 0)
            cur = (cur + 1) % n
            self.assay_standing = cur >= N_ACTIVE
            self.assay_chain = cur - N_ACTIVE if self.assay_standing else cur
            self._run_assay()
        elif k == pygame.K_r:
            self._auto_route()
        elif k == pygame.K_x:
            if self.editing is not None:
                self.route = []
                self.say("path cleared — click sockets to build a new one")
        elif k == pygame.K_g:
            self._fuse()
        elif k == pygame.K_v:
            if self.assay is None:
                self.say("nothing to hold on to")
            elif self.pinned is not None:
                self.pinned = None
                self.say("let it go")
            else:
                n = self.assay_chain + (5 if self.assay_standing else 1)
                self.pinned = ("chain %d" % n, self.assay)
                self.say("holding that one — assay another to compare")
        elif k == pygame.K_l:
            self.shelf_open = True
            self.shelf_index = 0
            self.tut_shelf = True
        elif k in (pygame.K_F1, pygame.K_SLASH, pygame.K_QUESTION):
            self.show_tutorial = not self.show_tutorial

    def _fuse(self):
        """Grow the organ you are holding into the one you have selected.

        Both are consumed and one socket comes back with a graft that does
        what both did, in order, keeping a little less. It is function
        composition, so it needs no rules of its own and cannot be tuned
        apart from its parents."""
        body = self.body
        if self.held is None or self.sel_cell is None:
            self.say("to graft: click an organ in your body, hold another "
                     "from CARRIED, then press G")
            return
        target = body.organ_at(self.sel_cell)
        if target is None:
            self.say("nothing selected to graft onto")
            return
        ok, why = can_fuse(target.type, self.held.type)
        if not ok:
            self.say(why)
            return
        key = fuse_key(target.key, self.held.key)
        grafted = make(key)
        body.uninstall(self.sel_cell)
        for o in list(body.pack):
            if o is target or o is self.held:
                body.pack.remove(o)
        body.install(self.sel_cell, grafted)
        self.held = None
        self.sel_pack = None
        self.game.codex.see_organ(key)
        body.recompute_standing()
        self._run_assay()
        self.say("grew them together: %s" % grafted.name)

    def _auto_route(self):
        """Find a legal path for the slot being edited. Not clever — it is
        the shortest valid one — but it means a player who understands the
        idea and is fighting the mouse can stop fighting the mouse."""
        if self.editing is None:
            self.say("press 1-6 first to choose a chain to build")
            return
        body = self.body
        standing = self.standing_edit
        starts = [c for c, o in body.cells.items()
                  if o is not None and o.role == INTAKE]
        if standing:
            ends = [c for c, o in body.cells.items()
                    if o is not None and o.role == TRANSFORM]
        else:
            ends = [c for c, o in body.cells.items()
                    if o is not None and o.role == VENT]
        best = None
        for s in starts:
            for t in ends:
                path = self._path(s, t, standing)
                if path and (best is None or len(path) > len(best)):
                    best = path
        if best is None:
            self.say("no legal path exists in this body — you need a way in"
                     + ("" if standing else " and a way out")
                     + " that can be joined up")
            return
        self.route = best
        self.say("routed for you — ENTER to keep it")

    def _path(self, start, end, standing):
        import collections
        body = self.body
        seen = {start: None}
        q = collections.deque([start])
        while q:
            cur = q.popleft()
            if cur == end:
                break
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cur[0] + d[0], cur[1] + d[1])
                if n in seen:
                    continue
                o = body.organ_at(n)
                if o is None:
                    continue
                if n != end and o.role != TRANSFORM:
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
        ok, _ = body.validate(Chain(path), standing=standing)
        return path if ok else None

    # --- the shelf --------------------------------------------------------

    def _shelf_key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_l):
            self.shelf_open = False
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.shelf_index = (self.shelf_index + 1) % len(SHELF)
        elif k in (pygame.K_UP, pygame.K_w):
            self.shelf_index = (self.shelf_index - 1) % len(SHELF)
        elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self._load_preset(SHELF[self.shelf_index])

    def _shelf_click(self, e):
        for i in range(len(SHELF)):
            if self._shelf_rect(i).collidepoint(e.pos):
                if self.shelf_index == i:
                    self._load_preset(SHELF[i])
                self.shelf_index = i
                return
        self.shelf_open = False

    @staticmethod
    def _shelf_rect(i):
        return pygame.Rect(120, 128 + i * 34, 420, 31)

    def _load_preset(self, preset):
        """Fit a prebuilt chain, using parts you already have."""
        body = self.body
        short = missing_for(preset, body)
        if short:
            names = ", ".join(sorted({BY_KEY[k].name for k in short}))
            self.say("you do not have: %s" % names)
            return

        standing = preset.kind == STANDING
        cells = self._free_run(len(preset.organs), standing)
        if cells is None:
            self.say("no run of %d free sockets — take something out first"
                     % len(preset.organs))
            return

        for cell, key in zip(cells, preset.organs):
            cur = body.organ_at(cell)
            if cur is not None:
                body.uninstall(cell)
            org = next((o for o in body.pack if o.key == key), None)
            if org is None:
                org = self._reclaim(key)
            if org is None:
                self.say("something went wrong fitting %s" % preset.name)
                return
            body.install(cell, org)

        ch = Chain(list(cells))
        ok, why = body.validate(ch, standing=standing)
        if not ok:
            self.say("%s would not route: %s" % (preset.name, why))
            return
        slot = 0 if standing else self._free_slot()
        self.pool(standing)[slot] = ch
        body.recompute_standing()
        self.assay_chain = slot
        self.assay_standing = standing
        self.editing = None
        self.route = []
        self.shelf_open = False
        self._run_assay()
        self.say("%s fitted to %s %d" % (
            preset.name, "standing slot" if standing else "chain",
            slot + (5 if standing else 1)))

    def _free_slot(self):
        for i, ch in enumerate(self.body.chains):
            ok, _ = self.body.validate(ch)
            if not ok:
                return i
        return len(self.body.chains) - 1

    def _reclaim(self, key):
        used = set()
        for ch in list(self.body.chains) + list(self.body.standing):
            used.update(ch.cells)
        for cell, o in self.body.cells.items():
            if o is not None and o.key == key and cell not in used:
                return self.body.uninstall(cell)
        return None

    def _free_run(self, n, standing):
        used = set()
        for i, ch in enumerate(self.body.chains):
            used.update(ch.cells)
        if not standing:
            for ch in self.body.standing:
                used.update(ch.cells)
        free = [c for c in sorted(self.body.cells) if c not in used]
        freeset = set(free)
        for start in free:
            path, cur = [start], start
            while len(path) < n:
                nxt = None
                for d in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    cand = (cur[0] + d[0], cur[1] + d[1])
                    if cand in freeset and cand not in path:
                        nxt = cand
                        break
                if nxt is None:
                    break
                path.append(nxt)
                cur = nxt
            if len(path) == n:
                return path
        return None

    # --------------------------------------------------------------- assay

    def _run_assay(self):
        i, standing = self.assay_chain, self.assay_standing
        cells = self.route if (self.editing == i
                               and self.standing_edit == standing
                               and self.route) else \
            self.pool(standing)[i].cells
        ch = Chain(list(cells))
        ok, why = self.body.validate(ch, standing=standing)
        if not ok:
            self.assay = None
            return
        organs = self.body.chain_organs(ch)
        ctx = ChainContext(None, None, (0, 0), (1, 0))
        stages = []
        charge = organs[0].apply(Charge(), ctx)
        stages.append((organs[0].name, charge.copy()))
        middle = organs[1:] if standing else organs[1:-1]
        for o in middle:
            if o.type.key == "bladder":
                stages.append((o.name + " (fills first)", charge.copy()))
                continue
            charge = o.apply(charge, ctx)
            stages.append((o.name, charge.copy()))
        for _ in range(ctx.recursions):
            for o in middle:
                if o.type.key == "bladder":
                    continue
                charge = o.apply(charge, ctx)
            stages.append(("(around again)", charge.copy()))
        if not standing:
            stages.append((organs[-1].name, charge.copy()))
        self.assay = (stages, charge.copy(), ctx, standing)
        for o in organs:
            self.game.codex.see_organ(o.key)

    # ---------------------------------------------------------------- draw

    def update(self, dt):
        self.msg_time += dt
        self.tutorial.advance(self.body, self)

    def draw(self, surf):
        surf.fill((11, 13, 16))
        self._draw_header(surf)
        self._draw_grid(surf)
        self._draw_slots(surf)
        self._draw_pack(surf)
        self._draw_detail(surf)
        self._draw_assay(surf)
        if self.show_tutorial and not self.tutorial.done:
            self._draw_tutorial(surf)
        if self.shelf_open:
            self._draw_shelf(surf)
        self._draw_status(surf)

    def _draw_header(self, surf):
        text(surf, "THE BENCH", (GRID_X, 34), 38, (200, 210, 220), bold=True)
        keys = ("right-click removes  ·  1-6 edit a chain  ·  R routes it "
                "for you  ·  SPACE assays  ·  V hold one to compare  ·  "
                "G graft two together  ·  L shelf  ·  F1 help  ·  ESC back")
        text(surf, keys, (GRID_X, 74), 16, (104, 114, 124))

    def _status_line(self):
        if self.shelf_open:
            return ("the shelf — up/down to browse, ENTER to fit it, "
                    "ESC to close", (170, 190, 205))
        if self.held is not None:
            return ("holding %s — left-click an empty socket to fit it, "
                    "ESC to put it down" % self.held.name, (200, 200, 150))
        if self.editing is not None:
            n = self.editing + (5 if self.standing_edit else 1)
            kind = "STANDING chain" if self.standing_edit else "chain"
            ok, why = self.body.validate(Chain(self.route),
                                         standing=self.standing_edit)
            tail = "ENTER to keep it" if ok else why
            return ("editing %s %d — %d socket%s so far. click sockets in "
                    "order · BACKSPACE undo · X clear · %s · ESC cancel"
                    % (kind, n, len(self.route),
                       "" if len(self.route) == 1 else "s", tail),
                    (150, 205, 195) if ok else (200, 175, 140))
        return ("press 1-4 to edit a chain you fire, 5-6 for one you run",
                (100, 112, 122))

    def _draw_status(self, surf):
        w, h = surf.get_size()
        line, col = self._status_line()
        bar = pygame.Rect(0, h - 34, w, 34)
        pygame.draw.rect(surf, (17, 20, 24), bar)
        pygame.draw.line(surf, (34, 40, 46), (0, h - 34), (w, h - 34))
        text(surf, line, (GRID_X, h - 25), 19, col)
        if self.message and self.msg_time < 5.0:
            a = int(255 * min(1.0, (5.0 - self.msg_time) / 1.4))
            text(surf, self.message, (w - 24, h - 25), 19, (222, 206, 170),
                 alpha=a, right=True)

    def _draw_grid(self, surf):
        body = self.body
        editing = self.editing is not None
        active = self.route if editing else \
            self.pool(self.assay_standing)[self.assay_chain].cells

        for a, b in zip(active, active[1:]):
            ra, rb = self.cell_rect(*a), self.cell_rect(*b)
            col = (120, 190, 175) if (editing and self.standing_edit) else \
                (110, 155, 185)
            pygame.draw.line(surf, col, ra.center, rb.center, 8)

        for cy in range(GRID_H):
            for cx in range(GRID_W):
                self._draw_cell(surf, (cx, cy), active, editing)

        text(surf, "%d sockets" % len(body.cells),
             (GRID_X, GRID_Y + GRID_H * (CELL + PAD) + 6), 17, (98, 108, 118))

    def _draw_cell(self, surf, cell, active, editing):
        body = self.body
        cx, cy = cell
        rect = self.cell_rect(cx, cy)
        if cell not in body.cells:
            pygame.draw.rect(surf, (17, 19, 22), rect, border_radius=5)
            pygame.draw.rect(surf, (26, 29, 33), rect, 1, border_radius=5)
            return
        org = body.organ_at(cell)
        pygame.draw.rect(surf, (24, 28, 32), rect, border_radius=5)

        edge, width = (50, 56, 62), 1
        if cell == self.sel_cell:
            edge, width = (215, 228, 240), 2
        elif cell in active:
            edge, width = ((150, 210, 195) if self.standing_edit
                           else (130, 175, 200)), 2
        elif cell == self.hover:
            edge, width = (110, 125, 140), 2
        elif editing and org is not None:
            edge = (78, 92, 104)
        pygame.draw.rect(surf, edge, rect, width, border_radius=5)

        if org is None:
            if self.held is not None:
                text(surf, "+", rect.center, 26, (90, 110, 120), center=True)
            return

        col = ROLE_COLORS.get(org.role, (180, 180, 180))
        if org.seized:
            col = (235, 120, 100)
        text(surf, org.glyph, (rect.centerx, rect.centery - 10), 32, col,
             center=True)
        nm = org.name if len(org.name) <= 11 else org.name[:10] + "."
        text(surf, nm, (rect.centerx, rect.bottom - 25), 14, (146, 156, 166),
             center=True)
        # The measured tag. This is the single change that answers
        # "I cannot tell what things do" at a glance.
        text(surf, bias_of(org.type), (rect.centerx, rect.bottom - 13), 14,
             (128, 158, 150), center=True)

        hot = min(1.0, org.heat / C.ORGAN_SEIZE_AT)
        if hot > 0.03:
            pygame.draw.rect(surf, (214, 132, 80),
                             pygame.Rect(rect.x + 4, rect.y + 4,
                                         int((CELL - 8) * hot), 3))
        if cell in active:
            n = active.index(cell) + 1
            pygame.draw.circle(surf, (16, 20, 24), (rect.x + 12, rect.y + 12), 9)
            text(surf, str(n), (rect.x + 12, rect.y + 12), 17,
                 (190, 225, 215), center=True)

    def _draw_slots(self, surf):
        body = self.body
        text(surf, "FIRED", (SLOT_X, 122), 22, (158, 170, 180), bold=True)
        for i in range(N_ACTIVE):
            self._draw_slot(surf, i, False)
        y = self.slot_rect(0, True).y - 26
        text(surf, "RUNNING", (SLOT_X, y), 22, (150, 190, 178), bold=True)
        text(surf, "no way out. always on. it feeds you.",
             (SLOT_X + 110, y + 4), 15, (96, 118, 110))
        for i in range(N_STANDING):
            self._draw_slot(surf, i, True)

        fx = body.standing_fx
        y = self.slot_rect(N_STANDING - 1, True).bottom + 12
        up = body.upkeep
        text(surf, "upkeep %.2f/sec" % up, (SLOT_X, y), 19,
             (150, 160, 170) if up < 1.2 else (224, 160, 118))
        bits = []
        for label, key, t in (("burning", "heat", 0.3), ("hazed", "murk", 0.3),
                              ("tended", "gentle", 0.3), ("quick", "jolt", 0.5),
                              ("caustic", "caustic", 0.4)):
            if fx[key] > t:
                bits.append("%s %.1f" % (label, fx[key]))
        if fx["lift"] > 0.6:
            bits.append("buoyant %.1f" % fx["lift"])
        elif fx["lift"] < -0.6:
            bits.append("heavy %.1f" % -fx["lift"])
        text(surf, "  ".join(bits) or "you are running nothing",
             (SLOT_X, y + 22), 18,
             (150, 190, 178) if bits else (98, 108, 116))

    def _draw_slot(self, surf, i, standing):
        body = self.body
        ch = self.pool(standing)[i]
        rect = self.slot_rect(i, standing)
        ok, why = body.validate(ch, standing=standing)
        organs = body.chain_organs(ch) if ok else None
        editing = self.editing == i and self.standing_edit == standing
        shown = (i == self.assay_chain
                 and self.assay_standing == standing)

        if editing:
            pygame.draw.rect(surf, (26, 42, 40), rect, border_radius=4)
            pygame.draw.rect(surf, (140, 205, 190), rect, 2, border_radius=4)
        elif shown:
            pygame.draw.rect(surf, (28, 33, 38), rect, border_radius=4)
        pygame.draw.rect(surf, (60, 70, 78), rect, 1, border_radius=4)

        num = i + (5 if standing else 1)
        text(surf, str(num), (rect.x + 10, rect.y + 9), 22,
             (210, 230, 222) if (editing or shown) else (112, 124, 132))
        if organs:
            text(surf, "  ".join(o.glyph for o in organs),
                 (rect.x + 34, rect.y + 5), 21, (198, 212, 222))
            names = " > ".join(o.name.lower() for o in organs)
            if len(names) > 42:
                names = names[:41] + "..."
            text(surf, names, (rect.x + 34, rect.y + 24), 14, (100, 112, 120))
        else:
            text(surf, why, (rect.x + 34, rect.y + 12), 16, (104, 96, 96))

    def _draw_pack(self, surf):
        text(surf, "CARRIED", (PACK_X, 122), 22, (158, 170, 180), bold=True)
        pack = self.body.pack
        if not pack:
            text(surf, "nothing spare", (PACK_X, 162), 17, (86, 94, 102))
            return
        for i, org in enumerate(pack[:self.PACK_ROWS]):
            rect = self.pack_rect(i)
            sel = org is self.held
            if sel:
                pygame.draw.rect(surf, (36, 42, 48), rect, border_radius=3)
                pygame.draw.rect(surf, (198, 212, 224), rect, 1,
                                 border_radius=3)
            elif i == self.hover_pack:
                pygame.draw.rect(surf, (26, 30, 35), rect, border_radius=3)
            col = ROLE_COLORS.get(org.role, (180, 180, 180))
            text(surf, org.glyph, (rect.x + 10, rect.y + 5), 20, col)
            text(surf, org.name, (rect.x + 34, rect.y + 6), 18, (178, 188, 198))
            text(surf, bias_of(org.type), (rect.right - 8, rect.y + 7), 15,
                 (120, 148, 142), right=True)
        if len(pack) > self.PACK_ROWS:
            text(surf, "and %d more" % (len(pack) - self.PACK_ROWS),
                 (PACK_X, self.pack_rect(self.PACK_ROWS).y), 16,
                 (90, 100, 108))

    def _draw_detail(self, surf):
        x, y = GRID_X, GRID_Y + GRID_H * (CELL + PAD) + 26
        org = None
        if self.sel_cell is not None:
            org = self.body.organ_at(self.sel_cell)
        if org is None and self.held is not None:
            org = self.held
        if self.show_tutorial and not self.tutorial.done:
            # The tutorial owns the bottom of this column while it is up.
            if org is None:
                return
        if org is None:
            text(surf, "click any organ to read it", (x, y), 20,
                 (96, 106, 114))
            return

        text(surf, org.name, (x, y), 27, (216, 226, 236), bold=True)
        text(surf, ROLE_WORD.get(org.role, org.role), (x + 240, y + 6), 18,
             ROLE_COLORS.get(org.role, (150, 150, 150)))
        # Measured, not written down. Always shown, from the first second.
        width = 430 if (self.show_tutorial and not self.tutorial.done) else 700
        yy = _wrapped(surf, function_of(org.type), (x, y + 30), width, 19,
                      (186, 206, 198))
        if not (self.show_tutorial and not self.tutorial.done):
            yy = _wrapped(surf, org.type.blurb, (x, yy + 6), width, 18,
                          (128, 138, 148))
        conf = self.game.codex.organ_confidence(org.key)
        line = organ_line(org.key, conf)
        if line and conf >= 2 and not self.show_tutorial:
            _wrapped(surf, "— " + line, (x, yy + 6), 700, 18, (166, 190, 180))

    def _draw_assay(self, surf):
        n = self.assay_chain + (5 if self.assay_standing else 1)
        top = self.LOWER_Y
        text(surf, "THE ASSAY", (SLOT_X, top - 26), 22, (158, 170, 180),
             bold=True)
        text(surf, "chain %d · TAB switches" % n, (SLOT_X + 128, top - 22),
             16, (100, 110, 118))
        text(surf, "WHAT IT WOULD DO", (PACK_X, top - 26), 22,
             (158, 170, 180), bold=True)

        if self.assay is None:
            text(surf, "that chain does not run yet", (SLOT_X, top), 17,
                 (100, 110, 118))
            return
        stages, final, ctx, standing = self.assay

        bw = 250
        yy = top
        for (name, ch) in stages[-5:]:
            text(surf, name, (SLOT_X, yy), 15, (140, 150, 160))
            m = max(0.001, ch.magnitude)
            xx = SLOT_X
            for i in range(N_HUMOURS):
                seg = int(bw * abs(ch[i]) / m)
                if seg > 0:
                    pygame.draw.rect(surf, COLORS[i],
                                     pygame.Rect(xx, yy + 14, seg, 6))
                    xx += seg
            text(surf, "%.1f" % ch.magnitude, (SLOT_X + bw + 8, yy + 5), 14,
                 (110, 120, 130))
            yy += 25

        eff, rows = effect_summary(final)
        pin_rows = {}
        if self.pinned is not None:
            _plabel, (_ps, pfinal, _pc, _pst) = self.pinned
            _pe, pr = effect_summary(pfinal)
            pin_rows = {r[0]: r[1] for r in pr}
            text(surf, "vs %s (V to drop)" % self.pinned[0],
                 (PACK_X + 296, top - 22), 15, (150, 176, 190), right=True)

        y2 = top
        if not rows:
            text(surf, "almost nothing", (PACK_X, y2), 18, (110, 120, 128))
        for label, value, frac, col in rows[:6]:
            text(surf, label, (PACK_X, y2), 16, (150, 160, 170))
            pygame.draw.rect(surf, (26, 30, 34),
                             pygame.Rect(PACK_X + 92, y2 + 3, 150, 9))
            pygame.draw.rect(surf, col,
                             pygame.Rect(PACK_X + 92, y2 + 3,
                                         int(150 * frac), 9))
            if label in pin_rows:
                # The held chain, as a notch on the same bar. Comparing two
                # builds used to mean remembering four numbers across two
                # screens, which nobody does.
                other = pin_rows[label]
                ratio = min(1.0, other / max(1e-6, value) * frac)
                nx = PACK_X + 92 + int(150 * ratio)
                pygame.draw.line(surf, (210, 220, 230), (nx, y2 + 1),
                                 (nx, y2 + 14), 2)
                delta = value - other
                text(surf, "%+.1f" % delta, (PACK_X + 296, y2), 15,
                     (150, 200, 172) if delta >= 0 else (216, 140, 120),
                     right=True)
            else:
                text(surf, "%.1f" % value, (PACK_X + 296, y2), 15,
                     (120, 130, 138), right=True)
            y2 += 19

        notes = []
        if ctx.count > 1:
            notes.append("%d at once" % ctx.count)
        if ctx.recursions:
            notes.append("runs %dx" % (1 + ctx.recursions))
        if ctx.quiet < 0.85:
            notes.append("quieted")
        elif ctx.quiet > 1.2:
            notes.append("noisy")
        if ctx.viability_cost > 0:
            notes.append("costs you %.1f" % ctx.viability_cost)
        if eff.opens_tissue:
            notes.append("OPENS GROWN DOORS")
        bl, _amt = blend_of(final)
        if bl:
            notes.append(bl)
        if notes:
            _wrapped(surf, "also: " + " · ".join(notes), (PACK_X, y2 + 10),
                     300, 16, (128, 174, 196))

    def _draw_tutorial(self, surf):
        step = self.tutorial.step
        title, body_text, prompt, _ = Tutorial.STEPS[step]
        w, h = surf.get_size()
        # Left column only. A full-width panel covered the Assay, which is
        # the one thing the tutorial keeps telling you to go and look at.
        panel = pygame.Rect(GRID_X, h - 226, 460, 184)
        pygame.draw.rect(surf, (18, 26, 30), panel, border_radius=6)
        pygame.draw.rect(surf, (70, 116, 108), panel, 1, border_radius=6)
        text(surf, "%d/%d" % (step + 1, len(Tutorial.STEPS)),
             (panel.x + 14, panel.y + 11), 17, (100, 140, 132))
        text(surf, title, (panel.x + 52, panel.y + 9), 22, (176, 216, 204),
             bold=True)
        _wrapped(surf, body_text, (panel.x + 14, panel.y + 38), 430, 18,
                 (162, 178, 186))
        text(surf, prompt, (panel.x + 14, panel.bottom - 44), 19,
             (140, 190, 178))
        text(surf, "F1 hides this", (panel.right - 14, panel.bottom - 22), 15,
             (84, 106, 100), right=True)

    def _draw_shelf(self, surf):
        w, h = surf.get_size()
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((7, 9, 11, 248))
        surf.blit(veil, (0, 0))
        text(surf, "THE SHELF", (120, 62), 34, (200, 212, 222), bold=True)
        text(surf, "chains that work. loading one uses parts you already "
                   "carry.", (120, 98), 18, (120, 132, 142))

        for i, p in enumerate(SHELF):
            rect = self._shelf_rect(i)
            sel = i == self.shelf_index
            short = missing_for(p, self.body)
            if sel:
                pygame.draw.rect(surf, (28, 34, 40), rect, border_radius=4)
                pygame.draw.rect(surf, (190, 208, 220), rect, 1,
                                 border_radius=4)
            col = (208, 220, 230) if not short else (116, 110, 108)
            text(surf, p.name, (rect.x + 12, rect.y + 6), 20, col)
            kind = "running" if p.kind == STANDING else "fired"
            text(surf, kind, (rect.x + 150, rect.y + 8), 16,
                 (140, 186, 176) if p.kind == STANDING else (150, 160, 170))
            glyphs = " ".join(BY_KEY[k].glyph for k in p.organs)
            text(surf, glyphs, (rect.x + 236, rect.y + 6), 19,
                 col if not short else (100, 96, 94))
            if short:
                text(surf, "missing", (rect.right - 10, rect.y + 8), 15,
                     (168, 116, 106), right=True)

        p = SHELF[self.shelf_index]
        x = 590
        text(surf, p.name, (x, 128), 30, (216, 226, 236), bold=True)
        text(surf, " > ".join(BY_KEY[k].name for k in p.organs), (x, 166),
             18, (150, 176, 190))
        yy = _wrapped(surf, p.note, (x, 200), 560, 20, (186, 196, 204))
        if p.teaches:
            yy = _wrapped(surf, p.teaches, (x, yy + 14), 560, 19,
                          (150, 200, 184))
        short = missing_for(p, self.body)
        if short:
            names = ", ".join(sorted({BY_KEY[k].name for k in short}))
            _wrapped(surf, "you do not have: " + names, (x, yy + 20), 560, 19,
                     (206, 132, 120))
        else:
            text(surf, "ENTER to fit it", (x, yy + 20), 20, (170, 210, 196))


def _wrapped(surf, s, pos, width, size, color):
    f = font(size)
    line, y = "", pos[1]
    for word in str(s).split():
        trial = (line + " " + word).strip()
        if f.size(trial)[0] > width and line:
            text(surf, line, (pos[0], y), size, color)
            y += size + 2
            line = word
        else:
            line = trial
    if line:
        text(surf, line, (pos[0], y), size, color)
        y += size + 2
    return y
