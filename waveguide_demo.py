"""Build order §9, stage 1: two-edge waveguide, one junction, no game.

Watch reflection and interference on screen. Kill criterion from the design
doc: if this doesn't read as alive and legible in a single evening, the
visualization approach is wrong and everything downstream inherits the
problem — so this stays a standalone scene, not wired into the player game.

Controls:
  SPACE       inject a short broadband burst at the left end (node 0)
  H (hold)    inject a longer, near-tonal burst while held
  R           reset the network to silence
  UP/DOWN     change the right edge's impedance (junction mismatch)
  P           dump a screenshot to debug_output/ so it can be inspected later
  ESC         quit
"""

import os

import numpy as np
import pygame

from sigilwave.sim.network import Network, raised_cosine_burst

DEBUG_SCREENSHOT_PATH = os.path.join(os.path.dirname(__file__), "debug_output", "waveguide_debug.png")

WIDTH, HEIGHT = 1100, 500
FIXED_DT = 1 / 400  # matches the design doc's sim rate (§5): dt = dx/c
SAMPLES_PER_EDGE = 220
IMPEDANCE_LEFT = 50.0
PLOT_MARGIN_X = 60
PLOT_Y = HEIGHT // 2
PLOT_AMPLITUDE_SCALE = 140.0

COLOR_BG = (10, 11, 15)
COLOR_AXIS = (60, 66, 78)
COLOR_LEFT_EDGE = (120, 200, 230)
COLOR_RIGHT_EDGE = (230, 150, 110)
COLOR_JUNCTION = (240, 240, 240)
COLOR_TEXT = (170, 190, 205)
COLOR_FLASH = (255, 220, 120)


