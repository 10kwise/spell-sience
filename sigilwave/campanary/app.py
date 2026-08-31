"""Mode machine, HUD, and the main loop.

The loop is a fixed-step accumulator because a bell's resonance is measured
in simulation steps: a player on a fast machine and a player on a slow one
have to get the same instrument. Hitstop is applied by *withholding* steps
rather than by scaling dt, so a freeze is a real freeze and never a
slow-motion smear.
"""

import math
import random

import pygame

from sigilwave.camera import Camera

from . import audio, notes, render
from .arena import Belfry, Player, BELL_WORLD_SCALE
from .forge import Foundry
from .foes import GreatBell, Twin
from .notes import NOTE_NAMES, NOTE_SHORT
from .run import ACTS, Codex, Run

WIDTH, HEIGHT = 1280, 800
FIXED_DT = 1 / 120.0
MAX_FRAME = 0.2
ANVIL_SECONDS = 12.0


class App:
    def __init__(self, screen=None):
        pygame.init()
        audio.init()
        pygame.display.set_caption("CAMPANARY")
        self.screen = screen or pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.font = pygame.font.SysFont("consolas", 16)
        self.small = pygame.font.SysFont("consolas", 13)
        self.big = pygame.font.SysFont("consolas", 30, bold=True)
        self.huge = pygame.font.SysFont("consolas", 54, bold=True)
        self.clock = pygame.time.Clock()
        self.running = True

        self.codex = Codex.load()
        self.run = None
        self.mode = "TITLE"
        self.belfry = None
        self.foundry = None
        self.camera = Camera(*self.screen.get_size())
        self.glow = render.Glow(self.screen.get_size())
        self.time = 0.0
        self.offers = []
        self.offer_msg = ""
        self.flash = 0.0
        self.beat_tick = 0

    # ------------------------------------------------------------------ flow

    def start(self):
        self.run = Run(self.codex)
        self.enter_foundry(first=True)

    def enter_foundry(self, first=False, anvil=False):
        self.foundry = Foundry(self.run, (self.font, self.small, self.big),
                               ANVIL_SECONDS if anvil else None)
        if first:
            self.foundry.say("two bells are ready. The Toll is four times The Hand, "
                             "and reaches four times as far.", 8.0)
        self.mode = "FOUNDRY"

    def enter_belfry(self):
        spec = self.run.spec
        # Going down is also going to the forge fire. A bell you cooked in
        # the last room is not still cooked in the next one - char is a
        # within-fight resource, and carrying it between waves would turn one
        # greedy swell into a punishment two minutes later, which is exactly
        # the kind of delayed consequence this rebuild exists to remove.
        for b in self.run.bells:
            b.char = 0.0
            b.cracked = False
        player = Player(pygame.Vector2(0, 0), self.run.bells)
        player.hp = self.run.hp
        player.max_hp = self.run.max_hp
        self.belfry = Belfry(player, spec, seed=hash((self.run.act, self.run.wave)) & 0xFFFF,
                             on_event=self._event)
        self.camera.snap_to(player.pos)
        self.mode = "BELFRY"

    def _event(self, kind, payload):
        if kind == "shatter":
            self.run.shatters += 1
            self.flash = 0.55

    def finish_wave(self):
        self.run.hp = max(15.0, self.belfry.player.hp)
        nxt = self.run.advance()
        if nxt == "done":
            self.mode = "WON"
            self.codex.end_run(self.run)
        elif nxt == "reward":
            self.offers = self.run.offers()
            self.offer_msg = ""
            self.mode = "REWARD"
        else:
            self.enter_foundry(anvil=True)

    # ---------------------------------------------------------------- input

    def handle(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.VIDEORESIZE:
                self.camera.resize(e.w, e.h)
                self.glow.resize((e.w, e.h))
            elif self.mode == "TITLE":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        self.running = False
                    else:
                        self.start()
            elif self.mode == "FOUNDRY":
                self.foundry.event(e, self.screen)
            elif self.mode == "BELFRY":
                self._belfry_event(e)
            elif self.mode == "REWARD":
                self._reward_event(e)
            elif self.mode in ("DEAD", "WON"):
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        self.running = False
                    else:
                        self.mode = "TITLE"

    def _belfry_event(self, e):
        p = self.belfry.player
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.mode = "TITLE"
            elif pygame.K_1 <= e.key <= pygame.K_3:
                self._swap = e.key - pygame.K_1
            elif e.key == pygame.K_q:
                self._swap = (p.active + 1) % max(1, len(p.bells))
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                self._strike = True
            elif e.button == 3:
                self._swap = (p.active + 1) % max(1, len(p.bells))
        elif e.type == pygame.MOUSEWHEEL:
            self._swap = (p.active + (1 if e.y > 0 else -1)) % max(1, len(p.bells))

    def _reward_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key in (pygame.K_1, pygame.K_2):
            i = e.key - pygame.K_1
            if i < len(self.offers):
                self.offer_msg = self.run.take(self.offers[i][0])
                self.offers = []
                audio.ui(True)
        elif self.offers == [] and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            self.enter_foundry(anvil=False)

    # --------------------------------------------------------------- update

    def update(self, dt):
        self.time += dt
        self.flash = max(0.0, self.flash - dt * 3.0)
        if self.mode == "FOUNDRY":
            keys = pygame.key.get_pressed()
            self.foundry.update(dt, keys[pygame.K_SPACE])
            if self.foundry.done:
                self.enter_belfry()
        elif self.mode == "BELFRY":
            self._update_belfry(dt)

    def _update_belfry(self, dt):
        b = self.belfry
        keys = pygame.key.get_pressed()
        move = pygame.Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        holding = pygame.mouse.get_pressed()[0]
        dash = keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        strike = getattr(self, "_strike", False)
        swap = getattr(self, "_swap", None)
        self._strike = False
        self._swap = None

        if b.hitstop > 0.0:
            b.hitstop = max(0.0, b.hitstop - dt)
            # Still poll input during a freeze so a queued strike is not lost.
            if strike:
                self._strike = True
            return

        b.update(dt, move, strike, holding, dash, swap)
        self._metronome(b)

        self.camera.follow(b.player.pos + b.player.vel * 0.16, min(1.0, 9.0 * dt))
        if b.cleared:
            self.finish_wave()
        elif b.failed:
            self.mode = "DEAD"
            self.codex.end_run(self.run)

    def _metronome(self, b):
        """A tick on the bell's own pulse. This is the only sound in the game
        that is not caused by something happening, and it is what turns the
        beat from a thing on screen into a thing in the room."""
        bell = b.player.bell
        if bell is None or bell.is_empty or bell.period <= 1e-6:
            return
        n = int(bell.time / bell.period)
        if n != self.beat_tick:
            self.beat_tick = n
            audio.tick(False)

    # ----------------------------------------------------------------- draw

    def draw(self):
        s = self.screen
        self.glow.resize(s.get_size())
        if self.mode == "TITLE":
            self._draw_title(s)
        elif self.mode == "FOUNDRY":
            self.foundry.draw(s)
        elif self.mode == "BELFRY":
            self._draw_belfry(s)
        elif self.mode == "REWARD":
            self._draw_reward(s)
        elif self.mode == "DEAD":
            self._draw_end(s, "THE BELL IS SILENT", (240, 130, 120))
        elif self.mode == "WON":
            self._draw_end(s, "THE TOWER IS QUIET", (170, 240, 190))
        pygame.display.flip()

    def _draw_belfry(self, s):
        b = self.belfry
        cam = self.camera
        shake = b.shake
        if shake > 0.0:
            cam.pos += pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * shake * 10

        render.draw_floor(s, cam, b)
        render.draw_stains(s, cam, b)
        self.glow.clear()

        p = b.player
        bell = p.bell
        render.draw_reach(s, self.glow, cam, p, bell)
        render.draw_beat(self.glow, cam, p, bell)

        seen = set()
        for f in b.foes:
            if isinstance(f, Twin) and f.bonded and id(f) not in seen:
                seen.add(id(f))
                seen.add(id(f.bond))
                render.draw_bond(self.glow, cam, f, f.bond)
        for f in b.foes:
            render.draw_foe(s, self.glow, cam, f, b.time)

        for r in b.rings:
            render.draw_ring(self.glow, cam, r)
        for r in b.hostile:
            render.draw_hostile_ring(self.glow, cam, r)

        render.draw_player(s, self.glow, cam, p, bell, b.time)
        render.draw_marks(s, self.glow, cam, b)
        render.draw_shards(s, cam, b)
        self.glow.blit_onto(s)

        if self.flash > 0.0:
            veil = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            veil.fill((255, 255, 255, int(60 * self.flash)))
            s.blit(veil, (0, 0))

        self._draw_hud(s, b)

    # ------------------------------------------------------------------ HUD

    def _draw_hud(self, s, b):
        w, h = s.get_size()
        p = b.player

        # Health. One bar, top left, and nothing else up there.
        pygame.draw.rect(s, (34, 38, 48), (18, 18, 260, 12))
        frac = max(0.0, p.hp / p.max_hp)
        col = (226, 236, 250) if frac > 0.35 else (250, 120, 108)
        pygame.draw.rect(s, col, (18, 18, int(260 * frac), 12))
        pygame.draw.rect(s, (60, 68, 84), (18, 18, 260, 12), 1)

        # The bells. Note name, tempo, char, and which one is in hand.
        y = 44
        for i, bell in enumerate(p.bells):
            box = pygame.Rect(18, y, 260, 40)
            if i == p.active:
                pygame.draw.rect(s, (24, 29, 39), box)
                pygame.draw.rect(s, (92, 106, 130), box, 1)
            name = bell.name if bell else "empty"
            note_col = bell.color if (bell and bell.has_loop) else (100, 108, 124)
            label = f"{i + 1} {name}"
            if bell is not None and bell.cracked:
                label += "  CRACKED"
                note_col = (240, 120, 110)
            s.blit(self.small.render(label, True, (206, 218, 234)), (26, y + 5))
            if bell is not None and bell.has_loop:
                sub = f"{notes.note_name(bell.note)}  {int(bell.reach)}px"
                s.blit(self.small.render(sub, True, note_col), (26, y + 21))
                # char
                ch = min(1.0, bell.char)
                if ch > 0.02:
                    pygame.draw.rect(s, (44, 32, 30), (172, y + 26, 96, 5))
                    pygame.draw.rect(s, (245, 150, 110) if ch < 0.85 else (255, 90, 80),
                                     (172, y + 26, int(96 * ch), 5))
            y += 46

        # The chorus. The only number that goes up because of timing.
        if p.chorus > 0:
            mult = p.chorus_mult
            t = self.big.render(f"x{mult:0.2f}", True, render.HOT)
            s.blit(t, (18, y + 10))
            s.blit(self.small.render("CHORUS", True, (180, 196, 220)),
                   (24 + t.get_width(), y + 24))

        # Where you are.
        lab = self.small.render(self.run.label, True, (140, 154, 176))
        s.blit(lab, (w - lab.get_width() - 20, 20))
        room = self.small.render(b.spec.get("name", ""), True, (196, 208, 226))
        s.blit(room, (w - room.get_width() - 20, 38))
        left = self.small.render(f"{len(b.foes)} left", True, (140, 154, 176))
        s.blit(left, (w - left.get_width() - 20, 56))

        # The boss's call, spelled out - it is a pitch, so it is named.
        if b.announce is not None and b.announce_t > 0.0:
            n = b.announce
            t = self.huge.render(NOTE_NAMES[n], True, notes.NOTE_COLORS[n])
            sub = self.small.render("answer it", True, (200, 210, 226))
            box = pygame.Rect(w // 2 - t.get_width() // 2 - 26, 66,
                              t.get_width() + 52, t.get_height() + 30)
            veil = pygame.Surface(box.size, pygame.SRCALPHA)
            veil.fill((8, 9, 13, 205))
            s.blit(veil, box.topleft)
            pygame.draw.rect(s, notes.NOTE_COLORS[n], box, 1)
            s.blit(t, (w // 2 - t.get_width() // 2, 70))
            s.blit(sub, (w // 2 - sub.get_width() // 2, 70 + t.get_height()))

        if b.banner_t > 0.0:
            a = min(1.0, b.banner_t / 1.2)
            t = self.big.render(b.banner, True, render.lerp(render.BG, (240, 246, 255), a))
            s.blit(t, (w // 2 - t.get_width() // 2, h // 2 - 150))

        if b.lesson_t > 0.0:
            a = min(1.0, b.lesson_t / 1.0)
            t = self.font.render(b.lesson, True,
                                 render.lerp(render.BG, (255, 224, 158), a))
            s.blit(t, (w // 2 - t.get_width() // 2, h - 84))

        keys = "WASD move    LMB toll / hold to swell    SPACE dash    1-2 / RMB swap"
        t = self.small.render(keys, True, (86, 96, 114))
        s.blit(t, (w // 2 - t.get_width() // 2, h - 26))

    # --------------------------------------------------------------- screens

    def _draw_title(self, s):
        s.fill(render.BG)
        w, h = s.get_size()
        self.glow.clear()

        # Five rings, each half the last: the entire system, as a picture,
        # before a word of text.
        cx, cy = w // 2, h // 2 - 40
        for i in range(notes.N_NOTES):
            r = notes.NOTE_RADIUS[i] * 1.5
            a = 0.30 + 0.25 * math.sin(self.time * 1.6 - i * 0.7)
            pygame.draw.circle(self.glow.surf,
                               (*render.scale(notes.NOTE_COLORS[i], a), 255),
                               (cx, cy), int(r), 2)
        self.glow.blit_onto(s)

        t = self.huge.render("CAMPANARY", True, (238, 244, 255))
        s.blit(t, (cx - t.get_width() // 2, 70))
        for i, line in enumerate([
            "A big bell is deep. A small bell is high. That is all size does.",
            "Cast them in the foundry. Ring them at the things in the dark.",
            "",
            "Resonance breaks. Force moves. Pick one.",
        ]):
            col = (150, 164, 186) if i < 3 else (226, 200, 140)
            r = self.font.render(line, True, col)
            s.blit(r, (cx - r.get_width() // 2, 132 + i * 22))

        msg = "press any key" if not self.codex.runs else \
            f"press any key   -   {self.codex.runs} runs, {self.codex.shatters} shattered"
        r = self.font.render(msg, True, (200, 212, 230))
        s.blit(r, (cx - r.get_width() // 2, h - 96))

    def _draw_reward(self, s):
        s.fill(render.BG)
        w, h = s.get_size()
        t = self.big.render(f"{self.run.act_name} IS QUIET", True, (232, 240, 252))
        s.blit(t, (w // 2 - t.get_width() // 2, 120))

        if self.offers:
            for i, (kind, label, desc) in enumerate(self.offers):
                y = 240 + i * 110
                box = pygame.Rect(w // 2 - 320, y, 640, 84)
                pygame.draw.rect(s, (18, 21, 29), box)
                pygame.draw.rect(s, (70, 82, 102), box, 1)
                s.blit(self.big.render(f"{i + 1}", True, (150, 168, 196)), (box.left + 20, y + 22))
                s.blit(self.font.render(label, True, (232, 240, 252)), (box.left + 70, y + 22))
                s.blit(self.small.render(desc, True, (140, 154, 176)), (box.left + 70, y + 46))
        else:
            t = self.font.render(self.offer_msg, True, (255, 224, 160))
            s.blit(t, (w // 2 - t.get_width() // 2, 260))
            t = self.small.render("ENTER - to the foundry", True, (150, 164, 186))
            s.blit(t, (w // 2 - t.get_width() // 2, 320))

    def _draw_end(self, s, title, col):
        s.fill(render.BG)
        w, h = s.get_size()
        t = self.huge.render(title, True, col)
        s.blit(t, (w // 2 - t.get_width() // 2, h // 2 - 90))
        lines = [
            f"{self.run.act_name}, wave {self.run.wave + 1}" if self.run else "",
            f"{self.run.shatters} shattered" if self.run else "",
            "",
            "any key",
        ]
        for i, line in enumerate(lines):
            r = self.font.render(line, True, (150, 164, 186))
            s.blit(r, (w // 2 - r.get_width() // 2, h // 2 - 10 + i * 24))

    # ----------------------------------------------------------------- loop

    def run_loop(self):
        acc = 0.0
        self._strike = False
        self._swap = None
        while self.running:
            frame = min(MAX_FRAME, self.clock.tick(240) / 1000.0)
            self.handle()
            acc += frame
            steps = 0
            while acc >= FIXED_DT and steps < 12:
                acc -= FIXED_DT
                steps += 1
                self.update(FIXED_DT)
            self.draw()


def main():
    App().run_loop()
    pygame.quit()


if __name__ == "__main__":
    main()
