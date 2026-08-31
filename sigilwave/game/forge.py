"""The Forge: drawing, measuring, and — most importantly — testing.

Design load this screen is carrying:

* **Experimentation must be free.** Undo is one key, the canvas resets to
  where it started, and nothing spends a resource until you leave. A system
  this deep is only learnable if being wrong is cheap; if a bad idea costs a
  run, players stop having ideas.

* **Failure must be diagnosable.** The Assay states what was *measured* —
  loop size, fundamental, chirality sign, coupler gaps, efficiency. A player
  whose sigil does nothing can read why. "It didn't work" is a bug report;
  "no loop, so no resonance to tap" is a lesson.

* **The test bench is the real thing.** The dummy runs the same Pulse code,
  the same vulnerability curve and the same air decay that combat does, so
  a sigil that works here works there. A bench that diverges from the game
  teaches players something false, which is worse than teaching nothing.

* **The band ruler.** Six faint circles, one per band, at the circumference
  that rings at it. This is the single highest-value piece of UI in the
  game: it converts "I need orange" into "draw about this big", which is the
  bridge between the colour-matching layer a new player uses and the
  frequency reasoning an experienced one uses. Same overlay, both readings.
"""

import math

import pygame

from sigilwave.ink import Stroke

from .bands import (
    BAND_COLORS, BAND_FEEL, BAND_LOOP_PX, BAND_NAMES, N_BANDS,
    band_color, dominant_band, vulnerability_curve,
)
from .combat import emissions_to_pulses, resonance_quality
from .library import LIBRARY
from .starters import FOCUS_HALF
from . import viz

_KIND_COLOR = {
    "emitter": (130, 210, 240),
    "capacitor": (240, 190, 120),
    "aura": (255, 150, 110),
    "barrier": (200, 210, 230),
    "conduit": (186, 140, 255),
    "inert": (120, 128, 145),
}

CANVAS_CENTER = (430, 330)
BENCH_TOP = 592
BENCH_LEFT = 40
BENCH_SCALE = 0.62          # world px -> screen px in the test lane
PANEL_X = 880


class Dummy:
    """A stationary target with a settable resonance. Not an enemy subclass
    on purpose — it has no behaviour, and giving it one would tempt the
    bench into diverging from combat."""

    def __init__(self):
        self.band = 1.0
        self.distance = 340.0
        self.hp = 1000.0
        self.max_hp = 1000.0
        self.radius = 20.0
        self.temperature = 0.0
        self.phase = 0.0
        self.dps_window = []
        self.last_quality = 0.0
        self.hit_flash = 0.0

    @property
    def vuln(self):
        return vulnerability_curve(self.band)

    def reset(self):
        self.hp = self.max_hp
        self.temperature = 0.0
        self.phase = 0.0
        self.dps_window = []

    def take(self, pulse, dt):
        q = resonance_quality(pulse.bands, self.vuln)
        dmg = pulse.damage_against(self.vuln)
        self.hp = max(0.0, self.hp - dmg)
        self.temperature += pulse.thermal()
        self.phase = min(1.0, self.phase + pulse.phase())
        self.last_quality = q
        self.hit_flash = 1.0
        self.dps_window.append((0.0, dmg))
        return dmg

    def update(self, dt):
        self.temperature *= max(0.0, 1.0 - 0.5 * dt)
        self.phase = max(0.0, self.phase - 0.7 * dt)
        self.hit_flash = max(0.0, self.hit_flash - dt * 3)
        self.dps_window = [(t + dt, d) for t, d in self.dps_window if t + dt < 1.0]
        if self.temperature > 0.02:
            self.hp = max(0.0, self.hp - 26.0 * self.temperature * dt)

    @property
    def dps(self):
        return sum(d for _, d in self.dps_window)


