"""THE STAGE -- step 3 of SUBMERGED.md 13.

There is no drawing system here, no oxygen, no death and no objective. There
is water, rock, and pings. The only question this screen exists to answer is
the one in 13.3: is firing sound into the dark and watching what the water
does to it worth doing for its own sake?

If the answer is no, nothing built on top of it will help, and finding that
out costs a day instead of a third rewrite.

    python -m sigilwave.stage.app
"""

import math

import numpy as np
import pygame

from ..medium.front import Front
from . import world

# ----------------------------------------------------------------------
# Time
# ----------------------------------------------------------------------
# Sound crosses this room in about a second at real speed, which is far too
# fast to watch, and watching is the entire point of this screen. Time is
# scaled so a ping takes about five seconds to cross -- slow enough to see a
# wavefront bend, which is the whole thesis.
TIME_SCALE = 0.2
TIME_SCALES = (0.05, 0.1, 0.2, 0.4, 1.0)

MAX_FRONTS = 8

# ----------------------------------------------------------------------
# Tone mapping
# ----------------------------------------------------------------------
# Intensity spans four decades between a ping's birth and its death, so it
# is mapped logarithmically. A linear ramp would show the first body length
# of every ping and nothing else -- and everything interesting the water
# does happens after that.
I_MIN = 6e-5
I_MAX = 1e-1
_LOG_MIN = math.log10(I_MIN)
_LOG_SPAN = math.log10(I_MAX) - _LOG_MIN

# The room is remembered per CELL, not per dot. An earlier version stamped a
# circle wherever a vertex found rock, and the result was a scatter of
# unconnected specks that never became a surface -- you could see that sound
# had touched something without ever seeing what. Marking the cell builds a
# real silhouette out of the same information.
KNOWN_DECAY = 0.988      # per frame; the room fades over roughly 15 s
PROBE_AHEAD = 11.0       # px ahead of a vertex to look for rock
PROBE_SPREAD = 1         # cells either side of a hit that also light up

# A front is a polyline, and when it folds through a caustic its vertices
# separate while staying joined in the list. Drawing that joining chord puts
# a long straight line across the room which is not a wavefront at all -- it
# is the data structure showing through. Segments longer than this are the
# fold, not the front, and are not drawn.
MAX_DRAWN_SEGMENT = 46.0

# A wavefront drawn only where it is right now is a thin curve that says
# nothing about where it has BEEN -- and everything the water does to sound
# is a fact about trajectory, not position. A ping trapped in the channel and
# a ping crossing it look identical in a single frame. So fronts also paint
# into a slowly-fading trail buffer: the room keeps a long exposure of every
# path sound has taken through it, and refraction becomes something you watch
# being drawn rather than something you infer.
TRAIL_FADE = (250, 250, 247)   # multiplied per frame; blue outlives warm

# Stamped every few frames rather than every frame. Drawn continuously the
# trail becomes a solid moire hatch that says only "sound was here"; stamped
# periodically it becomes a set of discrete arcs -- and the SPACING of those
# arcs is the local sound speed, because they are laid down on a fixed clock.
# So the long exposure draws the c-field itself: arcs crowd where water is
# slow and stretch where it is fast, which is 7.3's whole law made visible
# without a single number on screen.
TRAIL_STRIDE = 6

# Sound is cyan and moving; rock is warm and still. They have to be
# different colours or the picture is a tangle of blue lines in which the
# world and the wave are indistinguishable -- which is exactly what the
# first pass looked like.
ROCK_COLOUR = (208, 166, 116)
WARM_COLOUR = (206, 96, 54)
GAS_COLOUR = (150, 222, 190)

# ----------------------------------------------------------------------
# Dose
# ----------------------------------------------------------------------
# Both of these were applied once per FRAME while the key was held, which
# meant a tap did nothing and a tenth of a second did something absurd: heat
# reached 900 C and a sound-speed contrast of 3085x, which is not a mirror
# but a perfectly reflecting wall. A mechanic with no legible dose-response
# is unlearnable (9.1), so both are now rates per SECOND.
#
# The heat rate is chosen against the critical angle. A contrast of 1.2x
# reflects sound arriving within 56 degrees of grazing and passes the rest,
# so a warm mirror WORKS ONLY IF YOU PING SHALLOW -- the same skill the
# sound channel teaches, arrived at from the other direction. About a second
# of holding lands in that band; keep holding and it stiffens into a wall,
# which is a mistake the player is allowed to make and to see.
HEAT_RATE = 12.0         # per second
HEAT_RADIUS = 26.0

