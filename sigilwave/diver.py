"""A body in water. SUBMERGED.md 8, the FORCE verb.

The demo let you fly around with WASD, and that one shortcut took the reason
to build anything out of the game: if you can already go where you want, a
machine that pushes you is a worse version of a key you already have. 8 says
propulsion is *drawn* -- a mouth firing behind you -- and this is that,
plus the three things that make water feel like water rather than like air.

**Drag, measured against the WATER.** Quadratic, so there is a terminal speed
and letting go coasts to a stop instead of stopping dead. Measured against the
water rather than against the ground, which is the difference between a
current being scenery and a current being a force: drifting with it is free,
crossing it is not, and neither needed a rule.

**Added mass.** Push a body through water and you push a comparable mass of
water along with it, so it accelerates as though it were twice as heavy while
weighing exactly what it weighed. This is not a fudge and it is not friction
-- it is the single biggest reason underwater movement *feels* underwater:
everything you do arrives late and leaves slowly, and no amount of drag
tuning reproduces it, because drag punishes speed and added mass punishes
CHANGE.

**Anisotropy.** A diver is a long thing. Pointed the way you are going you
have a third of the drag you have broadside, so aiming where you travel is a
skill rather than a formality, and turning while fast is expensive.

**Buoyancy and trim.** You have a density and so does the water, and 7's
medium already tracks its own. Warm water is lighter, so a vent's plume
*lifts* you -- the best place to stand for power will not let you stand
still. And you carry a bladder: trim is slow, nearly free, and the only way
to change depth without spending anything, which makes it the exact opposite
of thrust in every respect that matters.

**Thrust.** Every front a mouth throws pushes back; every port a rig ejects
through pushes back harder and honestly.

One number here is a lie and it is named: real acoustic radiation pressure
could not move a diver, so `THRUST_PER_ENERGY` scales it to something a game
can be played with. It is the only such number in this file -- drag,
buoyancy, added mass and the current all fall out of quantities the medium
already has.
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

# Added mass, as a fraction of your own. A bluff body dragging water with it
# has an added-mass coefficient near 1, so you accelerate as though you were
# about twice as heavy -- and you still WEIGH what you weighed, so buoyancy is
# unaffected and only *changes* of motion are slowed.
#
# It is applied to the sum of the accelerations rather than to any one force,
# because that is what it is: the water does not care which force is pushing.
ADDED_MASS = 1.0

# Quadratic drag: F = -k |v| v, and `v` is measured relative to the WATER.
# Two coefficients because a diver is not a sphere -- streamlined along your
# own axis, broadside across it.
#
# ALONG is exactly the single coefficient this file used before, and that is
# deliberate rather than lazy: anisotropy is added by making BROADSIDE WORSE,
# not by making streamlined better. The other way round silently re-tunes
# every number already measured against the old drag -- the first attempt
# lowered it to 0.008 and a constant push stopped reaching a terminal speed at
# all, because the diver hit MAX_SPEED first and drag was no longer the thing
# limiting anybody. A speed cap that binds is a bug wearing a constant's name.
DRAG_ALONG = 0.038
DRAG_ACROSS = 0.114
# Deliberately small. The linear term is what a low-Reynolds-number ooze looks
# like and water is not one; with it at 0.9 it swamped both quadratic terms at
# every speed anyone actually travels, so pointing where you were going bought
# 18% and might as well not have existed. At 0.35 the quadratic terms are the
# ones doing the work, which is both correct for a body this size and what
# makes a diver GLIDE rather than trudge.
DRAG_LINEAR = 0.35

# You are close to neutrally buoyant, which is what a diver trims for. The
# gain is what turns a small density difference into a felt drift.
DIVER_DENSITY = 1000.4
BUOYANCY_GAIN = 210.0

# The bladder. Slow to change, free to hold, and it is the only way to change
# depth that does not spend anything -- so it is the opposite of thrust on
# every axis: thrust is fast, expensive, loud and horizontal by habit; trim is
# slow, cheap, silent and vertical.
#
# The rate is the interesting number rather than the gain. A real diver adds
# gas in small bursts and waits, and getting that wait wrong is how people
# end up on the surface with a headache; making the CHANGE slow rather than
# the effect weak is what reproduces it.
TRIM_GAIN = 14.0          # px/s^2 at full inflation
TRIM_RATE = 0.55          # how much of full travel per second
TRIM_AIR_PER_SEC = 0.9    # only while you are actually changing it

# A flutter kick. Deliberately weak and deliberately expensive: it exists so
# a player who has drawn nothing is not stuck, not so they can travel by it.
# Sized against the rig rather than against nothing. `rig_thrust` is honest
# now -- 2719 N on a 90 kg diver is 30 px/s^2 -- and against that a KICK of
# 240 made flailing FOUR TIMES FASTER than the machine you were supposed to
# build, which inverts the entire premise of SUBMERGED 8. At 9.0 a sustained
# kick tops out around 9 px/s against a basic thruster's 24, which leaves it
# doing exactly the job it is described as doing: it will just barely get you
# out of a surface current, and it will not get you anywhere.
#
# 9.0 was still not enough separation -- it topped out at 11.5 px/s against
# the rig's 23, and a factor of two is a choice rather than a verdict. At 4.0
# a kick settles at 6.6 px/s, which is three and a half times slower than the
# cheapest rig and *just* above the 5.7 px/s surface drift: you can crawl
# upstream in the shallows by flailing, and that is the entire list of things
# flailing is for.
KICK = 4.0
KICK_AIR_PER_SEC = 4.2

MAX_SPEED = 260.0


class Diver:
    def __init__(self, pos):
        self.pos = V(pos)
        self.vel = V(0.0, 0.0)
        self.aim = V(1.0, 0.0)
        self.last_thrust = V(0.0, 0.0)
        self.kicking = False
        # -1 fully vented (sink), +1 fully inflated (rise), 0 neutral.
        self.trim = 0.0
        self.trim_target = 0.0
        # What the water was doing last step, kept so a HUD can show you the
        # thing that is pushing you around.
        self.last_flow = V(0.0, 0.0)
        self.last_drag = V(0.0, 0.0)

    # -- forces --------------------------------------------------------
    def _buoyancy(self, medium) -> V:
        """Light water pushes you up, heavy water lets you sink.

        Read against the water at your own depth rather than a constant, so
        an ordinary stratified column is neutral and only an *anomaly* -- a
        plume, a cold pocket -- actually moves you. Otherwise every dive is
        one long fight with the profile."""
        try:
            # One definition of "unusual water", and it lives in the medium.
            # This used to be a bilinear density sampled here minus a single
            # row's mean, which are not the same quantity and differ by the
            # stratification itself -- see `Medium.density_anomaly_at`.
            anomaly = -medium.density_anomaly_at(self.pos.x, self.pos.y)
        except Exception:
            return V(0.0, 0.0)
        # Both terms are NEGATIVE for up, because +y is down. Written with
        # the wrong sign on trim, a full bladder sank you at 30 px/s.
        lift = -anomaly * BUOYANCY_GAIN - self.trim * TRIM_GAIN
        return V(0.0, lift)

    def flow(self, medium) -> V:
        """What the water here is doing, in px/s.

        This replaced `_current`, which took the gradient of the density
        anomaly and called it a velocity. That was a stand-in for a field the
        medium did not have; it does now (`Medium.flow_at`), it is derived
        from the same buoyancy the medium already applies to heat, and its
        horizontal half is deduced from continuity rather than guessed -- so a
        plume has an inflow underneath it because it has to, not because
        anybody drew one.
        """
        try:
            u, v = medium.flow_at(self.pos.x, self.pos.y)
        except Exception:
            return V(0.0, 0.0)
        return V(float(u), float(v))

    def _drag(self, relative) -> V:
        """Quadratic drag on the velocity RELATIVE TO THE WATER, split into
        the direction you are pointing and the direction you are not.

        The whole current system is this one word `relative`. Water moving
        past you is what slows you; water carrying you is not. Sitting still
        in a 20 px/s current means moving at 20 px/s over the ground for free,
        and holding station in it costs continuously -- which is the correct
        answer to both and needed no rule for either.
        """
        speed = relative.length()
        if speed < 1e-6:
            return V(0.0, 0.0)
        axis = V(self.aim)
        if axis.length_squared() < 1e-12:
            axis = V(1.0, 0.0)
        axis = axis.normalize()

        along = relative.dot(axis)
        along_v = axis * along
        across_v = relative - along_v

        f = -(along_v * (DRAG_ALONG * abs(along))
              + across_v * (DRAG_ACROSS * across_v.length())
              + relative * DRAG_LINEAR)
        return f

    def set_trim(self, target: float) -> None:
        """Ask for a bladder setting. It arrives when it arrives."""
        self.trim_target = max(-1.0, min(1.0, float(target)))

    def _step_trim(self, dt: float, economy=None) -> None:
        want = self.trim_target - self.trim
        if abs(want) < 1e-4:
            self.trim = self.trim_target
            return
        step = TRIM_RATE * dt
        self.trim += max(-step, min(step, want))
        # Changing trim means moving gas, and gas is air. Holding costs
        # nothing, which is why trim is what you use when you have time.
        if economy is not None:
            economy.air = max(0.0, economy.air - TRIM_AIR_PER_SEC * dt)

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
             bounds=None, economy=None):
        self._step_trim(dt, economy)

        flow = self.flow(medium)
        self.last_flow = flow
        relative = self.vel - flow
        drag = self._drag(relative)
        self.last_drag = drag

        acc = V(thrust) + V(kick) + self._buoyancy(medium) + drag
        # Added mass divides the SUM, because the water being dragged along
        # does not care which force is doing the dragging. Buoyancy is in here
        # too and that is correct: a lift you cannot accelerate into arrives
        # just as late as a push you cannot accelerate into.
        acc /= (1.0 + ADDED_MASS)

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

    def speed_through_water(self, medium) -> float:
        """How fast you are actually swimming, which is not how fast you are
        going. The number that costs you something."""
        return (self.vel - self.flow(medium)).length()

    def drift(self, medium) -> V:
        """The part of your motion the water is doing for you."""
        return self.flow(medium)
