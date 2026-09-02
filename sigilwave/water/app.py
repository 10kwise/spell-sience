"""Swim around in the water and look at it.

This is the only question this screen exists to answer: with no machine to
build, no air to spend and nothing trying to kill you, is the ocean worth
looking at? If it is not, the bench does not matter -- SUBMERGED asks the
player to stare at this for an hour while thinking about something else.

Nothing here is the game. It borrows the stage's room, reads the medium, and
drives the wake with a stand-in ping rather than a real wavefront, so that
none of it collides with the physics work happening in `medium/`.

    python -m sigilwave.water.app

    WASD / arrows   swim              LMB   ping
    H               heat the water    B     bubbles
    F               hide the readout  R     reset      ESC quit
"""

import math

import pygame

from ..stage import world
from .ping import Ping, step_all
from .shader import WaterShader

SWIM_SPEED = 190.0
HEAT_RATE = 12.0
HEAT_RADIUS = 26.0
BUBBLE_RATE = 0.30
BUBBLE_RADIUS = 30.0
DIVER = (168, 214, 232)
TEXT = (120, 168, 190)


def _spray(fn, pos, radius, dose, cell):
    """A patch, not a point. A single cell is smaller than the bilinear
    stencil that samples it, so a one-cell feature is read at roughly half its
    true strength -- and a one-cell curtain is barely a curtain at all."""
    n = max(1, int(radius / cell))
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            dx, dy = i * cell, j * cell
            r = math.hypot(dx, dy)
            if r <= radius:
                fn(pos[0] + dx, pos[1] + dy, dose * (1.0 - 0.6 * r / radius))


def _draw_diver(screen, pos):
    x, y = int(pos[0]), int(pos[1])
    pygame.draw.circle(screen, DIVER, (x, y), 5)
    pygame.draw.circle(screen, (12, 30, 46), (x, y), 5, 1)


def main():
    pygame.init()
    size = (world.WIDTH, world.HEIGHT)
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("SUBMERGED - the water")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 13)

    medium = world.build()
    shader = WaterShader(size, medium)
    diver = pygame.Vector2(430.0, 470.0)
    pings = []
    show_help = True
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
                elif e.key == pygame.K_f:
                    show_help = not show_help
                elif e.key == pygame.K_r:
                    medium = world.build()
                    shader = WaterShader(size, medium)
                    diver = pygame.Vector2(430.0, 470.0)
                    pings = []
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                pings.append(Ping(shader, diver.x, diver.y))

        keys = pygame.key.get_pressed()
        dx = ((keys[pygame.K_d] or keys[pygame.K_RIGHT])
              - (keys[pygame.K_a] or keys[pygame.K_LEFT]))
        dy = ((keys[pygame.K_s] or keys[pygame.K_DOWN])
              - (keys[pygame.K_w] or keys[pygame.K_UP]))
        if dx or dy:
            diver.x = min(max(diver.x + dx * SWIM_SPEED * dt, 8.0), world.WIDTH - 8.0)
            diver.y = min(max(diver.y + dy * SWIM_SPEED * dt, 8.0), world.HEIGHT - 8.0)
        if keys[pygame.K_h]:
            _spray(medium.add_heat, mouse, HEAT_RADIUS,
                   HEAT_RATE * dt, medium.cell_size)
        if keys[pygame.K_b]:
            _spray(lambda x, y, a: medium.add_bubbles(x, y, a, 1.4),
                   mouse, BUBBLE_RADIUS, BUBBLE_RATE * dt, medium.cell_size)

        medium.step(dt)
        pings = step_all(pings, dt)
        shader.draw(screen, (diver.x, diver.y), dt)
        _draw_diver(screen, diver)

        if show_help:
            lines = [
                "WASD swim   LMB ping   H heat   B bubbles   R reset   F hide",
                f"{clock.get_fps():4.0f} fps   {len(pings)} ping"
                f"{'' if len(pings) == 1 else 's'}",
            ]
            for i, text in enumerate(lines):
                screen.blit(font.render(text, True, TEXT),
                            (12, world.HEIGHT - 34 + i * 16))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
