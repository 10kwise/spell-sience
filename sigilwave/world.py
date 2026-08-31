"""The World layer (design doc §4.1), stages 5-6's minimal slice: one movable
token carrying all three fields (kinetic, thermal, phase). Fields-on-a-
coarse-grid and multiple entities come later — this exists only to prove a
drawing can move, heat/chill, and phase something.
"""

import pygame

PHASE_GHOST_THRESHOLD = 0.5  # above this, the token stops colliding with arena bounds (§2.9)
PHASE_DECAY_PER_SEC = 0.6
TEMPERATURE_DECAY_PER_SEC = 0.4
# How far outside bounds a ghosted token may drift before being soft-clamped.
# Without this, a sustained kinetic push during a long ghost window can carry
# the token arbitrarily far, and the instant phase decays back below
# PHASE_GHOST_THRESHOLD the very next collision check snaps it straight back
# to the wall in one frame — a large, jarring teleport-in-reverse that reads
# as a bug rather than "displacement," undercutting the whole point of the
# mechanic (§2.9). Capping the overshoot bounds how far that eventual snap
# can be, while still leaving plenty of room for a deliberate phase+kinetic
# displacement to read as passing through a wall.
GHOST_OVERSHOOT_MARGIN = 200.0


class Token:
    def __init__(self, pos: pygame.Vector2, radius: float = 16.0, damping: float = 0.9):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(0, 0)
        self.radius = radius
        self.damping = damping
        self.temperature = 0.0  # + hot (burn), - cold (chill); §2.9 thermal field
        self.phase = 0.0  # 0 = solid, 1 = fully non-interacting; §2.9 phase field

    def apply_kinetic_impulse(self, impulse: pygame.Vector2) -> None:
        self.vel += impulse

    def apply_thermal(self, amount: float) -> None:
        self.temperature += amount

    def apply_phase(self, amount: float) -> None:
        self.phase = max(0.0, min(1.0, self.phase + amount))

    def update(self, dt: float, bounds: pygame.Rect) -> None:
        self.pos += self.vel * dt
        self.vel *= self.damping ** (dt * 60)  # damping tuned per-frame at ~60fps, scaled to actual dt

        self.temperature *= max(0.0, 1.0 - TEMPERATURE_DECAY_PER_SEC * dt)
        self.phase = max(0.0, self.phase - PHASE_DECAY_PER_SEC * dt)

        if self.phase > PHASE_GHOST_THRESHOLD:
            # Ghosting: skip collision, but soft-clamp to a wide margin
            # outside bounds so un-ghosting later can't snap the token back
            # across an unbounded distance (see GHOST_OVERSHOOT_MARGIN).
            margin = GHOST_OVERSHOOT_MARGIN
            self.pos.x = max(bounds.left - margin, min(bounds.right + margin, self.pos.x))
            self.pos.y = max(bounds.top - margin, min(bounds.bottom + margin, self.pos.y))
            return

        if self.pos.x < bounds.left + self.radius:
            self.pos.x = bounds.left + self.radius
            self.vel.x *= -0.5
        elif self.pos.x > bounds.right - self.radius:
            self.pos.x = bounds.right - self.radius
            self.vel.x *= -0.5

        if self.pos.y < bounds.top + self.radius:
            self.pos.y = bounds.top + self.radius
            self.vel.y *= -0.5
        elif self.pos.y > bounds.bottom - self.radius:
            self.pos.y = bounds.bottom - self.radius
            self.vel.y *= -0.5
