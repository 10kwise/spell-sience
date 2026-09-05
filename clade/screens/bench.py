"""The Bench: surgery, and the Assay.

Two halves of one screen, and they are together on purpose. The left half
is where you rearrange yourself; the right half is where you find out what
that did. Separating them would turn "try it and see" into "commit and hope",
and trying it and seeing is the only teaching mechanism the game has.

The Assay is the most important thing in this file. It runs the selected
chain against a neutral sample and prints the humour vector **after every
organ** — so an ordering question that would take twenty minutes of combat
to answer takes four seconds here, for free, with no risk. That is the deal
the game is making with a curious player: it will never hide a mechanism
from you, it will only decline to tell you which mechanism you want.

Note what the Assay does *not* show: no damage number, no DPS, no rating.
It shows the vector and one line of plain observation. The player does the
last step themselves, and the last step is the game.
"""

import math

import pygame

from .. import config as C
from ..body import GRID_H, GRID_W, Chain
from ..effects import resolve
from ..humours import COLORS, GLYPHS, N_HUMOURS, NAMES, Charge, blend_of
from ..lore import organ_line
from ..organs import ChainContext, INTAKE, TRANSFORM, VENT
from ..render.hud import font, text

CELL = 70
PAD = 8
ROLE_COLORS = {
    INTAKE: (110, 170, 200),
    TRANSFORM: (190, 175, 140),
    VENT: (205, 130, 120),
}


