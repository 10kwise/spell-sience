"""The two halves, joined. SUBMERGED.md 13 step 5.

Until now there have been two games. The bench had drawings that made energy
and nowhere to put it; the stage had an ocean and pings that came from a
mouse click. This is the seam: a machine's mouths radiate into the medium as
fronts whose shape is the shape of the drawing.

Nothing new is simulated here. It owns the clock, and the clock is the whole
problem -- a waveguide network runs at one sample per `dx` of wire (100 Hz
here) while the medium is a field stepped per frame, so the machine takes
many steps for each step the water takes. Getting that ratio wrong would make
a drawn note come out at the wrong pitch in the water, which would quietly
break every range and refraction law downstream.

    python -m sigilwave.dive
"""

import math

from .bench.cavitation import Cavitation
from .bench.mouths import WATER_FREQ_RATIO, Emitter
from .bench.parts import SIM_DT, Assembly
from .medium.front import Front
from .stage import world

# The medium is stepped once per rendered frame; the network is stepped as
# many times as fit in that frame at its own rate. Both are then slowed
# together by the stage's TIME_SCALE, so slow motion slows the machine and
# the water by the same factor and their relative rates never drift.
FRAME_DT = 1.0 / 60.0
MAX_FRONTS = 24


class Rig:
    """A drawn machine, standing in the water, running."""

    def __init__(self, assembly: Assembly, medium=None, depth_m: float = 0.0,
                 time_scale: float = 0.2):
        self.assembly = assembly
        self.medium = medium if medium is not None else world.build()
        self.network = assembly.compile()
        self.cavitation = Cavitation(self.network, depth_m)
        self.emitter = Emitter(assembly, self.network)
        self.fronts = []
        self.time_scale = time_scale
        self._carry = 0.0
        self.sources = {}          # node_id -> callable(step) -> amplitude
        self.steps = 0

    def feed_node(self) -> int:
        """Where a source attaches: the leftmost node of the drawing. Not a
        mouth -- with a shared spine the feed point is a FORK, and asking for
        a terminal there silently attaches the source to one of the outputs
        instead, which looks like a machine that emits nothing."""
        graph = self.assembly.to_graph()
        return min(graph.nodes.items(), key=lambda kv: kv[1].pos[0])[0]

    def drive(self, node_id: int, amplitude: float, freq: float | None = None):
        """A source (3.1). Constant, or oscillating at a note -- and a loop
        only charges when it is driven near its own, which is the whole
        reason a source has a note at all."""
        if freq is None:
            self.sources[node_id] = lambda _i: amplitude
            return
        # `freq` is the note in the WATER, which is what a player means by a
        # note. The bench runs at its own scale and its own clock, so it has
        # to be converted down before it becomes a period in sim steps --
        # asking the bench directly for 420 Hz asks for eight times its
        # Nyquist and gets silence.
        bench_hz = freq / WATER_FREQ_RATIO
        period = max(3.0, 1.0 / (bench_hz * SIM_DT))
        self.sources[node_id] = (
            lambda i: amplitude * math.sin(2.0 * math.pi * i / period))

    def step(self, dt: float = FRAME_DT) -> None:
        sim_dt = dt * self.time_scale

        # The machine, at its own rate. The carry keeps fractional steps so a
        # slow-motion factor that is not a whole ratio does not silently
        # detune every loop in the drawing.
        self._carry += sim_dt / SIM_DT
        n = int(self._carry)
        self._carry -= n
        for _ in range(n):
            inj = {nid: fn(self.steps) for nid, fn in self.sources.items()}
            self.cavitation.step()
            self.network.step(inj or None)
            self.steps += 1
            for front in self.emitter.step():
                self.fronts.append(front)

        # The water, once.
        self.medium.step(sim_dt)
        for front in self.fronts:
            front.step(self.medium, sim_dt)
        self.fronts = [f for f in self.fronts if not f.is_dead()]
        if len(self.fronts) > MAX_FRONTS:
            self.fronts = self.fronts[-MAX_FRONTS:]

    # -- what the renderer wants ---------------------------------------
    @property
    def apertures(self):
        return self.emitter.groups

    def report(self) -> str:
        shapes = ", ".join(
            f"{g.shape()} ({g.span:.0f}px, {len(g.node_ids)} mouth"
            f"{'s' if len(g.node_ids) > 1 else ''})"
            for g in self.emitter.groups)
        return (f"{self.assembly.describe()}  ->  {shapes or 'no mouths'}"
                f"   [{self.emitter.born} fronts, "
                f"{self.cavitation.fired()} gate fires]")


def _feed_comb(n, spacing, curve=0.0, x=520.0, y=380.0):
    """A machine whose output aperture is n mouths in a bowed row, fed from a
    single spine so that only the far ends are open."""
    asm = Assembly()
    span = (n - 1) * spacing
    for i in range(n):
        oy = y - span / 2.0 + i * spacing
        t = (i - (n - 1) / 2.0) / max(n - 1, 1)
        bow = curve * (1.0 - t * t)
        asm.add_run((x - 240.0, y), (x + bow, oy))
    return asm


def demo_rigs():
    """One rig per line of 5.1's table, all fed identically, so the only
    thing that differs is the shape of the mouth."""
    return [
        ("SPITTER", _feed_comb(1, 30.0)),
        ("CARRY", _feed_comb(5, 34.0)),
        ("SNIPER", _feed_comb(5, 34.0, curve=-24.0)),
        ("WASH", _feed_comb(5, 34.0, curve=110.0)),
    ]


def main():
    """5.1's claim is about intensity AT A DISTANCE, not about how far the
    front's leading edge gets. A spitter's front travels as far as any other
    -- it is just worthless when it arrives -- so measuring reach alone makes
    the weakest mouth look like the best one."""
    print("a drawn machine, standing in the water")
    print("intensity delivered at range, all four fed identically")
    print("")
    bands = (120.0, 300.0, 500.0, 800.0)
    print(f"  {'':9s}{'aperture':>26s}" + "".join(f"{int(b):>10d} px" for b in bands))
    for name, asm in demo_rigs():
        rig = Rig(asm)
        # A whistle, not a hum. 7.4a: a mouth narrower than its own
        # wavelength cannot be aimed, and at 469 Hz the wavelength is 320 px
        # against a 149 px mouth -- so a sniper drawn for a low note is
        # physically a point source and the demo would be showing a rule
        # being broken rather than a shape being chosen.
        rig.drive(rig.feed_node(), 0.55, freq=3750.0)
        origin = max(rig.apertures, key=lambda g: g.centre.x).centre
        best = {b: 0.0 for b in bands}
        for _ in range(700):
            rig.step()
            for f in rig.fronts:
                for p0, _p1, inten in f.segments():
                    d = math.hypot(p0[0] - origin.x, p0[1] - origin.y)
                    for b in bands:
                        if abs(d - b) < 25.0:
                            best[b] = max(best[b], inten)
        g = max(rig.apertures, key=lambda x: x.centre.x)
        label = f"{g.shape()} {g.span:.0f}px"
        print(f"  {name:9s}{label:>26s}"
              + "".join(f"{best[b]:>12.5f}" for b in bands))
    print("")
    print("  a spitter is vicious up close and worthless at range;")
    print("  a carry is softer at birth and still there at the far band;")
    print("  a sniper is soft everywhere except where it converges.")


if __name__ == "__main__":
    main()
