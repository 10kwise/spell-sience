import random

import pygame

from . import config
from .arena import Arena
from .camera import Camera
from .entities import Enemy, Player
from .renderer import Renderer


class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.renderer = Renderer(screen)
        self.arena = Arena(config.ARENA_WIDTH, config.ARENA_HEIGHT, config.GRID_CELL_SIZE)
        self.camera = Camera(*screen.get_size())

        self.player = Player(pygame.Vector2(self.arena.width / 2, self.arena.height / 2))
        self.camera.snap_to(self.player.pos)

        self.enemies: list[Enemy] = []
        self._spawn_enemies()

        self.font = pygame.font.SysFont("consolas", 16)
        self.clock = pygame.time.Clock()
        self.running = True

    def _spawn_enemies(self) -> None:
        self.enemies = []
        for _ in range(config.ENEMY_COUNT):
            pos = pygame.Vector2(
                random.uniform(100, self.arena.width - 100),
                random.uniform(100, self.arena.height - 100),
            )
            self.enemies.append(Enemy(pos))

    def handle_resize(self, width: int, height: int) -> None:
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.renderer.surface = self.screen
        self.camera.resize(width, height)

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.arena)
        for enemy in self.enemies:
            enemy.update(dt, self.arena)

    def render(self, alpha: float) -> None:
        player_pos = self.player.interpolated_pos(alpha)
        self.camera.follow(player_pos, config.CAMERA_SMOOTHING)

        self.renderer.clear()
        self.renderer.draw_arena(self.arena, self.camera)

        for enemy in self.enemies:
            self.renderer.draw_entity(
                enemy.interpolated_pos(alpha), self.camera, enemy.radius, config.COLOR_ENEMY
            )

        self.renderer.draw_entity(player_pos, self.camera, self.player.radius, config.COLOR_PLAYER)

        hud_lines = [
            "WASD / arrows to move  —  ESC to quit",
            f"pos: {player_pos.x:.0f}, {player_pos.y:.0f}",
            f"fps: {self.clock.get_fps():.0f}",
        ]
        for i, line in enumerate(hud_lines):
            text = self.font.render(line, True, config.COLOR_HUD)
            self.screen.blit(text, (8, 8 + i * 18))

        pygame.display.flip()

    def run(self) -> None:
        accumulator = 0.0

        while self.running:
            frame_time = self.clock.tick(240) / 1000.0
            if frame_time > config.MAX_FRAME_TIME:
                frame_time = config.MAX_FRAME_TIME

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event.w, event.h)

            accumulator += frame_time
            while accumulator >= config.FIXED_DT:
                self.update(config.FIXED_DT)
                accumulator -= config.FIXED_DT

            alpha = accumulator / config.FIXED_DT
            self.render(alpha)
