"""SUBMERGED -- the running demo.

One screen, both halves. You draw a machine on the bench at the left; its
mouths radiate into the ocean at the right; the ocean bends what they emit
and lights the rock it touches. Energy comes out of the water when you stand
near a vent and out of your lungs when you do not.

The bench is a separate panel and not drawn in the water on purpose. 7.4a
pins two scales: the world is one pixel per metre because 7.3's sound channel
needs a kilometre of column, and a machine is an instrument you hold, so one
bench pixel is a centimetre. Drawn to scale in the world a hum loop would be
three pixels across. The panel is the honest way to show something 375 times
smaller than the room it is standing in.

    python -m sigilwave.dive_app
"""

import math

import pygame

from .bench.cavitation import Cavitation
from .bench.mouths import WATER_FREQ_RATIO, Emitter, aperture_wavelengths
from .bench.parts import DRAWABLE_RUNGS, MIN_RUN_LENGTH, SIM_DT, Assembly, snap_radius
from .bench.advice import diagnose
from .bench.gadgets import COUPLING_RANGE, ORDER as GADGET_ORDER, Rack
from .bench.presets import PRESETS, build as build_preset
from .bench.pulse import pulse_samples_directed
from .digging import Seams
from .diver import KICK, KICK_AIR_PER_SEC, THRUST_PER_ENERGY, Diver
from .sources import Body, Economy, Vent
from .stage import world
from .stage.app import TIME_SCALES, Renderer, tone

BENCH_W = 360
WIDTH, HEIGHT = BENCH_W + world.WIDTH, world.HEIGHT
MAX_FRONTS = 18

# Above the seabed, not in it. A vent's plume is what you stand in;
# a vent buried at floor level puts the diver on the rock, where every
# front born dies against it in the first metre.
VENTS = ((262.0, 636.0), (1010.0, 496.0))

GADGET_COLOUR = {"propeller": (140, 200, 255), "lamp": (255, 226, 150),
                 "gill": (150, 235, 190), "drill": (245, 160, 120)}
ADVICE_COLOUR = {"dead": (240, 120, 110), "wasteful": (240, 190, 110),
                 "fine": (140, 165, 190), "good": (140, 215, 165)}
TEXT = (108, 132, 158)
TEXT_HI = (198, 218, 236)
WIRE = (60, 74, 94)