# Thin bends, thick eats. At a void fraction near 0.15 a curtain is a 1.2x
# mirror that barely attenuates; held, it climbs toward total absorption.
# One system, two tools, and thickness is the knob.
BUBBLE_RATE = 0.30       # per second
BUBBLE_RADIUS = 30.0


def tone(intensity: float) -> float:
    """Intensity -> 0..1 brightness, logarithmically."""
    if intensity <= I_MIN:
        return 0.0
    b = (math.log10(intensity) - _LOG_MIN) / _LOG_SPAN
    return 0.0 if b <= 0.0 else (1.0 if b >= 1.0 else b)


def ramp(b: float):
    """Cold and dim to hot and bright. A front leaves white and arrives blue,
    which is the range law drawn as one animation rather than stated as a
    number."""
    if b < 0.5:
        t = b * 2.0
        return (int(14 + 56 * t), int(46 + 134 * t), int(104 + 136 * t))
    t = (b - 0.5) * 2.0
    return (int(70 + 185 * t), int(180 + 75 * t), int(240 + 15 * t))


# ----------------------------------------------------------------------
# Mouths (SUBMERGED.md 5.1)
# ----------------------------------------------------------------------
# Three genuinely different tools out of one number, because width is doing
# two opposite things at once: wide is softer at birth but straighter in
# flight; narrow is brutal at birth but diffracts away within a body length.
class Mouth:
    def __init__(self, name, span, curvature, freq, energy, hint):
        self.name = name
        self.span = span
        self.curvature = curvature
        self.freq = freq
        self.energy = energy
        self.hint = hint


MOUTHS = (
    Mouth("SPITTER", 4.0, 1.0 / 7.0, 2600.0, 1.0,
          "vicious at arm's length, gone by a body length"),
    Mouth("CARRY", 150.0, 0.0, 120.0, 1.0,
          "soft at birth, coherent, goes the distance"),
    Mouth("SNIPER", 150.0, -1.0 / 340.0, 600.0, 1.0,
          "soft everywhere except at one distance"),
    Mouth("OMNI", 0.0, 0.0, 700.0, 1.0,
          "sonar: everywhere at once, and weak everywhere"),
)


