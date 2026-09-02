"""The water shader. Six layers, none of them decoration.

Contract with the rest of the codebase: this class READS `medium.solid`,
`medium.temp`, `medium.bubbles`, `medium.c_field`, `medium.cell_size`,
`medium.nx`, `medium.ny`. It writes nothing, imports no front code, and holds
no reference to anything that steps. Hand it any object with those attributes
and it will draw it.

Why it is fast even though it posterises a full-resolution buffer: the water
field changes at the speed of heat diffusion and buoyancy, which is seconds,
not frames. So the expensive layer is rebuilt on a slow clock and cached, and
everything that actually moves at 60 Hz -- shafts, marine snow, wake -- is a
cheap overlay drawn on top of the cached surface.

The one trick worth naming: the level field is quantised AFTER it is upscaled,
never before. Posterising the 75x50 grid and then scaling it up gives 16-pixel
stair-steps; scaling the smooth field up and posterising at full resolution
gives smooth, curved, single-pixel-crisp contours out of the same coarse data.
That inversion is the whole difference between "cel shaded" and "low
resolution".
"""

import math

import numpy as np
import pygame

from .palette import (
    CAUSTIC,
    GAS,
    ROCK_FLOOR,
    ROCK_RIM,
    ROCK_TOP,
    SNOW,
    WAKE,
    WARM,
    build_lut,
)

# ----------------------------------------------------------------------
# The level field
# ----------------------------------------------------------------------
# Depth dominates so that the ramp stays monotonic and the deep stays dark --
# that is the mood, and it is also the progression axis. The field term is a
# perturbation on top: enough to bend a band around a vent plume and to crowd
# the bands together at the thermocline, not enough to make deep water look
# shallow where the sound channel turns c back upward.
DEPTH_WEIGHT = 0.74
FIELD_WEIGHT = 0.26

# Bubbles lift the water several bands toward the light. Physically this is
# Wood's collapse (a cloud is far slower than clear water) and optically it is
# scattering; both point the same way, which is why the curtain reads as milky
# without being special-cased.
GAS_LIFT = 0.42
GAS_FULL = 0.20          # bubble fraction that counts as a full curtain

# Heat diffuses about one cell per second, so ten rebuilds a second is already
# finer than anything the medium can do. At 60 fps this is the difference
# between 20 ms a frame and 3.
REBUILD_EVERY = 6

WARM_FULL = 2.5          # degrees above the row median that count as a plume
WARM_STEPS = 3.0
GAS_STEPS = 3.0

# ----------------------------------------------------------------------
# Internal waves
# ----------------------------------------------------------------------
# Without this the bands are dead-straight horizontal stripes, because c in an
# undisturbed ocean varies with depth and almost nothing else. Straight stripes
# read as a gradient chart rather than as water, and it is the single thing
# that most stops the picture from looking alive.
#
# The fix is not noise for its own sake: a density interface in a real ocean
# carries INTERNAL WAVES, slow metre-scale undulations that live on the
# interface and die away above and below it. So the displacement is enveloped
# on the thermocline -- found from the field rather than hardcoded -- and the
# bands ripple hardest exactly where there is something to ripple.
WAVE_AMPLITUDE = 0.034   # in normalised depth units
WAVE_FLOOR = 0.30        # how much of it survives away from the interface

# ----------------------------------------------------------------------
# Surface light
# ----------------------------------------------------------------------
# Shafts, not a caustic field. A 2D sine field upscaled with nearest-neighbour
# gave 6-pixel blocks that read as debris floating at the top of the screen;
# god rays are cheaper, crisper, and unmistakably underwater. Each shaft is a
# stack of trapezoid slices with a stepped falloff, so the fade is itself
# cel-shaded rather than fighting the style with a gradient.
SHAFT_COUNT = 6
SHAFT_SLICES = 5
# Turned right down from the first pass. Shafts are what says "underwater",
# but bright ones say "sunny lagoon", and a few dim cold ones say "there is a
# surface up there somewhere and you are a long way under it" -- which is the
# sentence this room is supposed to be saying.
SHAFT_GAIN = 0.13
SHAFT_SWAY = 26.0
SURFACE_STRIPS = ((26, 0.07), (14, 0.13), (6, 0.24))
# The sway has a period of about half a minute and the surface ripple a little
# under a second, so redrawing this geometry sixty times a second is drawing
# the same picture over and over. Rebuilt on a slow clock like the water body,
# and only the finished buffer is blitted each frame.
SHAFT_REBUILD_EVERY = 4

