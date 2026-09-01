"""THE BENCH -- step 4 of SUBMERGED.md 13.

Still water, five parts, one pulse, slow motion, a scrub bar. Nothing else.

*You cannot learn a system you cannot single-step* (10). Neither previous
build had this screen, and both failed for reasons that would have been
visible on it in a minute: a pulse that splits at a fork and gets caught in a
loop is either immediately obvious here or the parts are wrong.

The whole run is simulated the instant you fire, and the scrub bar walks
through what happened. Scrubbing is therefore free and exact -- you are
reading recorded state, not re-simulating with a smaller timestep, so time
runs backwards as honestly as it runs forwards.

    python -m sigilwave.bench.app
"""

import math

import pygame

from ..sim.network import raised_cosine_burst
from .parts import (
    DRAWABLE_RUNGS,
    GAP_MAX,
    JOIN_EPS,
    MIN_RUN_LENGTH,
    SIM_DT,
    Assembly,
    snap_radius,
)
from .pulse import pulse_samples_directed

WIDTH, HEIGHT = 1200, 800
CANVAS_H = 720
RUN_STEPS = 1400          # how much of the future one shot records
BURST_SAMPLES = 6

BG = (8, 10, 15)
WIRE = (52, 64, 82)
WIRE_HOT = (92, 112, 140)
FORK_C = (235, 176, 92)
MOUTH_C = (120, 220, 235)
GAP_C = (206, 96, 160)
TEXT = (108, 132, 158)
TEXT_HI = (196, 216, 232)


def blob_colour(amp, direction):
    """Sign is real and watchable: a pulse reflecting off a mouth comes back
    inverted, and that flip is one of the few places the simulation shows its
    working. Outbound is cool, returning is warm, and the sign sets which end
    of each ramp."""
    a = min(1.0, abs(amp) * 2.2)
    if direction > 0:
        base = (70, 190, 245) if amp >= 0 else (150, 120, 245)
    else:
        base = (250, 170, 90) if amp >= 0 else (245, 105, 105)
    return tuple(int(20 + (c - 20) * a) for c in base), a


class Bench:
    def __init__(self):
        self.asm = Assembly()
        self.tool = "run"
        self.drag_from = None
        self.drag_to = None
        self.history = []          # [[(x, y, amp, dir), ...], ...]
        self.energy = []           # (stored, radiated_cumulative)
        self.head = 0
        self.playing = False
        self.speed = 1
        self.fired_at = None
        self.note = ""

    # ---------------------------------------------------------- editing
    def begin(self, pos):
        self.drag_from = pygame.Vector2(pos)
        self.drag_to = pygame.Vector2(pos)

    def drag(self, pos):
        if self.drag_from is not None:
            self.drag_to = pygame.Vector2(pos)

    def commit(self):
        if self.drag_from is None:
            return
        a, b = self.drag_from, self.drag_to
        self.drag_from = self.drag_to = None
        if self.tool == "run":
            if (b - a).length() >= MIN_RUN_LENGTH:
                self.asm.add_run(a, b)
        else:
            r = (b - a).length()
            if r >= DRAWABLE_RUNGS[-1].radius * 0.4:
                self.asm.add_loop(a, r)
        self.clear_shot()

    def delete_at(self, pos):
        p = pygame.Vector2(pos)
        best, bd = None, 22.0
        for part in self.asm.parts:
            for q in part.points():
                d = (pygame.Vector2(q) - p).length()
                if d < bd:
                    best, bd = part.part_id, d
        if best is not None:
            self.asm.remove(best)
            self.clear_shot()

    def clear_shot(self):
        self.history = []
        self.energy = []
        self.head = 0
        self.playing = False
        self.fired_at = None

    # ---------------------------------------------------------- firing
    def fire(self, pos):
        """Compile, inject one burst, and record the entire run up front."""
        mouths = self.asm.mouth_nodes()
        if not mouths:
            self.note = "nothing to fire into - no free end for energy to enter by"
            return
        p = pygame.Vector2(pos)
        node_id, at = min(mouths, key=lambda m: (m[1] - p).length_squared())

        net = self.asm.compile()
        burst = raised_cosine_burst(BURST_SAMPLES, amplitude=1.0)
        self.history = []
        self.energy = []
        radiated = 0.0
        for i in range(RUN_STEPS):
            inj = {node_id: burst[i]} if i < len(burst) else None
            radiated += net.step(inj)
            self.history.append(
                pulse_samples_directed(net, self.asm, max_points_per_edge=48,
                                       min_amplitude=1e-4))
            self.energy.append((net.total_energy(), radiated))
        self.head = 0
        self.playing = True
        self.fired_at = at
        self.note = self.asm.describe()

    def advance(self):
        if self.playing and self.history:
            self.head += self.speed
            if self.head >= len(self.history):
                self.head = len(self.history) - 1
                self.playing = False

    def scrub(self, delta):
        if self.history:
            self.playing = False
            self.head = max(0, min(len(self.history) - 1, self.head + delta))