class Stage:
    def __init__(self):
        self.medium = world.build()
        self.fronts = []
        self.diver = pygame.Vector2(150.0, world.HEIGHT * 0.62)
        self.mouth_index = 1
        self.scale_index = 2
        self.paused = False
        self.show_field = False
        self.aim = pygame.Vector2(1.0, 0.0)
        self.last_fire = None

    # -- state ---------------------------------------------------------
    @property
    def mouth(self):
        return MOUTHS[self.mouth_index]

    @property
    def time_scale(self):
        return TIME_SCALES[self.scale_index]

    def fire(self, toward):
        """One ping. Energy is not created here -- 3.1 says a body is a
        source that burns oxygen -- but there is no oxygen on this screen,
        because this screen is not asking that question yet."""
        m = self.mouth
        d = pygame.Vector2(toward) - self.diver
        if d.length_squared() < 1e-9:
            d = pygame.Vector2(1.0, 0.0)
        d = d.normalize()
        self.aim = d

        if m.span <= 0.0:
            f = Front.omni(
                (self.diver.x, self.diver.y), m.energy, m.freq,
                radius=2.0, n_vertices=192, max_vertices=384,
            )
        else:
            f = Front(
                (self.diver.x, self.diver.y), (d.x, d.y),
                m.span, m.curvature, m.energy, m.freq,
                n_vertices=96, max_vertices=384,
            )
        self.fronts.append(f)
        if len(self.fronts) > MAX_FRONTS:
            self.fronts.pop(0)
        self.last_fire = m.name

    def heat(self, pos, dt):
        """8's first verb, by hand. Absorbed energy warms water; warm water
        is faster; sound bends away from fast water. Three rules and you have
        built a mirror -- but only if the contrast stays in the band where a
        critical angle exists."""
        dose = HEAT_RATE * dt
        self._spray(self.medium.add_heat, pos, HEAT_RADIUS, dose)

    def bubble(self, pos, dt):
        """Wood's collapse makes a curtain a mirror as well as a wall."""
        dose = BUBBLE_RATE * dt
        self._spray(lambda x, y, a: self.medium.add_bubbles(x, y, a, 1.4),
                    pos, BUBBLE_RADIUS, dose)

    def _spray(self, fn, pos, radius, dose):
        """A patch, not a point. A single cell is smaller than the bilinear
        stencil that samples it, so a one-cell feature is read at roughly
        half its true strength and a one-cell curtain is barely a curtain
        at all."""
        cs = self.medium.cell_size
        n = max(1, int(radius / cs))
        cells = []
        for j in range(-n, n + 1):
            for i in range(-n, n + 1):
                dx, dy = i * cs, j * cs
                r = math.hypot(dx, dy)
                if r <= radius:
                    cells.append((pos[0] + dx, pos[1] + dy, 1.0 - 0.6 * r / radius))
        if not cells:
            return
        share = dose / sum(w for _, _, w in cells) * len(cells)
        for x, y, w in cells:
            fn(x, y, share * w)

    # -- update --------------------------------------------------------
    def update(self, dt):
        if self.paused:
            return
        sim_dt = dt * self.time_scale
        self.medium.step(sim_dt)
        for f in self.fronts:
            f.step(self.medium, sim_dt)
        self.fronts = [f for f in self.fronts if not f.is_dead()]

    def swim(self, dx, dy, dt):
        # Movement is a placeholder. 8 says propulsion is drawn -- a mouth
        # firing behind you -- and that arrives at step 5, not here.
        speed = 210.0
        self.diver.x = min(max(self.diver.x + dx * speed * dt, 8.0), world.WIDTH - 8.0)
        self.diver.y = min(max(self.diver.y + dy * speed * dt, 8.0), world.HEIGHT - 8.0)


