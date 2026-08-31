"""The Foundry: where bells are cast.

The first version of this screen asked you to draw a circle freehand with a
mouse and then told you, accurately, that you had failed. That is not an
authoring tool, it is a dexterity test standing between the player and the
system - and the system is the point.

So the drawing is now made of **shapes**, and the shapes **snap to the note
ladder**:

    RING   press at the centre, drag out. The radius sticks to the notes,
           which are already drawn on the canvas, so "cast a TENOR" is one
           gesture that cannot miss.
    ARC    press at the centre, drag out, then sweep the mouse round. The
           arc follows your hand, and the direction you sweep *is* the
           winding - keep going past a full turn and it closes into a bell.
           Chirality taught by the gesture that produces it.
    LINE   a horn. Snaps to 15 degrees and to the ends of existing strokes.
    FREE   freehand, still here, with assisted closure.

And nothing is final. Hovering a stroke highlights it; the wheel **retunes**
a ring in place while the tuner needle moves under your hand, which is the
nudge-look-nudge loop the whole design wants and which was previously
impossible - you could only delete and redraw.

The other half is feedback. Before, a bell was a static line drawing and a
column of figures. Now the wave the simulation is actually running is drawn
*in the metal*: strike it and the pulse races round the ring, meets itself,
and stands. That is not an illustration of resonance. It is the buffer.
"""

import math

import pygame

from sigilwave.ink import Stroke

from . import audio, notes, render, shapes
from .bell import Bell
from .metals import ALL_METALS
from .notes import N_NOTES, NOTE_NAMES, NOTE_RADIUS, NOTE_SHORT
from .starters import CANVAS_HALF, blank

CLOSE_SNAP = 30.0
MIN_SPACING = 4.0
SNAP_PX = 9.0
PICK_PX = 14.0

TOOLS = [
    ("RING", "press at the centre, drag out. Snaps to the notes."),
    ("ARC", "drag out, then sweep. Sweep direction is the winding."),
    ("LINE", "a horn - biases the ring toward where it points."),
    ("FREE", "freehand. Ends near where it started, it closes."),
]

PANEL = (16, 19, 26)
EDGE = (44, 51, 65)
INK = (206, 218, 234)
DIM = (110, 122, 144)
GOOD = (150, 245, 170)
WARN = (255, 206, 120)


