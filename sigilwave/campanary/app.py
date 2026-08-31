"""Mode machine, HUD, and the main loop.

The loop is a fixed-step accumulator because a bell's resonance is measured
in simulation steps: a player on a fast machine and one on a slow machine
have to get the same instrument. Hitstop is applied by *withholding* steps
rather than by scaling dt, so a freeze is a real freeze and never a
slow-motion smear.

Most of what is new here is teaching. The game was unplayable-by-inspection:
it had four verbs, a note ladder and a matching rule, and told you none of
them. Three things fix that and all three are on screen rather than in a
manual - a title card that states the rule, a **target readout** naming the
nearest thing's note and which of your bells answers it, and a short chain of
prompts in the first wave that fire off what the player has actually done.
"""

import math
import random

import pygame

from sigilwave.camera import Camera

from . import audio, notes, render
from .arena import Belfry, Player, BELL_WORLD_SCALE
from .forge import Foundry
from .foes import GreatBell, Twin
from .notes import NOTE_NAMES
from .run import Codex, Session

WIDTH, HEIGHT = 1280, 800
FIXED_DT = 1 / 120.0
MAX_FRAME = 0.2

# The first wave walks the player through the four verbs. Each line waits on
# something they did rather than on a timer, so nobody is ever told to do a
# thing they have already worked out.
TUTORIAL = [
    ("toll", "LEFT CLICK to toll. The ring is your attack - it comes out of you,"
             " all the way round."),
    ("reach", "The ring stops at the circle on the floor. Nothing outside it is"
              " being hit."),
    ("beat", "Toll as the white ring lands on you. On the beat hits far harder"
             " - watch CHORUS climb."),
    ("note", "Everything has a note. Match it and it shatters; miss and you only"
             " shove it. Press 2 for your other bell."),
    ("dash", "SPACE dashes through anything. Every wind-up in the game is"
             " dodgeable."),
]


