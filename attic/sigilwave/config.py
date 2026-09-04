"""Tunable constants for the base game. Sim-specific numbers (dx, c, dt for
the waveguide network) belong in a separate module once §5 gets built —
this fixed step is the gameplay step, not the sim step."""

FIXED_DT = 1 / 60
MAX_FRAME_TIME = 0.25  # clamp spiral-of-death after alt-tab

ARENA_WIDTH = 2400
ARENA_HEIGHT = 1600
GRID_CELL_SIZE = 64

PLAYER_RADIUS = 14
PLAYER_SPEED = 220.0  # px/s

ENEMY_RADIUS = 12
ENEMY_SPEED = 90.0
ENEMY_COUNT = 5

CAMERA_SMOOTHING = 0.15

COLOR_BG = (10, 11, 15)
COLOR_GRID = (90, 110, 140)
COLOR_BOUNDS = (150, 180, 220)
COLOR_PLAYER = (127, 212, 224)
COLOR_ENEMY = (196, 106, 90)
COLOR_HUD = (159, 180, 199)