def draw(screen, bench, font, small, mouse):
    screen.fill(BG)
    asm = bench.asm

    # --- the drawing itself -------------------------------------------
    for part in asm.parts:
        pts = [(int(p[0]), int(p[1])) for p in part.points()]
        if len(pts) > 1:
            pygame.draw.lines(screen, WIRE, part.kind == "loop", pts, 2)

    for pos_a, pos_b, gap in asm.gaps():
        a = (int(pos_a[0]), int(pos_a[1]))
        b = (int(pos_b[0]), int(pos_b[1]))
        n = max(2, int((pygame.Vector2(b) - pygame.Vector2(a)).length() / 5))
        for i in range(n):
            if i % 2:
                continue
            t0, t1 = i / n, (i + 1) / n
            p0 = pygame.Vector2(a).lerp(b, t0)
            p1 = pygame.Vector2(a).lerp(b, t1)
            pygame.draw.line(screen, GAP_C, p0, p1, 1)

    for pos in asm.forks():
        pygame.draw.circle(screen, FORK_C, (int(pos[0]), int(pos[1])), 5)
    for _nid, pos in asm.mouth_nodes():
        pygame.draw.circle(screen, MOUTH_C, (int(pos[0]), int(pos[1])), 6, 2)

    # --- the pulse, which is the protagonist ---------------------------
    if bench.history:
        for x, y, amp, direction in bench.history[bench.head]:
            col, a = blob_colour(amp, direction)
            r = 2 + int(6.0 * a)
            pygame.draw.circle(screen, col, (int(x), int(y)), r)

    if bench.fired_at is not None:
        p = bench.fired_at
        pygame.draw.circle(screen, (245, 245, 210), (int(p[0]), int(p[1])), 3)

    # --- what is being drawn right now ---------------------------------
    if bench.drag_from is not None:
        a, b = bench.drag_from, bench.drag_to
        if bench.tool == "run":
            pygame.draw.line(screen, WIRE_HOT, a, b, 2)
        else:
            rung = snap_radius((b - a).length())
            pygame.draw.circle(screen, WIRE_HOT, (int(a.x), int(a.y)),
                               int(rung.radius), 2)
            screen.blit(small.render(f"{rung.name}  {rung.lap_seconds:.2f}s lap",
                                     True, TEXT_HI), (a.x + 10, a.y - 24))

    _panel(screen, bench, font, small)


def _panel(screen, bench, font, small):
    pygame.draw.rect(screen, (5, 7, 11), (0, CANVAS_H, WIDTH, HEIGHT - CANVAS_H))
    pygame.draw.line(screen, (28, 36, 48), (0, CANVAS_H), (WIDTH, CANVAS_H))

    label = bench.note or "draw something, then press SPACE to ping it"
    screen.blit(font.render(label, True, TEXT_HI), (16, CANVAS_H + 8))

    # The scrub bar is the whole recorded run with the playhead on it. 10
    # says the bench exists to be single-stepped, so this is the control the
    # screen is built around rather than a transport widget bolted underneath.
    bx, by, bw = 16, CANVAS_H + 34, WIDTH - 32
    pygame.draw.rect(screen, (22, 28, 38), (bx, by, bw, 8), border_radius=4)
    if bench.history:
        t = bench.head / max(1, len(bench.history) - 1)
        pygame.draw.rect(screen, (48, 92, 128), (bx, by, int(bw * t), 8),
                         border_radius=4)
        pygame.draw.circle(screen, TEXT_HI, (int(bx + bw * t), by + 4), 6)
        stored, radiated = bench.energy[bench.head]
        info = (f"t={bench.head * SIM_DT:5.2f}s   step {bench.head}/"
                f"{len(bench.history) - 1}   in the wires {stored:.4f}"
                f"   left by mouths {radiated:.4f}")
    else:
        info = "no shot recorded"
    screen.blit(small.render(info, True, TEXT), (bx, CANVAS_H + 50))

    tool = f"[{'RUN' if bench.tool == 'run' else 'LOOP'}]"
    screen.blit(small.render(
        f"{tool}  1 run  2 loop  LMB draw  RMB erase  SPACE fire  "
        f"P play  <- -> scrub  C clear  R reset", True, (72, 90, 110)),
        (bx, CANVAS_H + 66))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SUBMERGED - the bench")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 16)
    small = pygame.font.SysFont("consolas,menlo,monospace", 13)

    bench = Bench()
    running = True
    while running:
        clock.tick(60)
        mouse = pygame.mouse.get_pos()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_1:
                    bench.tool = "run"
                elif e.key == pygame.K_2:
                    bench.tool = "loop"
                elif e.key == pygame.K_SPACE:
                    bench.fire(mouse)
                elif e.key == pygame.K_p:
                    bench.playing = not bench.playing
                elif e.key == pygame.K_LEFT:
                    bench.scrub(-4)
                elif e.key == pygame.K_RIGHT:
                    bench.scrub(4)
                elif e.key == pygame.K_c:
                    bench.asm = Assembly()
                    bench.clear_shot()
                    bench.note = ""
                elif e.key == pygame.K_r:
                    bench = Bench()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1 and mouse[1] < CANVAS_H:
                    bench.begin(mouse)
                elif e.button == 3:
                    bench.delete_at(mouse)
            elif e.type == pygame.MOUSEMOTION:
                bench.drag(mouse)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                bench.commit()

        bench.advance()
        draw(screen, bench, font, small, mouse)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
