"""A body in water. SUBMERGED.md 8, the FORCE verb.

The demo let you fly around with WASD, and that one shortcut took the reason
to build anything out of the game: if you can already go where you want, a
machine that pushes you is a worse version of a key you already have. 8 says
propulsion is *drawn* -- a mouth firing behind you -- and this is that,
plus the three things that make water feel like water rather than like air.

**Drag.** Quadratic, so there is a terminal speed and letting go coasts to a
stop instead of stopping dead. This is most of the feel: you arrive somewhere
by deciding to stop early.

**Buoyancy.** You have a density and so does the water, and 7's medium
already tracks its own. Warm water is lighter, so a vent's plume *lifts*
you -- which means the best place to stand for power is also a place that
will not let you stand still. Nobody designed that; it is what putting heat
in water does, and 8.1 already said the same interaction bends your pings.

**Thrust.** Every front a mouth throws pushes back. A wide mouth firing
astern is a shove; a spitter is a kick.

One number here is a lie and it is named: real acoustic radiation pressure
could not move a diver, so `THRUST_PER_ENERGY` scales it to something a game
can be played with. It is the only such number in this file -- drag,
buoyancy and the current all fall out of quantities the medium already has.
"""

import math

import pygame

V = pygame.Vector2

# The one fudge. Momentum handed to the diver per unit of radiated energy.
#
# It is a force against RADIATED POWER, and two wrong versions came first.
# Reading it off the batched fronts gave two jolts in four seconds -- the
# renderer emits one front per twelve network steps, which is a drawing
# convenience and not a fact about the machine -- and drag ate both, so a
# driven machine moved the diver 63 px against 63 px for doing nothing at
# all, with flailing beating both. A machine radiating continuously pushes
# continuously, so thrust reads the per-step radiated energy instead and the
# batching cannot reach it.
#
# RETIRED for rigs, and kept for sound. `Diver.rig_thrust` computes momentum
# flux honestly because a rig ejects water; this constant survives only for
# `impulse_from`, where the thing being thrown really is sound and the lie
# really is still necessary.
THRUST_PER_ENERGY = 1300.0

# A diver and their gear. Needed the moment thrust became a real force in
# newtons rather than a scaled energy, and it is a person rather than a knob.
DIVER_MASS = 90.0         # kg

# Quadratic drag: F = -k |v| v. Water, not air -- the point is that speed is
# expensive and stopping is free.
DRAG = 0.0135
DRAG_LINEAR = 0.9

# You are close to neutrally buoyant, which is what a diver trims for. The
# gain is what turns a small density difference into a felt drift.
DIVER_DENSITY = 1000.4
BUOYANCY_GAIN = 210.0
CURRENT_GAIN = 165.0

# A flutter kick. Deliberately weak and deliberately expensive: it exists so
# a player who has drawn nothing is not stuck, not so they can travel by it.
KICK = 240.0
KICK_AIR_PER_SEC = 4.2

MAX_SPEED = 260.0


