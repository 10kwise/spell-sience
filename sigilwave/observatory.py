"""Watch the ocean. RIGS.md 13.

    python -m sigilwave.observatory

This is not the game and it is not the game loop. It is the thing that has to
exist before either, because every claim this project makes is currently a
number in a test report, and **a number is not a thing anybody can have an
opinion about.** RIGS.md 12 is explicit that the second go/no-go -- can a
person watch this and work out what is happening -- is the one a machine
cannot answer. This is the window that question gets asked through.

So it shows the simulation and nothing else. No objectives, no score, no
failure. You can swim, you can look, and you can drop a body in the water and
see what comes.

WHAT TO LOOK AT
---------------
Press 2 for `nutrient` and turn the time up. Within a minute the decomposers
have found the seeps, and within two the whole web is stacked on top of them:
scavengers and decomposers ON the seep, drifters around them, grazers held off
at a distance by the hunters sitting in the middle. Nothing in `creatures.py`
knows what a seep is. They are all just climbing the gradient of their own
comfort, and the food happens to come from three places.

Then press SPACE somewhere empty and watch what a carcass does. That is
RIGS.md 13.4's "death is a resource that propagates" -- the chum plume goes
DOWNTIDE rather than outward (press 1 to see it), the scavengers arrive first
because they smell it furthest, and everything else follows them in.

Then hold G with the heater selected and watch the stalkers turn toward you.
That is RIGS.md 9's whole argument in one gesture: the same field your rig
writes into is the field something else is reading.
"""

import math
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

from .diver import KICK, V, Diver
from .medium.field import Medium
from .rig import creatures as C
from .rig.chain import Chain, ambient_at
from .rig.couple import ambient_from, apply as couple_apply, report as rig_report
from .rig.library import PRESETS
from .rig.station import Station
from .sources import Economy, Vent

WORLD_W, WORLD_H = 1200, 800
TOPBAR = 78
WIN_W, WIN_H = WORLD_W, WORLD_H + TOPBAR

SIM_DT = 1.0 / 30.0          # creatures and the diver
MEDIUM_EVERY = 2             # so the medium runs at 15 Hz -- RIGS.md 13.7
SPEEDS = (1, 2, 4, 8, 16, 32)

# How long a frame is allowed to spend simulating before it gives up and draws
# anyway, in milliseconds.
#
# One sim tick costs about 2.6 ms with seventy creatures in the water, so 32x
# would be 83 ms a frame and the window would stop answering the keyboard.
# Time acceleration is what makes this thing watchable at all -- aggregation
# takes minutes -- so the speed setting is a REQUEST and this is the ceiling.
# The bar prints what was actually achieved, so a speed that cannot be reached
# says so rather than silently lying.
FRAME_BUDGET_MS = 13.0

INK = (232, 240, 242)
DIM = (128, 150, 158)
FAINT = (78, 96, 104)
BAR = (16, 24, 29)

# A channel is drawn as light added to the water, so the ocean shows through
# it. The knee is where the ramp is half bright: channels live between about
# 0.01 and 10, so a linear ramp shows nothing at the bottom and saturates at
# the top, and v/(v+k) is readable across the whole range.
# One knee per channel, because they do not live on the same scale: bloom
# peaks around 0.1 and nutrient around 3, so a single knee either blows out the
# top of one or shows nothing at all of the other.
CHANNEL_KNEE = {
    "chum": 0.12, "nutrient": 0.45, "bloom": 0.06,
    "swarm": 0.30, "shoal": 0.35, "menace": 0.25,
}
CHANNELS = ("chum", "nutrient", "bloom", "swarm", "shoal", "menace")
CHANNEL_COLOUR = {
    "chum":     (190, 70, 40),
    "nutrient": (150, 140, 60),
    "bloom":    (60, 170, 90),
    "swarm":    (60, 160, 175),
    "shoal":    (90, 140, 220),
    "menace":   (185, 60, 150),
}
SPECIES_COLOUR = {
    "scavenger": (255, 168, 64),
    "decomposer": (206, 198, 96),
    "drifter": (126, 232, 168),
    "grazer": (150, 226, 250),
    "hunter": (255, 84, 66),
    "stalker": (255, 130, 210),
}
# In pixels. Everything was 2.6-6 px in the first pass and the ecosystem was
# invisible from a normal viewing distance, which defeats the point of the
# window. A hunter has to read as a different KIND of thing at a glance, not
# as a slightly larger dot.
SPECIES_SIZE = {
    "scavenger": 5.0, "decomposer": 4.4, "drifter": 3.8,
    "grazer": 4.2, "hunter": 9.0, "stalker": 7.5,
}

