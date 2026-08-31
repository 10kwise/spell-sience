"""The 'World' from the pipeline (design doc §4.1): fields live on a coarse
grid, kept deliberately simple per §8 ('resist making the world as clever as
the ink'). For now this is just bounds plus a background grid to draw."""

import pygame


class Arena:
    def __init__(self, width: float, height: float, cell_size: float):
        self.width = width
        self.height = height
        self.cell_size = cell_size

    def clamp(self, pos: pygame.Vector2, radius: float) -> pygame.Vector2:
        return pygame.Vector2(
            min(self.width - radius, max(radius, pos.x)),
            min(self.height - radius, max(radius, pos.y)),
        )