class WaveguideDemo:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Sigil / Wave — stage 1: waveguide + junction")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.font = pygame.font.SysFont("consolas", 16)
        self.clock = pygame.time.Clock()
        self.running = True

        self.right_impedance = 150.0
        self.network = self._build_network(self.right_impedance)

        self.hold_burst_phase = 0.0
        self.flash_timer = 0.0  # brief highlight on the junction when a burst is injected
        self.pending_burst: list = []
        self.pending_burst_i = 0

    def _build_network(self, right_impedance: float) -> Network:
        net = Network()
        net.add_node(0)  # free end, left
        net.add_node(1)  # junction
        net.add_node(2)  # free end, right
        self.edge_left = net.add_edge(0, 1, SAMPLES_PER_EDGE, IMPEDANCE_LEFT)
        self.edge_right = net.add_edge(1, 2, SAMPLES_PER_EDGE, right_impedance)
        return net

    def reset(self) -> None:
        self.network = self._build_network(self.right_impedance)

    def handle_input(self, dt: float) -> dict:
        injections: dict[int, float] = {}
        keys = pygame.key.get_pressed()

        if keys[pygame.K_h]:
            self.hold_burst_phase += dt
            injections[0] = 0.6 * math_sin_ramp(self.hold_burst_phase)
            self.flash_timer = 0.05
        else:
            self.hold_burst_phase = 0.0

        return injections

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self._inject_burst()
                elif event.key == pygame.K_r:
                    self.reset()
                elif event.key == pygame.K_UP:
                    self.right_impedance = min(400.0, self.right_impedance + 10.0)
                    self.edge_right.impedance = self.right_impedance
                elif event.key == pygame.K_DOWN:
                    self.right_impedance = max(10.0, self.right_impedance - 10.0)
                    self.edge_right.impedance = self.right_impedance
                elif event.key == pygame.K_p:
                    self._save_debug_screenshot()

    def _save_debug_screenshot(self) -> None:
        os.makedirs(os.path.dirname(DEBUG_SCREENSHOT_PATH), exist_ok=True)
        pygame.image.save(self.screen, DEBUG_SCREENSHOT_PATH)
        print(f"[debug] screenshot saved to {DEBUG_SCREENSHOT_PATH}")

    def _inject_burst(self) -> None:
        self.pending_burst = raised_cosine_burst(24, amplitude=1.0)
        self.pending_burst_i = 0
        self.flash_timer = 0.15

    def step_sim(self, dt: float, held_injections: dict) -> None:
        injections = dict(held_injections)
        if self.pending_burst_i < len(self.pending_burst):
            injections[0] = injections.get(0, 0.0) + self.pending_burst[self.pending_burst_i]
            self.pending_burst_i += 1

        self.network.step(injections)
        if self.flash_timer > 0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def profile_points(self, edge, x_start: float, x_end: float) -> list:
        """Combined displacement u+ + u- along the edge, ordered A -> B.

        spatial_profile()[0] is the sample nearest to exiting: for the
        forward line (A->B) that's the B end, so it needs reversing; for the
        backward line (B->A) the exit end is already A, so it's already in
        A->B order.
        """
        forward = edge.forward.spatial_profile()
        backward = edge.backward.spatial_profile()
        displacement = forward[::-1] + backward
        n = len(displacement)
        xs = np.linspace(x_start, x_end, n)
        points = [(xs[i], PLOT_Y - displacement[i] * PLOT_AMPLITUDE_SCALE) for i in range(n)]
        return points

    def draw(self) -> None:
        self.screen.fill(COLOR_BG)

        pygame.draw.line(self.screen, COLOR_AXIS, (PLOT_MARGIN_X, PLOT_Y), (WIDTH - PLOT_MARGIN_X, PLOT_Y), 1)

        mid_x = WIDTH / 2
        left_points = self.profile_points(self.edge_left, PLOT_MARGIN_X, mid_x)
        right_points = self.profile_points(self.edge_right, mid_x, WIDTH - PLOT_MARGIN_X)

        if len(left_points) >= 2:
            pygame.draw.lines(self.screen, COLOR_LEFT_EDGE, False, left_points, 3)
        if len(right_points) >= 2:
            pygame.draw.lines(self.screen, COLOR_RIGHT_EDGE, False, right_points, 3)

        junction_color = COLOR_FLASH if self.flash_timer > 0 else COLOR_JUNCTION
        pygame.draw.circle(self.screen, junction_color, (int(mid_x), PLOT_Y), 6)
        pygame.draw.circle(self.screen, COLOR_JUNCTION, (PLOT_MARGIN_X, PLOT_Y), 5, 1)
        pygame.draw.circle(self.screen, COLOR_JUNCTION, (WIDTH - PLOT_MARGIN_X, PLOT_Y), 5, 1)

        r = (self.right_impedance - IMPEDANCE_LEFT) / (self.right_impedance + IMPEDANCE_LEFT)
        lines = [
            "SPACE burst | H hold-tone | UP/DOWN change right Z | R reset | ESC quit",
            f"Z_left={IMPEDANCE_LEFT:.0f}  Z_right={self.right_impedance:.0f}  "
            f"reflection r={r:+.2f}  transmission={1 - abs(r):.2f}",
            f"total energy: {self.network.total_energy():.4f}",
        ]
        for i, line in enumerate(lines):
            text = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (12, 10 + i * 18))

        pygame.display.flip()

    def run(self) -> None:
        accumulator = 0.0
        while self.running:
            frame_time = min(self.clock.tick(240) / 1000.0, 0.05)
            self.handle_events()

            accumulator += frame_time
            while accumulator >= FIXED_DT:
                injections = self.handle_input(FIXED_DT)
                self.step_sim(FIXED_DT, injections)
                accumulator -= FIXED_DT

            self.draw()

        pygame.quit()


def math_sin_ramp(t: float) -> float:
    """Smooth-attack tone for the held burst so H doesn't click on/off."""
    attack = min(1.0, t / 0.05)
    return attack * np.sin(2 * np.pi * 6.0 * t)


if __name__ == "__main__":
    WaveguideDemo().run()
