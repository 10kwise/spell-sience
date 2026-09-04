"""Tuning constants. One file, so balance is a diff and not a scavenger hunt.

Anything here that is load-bearing carries a note about what it trades
against, because the numbers in a game like this are not arbitrary and the
next person to touch one should know what they are about to break.
"""

# ---------------------------------------------------------------- display

SCREEN_W, SCREEN_H = 1280, 760
FPS = 60
# The light map is rendered small and scaled up. That is the whole trick
# behind cheap volumetric dark: a 1/5-scale additive buffer, smoothscaled,
# gives soft falloff for the price of a 256x152 blit.
LIGHT_SCALE = 5

TILE = 32                      # px per solid tile
ROOM_W, ROOM_H = 48, 27        # tiles per room -> 1536 x 864 px, wider than
                               # the screen, so the camera has somewhere to go

# ------------------------------------------------------------- the water

# Water is a fluid, not an ice rink. Drag is high and acceleration is low,
# so everything glides and nothing turns on a dime. This is the single
# biggest contributor to the game's pacing: if you raise ACCEL or lower
# DRAG, dread becomes twitch, and the stealth systems stop mattering
# because the player can simply outrun consequences.
PLAYER_ACCEL = 1150.0
PLAYER_DRAG = 3.1
PLAYER_MAX_SPEED = 235.0

# Buoyancy. A body's brine fraction decides whether it sinks or rises, and
# that is traversal, not flavour: heavy bodies walk the floor, light bodies
# climb shafts. NEUTRAL_BRINE is the fraction at which you hang still.
GRAVITY = 470.0
NEUTRAL_BRINE = 0.30
BUOYANCY_GAIN = 3.4

# ------------------------------------------------------------ metabolism

# Reserve is the tank your chains fire from. Small enough that a greedy
# chain empties it in a handful of shots, so you must go and take more
# from the world, which is the thing that makes you leave cover.
RESERVE_CAP = 100.0
RESERVE_START = 40.0

VIABILITY_MAX = 100.0
# Starvation. Running dry does not kill quickly — it kills *inevitably*,
# which is a different and better feeling. You always have time to fix it
# and you always know you are on a clock.
STARVE_RATE = 3.6              # viability/sec at zero reserve
IMBALANCE_RATE = 2.2           # viability/sec at maximum composition strain

# ------------------------------------------------------------------ heat

# Organ heat. An organ that fires accumulates heat, spills a fraction into
# its grid neighbours, and dumps the rest into the water where it becomes
# light and noise. Layout is thermal management; thermal management is
# stealth. These three numbers are that whole loop.
ORGAN_HEAT_CAP = 100.0
ORGAN_CONDUCT = 0.55           # fraction/sec moved toward a hot neighbour
ORGAN_RADIATE = 0.30           # fraction/sec dumped into the world
ORGAN_SEIZE_AT = 88.0          # above this an organ stops working
ORGAN_COOL_AT = 62.0           # ...and does not restart until it drops here
                               # (hysteresis: without a gap, an organ at the
                               # threshold stutters on and off every frame)

# ------------------------------------------------------------ disturbance

# The attention economy. Every loud thing adds; it bleeds off slowly. The
# Apex homes on it. DISTURB_DECAY is the most dangerous knob in the file:
# raise it and stealth becomes free, lower it and a single mistake ends a
# run an hour later.
DISTURB_CAP = 100.0
DISTURB_DECAY = 2.4            # per second
DISTURB_APEX_WAKE = 42.0       # the Apex starts hunting above this
DISTURB_APEX_SLEEP = 16.0      # ...and loses interest below this

# ------------------------------------------------------------- effects

# Master exchange rate: humour magnitude -> world consequence. Everything
# downstream of these is derived, so this is the one place to turn if the
# whole game feels too weak or too strong.
EFFECT_SCALE = 1.0
DAMAGE_PER_MAGNITUDE = 4.2
FORCE_PER_MAGNITUDE = 240.0
HEAT_PER_MAGNITUDE = 1.35
SILT_PER_MAGNITUDE = 0.90
SPARK_PER_MAGNITUDE = 1.20

# Incoming damage, scaled once at the point it lands on you.
#
# Creatures and the player share every rule up to this line, which is the
# whole design — but they do not share a viability budget, and unscaled the
# shared rules were lethal in a way that broke the pacing rather than
# sharpening it: an Ossuary's cone came to 52 against a player with 100, a
# pair of Carrion Drifts could take a healthy body to dead inside two
# frames, and every routing, stealth and retreat decision in the game
# stopped mattering because nothing survived contact either way.
#
# At 0.45 the heaviest thing in the deep hits for about a quarter of you.
# Four or five landed attacks is long enough to notice, decide and run,
# which is the fight this game is supposed to be having.
HOSTILE_DAMAGE = 0.45

# Divergence: 0 = perfectly balanced humours, 1 = a single humour.
# This is the two-sided key. Below GENTLE_BELOW a charge counts as living
# tissue and can open things; above it a charge is a weapon and is heard.
GENTLE_BELOW = 0.22
DIVERGENCE_DAMAGE_FLOOR = 0.15  # below this a charge is too smeared to concentrate

# --------------------------------------------------------------- fields

FIELD_CELL = 24.0              # px per field cell
HEAT_DECAY = 0.42              # per second
HEAT_DIFFUSE = 1.6             # per second
SILT_DECAY = 0.16              # silt lingers; that is the point of silt
SILT_DIFFUSE = 0.9
CURRENT_DECAY = 1.1
SPARKF_DECAY = 2.6             # charged water dissipates fast
MAX_DIFFUSE_STEP = 0.45        # explicit-Laplacian stability cap

# -------------------------------------------------------------- rendering

# Sight. You see by your own glow and by whatever else is burning. This is
# the horror budget: a bigger number is a safer game.
# Sight. You see by your own glow and by whatever else is burning.
#
# 96px was honest to the fiction and unplayable in practice: on a 1280-wide
# screen it lit a pool smaller than the player's own HUD widget, and the
# room around it was not dark so much as *absent* — you could not tell a
# wall from an opening from a bug in the renderer, which is the one kind of
# darkness that stops being frightening.
BASE_SIGHT = 245.0             # px, your dimmest possible glow
SIGHT_PER_ICHOR = 3.2          # ...and what carrying heat adds to it
MAX_SIGHT = 620.0

# The floor of the light buffer. Not zero: a faint everywhere-glow means
# the shape of the room is *suggested* at any distance while remaining
# unreadable, so you always know there is geometry and never know what it
# is. Raising this is the fastest way to make the game less frightening.
LIGHT_FLOOR = (30, 33, 40)

AMBIENT = (7, 10, 13)          # what "unlit" looks like. Never pure black:
                               # pure black hides the difference between an
                               # empty room and a wall, and that reads as a
                               # bug rather than as darkness.
