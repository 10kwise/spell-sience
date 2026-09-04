"""Mode manager, main loop, and the Field's renderer.

Modes are a small state machine — TITLE, FORGE, FIELD, REWARD, DEAD — and
the loop is a fixed-step accumulator so the wave sims advance at a rate
independent of frame rate. That is not a nicety: a sigil's resonance is
measured in sim steps, so a player on a fast machine and a player on a slow
one must get the same instrument.
"""

import math
import random

import pygame

from sigilwave.camera import Camera

from .bands import BAND_NAMES, band_color, dominant_band
from .field import Field, MANA_MAX, Player
from .forge import Forge
from .rooms import rewards_for, room_spec
from .run import Codex, Run
from . import viz

WIDTH, HEIGHT = 1280, 800
FIXED_DT = 1 / 120.0
MAX_FRAME = 0.20

BG = (11, 12, 17)
GRID = (28, 33, 43)
TEXT = (188, 202, 220)
DIM = (110, 124, 146)


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("WAVEWRIGHT")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.font = pygame.font.SysFont("consolas", 16)
        self.small = pygame.font.SysFont("consolas", 13)
        self.big = pygame.font.SysFont("consolas", 30, bold=True)
        self.clock = pygame.time.Clock()
        self.running = True

        self.codex = Codex.load()
        self.run = None
        self.mode = "TITLE"
        self.field = None
        self.forge = None
        self.camera = Camera(WIDTH, HEIGHT)
        self.impact_ages = {}
        self.reward_choices = []
        self.reward_msg = ""
        self.time = 0.0
        self.hint = ""
        self.hint_t = 0.0
        self.shake = 0.0
        self.hitstop = 0.0

    # ------------------------------------------------------------------ flow

    def start_run(self):
        self.run = Run(self.codex)
        self.enter_forge(first=True)

    def enter_forge(self, first=False):
        self.forge = Forge(self.run, self.font, self.small)
        if first:
            self.forge.notify("Three sigils are ready. Shove and Draw are the same ring, wound opposite ways.")
        self.mode = "FORGE"

    def enter_field(self):
        spec = room_spec(self.run.room_index)
        player = Player(pygame.Vector2(0, 0), self.run.foci)
        player.hp = self.run.player_hp
        player.max_hp = self.run.player_max_hp
        self.field = Field(player, spec, seed=self.run.room_index * 733)
        self.camera.snap_to(player.pos)
        self.impact_ages = {}
        self.mode = "FIELD"
        self.hint = spec.get("teaches", "")
        self.hint_t = 9.0

    def finish_room(self):
        self.run.player_hp = max(12.0, self.field.player.hp)
        self.run.room_index += 1
        self.run.deepest = max(self.run.deepest, self.run.room_index)
        for drop in self.field.drops:
            if self.run.add_drop(drop):
                self.hint = f"read {drop.name} from the corpse - it is in focus {len(self.run.foci)}"
                self.hint_t = 8.0
        self.codex.save()
        self.reward_choices = rewards_for(self.run.room_index, self.run)
        self.reward_msg = ""
        self.mode = "REWARD"

    # ---------------------------------------------------------------- events

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if self.mode == "TITLE":
                self._title_event(event)
            elif self.mode == "FORGE":
                self._forge_event(event)
            elif self.mode == "FIELD":
                self._field_event(event)
            elif self.mode == "REWARD":
                self._reward_event(event)
            elif self.mode == "DEAD":
                self._dead_event(event)

    def _title_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.running = False
            else:
                self.start_run()

    def _forge_event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and not self.forge.renaming:
            self.forge.set_hold(True)
            return
        if e.type == pygame.KEYUP and e.key == pygame.K_SPACE:
            self.forge.set_hold(False)
            return
        self.forge.handle_event(e)
        if self.forge.done:
            self.forge.set_hold(False)
            for f in self.run.foci:
                f.quench()
                f.char = 0.0
                f.disabled = False
            self.enter_field()

    def _field_event(self, e):
        p = self.field.player
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.mode = "TITLE"
            elif pygame.K_1 <= e.key <= pygame.K_4:
                p.switch(e.key - pygame.K_1)
            elif e.key == pygame.K_q:
                f = p.focus
                if f and self.field.detonate(f, p.pos):
                    self.shake = min(1.0, self.shake + 0.9)
                    self.hitstop = max(self.hitstop, 0.07)
            elif e.key == pygame.K_e:
                if self.field.stamp_relay(p.pos + p.aim * 90):
                    self.hint = "relay placed - stand within reach and it fires what you feed it"
                    self.hint_t = 5.0
            elif e.key in (pygame.K_LSHIFT, pygame.K_SPACE):
                p.try_dash(p.vel)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                p.try_tap()
            elif e.button == 3:
                p.set_hold(True)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 3:
            p.set_hold(False)
        elif e.type == pygame.MOUSEWHEEL:
            p.switch((p.active + (1 if e.y < 0 else -1)) % max(1, len(p.foci)))

    def _reward_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_1, pygame.K_2):
                idx = e.key - pygame.K_1
                if idx < len(self.reward_choices) and not self.reward_msg:
                    self.reward_msg = self.run.apply_reward(self.reward_choices[idx][0])
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE) and self.reward_msg:
                self.enter_forge()

    def _dead_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.running = False
            else:
                self.mode = "TITLE"

    # ---------------------------------------------------------------- update

    def update(self, dt):
        self.time += dt
        self.hint_t = max(0.0, self.hint_t - dt)
        self.shake = max(0.0, self.shake - dt * 3.0)

        if self.mode == "FORGE":
            self.forge.update(dt)
        elif self.mode == "FIELD":
            keys = pygame.key.get_pressed()
            move = pygame.Vector2(
                (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
                (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
            )
            p = self.field.player
            mouse = pygame.Vector2(pygame.mouse.get_pos())
            world_mouse = mouse + self.camera.pos - pygame.Vector2(WIDTH / 2, HEIGHT / 2)
            aim = world_mouse - p.pos
            if aim.length_squared() > 1e-6:
                p.aim = aim.normalize()

            before = p.hp
            n_before = len(self.field.enemies)
            self.field.update(dt, move)
            if p.hp < before - 0.5:
                self.shake = min(1.0, self.shake + 0.35)
                self.hitstop = max(self.hitstop, 0.035)
            if len(self.field.enemies) < n_before:
                self.shake = min(1.0, self.shake + 0.22)
                self.hitstop = max(self.hitstop, 0.05)

            for imp in self.field.impacts:
                self.impact_ages.setdefault(id(imp), 0.0)
            for k in list(self.impact_ages):
                self.impact_ages[k] += dt
                if self.impact_ages[k] > 0.4:
                    del self.impact_ages[k]
            self.field.impacts = [i for i in self.field.impacts if id(i) in self.impact_ages]

            self.camera.follow(p.pos + p.aim * 70, 0.10)

            if self.field.failed:
                self.mode = "DEAD"
            elif self.field.cleared:
                self.finish_room()

    # ------------------------------------------------------------------ draw

    def draw(self):
        if self.mode == "TITLE":
            self._draw_title()
        elif self.mode == "FORGE":
            self.forge.draw(self.screen)
        elif self.mode == "FIELD":
            self._draw_field()
        elif self.mode == "REWARD":
            self._draw_reward()
        elif self.mode == "DEAD":
            self._draw_dead()
        pygame.display.flip()

    # -- title ---------------------------------------------------------------

    def _draw_title(self):
        s = self.screen
        s.fill(BG)
        cx = WIDTH // 2
        s.blit(self.big.render("WAVEWRIGHT", True, (226, 236, 250)),
               (cx - 110, 190))
        lines = [
            "You do not cast spells. You build resonators and then play them.",
            "",
            "A ring's circumference sets its frequency. Frequency is colour.",
            "Colour is what a thing is weak to. Wind the ring the other way",
            "and every impulse it makes reverses.",
            "",
            "Nothing here is a lookup table. It is all one simulation.",
            "",
            f"codex: {len(self.codex.entries)} saved sigil(s)",
            "",
            "press any key",
        ]
        for i, line in enumerate(lines):
            col = TEXT if i < 7 else DIM
            r = self.font.render(line, True, col)
            s.blit(r, (cx - r.get_width() // 2, 260 + i * 22))

    # -- field ---------------------------------------------------------------

    def _draw_field(self):
        """Order matters here, and the reason is the whole look of the game.

        The arena is unlit. Everything visible is visible because something
        is radiating: your ink, a mote in flight, a fire you started. So the
        world and its actors are painted first, the darkness is laid over the
        top with holes punched where light sources are, and only the HUD and
        the off-screen markers sit above it — because information the player
        needs to survive must never be something the dark can hide."""
        s = self.screen
        s.fill(BG)
        f = self.field
        cam = self.camera
        if self.shake > 0:
            cam.pos += pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.shake * 9

        self._draw_grid(f.arena, cam)
        viz.draw_fields(s, f.grid, cam, self.time)

        for relay in f.relays:
            self._draw_relay(relay, f.player)
        for e in f.enemies:
            self._draw_enemy(e)
        for q in f.friendly:
            viz.draw_pulse(s, q, cam)
        for q in f.hostile:
            viz.draw_pulse(s, q, cam)
        for imp in f.impacts:
            viz.draw_impact(s, imp, cam, self.impact_ages.get(id(imp), 0.0))
        for pos, radius, colour, t in f.detonations:
            viz.draw_shockwave(s, cam.world_to_screen(pos), radius, colour, t / 0.42)

        self._draw_player(f.player)
        viz.draw_darkness(s, self._collect_lights(f))
        self._draw_offscreen_markers(f)
        self._draw_hud(f)

    def _collect_lights(self, f):
        """Every light in the room, and what it costs you.

        The player's own light grows with the charge in their sigil, which
        makes visibility and power the same resource. Creeping in the dark is
        safe and blind; winding up a capacitor turns you into a lantern in a
        room full of things that hunt by resonance. That tension is free —
        it falls straight out of drawing light from the simulation state
        rather than from a torch stat."""
        cam = self.camera
        lights = []
        p = f.player
        focus = p.focus
        charge = focus.charge_fraction() if focus is not None else 0.0
        sp = cam.world_to_screen(p.pos)
        lights.append((sp, 132 + 210 * charge, (255, 255, 255)))

        for q in f.friendly:
            if q.total > 0.02:
                lights.append((cam.world_to_screen(q.pos),
                               30 + 70 * min(1.0, q.total * 3), (255, 255, 255)))
        for q in f.hostile:
            if q.total > 0.05:
                lights.append((cam.world_to_screen(q.pos), 42, (255, 255, 255)))

        # Everything out there is a resonant object, so everything out there
        # glows a little — in its own band's colour. It keeps the dark from
        # being unfair without lighting the room, and it turns the colour
        # language into a horror mechanic: what you see first is a hue in the
        # black, and the hue already tells you what will kill it. A surging
        # one burns brighter, so the thing you have been feeding announces
        # itself before it reaches you.
        for e in f.enemies:
            glow = 54 + 26 * min(1.0, e.glut) + (34 if e.surge_t > 0 else 0)
            lights.append((cam.world_to_screen(e.pos), glow, band_color(e.resonance)))
        for pos, radius, _c, t in f.detonations:
            lights.append((cam.world_to_screen(pos), radius * (1.4 - t / 0.42), (255, 255, 255)))

        lights.extend(viz.field_lights(f.grid, cam, (WIDTH, HEIGHT)))
        return lights

    def _draw_grid(self, arena, cam):
        s = self.screen
        step = 128
        tl = cam.world_to_screen(pygame.Vector2(0, 0))
        x = tl.x % step
        while x < WIDTH:
            pygame.draw.line(s, GRID, (x, 0), (x, HEIGHT), 1)
            x += step
        y = tl.y % step
        while y < HEIGHT:
            pygame.draw.line(s, GRID, (0, y), (WIDTH, y), 1)
            y += step
        br = cam.world_to_screen(pygame.Vector2(arena.width, arena.height))
        pygame.draw.rect(s, (58, 68, 86), pygame.Rect(tl.x, tl.y, br.x - tl.x, br.y - tl.y), 2)

    def _draw_offscreen_markers(self, f):
        """An arena wider than the viewport means enemies spend real time
        outside it, and a player who cannot see what is left has no way to
        decide where to go. A chevron on the rim in the target's own band
        colour keeps both facts on screen at once: where it is, and what it
        will take."""
        s = self.screen
        margin = 34
        for e in f.enemies:
            p = self.camera.world_to_screen(e.pos)
            if -20 <= p.x <= WIDTH + 20 and -20 <= p.y <= HEIGHT + 20:
                continue
            cx, cy = WIDTH / 2, HEIGHT / 2
            d = pygame.Vector2(p.x - cx, p.y - cy)
            if d.length_squared() < 1e-6:
                continue
            d = d.normalize()
            # Push out to the rim rectangle rather than a circle, so markers
            # sit against the edge the enemy is actually beyond.
            scale = min(
                (WIDTH / 2 - margin) / abs(d.x) if abs(d.x) > 1e-6 else 1e9,
                (HEIGHT / 2 - margin) / abs(d.y) if abs(d.y) > 1e-6 else 1e9,
            )
            at = pygame.Vector2(cx, cy) + d * scale
            col = band_color(e.resonance)
            tip = at + d * 10
            left = at + pygame.Vector2(-d.y, d.x) * 7
            right = at + pygame.Vector2(d.y, -d.x) * 7
            pygame.draw.polygon(s, col, [tip, left, right])
            pygame.draw.circle(s, viz._lerp(BG, col, 0.35), (int(at.x), int(at.y)), 13, 1)

    def _draw_enemy(self, e):
        s = self.screen
        p = self.camera.world_to_screen(e.pos)
        if not (-80 < p.x < WIDTH + 80 and -80 < p.y < HEIGHT + 80):
            return

        body = (48, 54, 68)
        if e.temperature > 0.05:
            body = viz._lerp(body, (220, 90, 60), min(1.0, e.temperature))
        elif e.temperature < -0.05:
            body = viz._lerp(body, (90, 160, 240), min(1.0, -e.temperature))
        if e.hit_flash > 0:
            body = viz._lerp(body, (255, 255, 255), e.hit_flash * 0.55)

        if e.decohered:
            pygame.draw.circle(s, (200, 190, 255), (int(p.x), int(p.y)), int(e.radius) + 4, 1)

        # Wind-up. A committed attack has to be announced or dodging it is
        # luck: the ring collapses inward over the telegraph, so "it is about
        # to go" is readable from across the room without a health bar.
        if e.telegraph > 0.01:
            grow = int(e.radius + 26 * e.telegraph)
            pygame.draw.circle(s, (255, 236, 190), (int(p.x), int(p.y)), max(2, grow), 2)
            viz.draw_glow(s, p, 60, (255, 200, 120), e.telegraph * 0.8)

        pygame.draw.circle(s, body, (int(p.x), int(p.y)), int(e.radius))
        viz.draw_resonance_ring(s, p, e.radius, e.resonance, self.time + e.spin * 0.01)
        viz.hp_bar(s, (p.x, p.y - e.radius - 12), 40, max(0.0, e.hp / e.max_hp))

        # Glut: how much wrong-frequency energy it has swallowed. Drawn as an
        # arc filling around the body in its own resonance colour, so the
        # player watching their shots do nothing can see *why* — and can see
        # that continuing will make it worse.
        if e.glut > 0.02:
            r = int(e.radius + 9)
            rect = pygame.Rect(int(p.x) - r, int(p.y) - r, r * 2, r * 2)
            pygame.draw.arc(s, (255, 210, 120), rect,
                            -math.pi / 2, -math.pi / 2 + e.glut * math.tau, 3)
        if e.surge_t > 0:
            viz.draw_glow(s, p, int(e.radius * 3.4), (255, 170, 90),
                          0.35 + 0.25 * math.sin(self.time * 12))
        if e.temperature > 0.05:
            viz.draw_glow(s, p, int(e.radius * 2.6), (255, 120, 60),
                          min(0.9, e.temperature * 0.6))

        if e.sigil is not None:
            viz.draw_sigil(s, e.sigil, e.pos,
                           -e.aim.angle_to(pygame.Vector2(1, 0)),
                           viz.display_scale(e.sigil, 0.55),
                           alpha=0.85, show_nodes=False, width=2, camera=self.camera)

        # A bonded Choir draws its own standing wave, so the dangerous
        # antinode is visible before it hurts you.
        from .enemies import Choir

        if isinstance(e, Choir) and e.partner is not None and not e.partner.dead:
            if id(e) < id(e.partner):
                a = self.camera.world_to_screen(e.pos)
                b = self.camera.world_to_screen(e.partner.pos)
                env = e.beat_envelope()
                col = viz._lerp((40, 50, 70), (255, 140, 120), env)
                pygame.draw.line(s, col, a, b, max(1, int(1 + 5 * env)))

    def _draw_relay(self, relay, player):
        s = self.screen
        p = self.camera.world_to_screen(relay.pos)
        k = relay.coupling_to(player.pos)
        if k > 0.01:
            pp = self.camera.world_to_screen(player.pos)
            col = viz._lerp((26, 32, 44), (150, 200, 255), k * (0.5 + 0.5 * math.sin(self.time * 6)))
            pygame.draw.line(s, col, pp, p, max(1, int(1 + 3 * k)))
        viz.draw_sigil(s, relay.sigil, relay.pos, 0.0, viz.display_scale(relay.sigil, 0.8),
                       alpha=0.9, show_nodes=False, width=2, camera=self.camera)

    def _draw_player(self, p):
        s = self.screen
        sp = self.camera.world_to_screen(p.pos)
        focus = p.focus

        if focus is not None and not focus.is_empty:
            viz.draw_sigil(s, focus, p.pos, p.aim_deg, viz.display_scale(focus),
                           show_nodes=True, width=3, camera=self.camera)

        col = (130, 214, 226)
        if p.hurt_flash > 0:
            col = viz._lerp(col, (255, 120, 110), p.hurt_flash)
        if focus is not None and not focus.is_empty:
            viz.draw_glow(s, sp, int(p.radius * 3.2 + 90 * focus.charge_fraction()),
                          viz.sigil_hue(focus), 0.30 + 0.5 * focus.charge_fraction())
        if p.phase > 0.3:
            pygame.draw.circle(s, (210, 200, 255), (int(sp.x), int(sp.y)), int(p.radius + 5), 1)
        pygame.draw.circle(s, col, (int(sp.x), int(sp.y)), int(p.radius))
        tip = sp + p.aim * (p.radius + 12)
        pygame.draw.line(s, (200, 226, 240), sp + p.aim * p.radius, tip, 2)

        if focus is not None and focus.beat_period > 1e-6:
            viz.draw_beat_ring(s, sp, int(p.radius + 6), focus.beat_phase, focus.on_beat_flash)

    def _draw_hud(self, f):
        s = self.screen
        p = f.player

        viz.draw_meter(s, pygame.Rect(16, 16, 260, 14), p.hp / p.max_hp, (216, 88, 78))
        s.blit(self.small.render(f"{max(0, int(p.hp))}", True, (240, 200, 196)), (284, 16))
        viz.draw_meter(s, pygame.Rect(16, 36, 260, 8), p.mana / MANA_MAX, (110, 180, 240))

        # Focus strip: charge, char and beat for each carried instrument, so
        # switching is an informed decision rather than a guess.
        y = 60
        for i, sig in enumerate(p.foci):
            active = i == p.active
            box = pygame.Rect(16, y, 260, 40)
            pygame.draw.rect(s, (26, 30, 40) if active else (18, 20, 27), box)
            pygame.draw.rect(s, (110, 190, 220) if active else (44, 50, 62), box, 1)
            name = f"{i + 1} {sig.name[:14]}"
            s.blit(self.small.render(name, True, (226, 236, 248) if active else (128, 142, 162)),
                   (24, y + 4))
            # What kind of instrument this is, read off its topology. A
            # capacitor and an emitter are played completely differently, and
            # in the heat of a room the player needs that at a glance rather
            # than by remembering what they drew three rooms ago.
            if sig.is_capacitor:
                s.blit(self.small.render("CAP", True, (240, 190, 120)), (172, y + 4))
            elif not sig.terminals:
                s.blit(self.small.render("inert", True, (120, 128, 145)), (172, y + 4))
            if sig.barrier_strength > 0.3:
                s.blit(self.small.render("shield", True, (200, 210, 230)), (206, y + 4))
            bands = sig.measured_bands()
            centre, tot = dominant_band(bands)
            if tot > 1e-9:
                pygame.draw.circle(s, band_color(centre), (250, y + 11), 5)
            viz.draw_meter(s, pygame.Rect(24, y + 24, 110, 6), sig.charge_fraction(), (110, 190, 240))
            viz.draw_meter(s, pygame.Rect(140, y + 24, 110, 6), sig.char,
                           (255, 70, 60) if sig.disabled else (240, 150, 90))
            if sig.disabled:
                s.blit(self.small.render("BURNED OUT", True, (255, 110, 96)), (150, y + 3))
            y += 44

        target = f.scan_target()
        if target is not None:
            self._draw_target_panel(target, p)

        if f.banner_t > 0 and f.banner:
            a = min(1.0, f.banner_t / 1.2)
            r = self.font.render(f.banner, True, viz._lerp(BG, (240, 226, 170), a))
            s.blit(r, (WIDTH // 2 - r.get_width() // 2, 92))

        if self.hint_t > 0 and self.hint:
            a = min(1.0, self.hint_t / 2.0)
            for i, line in enumerate(_wrap(self.hint, 78)):
                r = self.small.render(line, True, viz._lerp(BG, (170, 196, 220), a))
                s.blit(r, (WIDTH // 2 - r.get_width() // 2, HEIGHT - 96 + i * 17))

        room = room_spec(self.run.room_index)
        s.blit(self.small.render(
            f"{room['name']}  -  depth {self.run.room_index + 1}  -  {len(f.enemies)} left",
            True, DIM), (WIDTH - 340, 18))
        s.blit(self.small.render(
            "LMB strike   RMB sustain   1-4 focus   SHIFT dash   E relay   Q RELEASE",
            True, (86, 98, 118)), (16, HEIGHT - 24))

    def _draw_target_panel(self, e, p):
        s = self.screen
        x, y = WIDTH - 340, 44
        pygame.draw.rect(s, (17, 19, 26), (x, y, 324, 96))
        pygame.draw.rect(s, (48, 56, 70), (x, y, 324, 96), 1)
        col = band_color(e.resonance)
        pygame.draw.circle(s, col, (x + 18, y + 18), 7)
        s.blit(self.font.render(e.label, True, (222, 232, 246)), (x + 34, y + 10))
        b = int(round(e.resonance))
        s.blit(self.small.render(
            f"rings at band {b} ({BAND_NAMES[b]})", True, col), (x + 34, y + 30))
        s.blit(self.small.render(e.lesson[:44], True, (132, 148, 170)), (x + 12, y + 52))

        focus = p.focus
        if focus is not None:
            from .combat import resonance_quality

            q = resonance_quality(focus.measured_bands(), e.vuln)
            s.blit(self.small.render(
                f"your current output matches {q * 100:.0f}%", True,
                (120, 220, 140) if q > 0.45 else (230, 160, 90)), (x + 12, y + 72))

    # -- reward / dead -------------------------------------------------------

    def _draw_reward(self):
        s = self.screen
        s.fill(BG)
        cx = WIDTH // 2
        s.blit(self.big.render("ROOM CLEARED", True, (226, 236, 250)), (cx - 130, 150))
        if not self.reward_msg:
            s.blit(self.font.render("choose one", True, DIM), (cx - 44, 200))
            for i, (_, label, desc) in enumerate(self.reward_choices):
                y = 250 + i * 90
                box = pygame.Rect(cx - 280, y, 560, 70)
                pygame.draw.rect(s, (19, 22, 29), box)
                pygame.draw.rect(s, (70, 82, 100), box, 1)
                s.blit(self.font.render(f"{i + 1}.  {label}", True, (226, 236, 250)),
                       (box.x + 20, box.y + 14))
                s.blit(self.small.render(desc, True, DIM), (box.x + 20, box.y + 42))
        else:
            for i, line in enumerate(_wrap(self.reward_msg, 60)):
                r = self.font.render(line, True, (200, 226, 190))
                s.blit(r, (cx - r.get_width() // 2, 260 + i * 24))
            r = self.font.render("ENTER to return to the forge", True, DIM)
            s.blit(r, (cx - r.get_width() // 2, 420))

    def _draw_dead(self):
        s = self.screen
        s.fill((16, 11, 13))
        cx = WIDTH // 2
        s.blit(self.big.render("BURNED OUT", True, (240, 150, 140)), (cx - 118, 220))
        lines = [
            f"depth reached: {self.run.deepest + 1}",
            f"codex: {len(self.codex.entries)} sigil(s) kept",
            "",
            "Your sigils survive. Understanding is the only thing that",
            "carries between runs, which is the only progression worth having.",
            "",
            "press any key",
        ]
        for i, line in enumerate(lines):
            r = self.font.render(line, True, TEXT if i < 2 else DIM)
            s.blit(r, (cx - r.get_width() // 2, 290 + i * 24))

    # ------------------------------------------------------------------ loop

    def run_loop(self):
        acc = 0.0
        while self.running:
            frame = min(self.clock.tick(120) / 1000.0, MAX_FRAME)
            self.handle_events()
            # Hitstop: freeze the simulation for a few frames on a heavy
            # landing while continuing to draw. It is the cheapest weight
            # there is — a hit that stops time reads as having mass, and one
            # that does not reads as a number going down.
            if self.hitstop > 0:
                self.hitstop = max(0.0, self.hitstop - frame)
                acc = min(acc, FIXED_DT)
            acc += frame
            steps = 0
            while acc >= FIXED_DT and steps < 8 and self.hitstop <= 0:
                self.update(FIXED_DT)
                acc -= FIXED_DT
                steps += 1
            if steps >= 8:
                acc = 0.0
            self.draw()
        self.codex.save()
        pygame.quit()


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def main():
    App().run_loop()
