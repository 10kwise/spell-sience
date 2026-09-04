import pygame


class Camera:
    def __init__(self, viewport_width: int, viewport_height: int):
        self.pos = pygame.Vector2(0, 0)
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

    def resize(self, width: int, height: int) -> None:
        self.viewport_width = width
        self.viewport_height = height

    def snap_to(self, target: pygame.Vector2) -> None:
        self.pos = pygame.Vector2(target)

    def follow(self, target: pygame.Vector2, smoothing: float) -> None:
        self.pos += (target - self.pos) * smoothing

    def world_to_screen(self, world: pygame.Vector2) -> pygame.Vector2:
        return pygame.Vector2(
            world.x - self.pos.x + self.viewport_width / 2,
            world.y - self.pos.y + self.viewport_height / 2,
        )