class App:
    def __init__(self, screen=None):
        pygame.init()
        audio.init()
        pygame.display.set_caption("CAMPANARY")
        self.screen = screen or pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.font = pygame.font.SysFont("consolas", 16)
        self.small = pygame.font.SysFont("consolas", 13)
        self.big = pygame.font.SysFont("consolas", 30, bold=True)
        self.huge = pygame.font.SysFont("consolas", 52, bold=True)
        self.clock = pygame.time.Clock()
        self.running = True

        self.codex = Codex.load()
        self.session = None
        self.mode = "TITLE"
        self.belfry = None
        self.foundry = None
        self.camera = Camera(*self.screen.get_size())
        self.glow = render.Glow(self.screen.get_size())
        self.time = 0.0
        self.beat_tick = 0
        self.tutorial = 0
        self.prompt = ""
        self.prompt_t = 0.0
        self._strike = False
        self._swap = None

    # ------------------------------------------------------------------ flow

    def start(self):
        self.session = Session(self.codex)
        self.tutorial = 0
        self.enter_foundry(first=True)

    def enter_foundry(self, first=False):
        self.foundry = Foundry(self.session, (self.font, self.small, self.big))
        if first:
            self.foundry.say("two bells are ready. The Toll is four times The Hand,"
                             " and reaches four times as far. ENTER to go down.", 9.0)
        self.mode = "FOUNDRY"

    def enter_belfry(self):
        spec = self.session.spec
        # Going down is also going to the forge fire: char is a within-fight
        # resource, and carrying it between waves would turn one greedy swell
        # into a punishment two minutes later.
        for b in self.session.bells:
            b.char = 0.0
            b.cracked = False
        player = Player(pygame.Vector2(0, 0), self.session.bells)
        player.hp = self.session.hp
        player.max_hp = self.session.max_hp
        self.belfry = Belfry(player, spec, seed=self.session.wave * 977,
                             on_event=self._event)
        self.camera.snap_to(player.pos)
        self.mode = "BELFRY"

    def _event(self, kind, payload):
        if kind == "shatter":
            self.session.shatters += 1

    def finish_wave(self):
        self.session.hp = max(25.0, self.belfry.player.hp)
        self.session.advance()
        self.enter_foundry()

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
            elif self.mode == "DEAD":
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

    # --------------------------------------------------------------- update

    def update(self, dt):
        self.time += dt
        self.prompt_t = max(0.0, self.prompt_t - dt)
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
        strike, swap = self._strike, self._swap
        self._strike, self._swap = False, None

        if b.hitstop > 0.0:
            b.hitstop = max(0.0, b.hitstop - dt)
            if strike:
                self._strike = True      # never eat a queued strike
            return

        b.update(dt, move, strike, holding, dash, swap)
        self._metronome(b)
        self._teach(b)

        self.camera.follow(b.player.pos + b.player.vel * 0.16, min(1.0, 9.0 * dt))
        if b.cleared:
            self.finish_wave()
        elif b.failed:
            self.mode = "DEAD"
            self.codex.end(self.session)

    def _metronome(self, b):
        """A tick on the held bell's own pulse. The only sound in the game
        not caused by something happening, and what turns the beat from a
        thing on screen into a thing in the room."""
        bell = b.player.bell
        if bell is None or bell.is_empty or bell.period <= 1e-6:
            return
        n = int(bell.time / bell.period)
        if n != self.beat_tick:
            self.beat_tick = n
            audio.tick(False)

    def _teach(self, b):
        """Advance the first-wave prompts off what the player has done."""
        if self.session.wave > 0 or self.tutorial >= len(TUTORIAL):
            return
        p = b.player
        key = TUTORIAL[self.tutorial][0]
        done = (
            (key == "toll" and p.tolls >= 2)
            or (key == "reach" and p.tolls >= 5)
            or (key == "beat" and p.chorus >= 2)
            or (key == "note" and any(f.crack > 0.15 for f in b.foes))
            or (key == "dash" and p.dash_cd > 0.0)
        )
        if self.prompt_t <= 0.0 and not done:
            self.prompt = TUTORIAL[self.tutorial][1]
            self.prompt_t = 0.6
        if done:
            self.tutorial += 1
            self.prompt_t = 0.0
            if self.tutorial < len(TUTORIAL):
                self.prompt = TUTORIAL[self.tutorial][1]
                self.prompt_t = 0.6
            else:
                self.prompt = ""

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
        elif self.mode == "DEAD":
            self._draw_end(s)
        pygame.display.flip()

    def _draw_belfry(self, s):
        b, cam = self.belfry, self.camera
        if b.shake > 0.0:
            cam.pos += pygame.Vector2(random.uniform(-1, 1),
                                      random.uniform(-1, 1)) * b.shake * 11

        render.draw_floor(s, cam, b)
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

        render.draw_hazards(s, self.glow, cam, b)
        for r in b.rings:
            render.draw_ring(self.glow, cam, r)
        for r in b.hostile:
            render.draw_hostile_ring(self.glow, cam, r)

        render.draw_player(s, self.glow, cam, p, bell, b.time)
        render.draw_marks(s, self.glow, cam, b)
        b.fx.draw(s, self.glow, cam)
        render.draw_offscreen(s, self.glow, cam, b)
        self.glow.blit_onto(s)
        b.fx.draw_washes(s)
        b.fx.draw_vignettes(s)

        self._draw_hud(s, b)

    # ------------------------------------------------------------------ HUD

    def _draw_hud(self, s, b):
        w, h = s.get_size()
        p = b.player

        # Health. Segmented, because three or four hits kill and a bar of
        # pixels does not tell you how many you have left.
        hits = 4
        seg = 62
        for i in range(hits):
            x = 18 + i * (seg + 4)
            full = p.hp / p.max_hp > i / hits
            frac = max(0.0, min(1.0, (p.hp / p.max_hp - i / hits) * hits))
            pygame.draw.rect(s, (32, 36, 46), (x, 18, seg, 13))
            if frac > 0:
                col = (232, 240, 252) if p.hp / p.max_hp > 0.34 else (252, 116, 104)
                pygame.draw.rect(s, col, (x, 18, int(seg * frac), 13))
            pygame.draw.rect(s, (62, 70, 86), (x, 18, seg, 13), 1)

        # The bells.
        y = 44
        for i, bell in enumerate(p.bells):
            if bell.is_empty:
                continue
            box = pygame.Rect(18, y, 268, 40)
            if i == p.active:
                pygame.draw.rect(s, (24, 29, 39), box)
                pygame.draw.rect(s, (96, 112, 138), box, 1)
            col = bell.color if bell.has_loop else (100, 108, 124)
            label = f"{i + 1} {bell.name}"
            if bell.cracked:
                label += "   CRACKED"
                col = (245, 120, 108)
            s.blit(self.small.render(label, True, (208, 220, 236)), (26, y + 5))
            if bell.has_loop:
                s.blit(self.small.render(
                    f"{notes.note_name(bell.note)}  {int(bell.reach)}px", True, col),
                    (26, y + 21))
                ch = min(1.0, bell.char)
                if ch > 0.02:
                    pygame.draw.rect(s, (44, 32, 30), (180, y + 26, 96, 5))
                    pygame.draw.rect(s, (245, 150, 110) if ch < 0.85 else (255, 90, 80),
                                     (180, y + 26, int(96 * ch), 5))
            y += 44

        if p.chorus > 0:
            t = self.big.render(f"x{p.chorus_mult:0.2f}", True, render.HOT)
            s.blit(t, (18, y + 8))
            s.blit(self.small.render("CHORUS", True, (182, 198, 222)),
                   (24 + t.get_width(), y + 22))

        self._draw_target(s, b, w)

        lab = self.small.render(self.session.label, True, (142, 156, 178))
        s.blit(lab, (w - lab.get_width() - 20, 20))
        room = self.small.render(b.spec.get("name", ""), True, (198, 210, 228))
        s.blit(room, (w - room.get_width() - 20, 38))
        left = self.small.render(f"{len(b.foes)} left", True, (142, 156, 178))
        s.blit(left, (w - left.get_width() - 20, 56))

        if b.announce is not None and b.announce_t > 0.0:
            self._banner_note(s, w, b.announce)

        if b.banner_t > 0.0:
            a = min(1.0, b.banner_t / 1.2)
            t = self.big.render(b.banner, True, render.lerp(render.BG, (240, 246, 255), a))
            s.blit(t, (w // 2 - t.get_width() // 2, h // 2 - 160))

        line = self.prompt if self.prompt_t > 0.0 else (b.lesson if b.lesson_t > 0 else "")
        col = (180, 224, 255) if self.prompt_t > 0.0 else (255, 224, 158)
        if line:
            t = self.font.render(line, True, col)
            box = pygame.Rect(w // 2 - t.get_width() // 2 - 16, h - 92,
                              t.get_width() + 32, t.get_height() + 14)
            veil = pygame.Surface(box.size, pygame.SRCALPHA)
            veil.fill((8, 10, 14, 190))
            s.blit(veil, box.topleft)
            s.blit(t, (w // 2 - t.get_width() // 2, h - 85))

        keys = "WASD move    LMB toll / hold to swell    SPACE dash    1-3 swap bell"
        t = self.small.render(keys, True, (88, 98, 116))
        s.blit(t, (w // 2 - t.get_width() // 2, h - 26))

    def _draw_target(self, s, b, w):
        """What the nearest thing is, and which bell answers it.

        The single clearest teaching device in the game. Everything needed to
        play correctly was already on screen - a colour, a tempo, a hum - and
        a new player has no idea any of it means anything. This says it in
        words for as long as it takes to stop needing to.
        """
        p = b.player
        foe = None
        best = 1e18
        for f in b.foes:
            d = (f.pos - p.pos).length_squared()
            if d < best:
                foe, best = f, d
        if foe is None:
            return

        x, y = w // 2 - 150, 18
        pygame.draw.rect(s, (14, 17, 23), (x, y, 300, 46))
        pygame.draw.rect(s, (46, 54, 68), (x, y, 300, 46), 1)

        name = self.small.render(foe.label.upper(), True, (206, 218, 234))
        s.blit(name, (x + 12, y + 6))

        if foe.note < 0:
            verdict, col = "NO NOTE - SHOVE IT", (176, 182, 194)
        elif not foe.crackable:
            verdict, col = "SEALED - ANSWER ITS PHRASE", (206, 200, 160)
        else:
            tag = notes.NOTE_NAMES[foe.note]
            answer = -1
            for i, bl in enumerate(p.bells):
                if bl.has_loop and abs(bl.note - foe.note) < 0.45:
                    answer = i
                    break
            held = p.bell
            if held is not None and held.has_loop and abs(held.note - foe.note) < 0.45:
                verdict, col = f"{tag} - MATCHED", (150, 245, 170)
            elif answer >= 0:
                verdict, col = f"{tag} - PRESS {answer + 1}", (255, 216, 130)
            else:
                verdict, col = f"{tag} - NO BELL FOR IT", (250, 140, 124)
        s.blit(self.small.render(verdict, True, col), (x + 12, y + 25))
        pygame.draw.circle(s, foe.color, (x + 284, y + 23), 8)

    def _banner_note(self, s, w, n):
        t = self.huge.render(NOTE_NAMES[n], True, notes.NOTE_COLORS[n])
        sub = self.small.render("answer it", True, (200, 210, 226))
        box = pygame.Rect(w // 2 - t.get_width() // 2 - 26, 76,
                          t.get_width() + 52, t.get_height() + 30)
        veil = pygame.Surface(box.size, pygame.SRCALPHA)
        veil.fill((8, 9, 13, 210))
        s.blit(veil, box.topleft)
        pygame.draw.rect(s, notes.NOTE_COLORS[n], box, 1)
        s.blit(t, (w // 2 - t.get_width() // 2, 80))
        s.blit(sub, (w // 2 - sub.get_width() // 2, 80 + t.get_height()))

    # --------------------------------------------------------------- screens

    def _draw_title(self, s):
        s.fill(render.BG)
        w, h = s.get_size()
        self.glow.clear()

        cx, cy = w // 2, h // 2 + 30
        for i in range(notes.N_NOTES):
            r = notes.NOTE_RADIUS[i] * 1.35
            a = 0.30 + 0.25 * math.sin(self.time * 1.6 - i * 0.7)
            pygame.draw.circle(self.glow.surf,
                               (*render.scale(notes.NOTE_COLORS[i], a), 255),
                               (cx, cy), int(r), 2)
        self.glow.blit_onto(s)

        t = self.huge.render("CAMPANARY", True, (238, 244, 255))
        s.blit(t, (cx - t.get_width() // 2, 54))
        for i, line in enumerate([
            "A big bell is deep. A small bell is high. That is all size does.",
            "Cast them in the foundry. Ring them at the things in the dark.",
        ]):
            r = self.font.render(line, True, (152, 166, 188))
            s.blit(r, (cx - r.get_width() // 2, 116 + i * 22))

        rules = [
            ("RESONANCE BREAKS", "Match a thing's note and it shatters - and heals you."),
            ("FORCE MOVES", "Any other note only shoves. Shove things into walls."),
            ("SIZE IS REACH", "Your ring stops at the circle on the floor."),
            ("THE BEAT", "Toll as the white ring lands. Chained, it doubles."),
        ]
        y = 186
        for head, body in rules:
            a = self.font.render(head, True, (226, 236, 250))
            b = self.small.render(body, True, (140, 154, 176))
            s.blit(a, (cx - 300, y))
            s.blit(b, (cx - 300 + 200, y + 3))
            y += 26

        keys = "WASD move    LMB toll, hold to swell    SPACE dash    1-3 swap bell"
        r = self.small.render(keys, True, (120, 134, 156))
        s.blit(r, (cx - r.get_width() // 2, y + 16))

        msg = "press any key" if not self.codex.runs else \
            f"press any key   -   best wave {self.codex.best + 1}, {self.codex.shatters} shattered"
        r = self.font.render(msg, True, (204, 216, 234))
        s.blit(r, (cx - r.get_width() // 2, h - 62))

    def _draw_end(self, s):
        s.fill(render.BG)
        w, h = s.get_size()
        t = self.huge.render("THE BELL IS SILENT", True, (240, 130, 120))
        s.blit(t, (w // 2 - t.get_width() // 2, h // 2 - 90))
        for i, line in enumerate([
            f"wave {self.session.wave + 1}   -   {self.session.shatters} shattered",
            "", "any key",
        ]):
            r = self.font.render(line, True, (152, 166, 188))
            s.blit(r, (w // 2 - r.get_width() // 2, h // 2 - 10 + i * 24))

    # ----------------------------------------------------------------- loop

    def run_loop(self):
        acc = 0.0
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
