import random

import pygame

from .arena import Arena
from . import config


class Player:
    def __init__(self, start_pos: pygame.Vector2):
        self.pos = pygame.Vector2(start_pos)
        self.prev_pos = pygame.Vector2(start_pos)
        self.radius = config.PLAYER_RADIUS
        self.speed = config.PLAYER_SPEED

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper, arena: Arena) -> None:
        self.prev_pos = pygame.Vector2(self.pos)

        move = pygame.Vector2(0, 0)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1

        if move.length_squared() > 0:
            move = move.normalize()

        self.pos += move * self.speed * dt
        self.pos = arena.clamp(self.pos, self.radius)

    def interpolated_pos(self, alpha: float) -> pygame.Vector2:
        return self.prev_pos.lerp(self.pos, alpha)


class Enemy:
    """Placeholder mover only — a stand-in target for collision/rendering
    until combat runs through the same ink/wave pipeline as the player
    (design doc §4, §6: 'Enemies cast with the identical pipeline')."""

    def __init__(self, start_pos: pygame.Vector2):
        self.pos = pygame.Vector2(start_pos)
        self.prev_pos = pygame.Vector2(start_pos)
        self.radius = config.ENEMY_RADIUS
        self.speed = config.ENEMY_SPEED
        self.heading = pygame.Vector2(1, 0).rotate(random.uniform(0, 360))
        self.retarget_in = random.uniform(0, 2)

    def update(self, dt: float, arena: Arena) -> None:
        self.prev_pos = pygame.Vector2(self.pos)

        self.retarget_in -= dt
        if self.retarget_in <= 0:
            self.heading = pygame.Vector2(1, 0).rotate(random.uniform(0, 360))
            self.retarget_in = random.uniform(1, 3)

        next_pos = self.pos + self.heading * self.speed * dt
        clamped = arena.clamp(next_pos, self.radius)

        if clamped.x != next_pos.x:
            self.heading.x *= -1
        if clamped.y != next_pos.y:
            self.heading.y *= -1

        self.pos = clamped

    def interpolated_pos(self, alpha: float) -> pygame.Vector2:
        return self.prev_pos.lerp(self.pos, alpha)
