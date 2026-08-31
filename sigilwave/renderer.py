import pygame

from . import config
from .arena import Arena
from .camera import Camera


class Renderer:
    def __init__(self, surface: pygame.Surface):
        self.surface = surface

    def clear(self) -> None:
        self.surface.fill(config.COLOR_BG)

    def draw_arena(self, arena: Arena, camera: Camera) -> None:
        cell = arena.cell_size
        w, h = self.surface.get_size()

        gx = 0.0
        while gx <= arena.width:
            a = camera.world_to_screen(pygame.Vector2(gx, 0))
            b = camera.world_to_screen(pygame.Vector2(gx, arena.height))
            pygame.draw.line(self.surface, config.COLOR_GRID, a, b, 1)
            gx += cell

        gy = 0.0
        while gy <= arena.height:
            a = camera.world_to_screen(pygame.Vector2(0, gy))
            b = camera.world_to_screen(pygame.Vector2(arena.width, gy))
            pygame.draw.line(self.surface, config.COLOR_GRID, a, b, 1)
            gy += cell

        top_left = camera.world_to_screen(pygame.Vector2(0, 0))
        rect = pygame.Rect(top_left.x, top_left.y, arena.width, arena.height)
        pygame.draw.rect(self.surface, config.COLOR_BOUNDS, rect, width=2)

        _ = (w, h)  # reserved for viewport culling once the entity count grows

    def draw_entity(self, pos: pygame.Vector2, camera: Camera, radius: float, color) -> None:
        screen_pos = camera.world_to_screen(pos)
        glow_radius = int(radius * 2.5)
        glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, 60), (glow_radius, glow_radius), glow_radius)
        self.surface.blit(glow, (screen_pos.x - glow_radius, screen_pos.y - glow_radius))
        pygame.draw.circle(self.surface, color, screen_pos, radius)