# ----------------------------------------------------------------------
# Marine snow
# ----------------------------------------------------------------------
# It sells "water" for almost nothing, and it does a second job: it gives the
# eye something moving between pings, so a still room never reads as a frozen
# one. Three parallax layers, sinking, because marine snow falls.
SNOW_COUNT = 260
SNOW_SPEEDS = (5.0, 9.0, 15.0)
SNOW_BRIGHT = (0.35, 0.6, 1.0)
SNOW_DRIFT = 3.0

# ----------------------------------------------------------------------
# Sight
# ----------------------------------------------------------------------
# The one field that makes this an eerie room rather than a lit diorama.
# Everything drawn -- water, shafts, snow, rock -- is multiplied by it before
# the ping is added on top, so the picture is dark by default and legible only
# where the player has earned it.
#
# WATER and LAND see differently, and that split is the whole design.
#
# The water gets a generous ambient, because it is the FOG -- LIMBO is dark
# silhouettes against a lighter ground, not black on black, and with no ambient
# at all the picture goes uniformly black and every silhouette in it disappears
# along with the banding. The sea is the thing you always see a little of.
#
# Land gets NO ambient. Rock is drawn as a near-black shape that occludes the
# fog behind it, so close land reads as a silhouette for free -- and far land,
# where the fog has already gone black, is genuinely invisible until a ping
# paints its edges. That is what makes a ping worth firing.
WATER_AMBIENT = 0.50
NEAR_REACH = 150.0
NEAR_FALLOFF = 1.5
SIGHT_REBUILD_EVERY = 3

# The fog falls away with distance as well, and it has to. A UNIFORM ambient
# lights the far side of the room just as well as the near side, and a black
# rock silhouette against lit fog is perfectly readable at any range -- so the
# whole map was legible without firing anything and the ping had no job. With
# the fog dying at range, distant rock is black on black and genuinely has to
# be found.
FOG_RANGE = 520.0
FOG_FAR = 0.16

# The room forgets. Slowly enough that a ping is worth spending and the map
# stays usable while you swim across it; fast enough that it has to be spent
# again. Half-life is about sixteen seconds at 60 fps.
REVEAL_DECAY = 0.9992
REVEAL_SPREAD = 1

# Corners fall away. Baked into the sight field rather than blitted separately,
# because both are a per-cell multiply and doing them together costs one pass
# instead of two.
VIGNETTE_STRENGTH = 0.55
VIGNETTE_POWER = 1.7

# ----------------------------------------------------------------------
# Grain
# ----------------------------------------------------------------------
# The last thing that separates "dark render" from "photographed in the dark".
# Generated at half resolution and scaled up with nearest, so a grain dot is
# two pixels -- real film grain is not pixel-sized either, and the half-size
# buffers cost a quarter of the memory.
GRAIN_TILES = 5
GRAIN_AMPLITUDE = 13

RIM_THICKNESS = 2
TOP_THICKNESS = 3

# ----------------------------------------------------------------------
# Wake
# ----------------------------------------------------------------------
# Quantised with CEIL, not floor. Floor is right for a tint that should vanish
# when it is weak, but a wavefront's whole story is what happens to it as it
# weakens -- flooring it means the front is drawn brightly for a moment and
# then snaps to nothing at a third of full strength, deleting the entire range
# the player is meant to be reading.
# The trail length is WAKE_DECAY against WAKE_CUTOFF, and it is the difference
# between a wavefront and a slab: at 0.88 a ring leaves a hundred-pixel wake
# that reads as a moving wall of light with holes in it. The front is the
# light source, so it wants to be thin, bright and edged.
WAKE_DECAY = 0.80
WAKE_STEPS = 5.0
WAKE_GAIN = 1.2
# Ceil without a cutoff lights every cell the front has EVER touched, because
# an arbitrarily small value still rounds up to one full step. The ring then
# fills in behind itself and reads as a disc. The cutoff is what makes it an
# arc again: below it the water has forgotten, above it the step ladder keeps
# the whole dynamic range.
WAKE_CUTOFF = 0.09
# The wake is ART, not physics, so it is not obliged to live on the medium's
# grid -- and at 16 px a cell a ring comes out visibly stair-stepped. Its own
# finer grid costs a few hundred kilobytes and buys a clean arc.
WAKE_SCALE = 4


def _gray_surface(field):
    """A (rows, cols) float array in 0..1 as an 8-bit pygame surface.

    Everything coarse in here becomes a surface exactly once, this way, so the
    row/column-to-width/height transpose lives in one place instead of being
    rediscovered (and got wrong) at four call sites."""
    g = np.clip(field * 255.0, 0.0, 255.0).astype(np.uint8)
    return pygame.surfarray.make_surface(
        np.repeat(np.transpose(g)[:, :, None], 3, axis=2))


def _tint_surface(field, colour, steps, ceil=False, cutoff=0.0):
    """A coarse field as a flat-shaded tint in one colour.

    Quantised before it is scaled, unlike the water body: a tint is a local
    blob a few cells across, so its steps want to stay soft-edged rather than
    fighting the water's contours for attention."""
    v = np.clip(field, 0.0, 1.0)
    if cutoff > 0.0:
        v = np.where(v < cutoff, 0.0, v)
    q = (np.ceil(v * steps) if ceil else np.floor(v * steps)) / steps
    rgb = (np.clip(q, 0.0, 1.0)[:, :, None]
           * np.array(colour, dtype=float)).astype(np.uint8)
    return pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))


def _blur3(a):
    """One separable 1-2-1 pass, edges held.

    A single bilinear jump out of a 75x50 grid leaves the interpolation's own
    facets in the field, and posterising turns every facet into a visible kink
    along a contour. Softening by one cell first costs nothing at this size and
    is what makes the band edges read as curves rather than as polygons."""
    b = a.astype(float, copy=True)
    if a.shape[0] > 2:
        b[1:-1, :] = (a[:-2, :] + 2.0 * a[1:-1, :] + a[2:, :]) * 0.25
    if a.shape[1] > 2:
        c = b.copy()
        c[:, 1:-1] = (b[:, :-2] + 2.0 * b[:, 1:-1] + b[:, 2:]) * 0.25
        return c
    return b


def _scatter_max(grid, rows, cols, amp, nx, ny):
    """Accumulate scattered samples into a grid, then keep the brighter of
    that and what was already there.

    Via `np.bincount`, NOT `np.maximum.at`. The `.at` form is an unbuffered
    ufunc and is spectacularly slow -- with a front resampled to fifteen
    hundred points it was costing more than every other layer of the shader
    put together. bincount does the scatter in C.

    The difference in semantics is that samples landing in the same cell SUM
    rather than take a maximum, which is the better answer anyway: where a
    front folds onto itself the wave really is louder there, so a caustic
    comes out brighter for free. It is clipped before it meets the grid so
    that a fold cannot exceed a full-strength front."""
    acc = np.bincount(rows * nx + cols, weights=amp, minlength=ny * nx)
    np.maximum(grid, np.minimum(acc.reshape(ny, nx), 1.0), out=grid)


def _thicken(mask, n, axis=None):
    """Grow a boolean mask by n pixels. Along `axis` only, if given.

    A one-pixel rim is invisible at any sane viewing distance, which is why the
    first pass looked like it had no rim light at all when it did."""
    out = mask.copy()
    for k in range(1, n + 1):
        if axis in (None, 0):
            out[k:, :] |= mask[:-k, :]
            out[:-k, :] |= mask[k:, :]
        if axis in (None, 1):
            out[:, k:] |= mask[:, :-k]
            out[:, :-k] |= mask[:, k:]
    return out