class BenchScreen:
    def __init__(self, game):
        self.game = game
        self.sel_cell = None
        self.sel_pack = None
        self.routing = None          # chain index being routed
        self.routing_standing = False
        self.route = []
        self.assay_standing = False
        self.assay = None            # (stages, effect) of the last run
        self.assay_chain = 0
        self.message = ""
        self.msg_time = 0.0
        self.grid_origin = (60, 130)
        self.hover = None

    # ------------------------------------------------------------- helpers

    @property
    def body(self):
        return self.game.body

    def say(self, msg):
        self.message = msg
        self.msg_time = 0.0

    def cell_rect(self, cx, cy):
        ox, oy = self.grid_origin
        return pygame.Rect(ox + cx * (CELL + PAD), oy + cy * (CELL + PAD),
                           CELL, CELL)

    def cell_at(self, pos):
        for cy in range(GRID_H):
            for cx in range(GRID_W):
                if self.cell_rect(cx, cy).collidepoint(pos):
                    return (cx, cy)
        return None

    def pack_rect(self, i):
        w = self.game.screen.get_width()
        return pygame.Rect(w - 330, 150 + i * 34, 300, 30)

    # -------------------------------------------------------------- events

    def handle(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.cell_at(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self._click(e)
        elif e.type == pygame.KEYDOWN:
            self._key(e)

    def _click(self, e):
        cell = self.cell_at(e.pos)
        if cell is not None:
            if self.routing is not None:
                self._route_click(cell)
                return
            if e.button == 3:
                org = self.body.uninstall(cell)
                if org:
                    self.say("removed %s" % org.name)
                    self._prune_chains(cell)
                return
            if self.sel_pack is not None and cell in self.body.cells \
                    and self.body.organ_at(cell) is None:
                org = self.sel_pack
                if self.body.install(cell, org):
                    self.say("installed %s" % org.name)
                    self.sel_pack = None
                    self.sel_cell = cell
                else:
                    self.say("it will not sit there")
                return
            if cell in self.body.cells:
                self.sel_cell = cell
                self.sel_pack = None
            return

        for i, org in enumerate(list(self.body.pack)):
            if self.pack_rect(i).collidepoint(e.pos):
                self.sel_pack = org
                self.sel_cell = None
                self.say("holding %s — click a socket" % org.name)
                return

    def _route_click(self, cell):
        if self.body.organ_at(cell) is None:
            self.say("nothing there to route through")
            return
        if self.route and cell == self.route[-1]:
            self.route.pop()
            return
        if cell in self.route:
            self.say("the path cannot cross itself")
            return
        if self.route:
            a = self.route[-1]
            if abs(a[0] - cell[0]) + abs(a[1] - cell[1]) != 1:
                self.say("it has to be next to the last one")
                return
        self.route.append(cell)

    def _key(self, e):
        k = e.key
        if k == pygame.K_ESCAPE:
            if self.routing is not None:
                self.routing = None
                self.route = []
                self.say("")
            else:
                self.game.leave_bench()
        elif pygame.K_1 <= k <= pygame.K_6:
            i = k - pygame.K_1
            standing = i >= 4
            slot = i - 4 if standing else i
            same = (self.routing == slot and self.routing_standing == standing)
            if same:
                self._commit_route(slot, standing)
            else:
                self.routing = slot
                self.routing_standing = standing
                pool = self.body.standing if standing else self.body.chains
                self.route = list(pool[slot].cells)
                self.assay_chain = slot
                self.assay_standing = standing
                if standing:
                    self.say("routing STANDING chain %d — no vent. it runs "
                             "all the time and it feeds you, not the water. "
                             "%d again to keep it" % (i + 1, i + 1))
                else:
                    self.say("routing chain %d — click sockets in order, %d "
                             "again to keep it" % (i + 1, i + 1))
        elif k == pygame.K_RETURN:
            if self.routing is not None:
                self._commit_route(self.routing, self.routing_standing)
        elif k == pygame.K_BACKSPACE:
            if self.routing is not None and self.route:
                self.route.pop()
        elif k == pygame.K_SPACE:
            self._run_assay()
        elif k == pygame.K_TAB:
            if self.assay_standing:
                self.assay_standing = False
                self.assay_chain = 0
            else:
                self.assay_chain += 1
                if self.assay_chain >= 4:
                    self.assay_chain = 0
                    self.assay_standing = True
            self._run_assay()

    def _commit_route(self, i, standing=False):
        pool = self.body.standing if standing else self.body.chains
        ch = Chain(list(self.route), pool[i].name)
        ok, why = self.body.validate(ch, standing=standing)
        if not ok:
            self.say(why)
            return
        pool[i] = ch
        self.routing = None
        self.routing_standing = False
        self.route = []
        self.assay_chain = i
        self.assay_standing = standing
        self.body.recompute_standing()
        self.say("%s %d set" % ("standing chain" if standing else "chain",
                                i + (5 if standing else 1)))
        self._run_assay()

    def _prune_chains(self, cell):
        for ch in list(self.body.chains) + list(self.body.standing):
            if cell in ch.cells:
                ch.cells = []
        self.body.recompute_standing()

    # --------------------------------------------------------------- assay

    def _run_assay(self):
        """Fire the chain into nothing, with a neutral sample, and record
        the vector at every step. No body is passed to the ChainContext, so
        intakes hand back a balanced laboratory draught rather than
        whatever you happen to be carrying — which is what makes the Assay
        a measurement of the *chain* rather than of your current lunch."""
        i = self.assay_chain
        standing = self.assay_standing
        ch = (self.body.standing if standing else self.body.chains)[i]
        ok, why = self.body.validate(ch, standing=standing)
        if not ok:
            self.assay = None
            self.say(why)
            return
        organs = self.body.chain_organs(ch)
        ctx = ChainContext(None, None, (0, 0), (1, 0))
        stages = []
        charge = organs[0].apply(Charge(), ctx)
        stages.append((organs[0].name, charge.copy()))
        middle = organs[1:] if standing else organs[1:-1]
        for o in middle:
            if o.type.key == "bladder":
                stages.append((o.name + " (holds)", charge.copy()))
                continue
            charge = o.apply(charge, ctx)
            stages.append((o.name, charge.copy()))
        for _ in range(ctx.recursions):
            for o in middle:
                if o.type.key == "bladder":
                    continue
                charge = o.apply(charge, ctx)
            stages.append(("(again)", charge.copy()))
        if not standing:
            stages.append((organs[-1].name, charge.copy()))
        self.assay = (stages, resolve(charge), ctx)
        for o in organs:
            self.game.codex.see_organ(o.key)

    # ---------------------------------------------------------------- draw

    def update(self, dt):
        self.msg_time += dt

    def draw(self, surf):
        surf.fill((11, 13, 16))
        w, h = surf.get_size()
        text(surf, "THE BENCH", (60, 44), 40, (200, 210, 220), bold=True)
        text(surf, "right-click a socket to remove.   1-4 route a fired "
                   "chain, 5-6 a standing one.   space assays.   esc leaves.",
             (60, 84), 18, (100, 110, 120))

        self._draw_grid(surf)
        self._draw_pack(surf)
        self._draw_assay(surf)
        self._draw_selected(surf)

        if self.message and self.msg_time < 4.0:
            a = int(255 * min(1.0, (4.0 - self.msg_time) / 1.2))
            text(surf, self.message, (w // 2, h - 34), 22, (200, 200, 180),
                 center=True, alpha=a)

    def _draw_grid(self, surf):
        body = self.body
        route = self.route if self.routing is not None else None
        if route is not None:
            active = route
        elif self.assay_standing:
            active = body.standing[self.assay_chain].cells
        else:
            active = body.chains[self.assay_chain].cells

        # The route, drawn under the cells so it reads as plumbing.
        for a, b in zip(active, active[1:]):
            ra, rb = self.cell_rect(*a), self.cell_rect(*b)
            pygame.draw.line(surf, (110, 150, 175), ra.center, rb.center, 7)

        for cy in range(GRID_H):
            for cx in range(GRID_W):
                cell = (cx, cy)
                rect = self.cell_rect(cx, cy)
                unlocked = cell in body.cells
                if not unlocked:
                    pygame.draw.rect(surf, (18, 20, 23), rect, border_radius=5)
                    pygame.draw.rect(surf, (28, 31, 35), rect, 1,
                                     border_radius=5)
                    continue
                org = body.organ_at(cell)
                pygame.draw.rect(surf, (24, 28, 32), rect, border_radius=5)
                edge = (52, 58, 64)
                if cell == self.sel_cell:
                    edge = (200, 215, 230)
                elif cell == self.hover:
                    edge = (110, 125, 140)
                elif active and cell in active:
                    edge = (120, 165, 190)
                pygame.draw.rect(surf, edge, rect, 2, border_radius=5)

                if org is None:
                    continue
                col = ROLE_COLORS.get(org.role, (180, 180, 180))
                hot = min(1.0, org.heat / C.ORGAN_SEIZE_AT)
                if org.seized:
                    col = (235, 120, 100)
                text(surf, org.glyph, (rect.centerx, rect.centery - 6), 34,
                     col, center=True)
                nm = org.name if len(org.name) <= 12 else org.name[:11] + "."
                text(surf, nm, (rect.centerx, rect.bottom - 13), 15,
                     (130, 140, 150), center=True)
                if hot > 0.03:
                    pygame.draw.rect(
                        surf, (210, 130, 80),
                        pygame.Rect(rect.x + 4, rect.y + 4,
                                    int((CELL - 8) * hot), 3))
                if org.integrity < 0.98:
                    pygame.draw.rect(
                        surf, (120, 110, 100),
                        pygame.Rect(rect.x + 4, rect.bottom - 6,
                                    int((CELL - 8) * org.integrity), 2))
                if active and cell in active:
                    n = active.index(cell) + 1
                    text(surf, str(n), (rect.x + 6, rect.y + 4), 17,
                         (150, 190, 210))

        ox, oy = self.grid_origin
        text(surf, "%d sockets" % len(body.cells),
             (ox, oy + GRID_H * (CELL + PAD) + 8), 18, (100, 110, 120))

        # Chain slots, beside the grid rather than beneath it: the panel
        # under the grid belongs to whatever is selected, and the two were
        # drawing on top of each other.
        cx = ox + GRID_W * (CELL + PAD) + 46
        text(surf, "FIRED", (cx, oy - 22), 24, (160, 172, 182), bold=True)
        for i in range(4):
            ch = body.chains[i]
            ok, why = body.validate(ch)
            organs = body.chain_organs(ch) if ok else None
            y = oy + 6 + i * 46
            sel = (i == self.assay_chain) and not self.assay_standing
            col = (200, 210, 220) if ok else (104, 96, 96)
            if sel:
                pygame.draw.rect(surf, (30, 35, 40),
                                 pygame.Rect(cx - 8, y - 6, 300, 40),
                                 border_radius=4)
            text(surf, str(i + 1), (cx, y), 24,
                 (215, 225, 235) if sel else (110, 120, 130))
            label = "  ".join(o.glyph for o in organs) if organs else why
            text(surf, label, (cx + 26, y + 2), 22 if organs else 17, col)
            if organs:
                names = " > ".join(o.name.lower() for o in organs)
                if len(names) > 40:
                    names = names[:39] + "..."
                text(surf, names, (cx + 26, y + 22), 15, (96, 106, 116))

        # Standing chains. The whole reason this screen is not a gun menu.
        sy = oy + 6 + 4 * 46 + 24
        text(surf, "RUNNING", (cx, sy - 30), 24, (150, 186, 176), bold=True)
        text(surf, "no vent. always on. it feeds you, not the water.",
             (cx, sy - 8), 16, (96, 116, 110))
        for i in range(len(body.standing)):
            ch = body.standing[i]
            ok, why = body.validate(ch, standing=True)
            organs = body.chain_organs(ch) if ok else None
            y = sy + 18 + i * 46
            sel = (i == self.assay_chain) and self.assay_standing
            col = (186, 216, 206) if ok else (104, 96, 96)
            if sel:
                pygame.draw.rect(surf, (28, 38, 36),
                                 pygame.Rect(cx - 8, y - 6, 300, 40),
                                 border_radius=4)
            text(surf, str(5 + i), (cx, y), 24,
                 (200, 226, 216) if sel else (108, 128, 122))
            label = "  ".join(o.glyph for o in organs) if organs else why
            text(surf, label, (cx + 26, y + 2), 22 if organs else 17, col)
            if organs:
                names = " > ".join(o.name.lower() for o in organs)
                if len(names) > 40:
                    names = names[:39] + "..."
                text(surf, names, (cx + 26, y + 22), 15, (92, 112, 106))

        fx = body.standing_fx
        y = sy + 18 + len(body.standing) * 46 + 10
        text(surf, "upkeep  %.2f / sec" % body.upkeep, (cx, y), 20,
             (150, 160, 170) if body.upkeep < 1.2 else (222, 158, 118))
        bits = []
        for label, key, thresh in (("burning", "heat", 0.3),
                                   ("hazed", "murk", 0.3),
                                   ("tended", "gentle", 0.3),
                                   ("quick", "jolt", 0.5),
                                   ("caustic", "caustic", 0.4)):
            if fx[key] > thresh:
                bits.append("%s %.1f" % (label, fx[key]))
        if fx["lift"] > 0.6:
            bits.append("buoyant %.1f" % fx["lift"])
        elif fx["lift"] < -0.6:
            bits.append("heavy %.1f" % -fx["lift"])
        if bits:
            text(surf, "  ".join(bits), (cx, y + 24), 19, (150, 190, 178))
        else:
            text(surf, "you are running nothing", (cx, y + 24), 19,
                 (100, 110, 116))

    def _draw_pack(self, surf):
        w = surf.get_width()
        text(surf, "CARRIED", (w - 330, 120), 24, (160, 172, 182), bold=True)
        if not self.body.pack:
            text(surf, "nothing", (w - 330, 152), 18, (86, 94, 102))
            return
        for i, org in enumerate(self.body.pack[:14]):
            rect = self.pack_rect(i)
            selected = org is self.sel_pack
            pygame.draw.rect(surf, (30, 34, 39) if selected else (20, 23, 27),
                             rect, border_radius=3)
            if selected:
                pygame.draw.rect(surf, (190, 205, 220), rect, 1,
                                 border_radius=3)
            col = ROLE_COLORS.get(org.role, (180, 180, 180))
            text(surf, org.glyph, (rect.x + 12, rect.y + 6), 22, col)
            text(surf, org.name, (rect.x + 40, rect.y + 8), 19,
                 (180, 190, 200))
            text(surf, org.role, (rect.right - 76, rect.y + 9), 16,
                 (90, 100, 110))

    def _draw_assay(self, surf):
        w, h = surf.get_size()
        x = w - 330
        y = 570
        text(surf, "THE ASSAY", (x, y - 34), 24, (160, 172, 182), bold=True)
        if self.assay is None:
            text(surf, "space — run chain %d" % (self.assay_chain + 1),
                 (x, y), 18, (86, 94, 102))
            return
        stages, eff, ctx = self.assay
        bw = 300
        yy = y
        for (name, ch) in stages[-6:]:
            text(surf, name, (x, yy), 17, (140, 150, 160))
            m = max(0.001, ch.magnitude)
            xx = x
            for i in range(N_HUMOURS):
                seg = int(bw * abs(ch[i]) / m)
                if seg > 0:
                    pygame.draw.rect(surf, COLORS[i],
                                     pygame.Rect(xx, yy + 16, seg, 7))
                    xx += seg
            text(surf, "%.1f" % ch.magnitude, (x + bw + 6, yy + 8), 15,
                 (110, 120, 130))
            yy += 30

    def _draw_selected(self, surf):
        w, h = surf.get_size()
        panel_x = 60
        panel_y = self.grid_origin[1] + GRID_H * (CELL + PAD) + 34
        org = None
        if self.sel_cell is not None:
            org = self.body.organ_at(self.sel_cell)
        elif self.sel_pack is not None:
            org = self.sel_pack

        if org is not None:
            text(surf, org.name, (panel_x, panel_y), 28, (215, 225, 235),
                 bold=True)
            text(surf, org.role, (panel_x + 260, panel_y + 6), 19,
                 ROLE_COLORS.get(org.role, (150, 150, 150)))
            _wrapped(surf, org.type.blurb, (panel_x, panel_y + 32), 640, 19,
                     (140, 150, 160))
            conf = self.game.codex.organ_confidence(org.key)
            line = organ_line(org.key, conf)
            if line:
                _wrapped(surf, "— " + line, (panel_x, panel_y + 88), 640, 19,
                         (170, 195, 185))
            elif conf == 0:
                text(surf, "— you have not used it.", (panel_x, panel_y + 88),
                     19, (96, 104, 112))
            return

        if self.assay is not None:
            stages, eff, ctx = self.assay
            text(surf, "what it would do", (panel_x, panel_y), 24,
                 (190, 200, 210), bold=True)
            _wrapped(surf, eff.describe(), (panel_x, panel_y + 30), 660, 21,
                     (200, 200, 185))
            bl, amt = blend_of(eff.charge)
            if bl:
                from ..humours import BLEND_NOTES
                _wrapped(surf, "%s — %s" % (bl, BLEND_NOTES.get(bl, "")),
                         (panel_x, panel_y + 62), 660, 19, (160, 180, 190))
            bits = []
            if ctx.count > 1:
                bits.append("%d at once" % ctx.count)
            if ctx.recursions:
                bits.append("runs %d times" % (1 + ctx.recursions))
            if ctx.quiet < 0.9:
                bits.append("quieted")
            elif ctx.quiet > 1.2:
                bits.append("noisy")
            if ctx.viability_cost > 0:
                bits.append("costs you %.1f" % ctx.viability_cost)
            if bits:
                text(surf, " · ".join(bits), (panel_x, panel_y + 96), 19,
                     (150, 165, 175))


def _wrapped(surf, s, pos, width, size, color):
    f = font(size)
    words = str(s).split()
    line, y = "", pos[1]
    for word in words:
        trial = (line + " " + word).strip()
        if f.size(trial)[0] > width and line:
            text(surf, line, (pos[0], y), size, color)
            y += size + 2
            line = word
        else:
            line = trial
    if line:
        text(surf, line, (pos[0], y), size, color)
    return y + size