def _blit_seams(surface, dive):
    """Rock, lit by how well your ping suits it. A wall you have merely seen
    is dim; a wall you have identified is bright, and the difference is the
    only identify interface there is."""
    lit = dive.seams.lit
    if lit.max() <= 0.01:
        return
    k = np.clip(lit, 0.0, 1.0)
    rgb = np.zeros((k.shape[0], k.shape[1], 3), dtype=np.uint8)
    rgb[..., 0] = (k * 236).astype(np.uint8)
    rgb[..., 1] = (k * 188).astype(np.uint8)
    rgb[..., 2] = (k * 118).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
    surface.blit(pygame.transform.smoothscale(surf, surface.get_size()),
                 (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def _wrap(screen, font, text, pos, width, colour):
    """Advice is sentences, and a sentence that runs off the panel is not a
    sentence anybody reads."""
    x, y = pos
    words = text.split()
    line = ""
    for w in words:
        trial = (line + " " + w).strip()
        if font.size(trial)[0] > width and line:
            screen.blit(font.render(line, True, colour), (x, y))
            y += 14
            line = w
        else:
            line = trial
    if line:
        screen.blit(font.render(line, True, colour), (x, y))
        y += 14
    return y


class _StageView:
    """The stage renderer wants a stage. This is one, backed by the rig."""

    def __init__(self, dive):
        self.dive = dive

    @property
    def medium(self):
        return self.dive.medium

    @property
    def fronts(self):
        return self.dive.fronts

    @property
    def diver(self):
        return self.dive.diver.pos

    @property
    def aim(self):
        return self.dive.aim

    @property
    def show_field(self):
        return self.dive.show_field


class Dive:
    def __init__(self):
        self.medium = world.build()
        self.assembly = Assembly()
        self.economy = Economy()
        self.body = Body()
        self.vents = [Vent(p) for p in VENTS]
        self.diver = Diver((430.0, 470.0))
        self.aim = pygame.Vector2(1.0, 0.0)
        self.kick = pygame.Vector2(0.0, 0.0)
        self.fronts = []
        self.show_field = False
        self.scale_index = 2
        self.driving = False
        self.tool = "run"
        self.drag_from = None
        self.drag_to = None
        self.note = "press F1-F8 to load a machine, then hold RMB to drive it"
        self.rack = Rack()
        self.lamp_light = 0.0
        self.seams = Seams(self.medium)
        self.broke = 0
        self.gadget_kind = 0
        # The note you are driving at. Hardcoded at 900 Hz in the first pass,
        # which is outside a propeller's band AND a gill's, so every gadget
        # correctly refused every machine and the whole layer looked broken.
        # Choosing the note is the player's central act (8.5) -- it is what
        # decides which device your machine can run at all.
        self.drive_hz = 900.0
        self.preset = None
        self.advice = []
        self._advice_at = -1
        self._rebuild()
        self._carry = 0.0
        self.steps = 0

    # -- the machine ---------------------------------------------------
    def _rebuild(self):
        self.network = self.assembly.compile() if self.assembly.parts else None
        self.cavitation = Cavitation(self.network) if self.network else None
        self.emitter = Emitter(self.assembly, self.network) if self.network else None
        self.note = self.assembly.describe() if self.assembly.parts else self.note
        # The whole point of the advice layer is that "why did that not work"
        # is answerable while drawing, so it is recomputed on every edit
        # rather than on request.
        self.advice = diagnose(self.assembly, self.network, self.emitter)

    def load_preset(self, index):
        if not (0 <= index < len(PRESETS)):
            return
        self.preset = PRESETS[index]
        self.assembly = build_preset(self.preset.name)
        self.drive_hz = self.preset.drive_hz
        self._rebuild()
        self.note = self.preset.summary

    def tune(self, step):
        """Walk the note ladder. The rungs are the loops a hand can draw, so
        tuning by rung means the note you pick is always one some loop in the
        drawing can actually be."""
        ladder = [r.note_hz * WATER_FREQ_RATIO for r in DRAWABLE_RUNGS]
        ladder = sorted(ladder)
        i = min(range(len(ladder)),
                key=lambda k: abs(ladder[k] - self.drive_hz))
        self.drive_hz = ladder[min(max(i + step, 0), len(ladder) - 1)]

    def begin(self, pos):
        self.drag_from = pygame.Vector2(pos)
        self.drag_to = pygame.Vector2(pos)

    def commit(self):
        if self.drag_from is None:
            return
        a, b = self.drag_from, self.drag_to
        self.drag_from = self.drag_to = None
        if self.tool == "run":
            if (b - a).length() >= MIN_RUN_LENGTH:
                self.assembly.add_run(a, b)
        else:
            r = (b - a).length()
            if r >= DRAWABLE_RUNGS[-1].radius * 0.4:
                self.assembly.add_loop(a, r)
        self._rebuild()

    def erase(self, pos):
        p = pygame.Vector2(pos)
        best, bd = None, 20.0
        for part in self.assembly.parts:
            for q in part.points():
                d = (pygame.Vector2(q) - p).length()
                if d < bd:
                    best, bd = part.part_id, d
        if best is not None:
            self.assembly.remove(best)
            self._rebuild()

    @property
    def time_scale(self):
        return TIME_SCALES[self.scale_index]

    def feed_node(self):
        graph = self.assembly.to_graph()
        if not graph.nodes:
            return None
        return min(graph.nodes.items(), key=lambda kv: kv[1].pos[0])[0]

    # -- the world -----------------------------------------------------
    def step(self, dt):
        sim_dt = dt * self.time_scale
        for v in self.vents:
            v.warm(self.medium, sim_dt)

        drive = 0.0
        if self.driving and self.network is not None:
            want = 0.55
            drive, _shortfall = self.economy.draw_energy(
                want, [self.body] + self.vents, self.diver.pos, dt)
            if self.economy.drowning:
                drive = 0.0

        born = []
        thrust_x = thrust_y = 0.0
        self.rack.step(self.emitter, dt)
        if self.network is not None:
            # The MACHINE runs at its own rate, not the water's. Slow motion
            # exists so a wavefront can be watched crossing a room; a
            # waveguide's samples are far too small to watch, and slowing
            # them only starves the machine -- tied to the water's scale a
            # 234 Hz note took eight seconds of wall clock per cycle, so the
            # note could not be measured and every gadget refused a machine
            # that was driving it correctly. The note is unaffected:
            # frequency is counted in bench steps and converted by a fixed
            # ratio, so running more of them per frame changes how fast the
            # machine lives, not what pitch it plays.
            self._carry += dt / SIM_DT
            n = min(int(self._carry), 40)
            self._carry -= n
            feed = self.feed_node()
            for _ in range(n):
                inj = None
                if drive > 0.0 and feed is not None:
                    period = max(3.0, 1.0 / ((self.drive_hz / WATER_FREQ_RATIO)
                                             * SIM_DT))
                    inj = {feed: drive * math.sin(
                        2.0 * math.pi * self.steps / period)}
                self.cavitation.step()
                self.network.step(inj)
                self.steps += 1
                for front in self.emitter.step():
                    self.fronts.append(self._place(front))
                    born.append(front)
                tx, ty = self.emitter.thrust_now
                # The aperture points along the machine's own frame; the
                # machine is in the diver's hands, so rotate it onto the aim.
                ax, ay = self.aim.x, self.aim.y
                thrust_x += tx * ax - ty * ay
                thrust_y += tx * ay + ty * ax

        # 8: propulsion is DRAWN. Every front a mouth throws pushes back, and
        # that reaction -- not a movement key -- is how a diver gets anywhere.
        thrust = pygame.Vector2(thrust_x, thrust_y) * (THRUST_PER_ENERGY / max(dt, 1e-6))
        # Gadgets are the other end of the wire (8.5). A propeller converts
        # what it is fed into a shove far more efficiently than raw radiation
        # pressure does, a gill hands back air, and a lamp lights the room.
        for g in self.rack.gadgets:
            if not g.running:
                continue
            if g.kind == "propeller":
                thrust += self.aim * (g.output * 90000.0)
            elif g.kind == "gill":
                self.economy.air = min(100.0, self.economy.air + g.output * 40.0 * dt)
            elif g.kind == "drill":
                # A drill only concentrates what it is fed; finding the
                # rock's note is still the player's problem.
                out = max(self.emitter.groups, key=lambda a: a.centre.x)
                tip = self.diver.pos + self.aim * 26.0
                self.broke = self.seams.strike(
                    tip.x, tip.y, 30.0, out.last_freq, g.output * 60.0, dt)
        self.lamp_light = sum(g.output for g in self.rack.gadgets
                              if g.kind == "lamp" and g.running)
        if self.kick.length_squared() > 1e-9:
            self.economy.air = max(0.0, self.economy.air
                                   - KICK_AIR_PER_SEC * dt)
        kick = self.kick * (KICK if not self.economy.drowning else 0.0)
        self.diver.aim = self.aim
        self.diver.last_thrust = thrust
        self.diver.step(dt, self.medium, thrust=thrust, kick=kick,
                        bounds=(world.WIDTH, world.HEIGHT))

        # Rock answers a ping brighter when the note suits it (8, step 7).
        # This is the whole identify layer: no readout, just a wall that
        # lights up more when you are asking it the right question.
        self.seams.fade()
        for f in self.fronts:
            verts = f.vertices
            if not verts:
                continue
            xs = [v.pos[0] for v in verts]
            ys = [v.pos[1] for v in verts]
            self.seams.light(xs, ys, f.freq, 1.0)

        self.medium.step(sim_dt)
        for f in self.fronts:
            f.step(self.medium, sim_dt)
        self.fronts = [f for f in self.fronts if not f.is_dead()]
        if len(self.fronts) > MAX_FRONTS:
            self.fronts = self.fronts[-MAX_FRONTS:]

    def _place(self, front):
        """A front is born in the frame of the mouth that made it. It enters
        the world at the diver, pointing where the diver points -- the
        machine is in their hands, not bolted to the bench."""
        offset = self.diver.pos + self.aim * 14.0
        return front.place((offset.x, offset.y), (self.aim.x, self.aim.y))

    def power_here(self) -> float:
        return sum(v.available_at(self.diver.pos) for v in self.vents)


def draw_bench(screen, dive, font, small):
    pygame.draw.rect(screen, (7, 9, 14), (0, 0, BENCH_W, HEIGHT))
    pygame.draw.line(screen, (30, 40, 54), (BENCH_W, 0), (BENCH_W, HEIGHT))

    for part in dive.assembly.parts:
        pts = [(int(p[0]), int(p[1])) for p in part.points()]
        if len(pts) > 1 and pts[0][0] < BENCH_W:
            pygame.draw.lines(screen, WIRE, part.kind == "loop", pts, 2)

    for pos_a, pos_b, _gap in dive.assembly.gaps():
        pygame.draw.line(screen, (170, 84, 132),
                         (int(pos_a[0]), int(pos_a[1])),
                         (int(pos_b[0]), int(pos_b[1])), 1)
    for pos in dive.assembly.forks():
        pygame.draw.circle(screen, (235, 176, 92), (int(pos[0]), int(pos[1])), 4)

    if dive.emitter is not None:
        for g in dive.emitter.groups:
            for p in g.positions:
                pygame.draw.circle(screen, (120, 220, 235), (int(p.x), int(p.y)), 5, 2)
            if len(g.positions) > 1:
                pygame.draw.lines(
                    screen, (70, 150, 175), False,
                    [(int(p.x), int(p.y)) for p in g.positions], 1)

    # the pulse in the wires
    if dive.network is not None:
        for x, y, amp, direction in pulse_samples_directed(
                dive.network, dive.assembly, max_points_per_edge=32,
                min_amplitude=1e-4):
            if x >= BENCH_W:
                continue
            b = min(1.0, abs(amp) * 3.0)
            col = ((250, 170, 90) if direction < 0 else (70, 190, 245))
            pygame.draw.circle(screen, tuple(int(20 + (c - 20) * b) for c in col),
                               (int(x), int(y)), 2 + int(3 * b))

    if dive.drag_from is not None:
        a, b = dive.drag_from, dive.drag_to
        if dive.tool == "run":
            pygame.draw.line(screen, (100, 124, 152), a, b, 2)
        else:
            rung = snap_radius((b - a).length())
            pygame.draw.circle(screen, (100, 124, 152),
                               (int(a.x), int(a.y)), int(rung.radius), 2)
            screen.blit(small.render(f"{rung.name}  {rung.note_hz*375:.0f} Hz",
                                     True, TEXT_HI), (a.x + 8, a.y - 22))

    # gadgets bolted to the machine
    for g in dive.rack.gadgets:
        col = GADGET_COLOUR[g.kind]
        r = 9 + int(5 * g.output * 12.0)
        if g.running:
            pygame.draw.circle(screen, col, (int(g.pos.x), int(g.pos.y)), r)
        pygame.draw.circle(screen, col, (int(g.pos.x), int(g.pos.y)), 9, 2)
        pygame.draw.circle(screen, (26, 32, 44),
                           (int(g.pos.x), int(g.pos.y)), int(COUPLING_RANGE), 1)
        screen.blit(small.render(g.kind[:4], True, col),
                    (g.pos.x + 12, g.pos.y - 7))

    screen.blit(font.render("THE BENCH", True, TEXT_HI), (12, 10))
    if dive.preset is not None:
        _wrap(screen, small, dive.preset.name.upper(), (12, 30), 330, TEXT_HI)
        _wrap(screen, small, dive.preset.try_this, (12, 46), 330, (140, 170, 120))

    # what is wrong with it, in sentences (3.2)
    y = HEIGHT - 150
    for n in dive.advice[:5]:
        col = ADVICE_COLOUR.get(n.severity, TEXT)
        y = _wrap(screen, small, n.text, (12, y), 336, col) + 3

    screen.blit(small.render(
        "1 run  2 loop  LMB draw  X erase  F1-F8 preset  G gadget  ,/. kind",
        True, (72, 90, 110)), (12, HEIGHT - 20))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SUBMERGED")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 15)
    small = pygame.font.SysFont("consolas,menlo,monospace", 12)

    dive = Dive()
    view = _StageView(dive)
    renderer = Renderer((world.WIDTH, world.HEIGHT), dive.medium)
    ocean = pygame.Surface((world.WIDTH, world.HEIGHT))
    running = True

    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        mx, my = pygame.mouse.get_pos()
        on_bench = mx < BENCH_W

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_1:
                    dive.tool = "run"
                elif e.key == pygame.K_2:
                    dive.tool = "loop"
                elif e.key == pygame.K_x and on_bench:
                    if not dive.rack.remove_at((mx, my)):
                        dive.erase((mx, my))
                elif pygame.K_F1 <= e.key <= pygame.K_F8:
                    dive.load_preset(e.key - pygame.K_F1)
                elif e.key == pygame.K_g and on_bench:
                    dive.rack.add(GADGET_ORDER[dive.gadget_kind], (mx, my))
                elif e.key == pygame.K_COMMA:
                    dive.gadget_kind = (dive.gadget_kind - 1) % len(GADGET_ORDER)
                elif e.key == pygame.K_PERIOD:
                    dive.gadget_kind = (dive.gadget_kind + 1) % len(GADGET_ORDER)
                elif e.key == pygame.K_UP:
                    dive.tune(+1)
                elif e.key == pygame.K_DOWN:
                    dive.tune(-1)
                elif e.key == pygame.K_TAB:
                    dive.show_field = not dive.show_field
                elif e.key == pygame.K_LEFTBRACKET:
                    dive.scale_index = max(0, dive.scale_index - 1)
                elif e.key == pygame.K_RIGHTBRACKET:
                    dive.scale_index = min(len(TIME_SCALES) - 1, dive.scale_index + 1)
                elif e.key == pygame.K_r:
                    dive = Dive()
                    view = _StageView(dive)
                    renderer = Renderer((world.WIDTH, world.HEIGHT), dive.medium)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1 and on_bench:
                    dive.begin((mx, my))
                elif e.button == 3:
                    dive.driving = True
            elif e.type == pygame.MOUSEMOTION:
                if dive.drag_from is not None:
                    dive.drag_to = pygame.Vector2(mx, my)
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1:
                    dive.commit()
                elif e.button == 3:
                    dive.driving = False

        keys = pygame.key.get_pressed()
        dx = keys[pygame.K_d] - keys[pygame.K_a]
        dy = keys[pygame.K_s] - keys[pygame.K_w]
        dive.kick = pygame.Vector2(dx, dy)
        if dive.kick.length_squared() > 1e-9:
            dive.kick = dive.kick.normalize()
        if not on_bench:
            d = pygame.Vector2(mx - BENCH_W, my) - dive.diver.pos
            if d.length_squared() > 1.0:
                dive.aim = d.normalize()

        dive.step(dt)

        screen.fill((3, 5, 11))
        renderer.draw(ocean, view)
        for v in dive.vents:
            pygame.draw.circle(ocean, (255, 150, 70), (int(v.pos.x), int(v.pos.y)), 6)
            pygame.draw.circle(ocean, (120, 60, 30), (int(v.pos.x), int(v.pos.y)),
                               int(v.reach), 1)
        _blit_seams(ocean, dive)
        screen.blit(ocean, (BENCH_W, 0))
        draw_bench(screen, dive, font, small)

        # the air bar: 3.1's whole progression curve, as one number
        power = dive.power_here()
        air = dive.economy.air
        bw = 260
        pygame.draw.rect(screen, (24, 30, 40), (BENCH_W + 16, 14, bw, 12))
        col = (90, 210, 160) if air > 30 else (230, 110, 90)
        pygame.draw.rect(screen, col, (BENCH_W + 16, 14, int(bw * air / 100.0), 12))
        msg = ("drawing power from the water" if power > 0.4
               else "burning your own air")
        screen.blit(small.render(f"air {air:5.1f}   {msg}", True,
                                 TEXT_HI if power > 0.4 else (230, 150, 130)),
                    (BENCH_W + 16, 30))
        screen.blit(small.render(dive.economy.report(), True, TEXT),
                    (BENCH_W + 16, 46))
        gk = GADGET_ORDER[dive.gadget_kind]
        from .bench.gadgets import KINDS as GK
        proto = GK[gk]()
        screen.blit(small.render(
            f"G places a {gk}: wants {proto.wants}, {proto.does}",
            True, GADGET_COLOUR[gk]), (BENCH_W + 16, 62))
        # NOT `running`: that is the main loop's own flag, and shadowing it
        # with a list made the window close on the first frame whenever no
        # gadget was going, which is every frame before you build one.
        live = [g.kind for g in dive.rack.gadgets if g.running]
        if live:
            screen.blit(small.render("running: " + ", ".join(live), True,
                                     (150, 220, 175)), (BENCH_W + 16, 78))
        screen.blit(small.render(
            f"driving at {dive.drive_hz:.0f} Hz (UP/DOWN to tune)   "
            "WASD kick   RMB drive   TAB field   [ ] time   R reset",
            True, TEXT), (BENCH_W + 16, HEIGHT - 22))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
