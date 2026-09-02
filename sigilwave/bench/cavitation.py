"""The gate. SUBMERGED.md 4.1.

The parts as built can only shape and delay: everything in the simulation is
proportional, so nothing can *decide*. The bench harness measured it exactly
-- a gap passes 0.227046 of what reaches it at every drive from 0.001 to
1000, identical to six significant figures over six decades. That is not a
gradual threshold, it is the total absence of one, and it is the leaky wire
2.1 blames for the previous build.

**Cavitation is where a real threshold comes from.** Water is held together by
its own ambient pressure; drive a negative pressure past the Blake threshold
and it tears open into a vapour cavity. The tearing is genuinely sharp -- it
is a mechanical failure, not a soft nonlinearity -- and the cavity's collapse
radiates a broadband click loud enough to stun prey, which is the pistol
shrimp already sitting in 7.3.

So a gap driven hard enough breaks down and conducts, exactly as "arcs across
with a spark" always described it. Three consequences fall out that were not
designed for:

**It latches.** A cavity does not vanish the instant the pressure that opened
it drops -- it persists and then collapses. That hysteresis is what makes the
gate a *trigger* rather than a comparator, and it is what 6's struck-out
LOOP + GAP timer needs: a loop charges, fires the gap, and the gap stays open
long enough to dump.

**It gets harder with depth.** The Blake threshold rises with ambient
pressure, so the same machine needs to be driven harder the deeper it is
taken. A design that fires reliably at the station may simply refuse to trip
at 700 m. That is the medium reaching into the drawing, and it is the reason
this belongs to the physics rather than to a tuning table.

**It is loud.** The collapse injects a broadband burst, so a gate firing is
audible and visible in the water, not just internally. A machine that decides
things announces itself.

Nothing here modifies `sigilwave/sim/`. A `CouplerChannel` keeps `kappa` and
its derived `scale` as plain attributes, so breakdown is a matter of writing
both between steps -- the game layer changing a physical property of the
water in the gap, which is exactly what cavitation is.
"""

import math

# Amplitude at which still water at the surface tears open. Set so that a
# pulse arriving at full strength trips the gate and the same pulse after one
# gap's worth of attenuation (0.227) does not -- otherwise a gate placed
# behind another gate could never be reached, and chains are the whole point.
BLAKE_SURFACE = 0.34

# Ambient pressure rises about one atmosphere per ten metres, and the
# threshold rises with it. 100 m therefore roughly doubles what it takes to
# trip a gate: a machine that works at the station may refuse at depth.
PRESSURE_SCALE_M = 100.0

# Broken down, the gap is no longer a gap -- there is a conducting cavity
# where the water was. Not 1.0: some energy goes into making the cavity, and
# a perfect coupler would let a loop drive itself through its own gate.
OPEN_KAPPA = 0.92

# How long a cavity lives once opened, in sim steps. This is the latch, and
# it is the difference between a trigger and a comparator.
HOLD_STEPS = 24

# It must fall well below the threshold to re-close, or a signal sitting near
# the threshold chatters the gate open and shut every step.
RELEASE_RATIO = 0.45

# After a cavity collapses the water there cannot immediately be torn open
# again -- it has to recover. Without this the gate re-fires on the very next
# step whenever the drive is still high, and the measured interval between
# collapses ran from 1 step to 79 with no rate to read. With it, the firing
# rate is set by the thing driving the gate rather than by the step size,
# which is what makes a loop's own note legible as a trigger rate.
REFRACTORY_STEPS = 10

# What the collapse radiates, as a fraction of the drive that opened it.
COLLAPSE_GAIN = 0.55


def blake_threshold(depth_m: float) -> float:
    """What it takes to tear water open at this depth."""
    return BLAKE_SURFACE * (1.0 + max(0.0, depth_m) / PRESSURE_SCALE_M)


class _Gate:
    __slots__ = ("coupler", "closed_kappa", "open_until", "ready_at",
                 "is_open", "fires")

    def __init__(self, coupler):
        self.coupler = coupler
        self.closed_kappa = coupler.kappa
        self.open_until = 0
        self.ready_at = 0
        self.is_open = False
        self.fires = 0


class Cavitation:
    """Drives every coupler in a network as a breakdown gate.

    Call `step()` immediately before `network.step()`. It reads the drive
    across each gap, decides whether the water there is torn open, and writes
    the coupling that follows from that decision.
    """

    def __init__(self, network, depth_m: float = 0.0):
        self.network = network
        self.depth_m = float(depth_m)
        self.threshold = blake_threshold(depth_m)
        self.gates = [_Gate(c) for c in network.couplers]
        self.steps = 0
        self.collapses = []          # (step, drive) per collapse, for the UI

    # -- the one thing that touches the simulation ---------------------
    @staticmethod
    def _write_kappa(coupler, kappa: float) -> None:
        for channel in (coupler.forward_channel, coupler.backward_channel):
            channel.kappa = kappa
            channel.scale = math.sqrt(max(0.0, 1.0 - kappa * kappa))

    @staticmethod
    def _drive(coupler) -> float:
        """The acoustic amplitude straining the water in the gap. Both
        travelling directions on both sides count: what tears water open is
        the pressure there, and the wave does not care which way it was
        going."""
        ea, eb = coupler.edge_a, coupler.edge_b
        la, lb = ea.forward.length, eb.forward.length
        a = abs(ea.forward.peek(coupler.pos_a)) + abs(ea.backward.peek(la - 1 - coupler.pos_a))
        b = abs(eb.forward.peek(coupler.pos_b)) + abs(eb.backward.peek(lb - 1 - coupler.pos_b))
        return max(a, b)

    def step(self) -> None:
        self.steps += 1
        for gate in self.gates:
            drive = self._drive(gate.coupler)
            if not gate.is_open:
                if drive >= self.threshold and self.steps >= gate.ready_at:
                    gate.is_open = True
                    gate.open_until = self.steps + HOLD_STEPS
                    gate.fires += 1
                    self.collapses.append((self.steps, drive))
                    self._write_kappa(gate.coupler, OPEN_KAPPA)
                    self._collapse(gate.coupler, drive)
            else:
                held = self.steps < gate.open_until
                if not held and drive < self.threshold * RELEASE_RATIO:
                    gate.is_open = False
                    gate.ready_at = self.steps + REFRACTORY_STEPS
                    self._write_kappa(gate.coupler, gate.closed_kappa)

    def _collapse(self, coupler, drive: float) -> None:
        """The cavity's collapse is the loudest thing in the ocean and it
        happens *in the gap*, not at a node -- so it is poked straight into
        both delay lines at the coupler's own position rather than injected
        somewhere convenient."""
        kick = COLLAPSE_GAIN * drive
        ea, eb = coupler.edge_a, coupler.edge_b
        la, lb = ea.forward.length, eb.forward.length
        ea.forward.poke(coupler.pos_a, ea.forward.peek(coupler.pos_a) + kick)
        eb.forward.poke(coupler.pos_b, eb.forward.peek(coupler.pos_b) + kick)
        ea.backward.poke(la - 1 - coupler.pos_a,
                         ea.backward.peek(la - 1 - coupler.pos_a) + kick)
        eb.backward.poke(lb - 1 - coupler.pos_b,
                         eb.backward.peek(lb - 1 - coupler.pos_b) + kick)

    # -- state, for the renderer ---------------------------------------
    @property
    def open_gates(self) -> list:
        return [i for i, g in enumerate(self.gates) if g.is_open]

    def fired(self) -> int:
        return sum(g.fires for g in self.gates)