SEEDS = ((250.0, 640.0), (930.0, 470.0), (600.0, 250.0))
COUNTS = {"scavenger": 10, "decomposer": 12, "drifter": 18, "grazer": 22, "hunter": 5}

RIGS = ("the thruster", "the heater", "the cooler", "the lamp", "the tap")


def _font(size, bold=False):
    return pygame.font.SysFont("consolas,dejavusansmono,monospace", size, bold=bold)


class Observatory:
    def __init__(self):
        self.med = Medium(WORLD_W, WORLD_H)
        C.install_channels(self.med)

        self.station = Station((150.0, 210.0))
        self.vent = Vent((930.0, 470.0))
        self.seeps = [C.Seep(p) for p in SEEDS]
        self.carcasses = []

        self.rng = np.random.default_rng(7)
        self.packs = {}
        for kind, n in COUNTS.items():
            self.packs[kind] = [
                C.make_cycle(kind, (float(self.rng.uniform(60, WORLD_W - 60)),
                                    float(self.rng.uniform(60, WORLD_H - 60))))
                for _ in range(n)
            ]
        # A few heat-hunters, so that running a rig has a visible audience.
        self.packs["stalker"] = [
            C.make("stalker", (float(self.rng.uniform(60, WORLD_W - 60)),
                               float(self.rng.uniform(60, WORLD_H - 60))))
            for _ in range(4)
        ]

        self.diver = Diver((200.0, 240.0))
        self.economy = Economy()

        self.presets = {p.name: p for p in PRESETS}
        self.rig_i = 0
        self.results = {}
        for name in RIGS:
            self.results[name] = self.presets[name].build().evaluate(ambient_at(240.0))

        self.channel = "nutrient"
        self.show_flow = False
        self.show_help = False
        self.paused = False
        self.speed_i = 2
        self.running_rig = False
        self.elapsed = 0.0
        self._tick = 0
        self._note = "press H for the controls"
        self.achieved = 0

        # Let the ocean settle before anybody looks at it.
        for _ in range(240):
            self.station.warm(self.med, 1 / 15.0)
            self.vent.warm(self.med, 1 / 15.0)
            self.med.step(1 / 15.0)

    # --- the simulation ---------------------------------------------------

    @property
    def rig_name(self):
        return RIGS[self.rig_i]

    def sim(self, dt, keys):
        self.elapsed += dt
        self._tick += 1

        C.snowfall(self.med, dt, self.rng)
        for s in self.seeps:
            s.step(dt, self.med)
        for b in self.carcasses:
            b.step(dt, self.med)
        self.carcasses = [b for b in self.carcasses if not b.spent]

        self.station.warm(self.med, dt)
        self.vent.warm(self.med, dt)

        sounds = [(self.station.pos.x, self.station.pos.y, 117.0, 1.0)]
        for kind, pack in self.packs.items():
            for c in pack:
                c.step(dt, self.med, sounds)

        # What the player is doing.
        thrust = V(0.0, 0.0)
        d = V(0.0, 0.0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            d.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            d.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            d.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            d.y += 1
        if d.length_squared() > 0:
            d = d.normalize()
            self.diver.aim = V(d)
            thrust = self.diver.rig_thrust(self.results["the thruster"], d)

        kick = V(0.0, 0.0)
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            aim = self.diver.aim if self.diver.aim.length_squared() else V(1, 0)
            kick = aim * KICK

        if keys[pygame.K_r]:
            self.diver.set_trim(-1.0)
        elif keys[pygame.K_f]:
            self.diver.set_trim(1.0)
        else:
            self.diver.set_trim(0.0)

        self.diver.step(dt, self.med, thrust=thrust, kick=kick,
                        bounds=(WORLD_W, WORLD_H), economy=self.economy)

        if self.running_rig and self.rig_name != "the thruster":
            couple_apply(self.results[self.rig_name], self.med,
                         self.diver.pos.x, self.diver.pos.y, dt)

        self.station.resupply(self.diver.pos, self.economy, dt)

        if self._tick % MEDIUM_EVERY == 0:
            self.med.step(dt * MEDIUM_EVERY)

    # --- drawing ----------------------------------------------------------

    def _water(self):
        med = self.med
        t = med.temp
        lo, hi = float(t.min()), float(t.max())
        n = (t - lo) / max(hi - lo, 0.5)

        # Warm water goes green, not red. The first palette added red with
        # temperature, which made the warm surface layer brown and the whole
        # ocean look like soil -- the stratification was legible and it did
        # not read as water, which for a window whose entire job is being
        # looked at is the same as being wrong.
        rgb = np.empty((med.ny, med.nx, 3), dtype=np.float32)
        rgb[..., 0] = 9.0 + 16.0 * n
        rgb[..., 1] = 24.0 + 40.0 * n
        rgb[..., 2] = 46.0 + 26.0 * n

        if self.channel:
            f = med.channels[self.channel]
            s = f / (f + CHANNEL_KNEE[self.channel])
            col = CHANNEL_COLOUR[self.channel]
            for i in range(3):
                rgb[..., i] += s * col[i]
            # A faint floor under any cell carrying anything at all, so the
            # edge of a plume is visible rather than fading into the water.
            edge = (f > 0.0) & (s < 0.12)
            for i in range(3):
                rgb[..., i][edge] += col[i] * 0.10

        rgb[med.solid] = (46, 42, 38)
        np.clip(rgb, 0, 255, out=rgb)
        surf = pygame.surfarray.make_surface(
            rgb.astype(np.uint8).transpose(1, 0, 2))
        return pygame.transform.smoothscale(surf, (WORLD_W, WORLD_H))

    def _flow(self, screen):
        u, v = self.med.flow_field
        cs = self.med.cell_size
        for r in range(0, self.med.ny, 3):
            for c in range(0, self.med.nx, 3):
                if self.med.solid[r, c]:
                    continue
                x = (c + 0.5) * cs
                y = (r + 0.5) * cs + TOPBAR
                ux, vy = float(u[r, c]), float(v[r, c])
                m = math.hypot(ux, vy)
                if m < 0.03:
                    continue
                k = min(22.0, m * 3.0)
                shade = min(1.0, m / 5.0)
                col = (int(60 + 90 * shade), int(100 + 70 * shade),
                       int(130 + 50 * shade))
                pygame.draw.line(screen, col, (x, y),
                                 (x + ux / m * k, y + vy / m * k), 1)

    def _creatures(self, screen):
        for kind, pack in self.packs.items():
            col = SPECIES_COLOUR[kind]
            base = SPECIES_SIZE[kind]
            for c in pack:
                x, y = int(c.pos[0]), int(c.pos[1]) + TOPBAR
                cond = getattr(c, "condition", 1.0)
                r = max(2, int(base * (0.62 + 0.38 * cond)))
                shade = tuple(int(v * (0.55 + 0.45 * cond)) for v in col)
                # A dark rim first, so a creature reads against bright water
                # and against a bright channel alike.
                pygame.draw.circle(screen, (6, 12, 16), (x, y), r + 2)
                pygame.draw.circle(screen, shade, (x, y), r)
                if kind in ("hunter", "stalker"):
                    pygame.draw.circle(screen, col, (x, y), r + 5, 1)
                if cond < 0.25:
                    pygame.draw.circle(screen, (90, 90, 96), (x, y), r + 3, 1)

    def _things(self, screen, small):
        for s in self.seeps:
            x, y = int(s.pos[0]), int(s.pos[1]) + TOPBAR
            pygame.draw.circle(screen, (120, 190, 140), (x, y), 11, 2)
            pygame.draw.circle(screen, (60, 110, 80), (x, y), 4)
        for b in self.carcasses:
            x, y = int(b.pos[0]), int(b.pos[1]) + TOPBAR
            frac = b.yield_left / C.CARCASS_YIELD
            pygame.draw.circle(screen, (210, 90, 60), (x, y), 5)
            pygame.draw.circle(screen, (250, 170, 120), (x, y),
                               int(5 + 9 * frac), 1)

        vx, vy = int(self.vent.pos.x), int(self.vent.pos.y) + TOPBAR
        pygame.draw.circle(screen, (232, 120, 70), (vx, vy), 9, 2)
        screen.blit(small.render("vent", True, (232, 120, 70)), (vx + 13, vy - 7))

        sx, sy = int(self.station.pos.x), int(self.station.pos.y) + TOPBAR
        pygame.draw.rect(screen, (120, 200, 165), (sx - 13, sy - 10, 26, 20), 2)
        pygame.draw.circle(screen, (60, 120, 100), (sx, sy),
                           int(self.station.dock_radius), 1)
        screen.blit(small.render("station", True, (120, 200, 165)), (sx + 20, sy - 7))

    def _diver(self, screen):
        p = self.diver.pos
        x, y = int(p.x), int(p.y) + TOPBAR
        aim = self.diver.aim if self.diver.aim.length_squared() else V(1, 0)
        col = (250, 226, 140) if self.running_rig else INK
        pygame.draw.circle(screen, col, (x, y), 6)
        pygame.draw.line(screen, col, (x, y),
                         (x + aim.x * 17, y + aim.y * 17), 2)
        flow = self.diver.flow(self.med)
        if flow.length() > 0.05:
            pygame.draw.line(screen, (90, 150, 200), (x, y),
                             (x + flow.x * 6, y + flow.y * 6), 1)
        if self.running_rig:
            pygame.draw.circle(screen, (250, 200, 120), (x, y), 14, 1)

    def _bar(self, screen, font, small):
        pygame.draw.rect(screen, BAR, (0, 0, WIN_W, TOPBAR))
        pygame.draw.line(screen, (40, 56, 64), (0, TOPBAR), (WIN_W, TOPBAR))

        # Three rows that do not share a column. The first version put the
        # species key and the diver's stats on the same line and they
        # overlapped, which in a window whose only job is legibility is not a
        # cosmetic problem.
        want = SPEEDS[self.speed_i]
        head = f"THE OCEAN   t+{self.elapsed:.0f}s   x{want}"
        if self.paused:
            head += "   PAUSED"
        screen.blit(font.render(head, True, INK), (14, 7))
        x = 14 + font.size(head)[0] + 18
        if not self.paused and self.achieved < want:
            msg = f"really x{self.achieved}"
            screen.blit(small.render(msg, True, (210, 160, 90)), (x, 10))
            x += small.size(msg)[0] + 18

        chan = self.channel or "none"
        screen.blit(small.render("showing", True, FAINT), (x, 10))
        screen.blit(small.render(chan, True, CHANNEL_COLOUR.get(self.channel, DIM)),
                    (x + small.size("showing ")[0], 10))

        rc = (250, 226, 140) if self.running_rig else DIM
        rig = f"[{self.rig_name}]" + ("  RUNNING" if self.running_rig else "")
        screen.blit(small.render(rig, True, rc), (WIN_W - 14 - small.size(rig)[0], 10))

        d = self.diver
        stats = (f"depth {d.pos.y:4.0f} m    over ground {d.speed:5.1f}    "
                 f"through water {d.speed_through_water(self.med):5.1f} px/s    "
                 f"trim {d.trim:+.2f}    air {self.economy.air:5.1f}    "
                 f"pack {self.economy.charge:5.2f}    "
                 f"{self.station.distance_to(d.pos):4.0f} m from home")
        if self.station.docked(d.pos):
            stats += "   DOCKED"
        screen.blit(small.render(stats, True, DIM), (14, 32))

        # The counts double as the key: same colour on the bar as in the water.
        x = 14
        for kind in ("scavenger", "decomposer", "drifter", "grazer",
                     "hunter", "stalker"):
            col = SPECIES_COLOUR[kind]
            pygame.draw.circle(screen, col, (x + 4, 60), 4)
            label = f"{kind} {len(self.packs[kind])}"
            screen.blit(small.render(label, True, col), (x + 13, 53))
            x += 26 + small.size(label)[0]
        note = self._note
        screen.blit(small.render(note, True, FAINT),
                    (WIN_W - 14 - small.size(note)[0], 53))

    def _help(self, screen, font, small):
        w, h = 640, 430
        x, y = (WIN_W - w) // 2, (WIN_H - h) // 2
        panel = pygame.Surface((w, h))
        panel.set_alpha(242)
        panel.fill((12, 18, 22))
        screen.blit(panel, (x, y))
        pygame.draw.rect(screen, (60, 84, 94), (x, y, w, h), 1)

        lines = [
            ("THE OCEAN -- controls", None),
            ("", None),
            ("WASD / arrows", "swim (a real rig's thrust, against real drag)"),
            ("shift", "kick. Deliberately feeble -- RIGS.md 12.7"),
            ("R / F", "trim up / down. Slow, silent, and free to hold"),
            ("", None),
            ("SPACE", "drop a carcass where you are"),
            ("left click", "drop a carcass there"),
            ("right click", "put a seep there"),
            ("G", "run the selected rig into the water"),
            ("[ / ]", "choose a rig"),
            ("", None),
            ("1-6", "show chum / nutrient / bloom / swarm / shoal / menace"),
            ("0", "show no channel, just the water"),
            ("C", "currents on / off"),
            ("T", "time: 1x 2x 4x 8x 16x 32x"),
            ("P", "pause"),
            ("H", "this"),
            ("", None),
            ("Try: press 2, press T a few times, and wait.", None),
            ("Then SPACE somewhere empty and press 1.", None),
        ]
        yy = y + 18
        for a, b in lines:
            if b is None:
                screen.blit((font if a.startswith("THE") else small).render(
                    a, True, INK if a.startswith("THE") else (190, 200, 205)),
                    (x + 22, yy))
            else:
                screen.blit(small.render(a, True, (250, 226, 140)), (x + 22, yy))
                screen.blit(small.render(b, True, DIM), (x + 168, yy))
            yy += 19

    def draw(self, screen, font, small):
        screen.blit(self._water(), (0, TOPBAR))
        if self.show_flow:
            self._flow(screen)
        self._things(screen, small)
        self._creatures(screen)
        self._diver(screen)
        self._bar(screen, font, small)
        if self.show_help:
            self._help(screen, font, small)

    # --- input ------------------------------------------------------------

    def key(self, k):
        if k == pygame.K_h:
            self.show_help = not self.show_help
        elif k == pygame.K_p:
            self.paused = not self.paused
        elif k == pygame.K_c:
            self.show_flow = not self.show_flow
        elif k == pygame.K_t:
            self.speed_i = (self.speed_i + 1) % len(SPEEDS)
        elif k == pygame.K_g:
            self.running_rig = not self.running_rig
            self._note = (f"running {self.rig_name} into the water"
                          if self.running_rig else "rig off")
        elif k == pygame.K_SPACE:
            self.carcasses.append(C.Carcass(pos=(self.diver.pos.x, self.diver.pos.y)))
            self._note = "a body. press 1 to watch the chum go downtide"
        elif k == pygame.K_LEFTBRACKET:
            self.rig_i = (self.rig_i - 1) % len(RIGS)
        elif k == pygame.K_RIGHTBRACKET:
            self.rig_i = (self.rig_i + 1) % len(RIGS)
        elif k == pygame.K_0:
            self.channel = None
        elif pygame.K_1 <= k <= pygame.K_6:
            self.channel = CHANNELS[k - pygame.K_1]

    def click(self, pos, button):
        x, y = pos[0], pos[1] - TOPBAR
        if y < 0:
            return
        if button == 1:
            self.carcasses.append(C.Carcass(pos=(float(x), float(y))))
            self._note = "a body. the scavengers smell it furthest"
        elif button == 3:
            self.seeps.append(C.Seep((float(x), float(y))))
            self._note = "a seep. the food web will find it"


def main():
    pygame.init()
    pygame.display.set_caption("RIGS -- the ocean")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    font = _font(18, True)
    small = _font(14)

    obs = Observatory()
    print("the ocean is settling...")
    print("H for controls. Press 2, then T a few times, and watch.")

    alive = True
    while alive:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                alive = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    alive = False
                else:
                    obs.key(e.key)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                obs.click(e.pos, e.button)

        keys = pygame.key.get_pressed()
        done = 0
        if not obs.paused:
            want = SPEEDS[obs.speed_i]
            t0 = time.perf_counter()
            while done < want:
                obs.sim(SIM_DT, keys)
                done += 1
                if (time.perf_counter() - t0) * 1000.0 > FRAME_BUDGET_MS:
                    break
        obs.achieved = done

        obs.draw(screen, font, small)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
