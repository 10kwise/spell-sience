"""The Foundry: where bells are cast, and the one screen that had to change
most.

The old Forge was an oscilloscope. It reported, accurately and at length,
that your drawing had "1 loop, largest 262px -> f0 0.0152 (clockwise, beat
0.66s), output centred on band 1.3, efficiency 40%". Every word of that is
true and none of it is a thing a person can act on, because it answers a
question nobody asked. There was no goal on the screen. You drew something,
and the machine told you what you had drawn.

Two changes, and they are the whole difference between homework and craft:

**1. There is a target.** The peal of the room ahead is on the screen - the
actual notes the actual things you are about to fight are tuned to. Drawing
is no longer open-ended; it is closing a gap. That single addition is also
the real fix for the old build's brute-force problem, because "you can draw
anything and it works" was never a balance failure. It was the absence of
anything to aim at.

**2. The readout is a tuner.** Not prose, not an efficiency percentage: a
needle, a note name, and how many cents flat or sharp you are. Everyone has
seen a guitar tuner. Nobody has to be taught to read one, and the act of
using one - nudge, look, nudge again - is exactly the hill-climb that
teaches the underlying rule, which is that the circumference *is* the pitch.

The Anvil is this same screen on a twelve-second clock, between waves. That
is the other half of the fix: authoring used to sit minutes away from its own
consequence, and twelve seconds after failing to reach something is when a
player actually wants to change their tool.
"""

import math

import pygame

from sigilwave.ink import Stroke

from . import audio, notes, render
from .bell import Bell
from .metals import ALL_METALS, BRONZE
from .notes import N_NOTES, NOTE_NAMES, NOTE_RADIUS, NOTE_SHORT
from .starters import CANVAS_HALF, blank

# Closing a loop by hand is the one act the entire game depends on, so it is
# assisted rather than left to luck: come back within this of where you
# started and the stroke closes exactly. The parser's own snap is 8px, which
# is a fine tolerance for a machine and a cruel one for a mouse.
CLOSE_SNAP = 30.0
MIN_SPACING = 4.0

PANEL = (16, 19, 26)
EDGE = (42, 49, 62)
INK = (200, 212, 228)
DIM = (108, 120, 142)


