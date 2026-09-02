"""A ping: the light you see the room by.

This replaces the expanding circle that came before it, which passed straight
through rock -- it drew a wavefront that had never heard of the world it was
crossing. A ping here is a fan of rays that are stopped, turned and spent by
the room, so what comes back is a fact about the room.

It is still NOT the simulation. `medium/front.py` owns real wavefronts: they
refract continuously through the sound-speed gradient, they fold, they carry a
frequency and they diffract, and its reflection is a proper bisect-and-mirror
against a Sobel normal. That code is correct -- fired at a wall it sends 41 of
192 vertices back the way they came -- and this package deliberately does not
import it, so the physics can be rewritten without the art noticing.

What this is: rays that march, reflect, lose energy, and stamp two things --
the WAKE, which is the visible wavefront, and the REVEAL, which is the room's
memory of having been touched. When the real fronts are wired in, a Front
already holds its vertices and intensities as arrays, so it stamps both
directly and this file goes away.
"""

import math

import numpy as np

# A ray loses most of its energy to a wall. Enough comes back to light the
# rock behind you and to let a second surface be found beyond the first, not
# enough for a ping to rattle around the room forever.
REFLECT_LOSS = 0.55

# Spreading loss on a circular front: energy over circumference, so amplitude
# falls as 1/sqrt(r). Slower than the real 1/r used in flight, on purpose --
# this exists to be looked at, not to be measured against.
BIRTH_RADIUS = 16.0

# What a ray writes into the room's memory when it touches rock. Scaled by the
# energy still in the ray, so a wall found by a tired twice-reflected ray is
# drawn fainter than one found head-on -- which is the range law doing the
# work that a brightness constant would otherwise have to fake.
REVEAL_GAIN = 1.35

RAY_COUNT = 300

# Two neighbours further apart than this are not two ends of the same piece of
# wavefront any more -- one of them has reflected. Roughly the width of a
# medium cell, which is the scale at which the room can turn a ray.
MAX_JOIN = 26.0

# Where to put samples between two joined neighbours. Four subdivisions keep
# the spacing under a wake cell out to the far corner of a 1200 px room.
FILL_FRACTIONS = (0.2, 0.4, 0.6, 0.8)
SPEED = 300.0
MIN_ENERGY = 0.015
MAX_BOUNCES = 3


class Ping:
    """One expanding fan of rays. Vectorised: every ray steps at once."""

    def __init__(self, shader, x, y, n_rays=RAY_COUNT, speed=SPEED,
                 energy=1.0):
        self.shader = shader
        self.medium = shader.medium
        a = np.linspace(0.0, 2.0 * math.pi, n_rays, endpoint=False)
        self.dx = np.cos(a)
        self.dy = np.sin(a)
        self.px = x + self.dx * BIRTH_RADIUS
        self.py = y + self.dy * BIRTH_RADIUS
        self.energy = np.full(n_rays, float(energy))
        self.dist = np.full(n_rays, BIRTH_RADIUS)
        self.bounces = np.zeros(n_rays, dtype=int)
        self.speed = speed
        self.alive = np.ones(n_rays, dtype=bool)
        # A ray born inside rock has nowhere to go and no normal worth
        # reading; it is heat, immediately.
        self.alive &= ~self.medium.is_solid_at(self.px, self.py)

    @property
    def dead(self):
        return not self.alive.any()

    def step(self, dt):
        if self.dead:
            return
        m = self.medium
        step_len = self.speed * dt
        live = self.alive

        nx = self.px + self.dx * step_len
        ny = self.py + self.dy * step_len

        # Rays that would end this step inside rock. Everything about seeing
        # the room happens here: they stop, they light what they hit, and they
        # leave in a direction the wall chose.
        hit = live & m.is_solid_at(nx, ny)
        if hit.any():
            hx, hy = self.px[hit], self.py[hit]
            snx, sny = self.shader.solid_normal_at(nx[hit], ny[hit])
            d = self.dx[hit] * snx + self.dy[hit] * sny
            # Only turn a ray that is actually heading into the surface. A ray
            # already leaving would be flipped back into the rock, which reads
            # as a wavefront sticking to a wall.
            into = d < 0.0
            self.dx[hit] = np.where(into, self.dx[hit] - 2.0 * d * snx, self.dx[hit])
            self.dy[hit] = np.where(into, self.dy[hit] - 2.0 * d * sny, self.dy[hit])
            # Nudged back along the normal, or the next step starts inside the
            # rock again and the ray dies against the surface it just found.
            self.px[hit] = hx + snx * 2.0
            self.py[hit] = hy + sny * 2.0
            self.energy[hit] *= REFLECT_LOSS
            self.bounces[hit] += 1
            self.shader.add_reveal(nx[hit], ny[hit],
                                   self.energy[hit] * REVEAL_GAIN)

        move = live & ~hit
        self.px[move] = nx[move]
        self.py[move] = ny[move]
        self.dist[move] += step_len

        # Spreading loss is a function of PATH LENGTH, not of distance from the
        # origin: a ray that has bounced back past its own birthplace has still
        # travelled every pixel of the way there and should be weak
        # accordingly. Kept as a factor rather than folded into `energy` so
        # that reflection loss stays the only thing that permanently spends a
        # ray, and the two never compound by accident.
        spread = np.sqrt(BIRTH_RADIUS / np.maximum(self.dist, BIRTH_RADIUS))

        out = ((self.px < 0.0) | (self.px >= m.width)
               | (self.py < 0.0) | (self.py >= m.height))
        self.alive &= ~out
        self.alive &= self.bounces <= MAX_BOUNCES
        self.alive &= (self.energy * spread) > MIN_ENERGY

        if self.alive.any():
            xs, ys, amps = self._front_samples(spread)
            self.shader.add_wake_points(xs, ys, amps)

    def _front_samples(self, spread):
        """The front as a continuous line, not as a row of dots.

        A fixed ray count means the spacing between neighbours GROWS with the
        radius, so a ring that looked solid when it was born comes out as a
        dashed circle by the time it is halfway across the room. Filling in
        between neighbours fixes that at every radius at once.

        Neighbours are only joined when they are still close together. Two
        rays that have diverged -- one reflected off a wall, the other sailed
        past its edge -- are no longer two ends of the same little piece of
        wavefront, and joining them would draw a chord straight across the
        room. That is the same fold-chord artefact the old renderer papered
        over with a maximum-segment-length threshold; here it falls out of
        asking the honest question instead."""
        live = self.alive
        amp = self.energy * spread
        x0, y0 = self.px, self.py
        x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
        a1 = np.roll(amp, -1)
        join = live & np.roll(live, -1)
        join &= (np.hypot(x1 - x0, y1 - y0) < MAX_JOIN)

        xs = [x0[live]]
        ys = [y0[live]]
        amps = [amp[live]]
        if join.any():
            jx0, jy0, ja0 = x0[join], y0[join], amp[join]
            jx1, jy1, ja1 = x1[join], y1[join], a1[join]
            for t in FILL_FRACTIONS:
                xs.append(jx0 + (jx1 - jx0) * t)
                ys.append(jy0 + (jy1 - jy0) * t)
                amps.append(ja0 + (ja1 - ja0) * t)
        return (np.concatenate(xs), np.concatenate(ys), np.concatenate(amps))


def step_all(pings, dt):
    """Advance every ping and drop the spent ones. Returns the survivors."""
    for p in pings:
        p.step(dt)
    return [p for p in pings if not p.dead]