class Renderer:
    """The world is drawn BY sound and fades back to black.

    Nothing here is decoration: the known-terrain buffer is the player's
    memory of the room, it decays, and the only way to refresh it is to spend
    a ping. That is 7's darkness made into an interface rather than an
    obstacle."""

    def __init__(self, size, medium):
        self.size = size
        self.glow = pygame.Surface(size)
        self.trails = pygame.Surface(size)
        self._frame = 0
        self.known = np.zeros((medium.ny, medium.nx))
        # Warm water and bubble clouds are invisible in a dark ocean, which
        # makes a mechanic you cannot see and therefore cannot learn. Sound
        # reveals the WATER as well as the rock: what a ping passes through
        # is remembered exactly like what it bounces off. That keeps 9.3 --
        # you see the thing itself, never a number describing it.
        self.known_warm = np.zeros((medium.ny, medium.nx))
        self.known_gas = np.zeros((medium.ny, medium.nx))
        # Compared against the row's own median, NOT against a snapshot of
        # the starting profile. A frozen baseline conflates two different
        # things: heat the player put somewhere, and the background gradient
        # being stirred by convection. The second is real physics but it is
        # not a warm patch, and showing it as one made heat look like it was
        # smearing and drifting on its own. A cell is warm when it is warmer
        # than the rest of the water AT ITS OWN DEPTH -- which is also the
        # only sense in which "warm" means anything in a stratified ocean.
        self._row_temp = np.zeros((medium.ny, 1))
        self._rgb = np.zeros((medium.ny, medium.nx, 3))
        self.field_cache = None

    def clear_memory(self):
        self.known[:] = 0.0
        self.known_warm[:] = 0.0
        self.known_gas[:] = 0.0
        self.trails.fill((0, 0, 0))

    def field_overlay(self, medium):
        """Not shown by default. 9.3 forbids a readout, and the player is
        meant to find the channel by pinging shallow -- but while building
        the room somebody has to be able to see the truth."""
        if self.field_cache is not None:
            return self.field_cache
        c = medium.c_field
        lo, hi = float(c.min()), float(c.max())
        norm = (c - lo) / max(hi - lo, 1e-9)
        rgb = np.zeros((medium.ny, medium.nx, 3), dtype=np.uint8)
        rgb[..., 0] = (46 * norm).astype(np.uint8)
        rgb[..., 1] = (16 + 30 * norm).astype(np.uint8)
        rgb[..., 2] = (70 - 40 * norm).astype(np.uint8)
        rgb[medium.solid] = (0, 0, 0)
        surf = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        self.field_cache = pygame.transform.smoothscale(surf, self.size)
        return self.field_cache

    def draw(self, screen, stage):
        medium = stage.medium
        screen.fill((3, 5, 11))
        if stage.show_field:
            screen.blit(self.field_overlay(medium), (0, 0))

        self.known *= KNOWN_DECAY          # the room forgets
        self.known_warm *= KNOWN_DECAY
        self.known_gas *= KNOWN_DECAY
        self._row_temp[:, 0] = np.median(medium.temp, axis=1)
        self.glow.fill((0, 0, 0))
        self.trails.fill(TRAIL_FADE, special_flags=pygame.BLEND_RGB_MULT)
        self._frame += 1
        stamp = (self._frame % TRAIL_STRIDE) == 0

        for f in stage.fronts:
            self._light_world(f, medium)
            self._draw_front(f, stamp)

        self._blit_known(screen)
        screen.blit(self.trails, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        screen.blit(self.glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self._bloom(screen)
        self._draw_diver(screen, stage)

    def _light_world(self, front, medium):
        """Where sound touches rock, that CELL lights up and stays lit a
        while. One batched medium call for the whole front rather than one
        per vertex, which is the difference between 3 ms and 0.2 ms."""
        verts = front.vertices
        if not verts:
            return
        n = len(verts)
        px = np.empty(n)
        py = np.empty(n)
        for i, v in enumerate(verts):
            p, d = v.pos, v.dir
            px[i] = p[0] + d[0] * PROBE_AHEAD
            py[i] = p[1] + d[1] * PROBE_AHEAD
        inten = front.intensity()
        cs = medium.cell_size

        # What the sound is passing THROUGH, lit where it passes.
        vr = np.clip((py / cs).astype(int), 0, medium.ny - 1)
        vc = np.clip((px / cs).astype(int), 0, medium.nx - 1)
        vb = np.array([tone(float(v)) for v in inten])
        warm = medium.temp[vr, vc] - self._row_temp[vr, 0]
        lit = vb * np.clip(warm / 3.0, 0.0, 1.0)
        if lit.any():
            np.maximum.at(self.known_warm, (vr, vc), lit)
        gas = np.clip(medium.bubbles[vr, vc] / 0.25, 0.0, 1.0) * vb
        if gas.any():
            np.maximum.at(self.known_gas, (vr, vc), gas)

        hit = medium.is_solid_at(px, py)
        if not hit.any():
            return
        cols = np.clip((px[hit] / cs).astype(int), 0, medium.nx - 1)
        rows = np.clip((py[hit] / cs).astype(int), 0, medium.ny - 1)
        bright = np.array([tone(float(v)) for v in inten[hit]])
        # A cell keeps the brightest return it has had, so a loud echo is not
        # erased by a faint one arriving behind it. Neighbouring rock lights
        # too: a probe lands on one cell, but what the sound actually met was
        # a surface, and lighting a single cell per vertex leaves the seabed
        # as unconnected specks that never resolve into a floor.
        for dr in range(-PROBE_SPREAD, PROBE_SPREAD + 1):
            for dc in range(-PROBE_SPREAD, PROBE_SPREAD + 1):
                rr = np.clip(rows + dr, 0, medium.ny - 1)
                cc = np.clip(cols + dc, 0, medium.nx - 1)
                near = medium.solid[rr, cc]
                if not near.any():
                    continue
                falloff = 1.0 if (dr == 0 and dc == 0) else 0.55
                np.maximum.at(self.known, (rr[near], cc[near]), bright[near] * falloff)

    def _blit_known(self, screen):
        rock = np.clip(self.known, 0.0, 1.0)
        warm = np.clip(self.known_warm, 0.0, 1.0)
        gas = np.clip(self.known_gas, 0.0, 1.0)
        if not (rock.any() or warm.any() or gas.any()):
            return
        for c in range(3):
            self._rgb[..., c] = np.minimum(
                rock * ROCK_COLOUR[c] + warm * WARM_COLOUR[c] + gas * GAS_COLOUR[c],
                255.0)
        surf = pygame.surfarray.make_surface(
            np.transpose(self._rgb.astype(np.uint8), (1, 0, 2)))
        screen.blit(pygame.transform.smoothscale(surf, self.size),
                    (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_front(self, front, stamp=False):
        for p0, p1, inten in front.segments():
            b = tone(float(inten))
            if b <= 0.02:
                continue
            if abs(p1[0] - p0[0]) + abs(p1[1] - p0[1]) > MAX_DRAWN_SEGMENT:
                continue        # a fold chord, not a wavefront
            a = (int(p0[0]), int(p0[1]))
            c = (int(p1[0]), int(p1[1]))
            col = ramp(b)
            pygame.draw.line(self.glow, col, a, c, 1 + int(2.5 * b))
            if stamp:
                # The trail takes a dimmer copy, so the live front always
                # reads brighter than its own history.
                pygame.draw.line(
                    self.trails,
                    (col[0] // 3, int(col[1] / 2.2), int(col[2] / 1.7)),
                    a, c, 1,
                )

    def _bloom(self, screen):
        """Cheap two-tap bloom. Sound in water should look like it is *in*
        something, not drawn on glass."""
        w, h = self.size
        small = pygame.transform.smoothscale(self.glow, (w // 6, h // 6))
        big = pygame.transform.smoothscale(small, (w, h))
        screen.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        screen.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_diver(self, screen, stage):
        d = stage.diver
        pygame.draw.circle(screen, (120, 200, 230), (int(d.x), int(d.y)), 5)
        pygame.draw.circle(screen, (18, 40, 58), (int(d.x), int(d.y)), 5, 1)
        tip = d + stage.aim * 16
        pygame.draw.line(screen, (70, 130, 165),
                         (int(d.x), int(d.y)), (int(tip.x), int(tip.y)), 1)


HELP = (
    "WASD swim    LMB ping    1-4 mouth    [ ] time    H heat    B bubbles"
    "    TAB field    SPACE pause    C clear    R reset"
)


def main():
    pygame.init()
    screen = pygame.display.set_mode((world.WIDTH, world.HEIGHT))
    pygame.display.set_caption("SUBMERGED - the stage")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 14)

    stage = Stage()
    renderer = Renderer((world.WIDTH, world.HEIGHT), stage.medium)
    running = True

    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        mouse = pygame.mouse.get_pos()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif pygame.K_1 <= e.key <= pygame.K_4:
                    stage.mouth_index = e.key - pygame.K_1
                elif e.key == pygame.K_LEFTBRACKET:
                    stage.scale_index = max(0, stage.scale_index - 1)
                elif e.key == pygame.K_RIGHTBRACKET:
                    stage.scale_index = min(len(TIME_SCALES) - 1, stage.scale_index + 1)
                elif e.key == pygame.K_TAB:
                    stage.show_field = not stage.show_field
                elif e.key == pygame.K_SPACE:
                    stage.paused = not stage.paused
                elif e.key == pygame.K_c:
                    renderer.clear_memory()
                elif e.key == pygame.K_r:
                    stage = Stage()
                    renderer = Renderer((world.WIDTH, world.HEIGHT), stage.medium)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                stage.fire(mouse)

        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        if dx or dy:
            stage.swim(dx, dy, dt)
        if keys[pygame.K_h]:
            stage.heat(mouse, dt)
        if keys[pygame.K_b]:
            stage.bubble(mouse, dt)

        stage.update(dt)
        renderer.draw(screen, stage)

        m = stage.mouth
        lines = [
            f"{m.name} - {m.hint}",
            f"time x{stage.time_scale:g}   fronts {len(stage.fronts)}   {clock.get_fps():4.0f} fps",
            HELP,
        ]
        for i, text in enumerate(lines):
            screen.blit(font.render(text, True, (90, 130, 155)), (12, 12 + i * 18))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