class Forge:
    def __init__(self, run, font, small):
        self.run = run
        self.font = font
        self.small = small
        self.slot = 0
        self.ink_index = 0
        self.current = None
        self.history = []
        self.dummy = Dummy()
        self.pulses = []
        self.show_ruler = True
        self.message = ""
        self.message_t = 0.0
        self.time = 0.0
        self.testing_hold = False
        self.renaming = False
        self.name_buffer = ""
        self.done = False
        self.browsing = False
        self.browse_i = 0

    # ------------------------------------------------------------------ state

    @property
    def sigil(self):
        return self.run.foci[self.slot] if self.run.foci else None

    @property
    def ink(self):
        return self.run.inks[self.ink_index % len(self.run.inks)]

    def notify(self, text):
        self.message = text
        self.message_t = 3.2

    def _snapshot(self):
        s = self.sigil
        if s is not None:
            self.history.append(s.to_dict())
            if len(self.history) > 40:
                self.history.pop(0)

    def undo(self):
        from .sigil import Sigil

        if not self.history:
            self.notify("nothing to undo")
            return
        self.run.foci[self.slot] = Sigil.from_dict(self.history.pop())
        self.notify("undo")

    def budget_used(self):
        s = self.sigil
        return s.ink_cost if s else 0.0

    def budget_left(self):
        return self.run.ink_budget - self.budget_used()

    # ----------------------------------------------------------------- events

    def to_canvas(self, screen_pos):
        return pygame.Vector2(screen_pos[0] - CANVAS_CENTER[0], screen_pos[1] - CANVAS_CENTER[1])

    def in_canvas(self, screen_pos):
        p = self.to_canvas(screen_pos)
        return abs(p.x) <= FOCUS_HALF and abs(p.y) <= FOCUS_HALF

    def handle_event(self, event):
        if self.renaming:
            self._rename_event(event)
            return
        if self.browsing:
            self._browse_event(event)
            return

        if event.type == pygame.KEYDOWN:
            self._key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.in_canvas(event.pos):
                if self.budget_left() <= 0:
                    self.notify("out of ink budget - undo or clear")
                    return
                self.current = Stroke(ink_type=self.ink)
                self.current.add_point(self.to_canvas(event.pos))
            elif event.button == 3:
                self.undo()
        elif event.type == pygame.MOUSEMOTION and self.current is not None:
            if self.in_canvas(event.pos):
                self.current.add_point(self.to_canvas(event.pos))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.current is not None:
            stroke = self.current
            self.current = None
            if len(stroke.points) >= 2 and self.sigil is not None:
                self._snapshot()
                self.sigil.strokes.append(stroke)
                self.sigil.recompile()
                if self.budget_left() < 0:
                    self.sigil.strokes.pop()
                    self.sigil.recompile()
                    self.notify("that stroke would exceed the ink budget")

    def _key(self, event):
        k = event.key
        if k == pygame.K_ESCAPE:
            self.done = True
        elif k in (pygame.K_BACKSPACE, pygame.K_z):
            self.undo()
        elif k == pygame.K_TAB:
            self.slot = (self.slot + 1) % max(1, len(self.run.foci))
            self.history.clear()
            self.dummy.reset()
        elif pygame.K_1 <= k <= pygame.K_9:
            idx = k - pygame.K_1
            if idx < len(self.run.inks):
                self.ink_index = idx
        elif k == pygame.K_c:
            if self.sigil is not None:
                self._snapshot()
                self.sigil.strokes.clear()
                self.sigil.recompile()
                self.notify("cleared")
        elif k == pygame.K_i:
            self.show_ruler = not self.show_ruler
        elif k == pygame.K_g:
            if self.sigil is not None:
                self.sigil.tap()
        elif k == pygame.K_LEFTBRACKET:
            self.dummy.band = max(0, self.dummy.band - 1)
            self.dummy.reset()
        elif k == pygame.K_RIGHTBRACKET:
            self.dummy.band = min(N_BANDS - 1, self.dummy.band + 1)
            self.dummy.reset()
        elif k == pygame.K_COMMA:
            self.dummy.distance = max(80.0, self.dummy.distance - 60.0)
        elif k == pygame.K_PERIOD:
            self.dummy.distance = min(1000.0, self.dummy.distance + 60.0)
        elif k == pygame.K_r:
            self.dummy.reset()
            if self.sigil is not None:
                self.sigil.quench()
                self.sigil.char = 0.0
                self.sigil.disabled = False
            self.notify("bench reset")
        elif k == pygame.K_l:
            self.browsing = True
        elif k == pygame.K_n:
            self.renaming = True
            self.name_buffer = self.sigil.name if self.sigil else ""
        elif k == pygame.K_e:
            self._set_ignition_to_hover()

    def _browse_event(self, event):
        """The shelf. Load a finished instrument into the slot you are
        editing, then take it apart.

        Loading overwrites, and that is fine because nothing here is scarce —
        the library is a starting point, not a reward, and treating it as
        loot would put a price on the one thing that most needs to be free."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_l):
            self.browsing = False
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.browse_i = (self.browse_i + 1) % len(LIBRARY)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.browse_i = (self.browse_i - 1) % len(LIBRARY)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            name, fn, kind, desc = LIBRARY[self.browse_i]
            self._snapshot()
            self.run.foci[self.slot] = fn()
            self.dummy.reset()
            self.browsing = False
            self.notify(f"loaded {name} - {desc}")

    def _rename_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_RETURN:
            if self.sigil is not None and self.name_buffer.strip():
                self.sigil.name = self.name_buffer.strip()[:22]
            self.renaming = False
        elif event.key == pygame.K_ESCAPE:
            self.renaming = False
        elif event.key == pygame.K_BACKSPACE:
            self.name_buffer = self.name_buffer[:-1]
        elif event.unicode and event.unicode.isprintable():
            self.name_buffer += event.unicode

    def _set_ignition_to_hover(self):
        """Where the spark goes in is a real choice — the doc measures a
        loop junction building 2.3-2.7x against a terminal's 1.8x — so it
        should be the player's, not an automatic pick."""
        s = self.sigil
        if s is None or not s.graph.nodes:
            return
        mouse = self.to_canvas(pygame.mouse.get_pos())
        best, bd = None, 1e9
        for nid, node in s.graph.nodes.items():
            d = (node.pos - mouse).length()
            if d < bd:
                best, bd = nid, d
        if best is not None and bd < 40:
            s.ignition_override = best
            s._pick_ignition()
            self.notify(f"ignition moved to node {best}")

    def set_hold(self, on):
        self.testing_hold = on
        if self.sigil is not None:
            self.sigil.set_hold(on)

    # ----------------------------------------------------------------- update

    def update(self, dt):
        self.time += dt
        self.message_t = max(0.0, self.message_t - dt)
        s = self.sigil
        if s is None:
            return

        emissions = s.advance(dt)
        if emissions:
            self.pulses.extend(
                emissions_to_pulses(emissions, pygame.Vector2(0, 0), 0.0, 1.0)
            )

        target = pygame.Vector2(self.dummy.distance, 0)
        for q in self.pulses:
            q.update(dt)
            if not q.spent and (q.pos - target).length() < self.dummy.radius + q.radius:
                self.dummy.take(q, dt)
                q.spent = True
        self.pulses = [q for q in self.pulses if not q.spent][-500:]
        self.dummy.update(dt)

    # ------------------------------------------------------------------ draw

    def draw(self, surface):
        surface.fill((13, 14, 19))
        self._draw_canvas(surface)
        self._draw_bench(surface)
        self._draw_panel(surface)
        self._draw_footer(surface)
        if self.browsing:
            self._draw_library(surface)
        if self.renaming:
            self._draw_rename(surface)

    def _draw_canvas(self, surface):
        cx, cy = CANVAS_CENTER
        rect = pygame.Rect(cx - FOCUS_HALF, cy - FOCUS_HALF, FOCUS_HALF * 2, FOCUS_HALF * 2)
        pygame.draw.rect(surface, (17, 19, 25), rect)
        pygame.draw.rect(surface, (52, 58, 72), rect, 1)

        # Forward marker: the sigil is rotated to your aim in combat, so the
        # player has to know which way "forwards" is while drawing.
        pygame.draw.line(surface, (60, 70, 88), (cx, cy), (cx + FOCUS_HALF - 6, cy), 1)
        pygame.draw.polygon(surface, (90, 104, 128),
                            [(cx + FOCUS_HALF - 6, cy), (cx + FOCUS_HALF - 16, cy - 5),
                             (cx + FOCUS_HALF - 16, cy + 5)])
        lbl = self.small.render("aim", True, (86, 98, 118))
        surface.blit(lbl, (cx + FOCUS_HALF - 44, cy - 18))

        if self.show_ruler:
            self._draw_band_ruler(surface, cx, cy)

        s = self.sigil
        if s is not None:
            viz.draw_sigil(surface, s, (cx, cy), 0.0, 1.0, show_nodes=True, width=3)

        if self.current is not None and len(self.current.points) >= 2:
            pts = [(p.x + cx, p.y + cy) for p in self.current.points]
            pygame.draw.lines(surface, self.ink.color, False, pts, 2)

    def _draw_band_ruler(self, surface, cx, cy):
        """One faint circle per band, at the size that rings at it."""
        for i in range(N_BANDS):
            r = BAND_LOOP_PX[i] / (2 * math.pi)
            if r < 4 or r > FOCUS_HALF:
                continue
            col = tuple(int(c * 0.30) for c in BAND_COLORS[i])
            pygame.draw.circle(surface, col, (cx, cy), int(r), 1)
            tag = self.small.render(f"{i}", True, tuple(int(c * 0.75) for c in BAND_COLORS[i]))
            surface.blit(tag, (cx + int(r) - 4, cy - int(r) - 14))

    def _draw_bench(self, surface):
        y = BENCH_TOP + 70
        pygame.draw.rect(surface, (16, 18, 23), (0, BENCH_TOP, surface.get_width(), 210))
        pygame.draw.line(surface, (44, 50, 62), (0, BENCH_TOP), (surface.get_width(), BENCH_TOP), 1)

        def sx(world_x):
            return BENCH_LEFT + world_x * BENCH_SCALE

        # distance ruler
        for d in range(0, 1001, 200):
            x = sx(d)
            pygame.draw.line(surface, (34, 39, 49), (x, y - 30), (x, y + 30), 1)
            surface.blit(self.small.render(f"{d}", True, (72, 82, 98)), (x - 10, y + 34))

        pygame.draw.circle(surface, (120, 200, 220), (int(sx(0)), int(y)), 9)
        surface.blit(self.small.render("emitter", True, (96, 112, 132)), (sx(0) - 22, y - 30))

        for q in self.pulses:
            px, py = sx(q.pos.x), y + q.pos.y * BENCH_SCALE
            if -20 < px < surface.get_width() + 20:
                r = max(2, int(2 + 4 * min(1.0, q.total * 8)))
                pygame.draw.circle(surface, q.color, (int(px), int(py)), r)

        d = self.dummy
        dx, dy = int(sx(d.distance)), int(y)
        col = band_color(d.band)
        if d.hit_flash > 0:
            pygame.draw.circle(surface, (255, 255, 255), (dx, dy), int(d.radius + 6 * d.hit_flash), 2)
        pygame.draw.circle(surface, (46, 52, 64), (dx, dy), int(d.radius))
        viz.draw_resonance_ring(surface, (dx, dy), d.radius, d.band, self.time, 2)
        viz.hp_bar(surface, (dx, dy - d.radius - 14), 60, d.hp / d.max_hp)

        info = [
            f"dummy: band {int(d.band)} ({BAND_NAMES[int(d.band)]})  [ ] to retune",
            f"range: {d.distance:.0f}px  , . to move",
            f"dps {d.dps:6.1f}   resonance {d.last_quality * 100:5.1f}%",
        ]
        for i, line in enumerate(info):
            surface.blit(self.small.render(line, True, (140, 156, 176)), (dx + 40, y - 34 + i * 17))

        feel = self.small.render(BAND_FEEL[int(d.band)], True, tuple(int(c * 0.8) for c in col))
        surface.blit(feel, (dx + 40, y + 22))

    def _draw_panel(self, surface):
        s = self.sigil
        x = PANEL_X
        y = 24
        title = self.font.render(f"FOCUS {self.slot + 1}: {s.name if s else '-'}", True, (226, 234, 246))
        surface.blit(title, (x, y))
        y += 30

        used, total = self.budget_used(), self.run.ink_budget
        surface.blit(self.small.render(f"ink {used:.0f} / {total:.0f}", True, (150, 164, 184)), (x, y))
        viz.draw_meter(surface, pygame.Rect(x, y + 18, 360, 8), used / max(total, 1),
                       (120, 200, 220) if used <= total else (230, 110, 90))
        y += 40

        if s is not None:
            bands = s.measured_bands()
            surface.blit(self.small.render("output spectrum", True, (150, 164, 184)), (x, y))
            viz.draw_spectrum(surface, pygame.Rect(x, y + 18, 360, 54), bands,
                              highlight=self.dummy.band)
            y += 82

            centre, tot = dominant_band(bands)
            match = resonance_quality(bands, self.dummy.vuln) if tot > 1e-9 else 0.0
            surface.blit(self.small.render(
                f"centre band {centre:.2f}   match vs dummy {match * 100:.0f}%",
                True, (170, 186, 206)), (x, y))
            y += 26

            surface.blit(self.small.render("charge / saturation / char", True, (150, 164, 184)), (x, y))
            viz.draw_meter(surface, pygame.Rect(x, y + 17, 116, 7), s.charge_fraction(), (110, 190, 240))
            viz.draw_meter(surface, pygame.Rect(x + 122, y + 17, 116, 7), s.saturation, (240, 200, 110))
            viz.draw_meter(surface, pygame.Rect(x + 244, y + 17, 116, 7), s.char,
                           (240, 120, 90) if not s.disabled else (255, 70, 60))
            y += 38

            # Archetype first: what *kind* of thing this drawing turned out
            # to be. It is read off the topology, never chosen, so it is a
            # measurement like everything else on this panel.
            kind = ("capacitor" if s.is_capacitor
                    else "emitter" if s.terminals else "inert")
            extra = []
            if s.barrier_strength > 0.3:
                extra.append(f"barrier {s.barrier_strength:.2f}")
            if s.coupler_sites:
                extra.append("conduit")
            tag = kind + ("  +  " + ", ".join(extra) if extra else "")
            surface.blit(self.font.render(tag.upper(), True, _KIND_COLOR.get(kind, (200, 212, 228))),
                         (x, y))
            y += 22

            surface.blit(self.font.render("ASSAY", True, (200, 212, 228)), (x, y))
            y += 24
            for line in s.assay().lines:
                for part in _wrap(line, 46):
                    surface.blit(self.small.render(part, True, (152, 168, 190)), (x, y))
                    y += 17
            y += 4
            y += 8

        surface.blit(self.font.render("INK", True, (200, 212, 228)), (x, y))
        y += 24
        for i, ink in enumerate(self.run.inks):
            sel = i == self.ink_index % len(self.run.inks)
            box = pygame.Rect(x, y, 360, 20)
            if sel:
                pygame.draw.rect(surface, (32, 38, 48), box)
            pygame.draw.rect(surface, ink.color, (x + 2, y + 4, 12, 12))
            name = f"{i + 1}. {ink.name}"
            surface.blit(self.small.render(name, True, (222, 230, 242) if sel else (140, 154, 174)),
                         (x + 22, y + 3))
            y += 21
        if 0 <= self.ink_index < len(self.run.inks):
            blurb = self.run.inks[self.ink_index % len(self.run.inks)].blurb
            y += 4
            for line in _wrap(blurb, 52):
                surface.blit(self.small.render(line, True, (116, 130, 150)), (x, y))
                y += 16

    def _draw_footer(self, surface):
        keys = ("LMB draw  RMB/Z undo  1-6 ink  TAB focus  L shelf  C clear  "
                "N name  E ignition  I ruler  G tap  SPACE hold  R reset  ESC descend")
        surface.blit(self.small.render(keys, True, (104, 118, 138)), (16, surface.get_height() - 22))
        if self.message_t > 0:
            surface.blit(self.font.render(self.message, True, (240, 220, 150)), (16, BENCH_TOP - 30))

    def _draw_library(self, surface):
        w, h = surface.get_size()
        box = pygame.Rect(w // 2 - 400, 60, 800, h - 160)
        pygame.draw.rect(surface, (14, 16, 21), box)
        pygame.draw.rect(surface, (92, 106, 128), box, 1)
        surface.blit(self.font.render("THE SHELF - load a working sigil, then take it apart",
                                      True, (226, 236, 250)), (box.x + 20, box.y + 16))
        surface.blit(self.small.render("up/down to browse   ENTER to load into this focus   L or ESC to close",
                                       True, (120, 136, 158)), (box.x + 20, box.y + 40))
        y = box.y + 72
        for i, (name, _fn, kind, desc) in enumerate(LIBRARY):
            sel = i == self.browse_i
            if sel:
                pygame.draw.rect(surface, (28, 34, 44), (box.x + 12, y - 4, box.width - 24, 40))
                pygame.draw.rect(surface, (110, 190, 220), (box.x + 12, y - 4, 3, 40))
            col = (232, 240, 250) if sel else (150, 164, 184)
            surface.blit(self.font.render(name, True, col), (box.x + 26, y))
            surface.blit(self.small.render(f"[{kind}]", True, _KIND_COLOR.get(kind, (130, 140, 160))),
                         (box.x + 130, y + 3))
            surface.blit(self.small.render(desc[:74], True, (126, 140, 162)), (box.x + 26, y + 20))
            y += 42

    def _draw_rename(self, surface):
        w, h = surface.get_size()
        box = pygame.Rect(w // 2 - 220, h // 2 - 50, 440, 100)
        pygame.draw.rect(surface, (20, 23, 30), box)
        pygame.draw.rect(surface, (90, 104, 126), box, 1)
        surface.blit(self.font.render("Name this sigil:", True, (200, 212, 228)),
                     (box.x + 18, box.y + 18))
        surface.blit(self.font.render(self.name_buffer + "_", True, (240, 226, 160)),
                     (box.x + 18, box.y + 52))


def _wrap(text, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines
