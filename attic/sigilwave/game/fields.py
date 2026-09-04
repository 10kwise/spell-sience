"""The world as a medium, not a backdrop.

This is the correction to the biggest mistake in the first build: every sigil
was an emitter, every emission became a mote, and every mote was damage. A
wave simulator got flattened into a gun. Standing waves, storage, reflection,
spreading heat and action at a distance — the entire reason to simulate waves
at all — had nowhere to land, because the world had no state for them to land
*in*.

So the world gets state. Three fields on a coarse grid, exactly the three the
design doc names, plus one bookkeeping layer:

    kinetic (vector)  wind. pushes everything, including you.
    thermal (scalar)  + burns, - freezes. spreads. sets fuel alight.
    phase   (scalar)  decoherence. matter here stops interacting.
    fuel    (scalar)  what is left to burn. consumed, never replenished.

Two consequences, both intended:

**Spells stop being bullets.** A sigil with nowhere to radiate dumps into the
field at its own feet and becomes an aura. A hot beam leaves a burning trail
that keeps working after you have walked away. A kinetic pulse leaves wind
that shoves the next thing through it. The output of the wave sim is now a
*change to the world*, and the projectile is only the fastest way to deliver
it.

**The world can kill you.** You read the same fields everything else does.
Your own fire burns you, your own wind shoves you, and a room you set alight
is a room you now have to cross. That is where the threat comes from — not
from enemies having more hit points.

Everything here is numpy on a ~50x35 grid, so the whole update is a handful
of array ops per frame.
"""

import math

import numpy as np
import pygame

CELL = 34.0                   # px per cell

# Per-second decay multipliers.
THERMAL_DECAY = 0.55
KINETIC_DECAY = 0.22
PHASE_DECAY = 0.30

# Diffusion, per *second*. These were per-step, which at 120Hz meant the
# blur ran 120 times a second — and since a blend toward the neighbour mean
# is not conservative, an isolated hot cell lost about 17% of itself every
# step and fire could never accumulate enough to spread at all. Rate-scaled
# below, and the kernel is now a proper Laplacian so heat moves between
# cells instead of quietly evaporating.
THERMAL_DIFFUSE = 1.5
PHASE_DIFFUSE = 0.8
MAX_DIFFUSE_STEP = 0.45       # stability cap: above ~0.5 the explicit
                              # Laplacian oscillates instead of diffusing

# Fire. Above IGNITE a cell with fuel starts burning; burning consumes fuel
# and emits heat, and that heat diffusing into a neighbour is what spreads
# it. BURN_HEAT/THERMAL_DECAY is a burning cell's steady state (~3.9) and
# THERMAL_DIFFUSE of that lands next door (~0.8), comfortably over IGNITE_AT
# — so fire propagates on its own rather than sitting where it was lit.
#
# The propagation condition is worth writing down, because it is easy to set
# these four numbers to values that quietly cannot spread at all. A burning
# cell settles at BURN_HEAT/(THERMAL_DECAY + THERMAL_DIFFUSE); its neighbour
# settles at roughly a quarter of the diffused share of that. Requiring the
# neighbour to clear IGNITE_AT gives
#
#     THERMAL_DIFFUSE * BURN_HEAT / (4 * (THERMAL_DECAY + THERMAL_DIFFUSE)^2) > IGNITE_AT
#
# which at these values is 0.73 against 0.55 — a fire that spreads, with
# enough margin that it does not stall on a cool patch but not so much that
# it ignores fuel entirely.
#
# What stops it is fuel, not a spread cap. Patches are scattered, a cell
# holds about a second of burning, and burnt ground never comes back. So a
# fire runs until it hits bare floor, which makes lighting one a question of
# *where* rather than whether, and makes a room you have already burned a
# different room than the one you started in.
IGNITE_AT = 0.55
BURN_RATE = 0.55              # fuel/sec consumed by a burning cell
BURN_HEAT = 9.0               # thermal/sec emitted by a burning cell
FREEZE_AT = -0.5              # below this, a cell is frozen: fuel will not light

MAX_THERMAL = 4.0
MAX_PHASE = 1.5
MAX_KINETIC = 900.0

_KERNELS = {}


class FieldGrid:
    def __init__(self, width, height, rng=None):
        self.w = max(4, int(width / CELL) + 1)
        self.h = max(4, int(height / CELL) + 1)
        self.width = width
        self.height = height
        shape = (self.h, self.w)

        self.thermal = np.zeros(shape, dtype=np.float32)
        self.phase = np.zeros(shape, dtype=np.float32)
        self.kinetic = np.zeros((self.h, self.w, 2), dtype=np.float32)
        self.fuel = np.zeros(shape, dtype=np.float32)
        self.burning = np.zeros(shape, dtype=bool)

        rng = rng or np.random.default_rng(0)
        # Scattered combustible matter. Not uniform — patches give the room
        # somewhere for fire to run and somewhere it will stop, which is what
        # makes setting a fire a decision about *where* rather than whether.
        noise = rng.random(shape).astype(np.float32)
        blob = _blur(_blur(noise))
        self.fuel = np.clip((blob - 0.42) * 4.2, 0.0, 1.0).astype(np.float32)

    # ------------------------------------------------------------ addressing

    def cell_of(self, pos):
        # Plain Python min/max, not np.clip. This is called tens of thousands
        # of times a second and np.clip on two scalars costs more than the
        # rest of the function put together — it was 120k calls and a third
        # of the frame budget in a profile.
        r = int(pos[1] / CELL)
        c = int(pos[0] / CELL)
        if r < 0: r = 0
        elif r > self.h - 1: r = self.h - 1
        if c < 0: c = 0
        elif c > self.w - 1: c = self.w - 1
        return r, c

    def sample_thermal(self, pos) -> float:
        r, c = self.cell_of(pos)
        return float(self.thermal[r, c])

    def sample_phase(self, pos) -> float:
        r, c = self.cell_of(pos)
        return float(self.phase[r, c])

    def sample_kinetic(self, pos) -> pygame.Vector2:
        r, c = self.cell_of(pos)
        k = self.kinetic[r, c]
        return pygame.Vector2(float(k[0]), float(k[1]))

    def is_burning(self, pos) -> bool:
        r, c = self.cell_of(pos)
        return bool(self.burning[r, c])

    # -------------------------------------------------------------- deposits

    def _stamp(self, arr, pos, radius, amount):
        """Add `amount` into a disc, falling off to zero at the rim.

        Falloff is linear in distance, not in distance squared. With cells
        this coarse a small radius covers barely one cell across, and the
        squared form drove every neighbour to exactly zero there — so a
        "radius 40" deposit landed entirely in a single cell, fire had
        nowhere to spread to, and the whole propagation system looked broken
        when it was only ever being handed one lit square.
        """
        cr = max(1, int(round(radius / CELL)))
        r0, c0 = self.cell_of(pos)
        rlo, rhi = max(0, r0 - cr), min(self.h, r0 + cr + 1)
        clo, chi = max(0, c0 - cr), min(self.w, c0 + cr + 1)
        if rlo >= rhi or clo >= chi:
            return
        # The falloff kernel depends only on cr, so build each one once. It
        # was being recomputed — four array allocations and a sqrt — on every
        # one of ~38,000 deposits per second.
        kern = _KERNELS.get(cr)
        if kern is None:
            span = np.arange(-cr, cr + 1, dtype=np.float32)
            dist = np.sqrt(span[:, None] ** 2 + span[None, :] ** 2)
            kern = np.clip(1.0 - dist / (cr + 0.5), 0.0, 1.0)
            _KERNELS[cr] = kern
        sub = kern[rlo - (r0 - cr):rhi - (r0 - cr), clo - (c0 - cr):chi - (c0 - cr)]
        arr[rlo:rhi, clo:chi] += sub * amount

    def add_thermal(self, pos, radius, amount):
        self._stamp(self.thermal, pos, radius, amount)

    def add_phase(self, pos, radius, amount):
        self._stamp(self.phase, pos, radius, amount)

    def add_ring(self, arr, pos, radius, amount, segments=10):
        """Deposit around a circle rather than filling a disc.

        A loop's near field peaks at the ink and is weakest in the middle,
        which is not a detail — a disc-shaped fire aura is centred on the
        caster and therefore sets the caster on fire, and no amount of
        tuning the magnitude fixes that because it is a geometry error. As a
        ring it becomes what it should always have been: a wall of fire you
        are standing inside."""
        for i in range(segments):
            a = 2 * math.pi * i / segments
            at = (pos[0] + math.cos(a) * radius, pos[1] + math.sin(a) * radius)
            self._stamp(arr, at, radius * 0.62, amount / segments * 2.4)

    def add_thermal_ring(self, pos, radius, amount):
        self.add_ring(self.thermal, pos, radius, amount)

    def add_phase_ring(self, pos, radius, amount):
        self.add_ring(self.phase, pos, radius, amount)

    def add_kinetic(self, pos, radius, vector):
        self._stamp(self.kinetic[:, :, 0], pos, radius, float(vector[0]))
        self._stamp(self.kinetic[:, :, 1], pos, radius, float(vector[1]))

    # ---------------------------------------------------------------- update

    def update(self, dt):
        # Fire first, so ignition this frame is visible this frame.
        hot_enough = self.thermal > IGNITE_AT
        has_fuel = self.fuel > 0.02
        self.burning = hot_enough & has_fuel

        if self.burning.any():
            burn = self.burning.astype(np.float32)
            self.fuel -= burn * BURN_RATE * dt
            np.clip(self.fuel, 0.0, 1.0, out=self.fuel)
            self.thermal += burn * BURN_HEAT * dt

        # Frozen ground refuses to light, which is what makes a chill sigil a
        # real counter to a burning room rather than a flavour difference.
        self.fuel[self.thermal < FREEZE_AT] *= (1.0 - 0.25 * dt)

        self.thermal = _diffuse(self.thermal, min(MAX_DIFFUSE_STEP, THERMAL_DIFFUSE * dt))
        self.phase = _diffuse(self.phase, min(MAX_DIFFUSE_STEP, PHASE_DIFFUSE * dt))

        self.thermal *= np.float32(max(0.0, 1.0 - THERMAL_DECAY * dt))
        self.phase *= np.float32(max(0.0, 1.0 - PHASE_DECAY * dt))
        self.kinetic *= np.float32(max(0.0, 1.0 - KINETIC_DECAY * dt))

        np.clip(self.thermal, -MAX_THERMAL, MAX_THERMAL, out=self.thermal)
        np.clip(self.phase, 0.0, MAX_PHASE, out=self.phase)
        np.clip(self.kinetic, -MAX_KINETIC, MAX_KINETIC, out=self.kinetic)

    # ----------------------------------------------------------------- intel

    def totals(self):
        return (
            float(np.abs(self.thermal).sum()),
            float(self.phase.sum()),
            int(self.burning.sum()),
        )


def _blur(a):
    """Plain 5-point average, for shaping the fuel map at startup only."""
    out = a.copy()
    out[1:, :] += a[:-1, :]
    out[:-1, :] += a[1:, :]
    out[:, 1:] += a[:, :-1]
    out[:, :-1] += a[:, 1:]
    return out / 5.0


def _neighbour_mean(a):
    """Mean of the four orthogonal neighbours, with edges reflected so the
    arena boundary neither leaks heat away nor piles it up."""
    up = np.empty_like(a); up[0] = a[0]; up[1:] = a[:-1]
    dn = np.empty_like(a); dn[-1] = a[-1]; dn[:-1] = a[1:]
    lf = np.empty_like(a); lf[:, 0] = a[:, 0]; lf[:, 1:] = a[:, :-1]
    rt = np.empty_like(a); rt[:, -1] = a[:, -1]; rt[:, :-1] = a[:, 1:]
    return (up + dn + lf + rt) * 0.25


def _diffuse(a, k):
    """One explicit diffusion step: move each cell a fraction of the way
    toward its neighbours' mean. Conservative — heat that leaves a cell
    arrives in the ones beside it rather than vanishing."""
    if k <= 0:
        return a
    return a + k * (_neighbour_mean(a) - a)