class Diver:
    def __init__(self, pos):
        self.pos = V(pos)
        self.vel = V(0.0, 0.0)
        self.aim = V(1.0, 0.0)
        self.last_thrust = V(0.0, 0.0)
        self.kicking = False

    # -- forces --------------------------------------------------------
    def _buoyancy(self, medium) -> V:
        """Light water pushes you up, heavy water lets you sink.

        Read against the water at your own depth rather than a constant, so
        an ordinary stratified column is neutral and only an *anomaly* -- a
        plume, a cold pocket -- actually moves you. Otherwise every dive is
        one long fight with the profile."""
        try:
            here = medium.density(self.pos.x, self.pos.y)
        except Exception:
            return V(0.0, 0.0)
        row = int(min(max(self.pos.y / medium.cell_size, 0), medium.ny - 1))
        ambient = float(medium.density_field[row].mean())
        # Positive when the water here is lighter than the rest of its layer.
        anomaly = ambient - here
        return V(0.0, -anomaly * BUOYANCY_GAIN)

    def _current(self, medium) -> V:
        """Water moves where density says it should -- but only where the
        density is *unusual for its depth*.

        The first version took the raw gradient, which in a stratified ocean
        is dominated by the stratification itself: heavy water below light
        water everywhere, always, by design. It read that as a permanent
        updraft and floated a motionless diver 193 px through still water
        with nothing acting on them. A stable column produces no flow. Only
        an anomaly does, so the gradient is taken of the anomaly field --
        density minus the mean at that depth -- which is exactly zero in
        water that is merely layered and non-zero around a plume."""
        try:
            cs = medium.cell_size
            r = int(min(max(self.pos.y / cs, 1), medium.ny - 2))
            c = int(min(max(self.pos.x / cs, 1), medium.nx - 2))
            d = medium.density_field
            rows = d[r - 1:r + 2]
            anom = rows - rows.mean(axis=1, keepdims=True)
            dx = float(anom[1, c + 1] - anom[1, c - 1])
            dy = float(anom[2, c] - anom[0, c])
        except Exception:
            return V(0.0, 0.0)
        # Flow runs from heavy toward light along the anomaly.
        return V(-dx, -dy) * CURRENT_GAIN

    def rig_thrust(self, result, direction) -> V:
        """Acceleration from a RIG's port, in px/s^2. RIGS.md 10.

        This is the method that retires `THRUST_PER_ENERGY`, and the retirement
        is the point. That constant is a named lie because real acoustic
        radiation pressure cannot move a diver -- SUBMERGED said so out loud
        and used it anyway, because sound was the only thing a machine could
        make.

        A rig ejects water. So the number is `mdot * v / m`, which is what a
        jet is, and there is nothing left to name. The one quantity that had to
        be added is the diver's own mass, and 90 kg is a person and their gear
        rather than a tuning knob.

        It is also CONTINUOUS rather than per-front. `impulse_from` below is a
        kick applied once when a front is thrown; a pump running is a force
        that persists, so this returns an acceleration for `step` to integrate
        and does not touch velocity itself.
        """
        from .rig import couple

        newtons = couple.thrust_from(result)
        if newtons <= 0.0:
            return V(0.0, 0.0)
        d = V(direction)
        if d.length_squared() < 1e-12:
            return V(0.0, 0.0)
        # The reaction points opposite the way the port faces.
        return -d.normalize() * (newtons / DIVER_MASS)

    def impulse_from(self, fronts_born) -> V:
        """Newton's third law, once per front. A mouth throws energy one way
        and the diver holding it goes the other -- once, when it is thrown."""
        push = V(0.0, 0.0)
        for front in fronts_born:
            e = front.total_energy()
            d = getattr(front, "_D0", None)
            if d is None or e <= 0.0:
                continue
            push -= V(float(d[0]), float(d[1])) * (e * THRUST_PER_ENERGY)
        return push

    def push(self, fronts_born) -> V:
        """Apply that impulse to velocity directly. Momentum is momentum; it
        does not get multiplied by a timestep on the way in."""
        imp = self.impulse_from(fronts_born)
        self.vel += imp
        if self.vel.length() > MAX_SPEED:
            self.vel.scale_to_length(MAX_SPEED)
        self.last_thrust = imp
        return imp

    # -- integration ---------------------------------------------------
    def step(self, dt, medium, thrust=V(0.0, 0.0), kick=V(0.0, 0.0),
             bounds=None):
        acc = V(thrust) + V(kick) + self._buoyancy(medium) + self._current(medium)

        speed = self.vel.length()
        if speed > 1e-6:
            drag = self.vel.normalize() * -(DRAG * speed * speed
                                            + DRAG_LINEAR * speed)
            acc += drag

        self.vel += acc * dt
        if self.vel.length() > MAX_SPEED:
            self.vel.scale_to_length(MAX_SPEED)
        self.pos += self.vel * dt

        if bounds is not None:
            w, h = bounds
            for axis in ("x", "y"):
                lim = (w if axis == "x" else h) - 10.0
                p = getattr(self.pos, axis)
                if p < 10.0 or p > lim:
                    setattr(self.pos, axis, min(max(p, 10.0), lim))
                    setattr(self.vel, axis, getattr(self.vel, axis) * -0.25)

        # Rock is solid. Sitting inside it is how the first build lost every
        # front it emitted, so the diver is pushed back out rather than
        # allowed to occupy it.
        try:
            if medium.is_solid(self.pos.x, self.pos.y):
                self.pos -= self.vel.normalize() * 3.0 if self.vel.length_squared() > 1e-6 else V(0, -3)
                self.vel *= -0.2
        except Exception:
            pass

    @property
    def speed(self) -> float:
        return self.vel.length()