class WaterShader:
    """Draws the ocean. Owns no simulation, mutates no medium."""

    def __init__(self, size, medium, seed=7):
        self.size = (int(size[0]), int(size[1]))
        self.medium = medium
        self._lut = build_lut()
        self.bands = len(self._lut)
        # Gray value -> band colour, resolved once so the per-frame path is a
        # single gather with no arithmetic in it.
        self._lut256 = np.array(
            [self._lut[(g * (self.bands - 1)) // 255] for g in range(256)],
            dtype=np.uint8)
        self._mid_size = (max(self.size[0] // 4, 2), max(self.size[1] // 4, 2))

        # The field term is normalised against a robust range taken ONCE, from
        # the room as built. Renormalising every frame would make the whole sea
        # change colour the moment a bubble cloud dropped the minimum through
        # the floor -- the picture would be keyed to the most extreme cell on
        # screen instead of to the water.
        c = np.asarray(medium.c_field, dtype=float)
        open_water = ~np.asarray(medium.solid)
        vals = c[open_water] if open_water.any() else c.ravel()
        self._c_lo = float(np.percentile(vals, 2.0))
        self._c_hi = float(np.percentile(vals, 98.0))
        if self._c_hi - self._c_lo < 1e-6:
            self._c_hi = self._c_lo + 1.0

        self._depth = (np.arange(medium.ny, dtype=float)
                       / max(medium.ny - 1, 1)).reshape(-1, 1)
        self._wave_envelope = self._find_interface(c)

        self._water = pygame.Surface(self.size)
        self._shafts = pygame.Surface(self.size)
        # An 8-bit surface whose palette IS the band ramp. See _rebuild_water.
        self._palette_surf = pygame.Surface(self.size, 0, 8)
        self._palette_surf.set_palette(
            [tuple(int(x) for x in c) for c in self._lut256])
        self._frame = 0
        self._time = 0.0

        # Sound in the water, in medium cells. A caller stamps into this; the
        # shader only decays and draws it. Keeping it here rather than in the
        # medium is what lets the physics be rewritten without touching art.
        self.wake = np.zeros((medium.ny * WAKE_SCALE, medium.nx * WAKE_SCALE))
        self._wake_cs = medium.cell_size / WAKE_SCALE
        # The room's memory of having been touched by a ping. This is the
        # player's map, and it is the main reason anything past arm's length
        # is ever visible at all.
        self.reveal = np.zeros((medium.ny, medium.nx))
        self._sight = pygame.Surface(self.size)
        self._sight_land = pygame.Surface(self.size)
        self._lit_scratch = pygame.Surface(self.size)

        rng = np.random.default_rng(seed)
        self._build_rock()
        self._build_snow(rng)
        self._build_shafts(rng)
        self._build_vignette()
        self._build_grain(rng)
        self._rebuild_water()

    # -- the interface -------------------------------------------------
    def _find_interface(self, c):
        """Where the water is most stratified, measured rather than assumed.

        The thermocline's depth is a property of the room, and rooms differ --
        a bench tank has no thermocline at all. Reading it off the field keeps
        this package from importing a constant out of `stage/world.py` and
        quietly desynchronising from it later."""
        column = np.mean(c, axis=1)
        if column.size < 3:
            return np.ones_like(self._depth)
        slope = np.abs(np.gradient(column))
        at = float(np.argmax(slope)) / max(column.size - 1, 1)
        width = 0.16
        env = np.exp(-((self._depth - at) / width) ** 2)
        return WAVE_FLOOR + (1.0 - WAVE_FLOOR) * env

    # -- static layers -------------------------------------------------
    def _build_rock(self):
        """A silhouette, not a smudge.

        The old renderer smoothscaled a 75x50 float grid to 1200x800, which is
        a 16x blur of coarse data and mush by construction. Terrain is static,
        so the honest thing is to pay once: upscale the boolean mask, threshold
        it back to a boolean at full resolution, and get a smooth curved
        silhouette with a single-pixel edge. Same information, no fog."""
        m = self.medium
        big = pygame.transform.smoothscale(
            _gray_surface(np.asarray(m.solid, dtype=float)), self.size)
        rock = pygame.surfarray.array3d(big)[:, :, 0] > 127

        # Four-neighbour erosion. The rim is what a ping catches first and it
        # is most of what makes rock read as a surface rather than a hole.
        eroded = np.ones_like(rock)
        eroded[1:, :] &= rock[:-1, :]
        eroded[:-1, :] &= rock[1:, :]
        eroded[:, 1:] &= rock[:, :-1]
        eroded[:, :-1] &= rock[:, 1:]
        eroded &= rock
        rim = _thicken(rock & ~eroded, RIM_THICKNESS) & rock

        # Rock with open water directly above it. Arrays here are indexed
        # [x, y] with y down, so "above" is the previous column of axis 1.
        water_above = np.ones_like(rock)
        water_above[:, 1:] = ~rock[:, :-1]
        top = _thicken(rock & water_above, TOP_THICKNESS, axis=1) & rock

        w, h = self.size
        floor = np.zeros((w, h, 3), dtype=np.uint8)
        floor[rock] = ROCK_FLOOR
        self._rock_floor = pygame.surfarray.make_surface(floor)
        self._rock_floor.set_colorkey((0, 0, 0))

        lit = np.zeros((w, h, 3), dtype=np.uint8)
        lit[rim] = ROCK_RIM
        lit[top] = ROCK_TOP        # the top face wins where they overlap
        self._rock_lit = pygame.surfarray.make_surface(lit)
        self._build_normals()

    def _build_normals(self):
        """Outward surface normals of the rock, on the medium's grid.

        A ping needs to know which way a wall faces in order to leave it, and
        it needs that for hundreds of rays at once -- so this is a field, read
        with a gather, rather than a per-point stencil. Terrain is static, so
        it is built once.

        The solid mask is blurred first because the gradient of a hard boolean
        is zero everywhere except in a one-cell band, and rays that land just
        inside a thick wall would find no normal at all and die in the rock."""
        s = _blur3(_blur3(np.asarray(self.medium.solid, dtype=float)))
        gy, gx = np.gradient(s)
        # s is high INSIDE the rock, so the outward normal is the negative
        # gradient: away from solid, into the water.
        nx, ny = -gx, -gy
        mag = np.sqrt(nx * nx + ny * ny)
        flat = mag < 1e-6
        # Deep inside a wall there is no gradient to read. Anything landing
        # there gets a straight-up normal, which is wrong but bounded -- the
        # alternative is a divide by zero and a NaN ray.
        self._normal_x = np.where(flat, 0.0, nx / np.maximum(mag, 1e-6))
        self._normal_y = np.where(flat, -1.0, ny / np.maximum(mag, 1e-6))

    def solid_normal_at(self, xs, ys):
        """Outward rock normal at world positions, batched."""
        m = self.medium
        cols = np.clip((np.asarray(xs) / m.cell_size).astype(int), 0, m.nx - 1)
        rows = np.clip((np.asarray(ys) / m.cell_size).astype(int), 0, m.ny - 1)
        return self._normal_x[rows, cols], self._normal_y[rows, cols]

    def _build_vignette(self):
        m = self.medium
        cx = (np.arange(m.nx) + 0.5) / m.nx - 0.5
        cy = (np.arange(m.ny) + 0.5) / m.ny - 0.5
        r = np.sqrt((cx.reshape(1, -1) * 1.15) ** 2 + cy.reshape(-1, 1) ** 2)
        r = np.clip(r / 0.72, 0.0, 1.0)
        self._vignette = 1.0 - VIGNETTE_STRENGTH * r ** VIGNETTE_POWER

    def _build_grain(self, rng):
        """A few fixed noise buffers, cycled. Generating noise per frame at
        this size costs more than the rest of the shader put together."""
        w, h = self.size
        gw, gh = max(w // 2, 2), max(h // 2, 2)
        self._grain = []
        for _ in range(GRAIN_TILES):
            n = rng.integers(0, GRAIN_AMPLITUDE, (gw, gh), dtype=np.uint8)
            surf = pygame.surfarray.make_surface(
                np.repeat(n[:, :, None], 3, axis=2))
            self._grain.append(pygame.transform.scale(surf, self.size))

    def _build_snow(self, rng):
        w, h = self.size
        n = SNOW_COUNT
        self._snow_x = rng.uniform(0.0, w, n)
        self._snow_y = rng.uniform(0.0, h, n)
        self._snow_layer = rng.integers(0, len(SNOW_SPEEDS), n)
        self._snow_phase = rng.uniform(0.0, 2.0 * math.pi, n)

    def _build_shafts(self, rng):
        w, h = self.size
        n = SHAFT_COUNT
        self._shaft_x = rng.uniform(-0.05, 1.05, n) * w
        self._shaft_w = rng.uniform(0.020, 0.075, n) * w
        self._shaft_len = rng.uniform(0.30, 0.74, n) * h
        self._shaft_tilt = rng.uniform(-0.20, 0.20, n)
        self._shaft_phase = rng.uniform(0.0, 2.0 * math.pi, n)
        self._shaft_bright = rng.uniform(0.45, 1.0, n)

    # -- the water body ------------------------------------------------
    def _wobble(self):
        """Three slow sines, enveloped on the interface. Cheap, and the only
        thing standing between this and a striped background."""
        t = self._time
        x = np.linspace(0.0, 1.0, self.medium.nx).reshape(1, -1)
        w = (np.sin((x * 2.0 + t * 0.045) * 2.0 * math.pi)
             + 0.55 * np.sin((x * 3.7 - t * 0.031) * 2.0 * math.pi)
             + 0.32 * np.sin((x * 6.3 + t * 0.019) * 2.0 * math.pi))
        return WAVE_AMPLITUDE * (w / 1.87) * self._wave_envelope

    def _rebuild_water(self):
        m = self.medium
        c = np.asarray(m.c_field, dtype=float)
        c_norm = np.clip((c - self._c_lo) / (self._c_hi - self._c_lo), 0.0, 1.0)

        level = DEPTH_WEIGHT * (self._depth + self._wobble()) + FIELD_WEIGHT * c_norm
        gas = np.clip(np.asarray(m.bubbles) / GAS_FULL, 0.0, 1.0)
        level = level - GAS_LIFT * gas

        # Upscale the SMOOTH field, then posterise at full resolution. Doing it
        # the other way round is the whole difference between clean contours
        # and 16-pixel stair-steps -- see the module docstring.
        #
        # In two stages, because one bilinear jump from 75x50 is only
        # C0-continuous: posterising it exposes the interpolation's own facets
        # as polygonal kinks along every contour. The intermediate pass costs
        # almost nothing (smoothscale is priced by its OUTPUT) and the second
        # filtering smooths the facets away.
        mid = pygame.transform.smoothscale(
            _gray_surface(_blur3(level)), self._mid_size)
        big = pygame.transform.smoothscale(mid, self.size)

        # A 256-entry lookup, not arithmetic. The gray value indexes straight
        # into the band colour, which removes an int32 promotion and a divide
        # over two and a half million pixels -- most of this method's cost.
        view = pygame.surfarray.pixels3d(big)
        gray = np.ascontiguousarray(view[:, :, 0])
        del view
        # Posterised by SDL's palette, not by numpy. `lut[gray]` looks like the
        # obvious way to turn a million gray values into band colours, but
        # fancy-indexing promotes the uint8 index array to intp and gathers
        # three bytes a pixel through it: measured at 16.8 ms against 1.5 for
        # this, for a pixel-identical result. The gray value IS the palette
        # index, so the lookup is something the blitter already does for free.
        pygame.surfarray.blit_array(self._palette_surf, gray)
        self._water.blit(self._palette_surf, (0, 0))

        # A cell is warm when it is warmer than the rest of the water AT ITS
        # OWN DEPTH. Against a frozen baseline this would also light up the
        # background gradient being stirred by convection, which is real
        # physics but is not a plume, and drawing it as one makes heat look
        # like it wanders off on its own.
        temp = np.asarray(m.temp)
        warm = (temp - np.median(temp, axis=1, keepdims=True)) / WARM_FULL
        if np.any(warm > 1.0 / WARM_STEPS):
            self._water.blit(
                pygame.transform.smoothscale(
                    _tint_surface(warm, WARM, WARM_STEPS), self.size),
                (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        if gas.any():
            self._water.blit(
                pygame.transform.smoothscale(
                    _tint_surface(gas, GAS, GAS_STEPS), self.size),
                (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    # -- moving layers -------------------------------------------------
    def _draw_surface_light(self, screen):
        """Shafts from a broken surface, plus the surface itself.

        Everything is drawn onto one scratch buffer with ordinary blits and
        added to the screen ONCE. Adding each shaft separately would make
        crossings sum to white, which is the one thing a flat-shaded picture
        must never do."""
        if self._frame % SHAFT_REBUILD_EVERY == 1:
            self._rebuild_shafts()
        screen.blit(self._shafts, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _rebuild_shafts(self):
        w, h = self.size
        t = self._time
        self._shafts.fill((0, 0, 0))

        for i in range(SHAFT_COUNT):
            sway = math.sin(t * 0.23 + self._shaft_phase[i]) * SHAFT_SWAY
            x0 = self._shaft_x[i] + sway
            length = self._shaft_len[i]
            for s in range(SHAFT_SLICES):
                y0 = length * s / SHAFT_SLICES
                y1 = length * (s + 1) / SHAFT_SLICES
                # Stepped falloff: the fade is quantised like everything else.
                b = self._shaft_bright[i] * SHAFT_GAIN * (1.0 - s / SHAFT_SLICES) ** 1.8
                col = tuple(int(cc * b) for cc in CAUSTIC)
                if max(col) <= 1:
                    continue
                hw0 = self._shaft_w[i] * 0.5 * (1.0 + 0.9 * y0 / max(length, 1.0))
                hw1 = self._shaft_w[i] * 0.5 * (1.0 + 0.9 * y1 / max(length, 1.0))
                cx0 = x0 + self._shaft_tilt[i] * y0
                cx1 = x0 + self._shaft_tilt[i] * y1
                pygame.draw.polygon(self._shafts, col, [
                    (cx0 - hw0, y0), (cx0 + hw0, y0),
                    (cx1 + hw1, y1), (cx1 - hw1, y1)])

        xs = np.linspace(0.0, w, 64)
        for depth_px, bright in SURFACE_STRIPS:
            ys = (depth_px
                  + np.sin(xs * 0.011 + t * 0.9) * 3.0
                  + np.sin(xs * 0.023 - t * 0.6) * 1.8)
            col = tuple(int(cc * bright) for cc in CAUSTIC)
            pts = [(0.0, 0.0)] + list(zip(xs, ys)) + [(w, 0.0)]
            pygame.draw.polygon(self._shafts, col, pts)

    def _step_snow(self, dt):
        speed = np.array(SNOW_SPEEDS)[self._snow_layer]
        self._snow_y += speed * dt
        self._snow_x += np.sin(self._snow_phase + self._snow_y * 0.01) * SNOW_DRIFT * dt
        w, h = self.size
        np.mod(self._snow_y, h, out=self._snow_y)
        np.mod(self._snow_x, w, out=self._snow_x)

    def _draw_snow(self, screen):
        h = self.size[1]
        for i in range(SNOW_COUNT):
            layer = self._snow_layer[i]
            # Dims with depth like everything else, so snow never floats
            # brighter than the water it is suspended in.
            fade = (1.0 - self._snow_y[i] / h) * 0.75 + 0.25
            b = SNOW_BRIGHT[layer] * fade
            col = (int(SNOW[0] * b), int(SNOW[1] * b), int(SNOW[2] * b))
            r = 1 if layer < 2 else 2
            pygame.draw.circle(screen, col,
                               (int(self._snow_x[i]), int(self._snow_y[i])), r)

    def _draw_rock(self, screen):
        """The silhouette first, then only the edges a ping has found.

        The floor is blitted AFTER the water has been fogged and is not itself
        darkened, which is the trick that makes both halves of the brief work
        at once: near the diver it is a black shape against lit fog, and far
        away it is a black shape against black fog -- invisible, until the
        rim and top faces are added back through the land field."""
        screen.blit(self._rock_floor, (0, 0))
        screen.blit(self._lit_scratch, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def add_reveal(self, xs, ys, amounts):
        """Remember that a ping touched rock here.

        Neighbours light too, at a discount. A ray lands on one cell, but what
        the sound met was a SURFACE, and lighting single cells leaves the room
        as a scatter of unconnected specks that never resolves into a wall --
        which is the mistake that made the previous renderer's terrain
        unreadable."""
        m = self.medium
        c0 = np.clip((np.asarray(xs) / m.cell_size).astype(np.intp), 0, m.nx - 1)
        r0 = np.clip((np.asarray(ys) / m.cell_size).astype(np.intp), 0, m.ny - 1)
        amp0 = np.clip(np.asarray(amounts, dtype=float), 0.0, 1.0)
        rr, cc, aa = [], [], []
        for dr in range(-REVEAL_SPREAD, REVEAL_SPREAD + 1):
            for dc in range(-REVEAL_SPREAD, REVEAL_SPREAD + 1):
                rr.append(np.clip(r0 + dr, 0, m.ny - 1))
                cc.append(np.clip(c0 + dc, 0, m.nx - 1))
                aa.append(amp0 if (dr == 0 and dc == 0) else amp0 * 0.6)
        _scatter_max(self.reveal, np.concatenate(rr), np.concatenate(cc),
                     np.concatenate(aa), m.nx, m.ny)

    def _rebuild_sight(self, diver):
        """Two fields out of the same three terms. See the Sight block."""
        m = self.medium
        near = np.zeros((m.ny, m.nx))
        fog = np.full((m.ny, m.nx), FOG_FAR)
        if diver is not None:
            xs = (np.arange(m.nx) + 0.5) * m.cell_size
            ys = (np.arange(m.ny) + 0.5) * m.cell_size
            dx = xs.reshape(1, -1) - float(diver[0])
            dy = ys.reshape(-1, 1) - float(diver[1])
            d = np.sqrt(dx * dx + dy * dy)
            near = np.clip(1.0 - d / NEAR_REACH, 0.0, 1.0) ** NEAR_FALLOFF
            fog = 1.0 - (1.0 - FOG_FAR) * np.clip(d / FOG_RANGE, 0.0, 1.0)
        known = near + self.reveal
        water = np.clip(WATER_AMBIENT * fog + known, 0.0, 1.0) * self._vignette
        land = np.clip(known, 0.0, 1.0) * self._vignette
        self._sight = pygame.transform.smoothscale(
            _gray_surface(water), self.size)
        self._sight_land = pygame.transform.smoothscale(
            _gray_surface(land), self.size)
        # The lit rock only changes when the land field does, so the multiply
        # happens here rather than once a frame in _draw_rock.
        self._lit_scratch.blit(self._rock_lit, (0, 0))
        self._lit_scratch.blit(self._sight_land, (0, 0),
                               special_flags=pygame.BLEND_RGB_MULT)

    def add_wake(self, x, y, radius, amount):
        """Sound raises the water it is in.

        This is the layer that replaces the old moire trail buffer. A wavefront
        is not a wire drawn over the sea; it is energy IN the sea, so it lifts
        the local water toward the light and gets posterised by the same steps
        as everything else. The trail comes out cel-shaded for free, and it is
        causally honest besides."""
        cs = self._wake_cs
        ny, nx = self.wake.shape
        c0 = max(int((x - radius) / cs), 0)
        c1 = min(int((x + radius) / cs) + 1, nx)
        r0 = max(int((y - radius) / cs), 0)
        r1 = min(int((y + radius) / cs) + 1, ny)
        if c0 >= c1 or r0 >= r1:
            return
        cols = (np.arange(c0, c1) + 0.5) * cs - x
        rows = (np.arange(r0, r1) + 0.5) * cs - y
        d = np.sqrt(rows.reshape(-1, 1) ** 2 + cols.reshape(1, -1) ** 2)
        w = np.clip(1.0 - d / max(radius, 1e-6), 0.0, 1.0) ** 2
        np.maximum(self.wake[r0:r1, c0:c1], w * amount,
                   out=self.wake[r0:r1, c0:c1])

    def add_wake_points(self, xs, ys, amounts, spread=0):
        """Stamp many samples of a wavefront at once.

        `add_wake` is a per-point call and a wide front is hundreds of points a
        frame, at which scale the numpy call overhead costs more than the
        arithmetic. This is the batched form, and it is also the shape the real
        fronts want -- a Front already holds its vertices and intensities as
        arrays.

        `spread` defaults to none, and should usually stay there. `np.maximum.at`
        is an unbuffered scatter and by far the most expensive thing in here, so
        a 3x3 stamp costs nine of them -- measured slower than simply sampling
        three times as densely and letting the blur in `_draw_wake` close the
        gaps, which is all the spread was ever doing."""
        cs = self._wake_cs
        ny, nx = self.wake.shape
        cols = np.clip((np.asarray(xs) / cs).astype(np.intp), 0, nx - 1)
        rows = np.clip((np.asarray(ys) / cs).astype(np.intp), 0, ny - 1)
        amp = np.asarray(amounts, dtype=float)
        if amp.ndim == 0:
            amp = np.full(rows.shape, float(amp))
        if spread:
            rr, cc, aa = [], [], []
            for dr in range(-spread, spread + 1):
                for dc in range(-spread, spread + 1):
                    f = (1.0 if (dr == 0 and dc == 0)
                         else 0.55 if abs(dr) + abs(dc) == 1 else 0.34)
                    rr.append(np.clip(rows + dr, 0, ny - 1))
                    cc.append(np.clip(cols + dc, 0, nx - 1))
                    aa.append(amp * f)
            rows, cols, amp = (np.concatenate(rr), np.concatenate(cc),
                               np.concatenate(aa))
        _scatter_max(self.wake, rows, cols, amp, nx, ny)

    def _draw_wake(self, screen):
        self.wake *= WAKE_DECAY
        peak = float(self.wake.max())
        if peak < 1e-3:
            return
        # Blurred once before it is stepped. However densely a front is
        # sampled, its points land in the wake grid unevenly, and posterising
        # that unevenness turns it into a stipple that reads as a dashed
        # circle. A second pass took the serration off the trailing edge too,
        # but it also softened the front into a cloud -- and this is the light
        # source, so it has to read as an edge. Denser rays close the gaps
        # instead.
        smooth = _blur3(self.wake) * WAKE_GAIN

        # Only the region the front is actually in. Scaling the whole wake
        # grid up to the full screen every frame was the single most expensive
        # thing in the shader, and for most of a ping's life the lit part of
        # it is a fraction of the room -- a new ring is a few cells across.
        # smoothscale is priced by its output, so shrinking the output is the
        # whole saving.
        live = smooth > WAKE_CUTOFF
        rows = np.flatnonzero(live.any(axis=1))
        cols = np.flatnonzero(live.any(axis=0))
        if rows.size == 0 or cols.size == 0:
            return
        ny, nx = self.wake.shape
        r0, r1 = int(rows[0]), int(rows[-1]) + 1
        c0, c1 = int(cols[0]), int(cols[-1]) + 1

        sub = _tint_surface(smooth[r0:r1, c0:c1], WAKE, WAKE_STEPS,
                            ceil=True, cutoff=WAKE_CUTOFF)
        sx = self.size[0] / nx
        sy = self.size[1] / ny
        x0, y0 = int(c0 * sx), int(r0 * sy)
        x1, y1 = int(c1 * sx), int(r1 * sy)
        screen.blit(pygame.transform.smoothscale(sub, (x1 - x0, y1 - y0)),
                    (x0, y0), special_flags=pygame.BLEND_RGB_ADD)

    # -- the frame -----------------------------------------------------
    def draw(self, screen, diver=None, dt=1.0 / 60.0):
        """Occlusion order, then the sight pass, then the light.

        The sea, the little light that reaches it, what is suspended in it and
        the rock that blocks all three are drawn at full strength. Only then is
        the whole picture multiplied down by what the player can actually see.

        The ping is added AFTER that multiply, and that ordering is the entire
        look: it is not a thing in the room being revealed, it is the thing
        doing the revealing, so it is the one layer darkness does not touch."""
        self._frame += 1
        self._time += dt
        self.reveal *= REVEAL_DECAY
        if self._frame % REBUILD_EVERY == 1:
            self._rebuild_water()
        if self._frame % SIGHT_REBUILD_EVERY == 1:
            self._rebuild_sight(diver)

        screen.blit(self._water, (0, 0))
        self._draw_surface_light(screen)
        self._step_snow(dt)
        self._draw_snow(screen)
        screen.blit(self._sight, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self._draw_rock(screen)
        self._draw_wake(screen)
        screen.blit(self._grain[self._frame % GRAIN_TILES], (0, 0),
                    special_flags=pygame.BLEND_RGB_ADD)