class Foundry:
    """Drawing, tuning, and testing. No stakes, unlimited undo."""

    def __init__(self, session, fonts):
        self.session = session
        self.font, self.small, self.big = fonts
        self.slot = 0
        self.tool = 0
        self.metal = ALL_METALS[0]
        self.clockwise = True
        self.notice = ""
        self.notice_t = 0.0
        self.time = 0.0
        self.done = False
        self.glow = render.Glow((16, 16))
        self.undo_stack = []

        self.pending = None        # in-progress shape
        self.free = None           # in-progress freehand stroke
        self.hover = -1            # index of the highlighted stroke
        self.drag_move = None
        self.snap_flash = 0.0
        self.mouse = pygame.Vector2(0, 0)

    # ------------------------------------------------------------ the bell

    @property
    def bell(self) -> Bell:
        while len(self.session.bells) < self.session.pegs:
            self.session.bells.append(blank())
        return self.session.bells[self.slot]

    def budget_left(self) -> float:
        return self.session.budget - self.bell.metal_cost

    def say(self, text, seconds=3.2):
        self.notice, self.notice_t = text, seconds

    def push_undo(self):
        self.undo_stack.append(self.bell.to_dict())
        del self.undo_stack[:-40]

    def rebuild(self, strokes):
        b = self.bell
        b.strokes = strokes
        b.recompile()

    # ---------------------------------------------------------- canvas maths

    def canvas_rect(self, surf):
        """The canvas has to leave room for everything under it.

        Sized off `h - 330` rather than `h - 200` because the tuner strip,
        its note labels and the notice line all live below the canvas, and at
        the larger size they ran off the bottom of an 800px window - the
        single most important readout on the screen was the part that got
        clipped.
        """
        w, h = surf.get_size()
        side = max(320, min(560, min(w - 470, h - 330)))
        return pygame.Rect(52, (h - side) // 2 - 46, side, side)

    def _k(self, rect):
        return rect.width / (CANVAS_HALF * 2)

    def to_canvas(self, pos, rect):
        k = self._k(rect)
        return pygame.Vector2((pos[0] - rect.centerx) / k, (pos[1] - rect.centery) / k)

    def to_screen(self, p, rect):
        k = self._k(rect)
        return pygame.Vector2(rect.centerx + p.x * k, rect.centery + p.y * k)

    # ------------------------------------------------------------- picking

    def pick(self, q):
        """Which stroke is under the cursor, if any."""
        best, bi = PICK_PX, -1
        for i, st in enumerate(self.bell.strokes):
            d = shapes.stroke_distance(st.points, q)
            if d < best:
                best, bi = d, i
        return bi

    def hovered_ring(self):
        """(index, centre, radius) if the highlighted stroke is a ring."""
        if not (0 <= self.hover < len(self.bell.strokes)):
            return None
        fit = shapes.circle_fit(self.bell.strokes[self.hover].points)
        if fit is None:
            return None
        return self.hover, fit[0], fit[1]

    # ---------------------------------------------------------------- input

    def event(self, e, surf):
        rect = self.canvas_rect(surf)
        mods = pygame.key.get_mods()

        if e.type == pygame.MOUSEMOTION:
            self.mouse = self.to_canvas(e.pos, rect)
            if self.drag_move is not None:
                self._move_to(self.mouse)
            elif self.pending is not None:
                self._drag(self.mouse)
            elif self.free is not None:
                self._free_extend(self.mouse)
            elif rect.collidepoint(e.pos):
                self.hover = self.pick(self.mouse)

        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1 and rect.collidepoint(e.pos):
                q = self.to_canvas(e.pos, rect)
                if (mods & pygame.KMOD_SHIFT) and self.hover >= 0:
                    self.push_undo()
                    self.drag_move = (self.hover, q,
                                      [pygame.Vector2(p) for p
                                       in self.bell.strokes[self.hover].points])
                else:
                    self._begin(q)
            elif e.button == 3:
                self.undo()
            elif e.button == 2 and self.hover >= 0:
                self._delete()

        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.drag_move is not None:
                self.drag_move = None
                self.bell.recompile()
            else:
                self._commit()

        elif e.type == pygame.MOUSEWHEEL:
            self._wheel(e.y)

        elif e.type == pygame.KEYDOWN:
            self._key(e)

    def _key(self, e):
        k = e.key
        if pygame.K_1 <= k <= pygame.K_4:
            self.tool = k - pygame.K_1
            self.say(f"{TOOLS[self.tool][0]} - {TOOLS[self.tool][1]}", 4.0)
        elif k in (pygame.K_q, pygame.K_e):
            pool = self.session.unlocked_metals()
            i = (pool.index(self.metal) + (1 if k == pygame.K_e else -1)) % len(pool)
            self.metal = pool[i]
            self.say(f"{self.metal.name} - {self.metal.blurb}", 4.5)
            audio.ui(k == pygame.K_e)
        elif k == pygame.K_r:
            self.clockwise = not self.clockwise
            self.say(f"new rings wind {'clockwise - push' if self.clockwise else 'anticlockwise - pull'}")
            audio.ui(self.clockwise)
        elif k == pygame.K_f:
            self._flip()
        elif k in (pygame.K_x, pygame.K_DELETE, pygame.K_BACKSPACE):
            self._delete()
        elif k == pygame.K_z:
            self.undo()
        elif k == pygame.K_c:
            self.push_undo()
            self.rebuild([])
            audio.ui(False)
        elif k == pygame.K_TAB:
            self.slot = (self.slot + 1) % max(1, self.session.pegs)
            self.undo_stack.clear()
            self.hover = -1
            audio.ui(True)
        elif k == pygame.K_g:
            self.test()
        elif k in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.done = True

    # ------------------------------------------------------------- drawing

    def _begin(self, q):
        name = TOOLS[self.tool][0]
        if name == "FREE":
            self.free = Stroke(points=[q], ink_type=self.metal)
            return
        self.pending = {"tool": name, "a": pygame.Vector2(q), "b": pygame.Vector2(q),
                        "r": 0.0, "snap": None, "sweep": 0.0, "last": None}

    def _drag(self, q):
        p = self.pending
        p["b"] = pygame.Vector2(q)
        if p["tool"] == "LINE":
            return
        d = q - p["a"]
        r = d.length()
        snapped, idx = shapes.nearest_note_radius(r, SNAP_PX)
        if idx is not None and idx != p["snap"]:
            self.snap_flash = 1.0
            audio.tick(True)
        p["r"], p["snap"] = (snapped if idx is not None else r), idx
        if p["tool"] == "ARC" and r > 12.0:
            ang = math.degrees(math.atan2(d.y, d.x))
            if p["last"] is None:
                p["last"] = ang
                p["start"] = ang
            else:
                step = (ang - p["last"] + 540.0) % 360.0 - 180.0
                p["sweep"] += step
                p["last"] = ang

    def _free_extend(self, q):
        q.x = max(-CANVAS_HALF, min(CANVAS_HALF, q.x))
        q.y = max(-CANVAS_HALF, min(CANVAS_HALF, q.y))
        self.free.add_point(q, MIN_SPACING)

    def _preview_points(self):
        """The points the pending gesture would produce, or None."""
        p = self.pending
        if p is None:
            return None
        if p["tool"] == "LINE":
            a, b = p["a"], self._line_end(p["b"])
            if (b - a).length() < 14.0:
                return None
            return shapes.line(a, b)
        if p["r"] < 10.0:
            return None
        if p["tool"] == "RING":
            return shapes.ring(p["a"], p["r"], self.clockwise)
        sweep = p.get("sweep", 0.0)
        if abs(sweep) < 8.0:
            return None
        if abs(sweep) >= 355.0:
            return shapes.ring(p["a"], p["r"], sweep > 0)
        return shapes.arc(p["a"], p["r"], p.get("start", 0.0), sweep)

    def _line_end(self, b):
        """Snap a horn to 15 degrees, and to the ends of existing strokes -
        because a horn that does not quite touch the ring is a horn that does
        nothing, and finding that out costs a trip downstairs."""
        a = self.pending["a"]
        best = None
        for st in self.bell.strokes:
            for cand in (st.points[0], st.points[-1]):
                if (cand - b).length() < 16.0:
                    best = cand
        if best is not None:
            return pygame.Vector2(best)
        d = b - a
        if d.length() < 1e-6:
            return b
        ang = round(math.degrees(math.atan2(d.y, d.x)) / 15.0) * 15.0
        return a + pygame.Vector2(1, 0).rotate(ang) * d.length()

    def _commit(self):
        if self.free is not None:
            stroke, self.free = self.free, None
            if len(stroke.points) < 3:
                return
            if (stroke.points[-1] - stroke.points[0]).length() <= CLOSE_SNAP:
                stroke.points.append(pygame.Vector2(stroke.points[0]))
            self._place(stroke)
            return
        pts = self._preview_points()
        self.pending = None
        if pts:
            self._place(Stroke(points=pts, ink_type=self.metal))

    def _place(self, stroke):
        cost = stroke.length() * self.metal.cost_per_px
        if cost > self.budget_left():
            self.say("not enough metal for that", 2.4)
            audio.ui(False)
            return
        self.push_undo()
        b = self.bell
        b.strokes.append(stroke)
        b.recompile()
        audio.ui(True)
        self._report()

    # ------------------------------------------------------------- editing

    def _wheel(self, dy):
        """Retune the highlighted ring in place.

        The most important interaction on the screen: the needle moves under
        your hand, so the relationship between size and pitch is something
        you feel rather than something you are told.
        """
        if self.pending is not None:
            self.pending["r"] = max(10.0, self.pending["r"] + dy * 3.0)
            return
        ring = self.hovered_ring()
        if ring is None:
            return
        i, c, r = ring
        new = max(8.0, r + dy * 3.0)
        snapped, idx = shapes.nearest_note_radius(new, SNAP_PX)
        if idx is not None:
            new = snapped
            if self.snap_flash <= 0.4:
                self.snap_flash = 1.0
                audio.tick(True)
        st = self.bell.strokes[i]
        cw = shapes.winding(st.points) > 0
        self.push_undo()
        st.points = shapes.ring(c, new, cw)
        self.bell.recompile()
        self._report(quiet=True)

    def _move_to(self, q):
        i, grab, original = self.drag_move
        off = q - grab
        self.bell.strokes[i].points = [p + off for p in original]

    def _flip(self):
        if not (0 <= self.hover < len(self.bell.strokes)):
            return
        self.push_undo()
        st = self.bell.strokes[self.hover]
        st.points = list(reversed(st.points))
        self.bell.recompile()
        audio.ui(True)
        self.say("flipped - " + ("push" if self.bell.push > 0 else "pull"))

    def _delete(self):
        if not (0 <= self.hover < len(self.bell.strokes)):
            return
        self.push_undo()
        self.bell.strokes.pop(self.hover)
        self.bell.recompile()
        self.hover = -1
        audio.ui(False)

    def undo(self):
        if not self.undo_stack:
            return
        self.session.bells[self.slot] = Bell.from_dict(self.undo_stack.pop())
        self.hover = -1
        audio.ui(False)

    def _report(self, quiet=False):
        b = self.bell
        if not b.has_loop:
            if not quiet:
                self.say("no closed ring - nothing to sound", 3.0)
            return
        off = notes.cents_off(b.note)
        name = notes.note_name(b.note)
        self.say(f"{name}, in tune" if abs(off) < 60
                 else f"{name}, {abs(off)} cents {'sharp' if off > 0 else 'flat'}",
                 2.0 if quiet else 3.2)

    def test(self):
        b = self.bell
        if b.is_empty:
            return
        b.strike()
        audio.toll(max(0.0, b.note), 0.8)

    # --------------------------------------------------------------- update

    def update(self, dt, holding_space=False):
        self.time += dt
        self.notice_t = max(0.0, self.notice_t - dt)
        self.snap_flash = max(0.0, self.snap_flash - dt * 3.0)
        self.bell.set_swell(holding_space)
        for b in self.session.bells:
            if not b.is_empty:
                b.advance(dt)

    # ----------------------------------------------------------------- draw

    def draw(self, surf):
        surf.fill(render.BG)
        self.glow.resize(surf.get_size())
        self.glow.clear()
        rect = self.canvas_rect(surf)
        self._draw_tools(surf, rect)
        self._draw_canvas(surf, rect)
        self._draw_tuner(surf, rect)
        self._draw_panel(surf, rect)
        self.glow.blit_onto(surf)
        self._draw_footer(surf)

    # ..........................................................  the toolbar

    def _draw_tools(self, surf, rect):
        y = rect.top - 34
        x = rect.left
        for i, (name, _) in enumerate(TOOLS):
            w = 78
            box = pygame.Rect(x, y, w - 6, 26)
            on = i == self.tool
            pygame.draw.rect(surf, (30, 36, 48) if on else (18, 21, 28), box)
            pygame.draw.rect(surf, (120, 140, 170) if on else EDGE, box, 1)
            lab = self.small.render(f"{i + 1} {name}", True, INK if on else DIM)
            surf.blit(lab, (box.centerx - lab.get_width() // 2, box.centery - 7))
            x += w
        wind = "PUSH" if self.clockwise else "PULL"
        col = (150, 210, 255) if self.clockwise else (255, 170, 210)
        lab = self.small.render(f"R  wind: {wind}", True, col)
        surf.blit(lab, (x + 12, y + 6))

    # ..........................................................  the canvas

    def _draw_canvas(self, surf, rect):
        pygame.draw.rect(surf, (12, 14, 19), rect)
        pygame.draw.rect(surf, EDGE, rect, 1)
        k = self._k(rect)
        targets = set(self.session.target_notes())

        # The note ladder, at actual size, with the room ahead's notes lit.
        #
        # Labelled down a column with leader lines rather than on the circles
        # themselves: the top two rings are 13 and 6px across, so anything
        # placed on them lands on top of everything else and the small end of
        # the ladder - the end that matters most, because it is where the
        # gates are - became unreadable.
        cx, cy = rect.center
        for i in range(N_NOTES):
            r = NOTE_RADIUS[i] * k
            if r > rect.width:
                continue
            want = i in targets
            base = notes.NOTE_COLORS[i]
            flash = self.snap_flash if (self.pending and self.pending.get("snap") == i) else 0.0
            col = render.scale(base, (0.6 if want else 0.28) + 0.4 * flash)
            if r >= 2:
                pygame.draw.circle(surf, col, (cx, cy), int(r), 2 if want else 1)

            ly = rect.top + 26 + i * 22
            lx = rect.right - 74
            lab = self.small.render(NOTE_SHORT[i], True,
                                    render.scale(base, 1.0 if want else 0.55))
            surf.blit(lab, (lx + 16, ly - 7))
            pygame.draw.line(surf, render.scale(base, 0.35 if not want else 0.6),
                             (cx + int(r * 0.7), cy - int(r * 0.7)), (lx + 10, ly), 1)
            pygame.draw.circle(surf, col, (lx + 6, ly), 3)

        self._draw_strokes(surf, rect)
        self._draw_wave(surf, rect)
        self._draw_preview(surf, rect)

    def _draw_strokes(self, surf, rect):
        b = self.bell
        charge = min(1.0, b.charge * 1.5)
        for i, st in enumerate(b.strokes):
            pts = [self.to_screen(p, rect) for p in st.points]
            if len(pts) < 2:
                continue
            xy = [(p.x, p.y) for p in pts]
            hot = i == self.hover
            base = st.ink_type.color
            col = render.lerp(base, b.color, 0.35 + 0.5 * charge)
            if hot:
                col = render.lerp(col, (255, 255, 255), 0.45)
                pygame.draw.lines(self.glow.surf,
                                  (*render.scale((150, 200, 255), 0.7), 255),
                                  False, xy, 7)
            pygame.draw.lines(surf, col, False, xy, 4 if hot else 3)

        ring = self.hovered_ring()
        if ring is not None:
            _, c, r = ring
            sc = self.to_screen(c, rect)
            rr = int(r * self._k(rect))
            # A handle, so it is obvious this thing can be grabbed and turned.
            pygame.draw.circle(surf, (120, 150, 190), (int(sc.x), int(sc.y)), 3)
            pygame.draw.circle(self.glow.surf, (*render.scale((160, 200, 255), 0.5), 255),
                               (int(sc.x + rr), int(sc.y)), 5, 2)

    def _draw_wave(self, surf, rect):
        """The simulation's own buffers, drawn along the metal.

        Strike the bell and watch the pulse run round the ring and stand.
        Nothing else in the Foundry tells you what resonance *is*.
        """
        b = self.bell
        if b.is_empty:
            return
        k = self._k(rect)
        col = b.color
        for edge in b.wave_samples():
            for p, amp in edge:
                a = min(1.0, abs(amp) * 2.6)
                if a < 0.06:
                    continue
                q = self.to_screen(p, rect)
                r = int(2 + 7 * a)
                c = col if amp >= 0 else render.lerp(col, (255, 245, 230), 0.55)
                pygame.draw.circle(self.glow.surf, (*render.scale(c, a), 255),
                                   (int(q.x), int(q.y)), r)

    def _draw_preview(self, surf, rect):
        """The ghost of what you are about to make, labelled with what it
        will be. Answering "what note is this?" during the gesture rather
        than after it is the entire difference between shaping and guessing.
        """
        pts = None
        if self.free is not None and len(self.free.points) > 1:
            pts = self.free.points
        else:
            pts = self._preview_points()
        if not pts:
            return
        xy = [(q.x, q.y) for q in (self.to_screen(p, rect) for p in pts)]
        pygame.draw.lines(surf, self.metal.color, False, xy, 2)
        pygame.draw.lines(self.glow.surf, (*render.scale(self.metal.color, 0.45), 255),
                          False, xy, 4)

        p = self.pending
        if p is not None and p["tool"] in ("RING", "ARC") and p["r"] > 10.0:
            n = notes.note_from_f0(4.0 / (2 * math.pi * p["r"]))
            off = notes.cents_off(n)
            snapped = p.get("snap") is not None
            txt = notes.note_name(n) + ("  in tune" if snapped or abs(off) < 40
                                        else f"  {off:+d}c")
            col = GOOD if (snapped or abs(off) < 40) else WARN
            lab = self.font.render(txt, True, col)
            # On the rim under the cursor rather than at the centre, where it
            # sat on top of the ladder's own labels and both became unreadable.
            c = self.to_screen(p["a"], rect)
            edge = self.to_screen(p["a"] + pygame.Vector2(0, -p["r"]), rect)
            lx = min(rect.right - lab.get_width() - 6, max(rect.left + 6,
                                                           edge.x - lab.get_width() // 2))
            surf.blit(lab, (lx, max(rect.top + 4, edge.y - 26)))
            if p["tool"] == "ARC":
                sw = self.small.render(f"{abs(int(p.get('sweep', 0)))} deg", True, DIM)
                surf.blit(sw, (c.x + 10, c.y + 10))

        if self.free is not None and len(self.free.points) > 2:
            start = self.to_screen(self.free.points[0], rect)
            close = (self.free.points[-1] - self.free.points[0]).length() <= CLOSE_SNAP
            pygame.draw.circle(self.glow.surf if close else surf,
                               (*render.scale(render.HOT, 0.9), 255) if close else DIM,
                               (int(start.x), int(start.y)), 12 if close else 7, 2)

    # ...........................................................  the tuner

    def _draw_tuner(self, surf, rect):
        b = self.bell
        w, x0 = rect.width, rect.left
        y = rect.bottom + 30
        pygame.draw.rect(surf, PANEL, (x0, y, w, 40))
        pygame.draw.rect(surf, EDGE, (x0, y, w, 40), 1)

        def at(note):
            return x0 + w * (note / (N_NOTES - 1.0))

        targets = set(self.session.target_notes())
        for i in range(N_NOTES):
            x = at(i)
            want = i in targets
            col = notes.NOTE_COLORS[i]
            h = 18 if want else 10
            pygame.draw.line(surf, col if want else render.scale(col, 0.4),
                             (x, y + 20 - h // 2), (x, y + 20 + h // 2), 3 if want else 1)
            lab = self.small.render(NOTE_SHORT[i], True,
                                    col if want else render.scale(col, 0.45))
            surf.blit(lab, (x - lab.get_width() // 2, y + 42))
            if want:
                pygame.draw.circle(self.glow.surf, (*render.scale(col, 0.9), 255),
                                   (int(x), y - 10), 5, 2)

        note = None
        if self.pending is not None and self.pending.get("r", 0) > 10.0:
            note = notes.note_from_f0(4.0 / (2 * math.pi * self.pending["r"]))
        elif b.has_loop:
            note = b.note

        if note is None:
            surf.blit(self.font.render("no closed ring", True, (210, 130, 120)),
                      (x0, y - 30))
            return
        nx = at(max(0.0, min(N_NOTES - 1.0, note)))
        pygame.draw.polygon(surf, render.HOT,
                            [(nx, y + 3), (nx - 7, y - 9), (nx + 7, y - 9)])
        pygame.draw.line(surf, render.HOT, (nx, y + 2), (nx, y + 38), 2)
        off = notes.cents_off(note)
        if abs(off) < 60:
            txt, col = f"{notes.note_name(note)} - in tune", GOOD
        else:
            txt, col = (f"{notes.note_name(note)}  {abs(off)} cents "
                        f"{'sharp' if off > 0 else 'flat'}"), WARN
        surf.blit(self.font.render(txt, True, col), (x0, y - 30))

    # ...........................................................  the panel

    def _draw_panel(self, surf, rect):
        b = self.bell
        x = rect.right + 40
        w = surf.get_width() - x - 32
        y = rect.top - 34

        surf.blit(self.big.render("THE FOUNDRY", True, INK), (x, y))
        y += 44

        # The target. The thing the old screen did not have.
        surf.blit(self.font.render("THE ROOM AHEAD", True, DIM), (x, y))
        y += 22
        spec = self.session.spec
        surf.blit(self.small.render(spec.get("name", ""), True, INK), (x, y))
        y += 20
        for n in self.session.target_notes():
            if n < 0:
                line, col = "dead metal - throw it into something", (152, 158, 170)
                pygame.draw.circle(surf, col, (x + 8, y + 7), 6, 1)
            else:
                line = f"{NOTE_NAMES[n]} - ring {int(notes.LOOP_PX[n])}px around"
                col = notes.NOTE_COLORS[n]
                pygame.draw.circle(surf, col, (x + 8, y + 7), 6)
            surf.blit(self.small.render(line, True, col), (x + 24, y))
            y += 20
        y += 14

        # Bells on their pegs.
        surf.blit(self.font.render("BELLS   [TAB]", True, DIM), (x, y))
        y += 22
        for i in range(self.session.pegs):
            bl = self.session.bells[i]
            box = pygame.Rect(x, y, w, 38)
            if i == self.slot:
                pygame.draw.rect(surf, (25, 30, 41), box)
                pygame.draw.rect(surf, (92, 106, 130), box, 1)
            sub, col = "empty - nothing drawn", DIM
            if bl.has_loop:
                sub = (f"{notes.note_name(bl.note)}   {int(bl.reach)}px   "
                       f"{'push' if bl.push > 0 else 'pull'}")
                col = bl.color
            surf.blit(self.small.render(f"{i + 1}. {bl.name}", True, INK), (x + 8, y + 4))
            surf.blit(self.small.render(sub, True, col), (x + 8, y + 20))
            y += 44
        y += 8

        # Metal.
        surf.blit(self.font.render("METAL   [Q/E]", True, DIM), (x, y))
        y += 22
        for m in self.session.unlocked_metals():
            on = m is self.metal
            pygame.draw.rect(surf, m.color if on else render.scale(m.color, 0.4),
                             (x, y + 3, 10, 10))
            surf.blit(self.small.render(m.name, True, INK if on else DIM), (x + 18, y))
            y += 19
        y += 4
        for line in _wrap(self.metal.blurb, 46):
            surf.blit(self.small.render(line, True, DIM), (x, y))
            y += 15
        y += 10

        self._draw_readout(surf, x, y, w, b)

    def _draw_readout(self, surf, x, y, w, b):
        surf.blit(self.font.render("MEASURED", True, DIM), (x, y))
        y += 22

        left = self.budget_left()
        frac = max(0.0, min(1.0, left / max(1.0, self.session.budget)))
        pygame.draw.rect(surf, (36, 42, 54), (x, y + 3, w, 8))
        pygame.draw.rect(surf, (150, 200, 255) if frac > 0.12 else (240, 130, 110),
                         (x, y + 3, int(w * frac), 8))
        surf.blit(self.small.render(f"metal {int(left)} / {int(self.session.budget)}",
                                    True, DIM), (x, y + 14))
        y += 38

        # What it is putting out, right now. A live meter beats a number.
        spec = b.spectrum()
        total = sum(spec) or 1.0
        bw = w // N_NOTES
        surf.blit(self.small.render("output", True, DIM), (x, y))
        y += 16
        for i in range(N_NOTES):
            h = int(34 * min(1.0, spec[i] / total * 2.2)) if total > 1e-9 else 0
            pygame.draw.rect(surf, (28, 33, 43), (x + i * bw, y, bw - 4, 34))
            if h > 0:
                pygame.draw.rect(surf, notes.NOTE_COLORS[i],
                                 (x + i * bw, y + 34 - h, bw - 4, h))
        y += 42

        rows = []
        if b.has_loop:
            rows.append(("reach", f"{int(b.reach)}px", b.color))
            rows.append(("tolls every", f"{b.period:0.2f}s", INK))
            rows.append(("winding", "push" if b.push > 0 else "pull", INK))
        rows.append(("char", f"{int(min(1.0, b.char) * 100)}%",
                     (240, 140, 110) if b.char > 0.4 else DIM))
        for label, value, col in rows:
            surf.blit(self.small.render(label, True, DIM), (x, y))
            surf.blit(self.small.render(value, True, col), (x + 108, y))
            y += 18

        # Reach, at world scale, next to a player-sized dot. The tuner says
        # what note; this says what that means where it matters.
        if b.has_loop:
            y += 12
            scale = min(1.0, (w - 20) / (b.reach * 2.0))
            cx, cy = x + w // 2, y + int(b.reach * scale) + 6
            pygame.draw.circle(surf, render.scale(b.color, 0.5), (cx, cy),
                               int(b.reach * scale), 1)
            pygame.draw.circle(surf, (235, 242, 252), (cx, cy),
                               max(2, int(15 * scale)))

    def _draw_footer(self, surf):
        h = surf.get_height()
        if self.notice_t > 0.0:
            a = min(1.0, self.notice_t)
            surf.blit(self.small.render(self.notice, True,
                                        render.lerp(render.BG, (255, 224, 160), a)),
                      (18, h - 48))
        keys = ("hover a stroke: WHEEL retune   F flip   X delete   SHIFT+drag move"
                "      Z/RMB undo   C clear   G strike   SPACE swell   ENTER descend")
        surf.blit(self.small.render(keys, True, DIM), (18, h - 26))


def _wrap(text, width):
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out