class Foundry:
    """Drawing, tuning, and testing. No stakes, unlimited undo."""

    def __init__(self, run, fonts, anvil_seconds=None):
        self.run = run
        self.font, self.small, self.big = fonts
        self.slot = 0
        self.metal = ALL_METALS[0]
        self.drawing = None
        self.notice = ""
        self.notice_t = 0.0
        self.time = 0.0
        self.test_t = 0.0
        self.anvil = anvil_seconds
        self.left = anvil_seconds or 0.0
        self.done = False
        self.glow = render.Glow((16, 16))
        self.undo_stack = []

    # ------------------------------------------------------------ the bell

    @property
    def bell(self) -> Bell:
        while len(self.run.bells) < self.run.pegs:
            self.run.bells.append(blank())
        return self.run.bells[self.slot]

    def replace(self, bell):
        self.run.bells[self.slot] = bell

    def spent(self) -> float:
        return self.bell.metal_cost

    def budget_left(self) -> float:
        return self.run.budget - self.spent()

    def say(self, text, seconds=3.0):
        self.notice = text
        self.notice_t = seconds

    # ------------------------------------------------------------ drawing

    def canvas_rect(self, surf):
        w, h = surf.get_size()
        side = min(w - 430, h - 150)
        side = max(320, min(560, side))
        return pygame.Rect(56, (h - side) // 2, side, side)

    def to_canvas(self, screen_pos, rect):
        s = rect.width / (CANVAS_HALF * 2)
        return pygame.Vector2((screen_pos[0] - rect.centerx) / s,
                              (screen_pos[1] - rect.centery) / s)

    def to_screen(self, p, rect):
        s = rect.width / (CANVAS_HALF * 2)
        return pygame.Vector2(rect.centerx + p.x * s, rect.centery + p.y * s)

    def begin(self, pos, rect):
        if not rect.collidepoint(pos):
            return
        self.drawing = Stroke(points=[self.to_canvas(pos, rect)], ink_type=self.metal)

    def extend(self, pos, rect):
        if self.drawing is None:
            return
        p = self.to_canvas(pos, rect)
        p.x = max(-CANVAS_HALF, min(CANVAS_HALF, p.x))
        p.y = max(-CANVAS_HALF, min(CANVAS_HALF, p.y))
        self.drawing.add_point(p, MIN_SPACING)

    def finish(self):
        stroke = self.drawing
        self.drawing = None
        if stroke is None or len(stroke.points) < 3:
            return
        # Assisted closure. A ring that nearly closes is a ring the player
        # meant to close, and a ring that does not close is not a bell.
        if (stroke.points[-1] - stroke.points[0]).length() <= CLOSE_SNAP:
            stroke.points.append(pygame.Vector2(stroke.points[0]))

        cost = stroke.length() * self.metal.cost_per_px
        if cost > self.budget_left():
            self.say("not enough metal for that", 2.4)
            audio.ui(False)
            return

        self.undo_stack.append(self.bell.to_dict())
        b = self.bell
        b.strokes.append(stroke)
        b.recompile()
        audio.ui(True)
        self._report()

    def undo(self):
        if not self.undo_stack:
            b = self.bell
            if b.strokes:
                b.strokes.pop()
                b.recompile()
            return
        self.replace(Bell.from_dict(self.undo_stack.pop()))
        audio.ui(False)
        self._report()

    def clear(self):
        self.undo_stack.append(self.bell.to_dict())
        b = self.bell
        b.strokes.clear()
        b.recompile()
        audio.ui(False)

    def _report(self):
        b = self.bell
        if not b.has_loop:
            self.say("no closed ring - nothing to sound", 3.0)
            return
        off = notes.cents_off(b.note)
        name = notes.note_name(b.note)
        if abs(off) < 60:
            self.say(f"cast: {name}, in tune")
        else:
            self.say(f"cast: {name}, {abs(off)} cents {'sharp' if off > 0 else 'flat'}")

    def test(self):
        b = self.bell
        if b.is_empty:
            return
        b.strike()
        self.test_t = 1.0
        audio.toll(max(0.0, b.note), 0.8)

    def swell(self, on):
        self.bell.set_swell(on)

    # --------------------------------------------------------------- input

    def event(self, e, surf):
        rect = self.canvas_rect(surf)
        if e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                self.begin(e.pos, rect)
            elif e.button == 3:
                self.undo()
        elif e.type == pygame.MOUSEMOTION and self.drawing is not None:
            self.extend(e.pos, rect)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.finish()
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_z:
                self.undo()
            elif e.key == pygame.K_c:
                self.clear()
            elif e.key == pygame.K_TAB:
                self.slot = (self.slot + 1) % max(1, self.run.pegs)
                self.undo_stack.clear()
                audio.ui(True)
            elif e.key in (pygame.K_g, pygame.K_SPACE):
                self.test()
            elif pygame.K_1 <= e.key <= pygame.K_3:
                i = e.key - pygame.K_1
                pool = self.run.unlocked_metals()
                if i < len(pool):
                    self.metal = pool[i]
                    self.say(f"{self.metal.name} - {self.metal.blurb}", 4.0)
            elif e.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.done = True
        elif e.type == pygame.KEYUP and e.key == pygame.K_SPACE:
            self.swell(False)

    def update(self, dt, holding_space=False):
        self.time += dt
        self.notice_t = max(0.0, self.notice_t - dt)
        self.test_t = max(0.0, self.test_t - dt)
        self.bell.set_swell(holding_space)
        for b in self.run.bells:
            if not b.is_empty:
                b.advance(dt)
        if self.anvil is not None:
            self.left -= dt
            if self.left <= 0.0:
                self.done = True

    # -------------------------------------------------------------- drawing

    def draw(self, surf):
        surf.fill(render.BG)
        self.glow.resize(surf.get_size())
        self.glow.clear()
        rect = self.canvas_rect(surf)
        self._draw_canvas(surf, rect)
        self._draw_tuner(surf, rect)
        self._draw_panel(surf, rect)
        self.glow.blit_onto(surf)
        self._draw_footer(surf)

    # ..........................................................  the canvas

    def _draw_canvas(self, surf, rect):
        pygame.draw.rect(surf, (13, 15, 21), rect)
        pygame.draw.rect(surf, EDGE, rect, 1)
        s = rect.width / (CANVAS_HALF * 2)

        # The note ladder, drawn *on the canvas* as the actual sizes. This is
        # the ruler that turns "I want that note" into "draw this big", and
        # it is the reason nobody has to be told what the numbers mean.
        for i in range(N_NOTES):
            r = NOTE_RADIUS[i] * s
            if r < 3 or r > rect.width:
                continue
            col = render.scale(notes.NOTE_COLORS[i], 0.30)
            pygame.draw.circle(surf, col, rect.center, int(r), 1)
            label = self.small.render(NOTE_SHORT[i], True, render.scale(notes.NOTE_COLORS[i], 0.8))
            # Fanned around the circles rather than stacked above them: the
            # top two rings are 13 and 6px, so centred labels piled on top of
            # each other and the small end of the ladder was unreadable.
            ang = math.radians(-90 + 26 * i)
            lx = rect.centerx + math.cos(ang) * r
            ly = rect.centery + math.sin(ang) * r
            surf.blit(label, (lx - label.get_width() // 2, ly - 16))

        b = self.bell
        charge = b.charge
        for stroke in b.strokes:
            pts = [self.to_screen(p, rect) for p in stroke.points]
            if len(pts) < 2:
                continue
            base = stroke.ink_type.color
            col = render.lerp(base, b.color, 0.4 + 0.5 * min(1.0, charge))
            pygame.draw.lines(surf, col, False, [(p.x, p.y) for p in pts], 3)
            if charge > 0.05:
                pygame.draw.lines(self.glow.surf,
                                  (*render.scale(b.color, 0.6 * min(1.0, charge)), 255),
                                  False, [(p.x, p.y) for p in pts], 6)

        if self.drawing is not None and len(self.drawing.points) > 1:
            pts = [self.to_screen(p, rect) for p in self.drawing.points]
            pygame.draw.lines(surf, self.metal.color, False, [(p.x, p.y) for p in pts], 2)
            start = pts[0]
            if (self.drawing.points[-1] - self.drawing.points[0]).length() <= CLOSE_SNAP:
                # Tell them, right now, that letting go here makes a bell.
                pygame.draw.circle(self.glow.surf, (*render.scale(render.HOT, 0.9), 255),
                                   (int(start.x), int(start.y)), 12, 2)
            else:
                pygame.draw.circle(surf, DIM, (int(start.x), int(start.y)), 7, 1)

    # ...........................................................  the tuner

    def _draw_tuner(self, surf, rect):
        """A needle, a note, and how far off. The entire assay."""
        b = self.bell
        w = rect.width
        x0 = rect.left
        y = rect.bottom + 26
        bar = pygame.Rect(x0, y, w, 40)
        pygame.draw.rect(surf, PANEL, bar)
        pygame.draw.rect(surf, EDGE, bar, 1)

        def at(note):
            return x0 + w * (note / (N_NOTES - 1.0))

        targets = set(self.run.target_notes())
        for i in range(N_NOTES):
            x = at(i)
            wanted = i in targets
            col = notes.NOTE_COLORS[i]
            h = 18 if wanted else 10
            pygame.draw.line(surf, col if wanted else render.scale(col, 0.4),
                             (x, y + 20 - h // 2), (x, y + 20 + h // 2), 3 if wanted else 1)
            lab = self.small.render(NOTE_SHORT[i], True,
                                    col if wanted else render.scale(col, 0.45))
            surf.blit(lab, (x - lab.get_width() // 2, y + 42))
            if wanted:
                # A little bell over every note the next room will ask for.
                pygame.draw.circle(self.glow.surf, (*render.scale(col, 0.85), 255),
                                   (int(x), y - 10), 5, 2)

        if b.has_loop:
            nx = at(max(0.0, min(N_NOTES - 1.0, b.note)))
            pygame.draw.polygon(surf, render.HOT,
                                [(nx, y + 3), (nx - 7, y - 9), (nx + 7, y - 9)])
            pygame.draw.line(surf, render.HOT, (nx, y + 2), (nx, y + 38), 2)

            off = notes.cents_off(b.note)
            name = notes.note_name(b.note)
            if abs(off) < 60:
                txt, col = f"{name} - in tune", (150, 245, 170)
            else:
                txt = f"{name}  {abs(off):+5d}c {'sharp' if off > 0 else 'flat'}".replace("+", "")
                col = (255, 206, 120)
            t = self.font.render(txt, True, col)
            surf.blit(t, (x0, y - 30))
        else:
            t = self.font.render("no closed ring", True, (200, 130, 120))
            surf.blit(t, (x0, y - 30))

    # ...........................................................  the panel

    def _draw_panel(self, surf, rect):
        b = self.bell
        x = rect.right + 40
        w = surf.get_width() - x - 34
        y = rect.top - 26

        if self.anvil is not None:
            k = max(0.0, self.left) / max(1e-6, self.anvil)
            head = self.big.render("THE ANVIL", True, (255, 214, 140))
            surf.blit(head, (x, y))
            clock = pygame.Rect(x, y + 38, int(w * k), 6)
            pygame.draw.rect(surf, (60, 66, 80), (x, y + 38, w, 6))
            pygame.draw.rect(surf, (255, 200, 120), clock)
            sub = self.small.render(f"{self.left:0.0f}s - ENTER to go down now", True, DIM)
            surf.blit(sub, (x, y + 50))
            y += 78
        else:
            head = self.big.render("THE FOUNDRY", True, INK)
            surf.blit(head, (x, y))
            y += 48

        # What the next room is tuned to. The target - the thing the old
        # build's Forge did not have.
        surf.blit(self.font.render("THE ROOM AHEAD", True, DIM), (x, y))
        y += 24
        spec = self.run.spec
        if spec:
            surf.blit(self.small.render(spec.get("name", ""), True, INK), (x, y))
            y += 20
            for n in self.run.target_notes():
                if n < 0:
                    line = "dead metal - nothing will ring it, throw it"
                    col = (150, 156, 168)
                    pygame.draw.circle(surf, col, (x + 8, y + 7), 6, 1)
                else:
                    line = f"{NOTE_NAMES[n]} - a ring {int(notes.LOOP_PX[n])}px around"
                    col = notes.NOTE_COLORS[n]
                    pygame.draw.circle(surf, col, (x + 8, y + 7), 6)
                surf.blit(self.small.render(line, True, col), (x + 24, y))
                y += 20
        y += 14

        # The bells on their pegs.
        surf.blit(self.font.render("BELLS", True, DIM), (x, y))
        y += 24
        for i in range(self.run.pegs):
            bl = self.run.bells[i] if i < len(self.run.bells) else None
            box = pygame.Rect(x, y, w, 40)
            if i == self.slot:
                pygame.draw.rect(surf, (26, 31, 42), box)
                pygame.draw.rect(surf, (86, 100, 124), box, 1)
            name = bl.name if bl else "empty"
            note_txt = "-"
            col = DIM
            if bl is not None and bl.has_loop:
                note_txt = f"{notes.note_name(bl.note)}  {bl.period:0.2f}s  {'push' if bl.push > 0 else 'pull'}"
                col = bl.color
            surf.blit(self.small.render(f"{i + 1}. {name}", True, INK), (x + 8, y + 5))
            surf.blit(self.small.render(note_txt, True, col), (x + 8, y + 21))
            y += 46
        y += 10

        # Metal.
        surf.blit(self.font.render("METAL", True, DIM), (x, y))
        y += 24
        for i, m in enumerate(self.run.unlocked_metals()):
            sel = m is self.metal
            pygame.draw.rect(surf, m.color, (x, y + 3, 10, 10))
            surf.blit(self.small.render(f"{i + 1}. {m.name}", True, INK if sel else DIM),
                      (x + 18, y))
            y += 19
        y += 6
        for line in _wrap(self.metal.blurb, 44):
            surf.blit(self.small.render(line, True, DIM), (x, y))
            y += 16
        y += 10

        # The three live facts, and nothing else.
        surf.blit(self.font.render("MEASURED", True, DIM), (x, y))
        y += 24
        left = self.budget_left()
        pygame.draw.rect(surf, (36, 42, 54), (x, y + 4, w, 8))
        frac = max(0.0, min(1.0, left / max(1.0, self.run.budget)))
        pygame.draw.rect(surf, (150, 200, 255) if frac > 0.12 else (240, 130, 110),
                         (x, y + 4, int(w * frac), 8))
        surf.blit(self.small.render(f"metal left {int(left)} / {int(self.run.budget)}",
                                    True, DIM), (x, y + 16))
        y += 42
        rows = []
        if b.has_loop:
            rows.append(("reach", f"{int(b.reach)}px", b.color))
            rows.append(("ring", f"{int(2 * math.pi * notes.NOTE_RADIUS[max(0, min(4, round(b.note)))])}px around", DIM))
            rows.append(("toll every", f"{b.period:0.2f}s", INK))
            rows.append(("winding", "push" if b.push > 0 else "pull", INK))
        rows.append(("char", f"{int(min(1.0, b.char) * 100)}%",
                     (240, 140, 110) if b.char > 0.4 else DIM))
        for label, value, col in rows:
            surf.blit(self.small.render(label, True, DIM), (x, y))
            surf.blit(self.small.render(value, True, col), (x + 110, y))
            y += 18



    def _draw_footer(self, surf):
        h = surf.get_height()
        if self.notice_t > 0.0:
            a = min(1.0, self.notice_t)
            t = self.font.render(self.notice, True,
                                 render.lerp(render.BG, (255, 224, 160), a))
            surf.blit(t, (18, h - 54))
        keys = ("LMB draw   RMB/Z undo   C clear   1-3 metal   TAB bell   "
                "G strike   SPACE swell   ESC descend")
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
