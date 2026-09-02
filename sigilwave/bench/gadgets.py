"""Things that react to what you feed them. SUBMERGED.md 8.

Until now a machine could only make sound. That is a thin reason to draw:
the player builds a waveform and the water does something to it, and the
whole loop is admiring physics. A gadget is the other end of the wire -- a
device you point a mouth at, with **one rule about what it wants** -- and it
turns "make a waveform" into "drive that thing".

This is the piece that makes the drawing purposeful, and it is deliberately
NOT a glyph system. A glyph whose meaning someone decided is a lookup table
with good art, and 2.1 is the account of why that fails: the meaning is
authored, so nothing emerges from combining. A gadget's behaviour is not
authored. It states a band and a threshold, and everything else -- whether
your machine can reach it, whether it can reach it at range, whether two
gadgets can be driven at once -- falls out of the parts you already have.

**Every gadget is two sentences.** What it wants, and what it does. That is
the whole contract, and it is what makes a chain of them learnable:

    I need air        -> a gill wants a chirp, loudly
    a chirp is small  -> a small loop rings high but stores little
    so it must charge -> a loop charges only when GAPPED off its feed
    and to reach it   -> the mouth must be twice as wide as that loop

Four rules the player already met, arriving as one problem with one answer.
None of that chain is written down anywhere in this file; it is what the
numbers already were.
"""

import math
from dataclasses import dataclass, field

import pygame

from .mouths import BENCH_M_PER_PX, C_WATER, wavelength_px

V = pygame.Vector2

# A gadget hears an aperture within this. Beyond it, the mouth is talking to
# the water instead -- which is the whole reason placement is a decision.
COUPLING_RANGE = 74.0


@dataclass
class Gadget:
    """A device at a place, waiting to be driven.

    `band` is the range of notes it responds to and `threshold` is the drive
    below which nothing at all happens. The threshold is not difficulty
    padding: it is what makes a half-built machine visibly fail rather than
    quietly underperform, which is 9.5.
    """

    kind: str
    wants: str
    does: str
    band: tuple
    threshold: float
    pos: V = field(default_factory=lambda: V(0.0, 0.0))
    charge: float = 0.0
    output: float = 0.0
    lit: float = 0.0

    def tuned(self, freq: float) -> float:
        """How well a note suits this gadget: 1.0 dead centre, 0 outside.

        Smooth rather than a hard window, because 9.2 forbids ambiguous
        middles in the DRAWING but a gadget being half-driven is legible --
        it visibly does half as much, and that is a reading the player can
        act on."""
        lo, hi = self.band
        if freq <= 0.0 or freq < lo * 0.5 or freq > hi * 2.0:
            return 0.0
        if lo <= freq <= hi:
            return 1.0
        edge = lo * 0.5 if freq < lo else hi * 2.0
        near = lo if freq < lo else hi
        return max(0.0, 1.0 - abs(freq - near) / abs(edge - near))

    def drive(self, amplitude: float, freq: float, dt: float) -> float:
        """Feed it. Returns what it produced this step."""
        fit = self.tuned(freq)
        got = amplitude * fit
        if got < self.threshold:
            self.output *= 0.86
            self.charge = max(0.0, self.charge - dt)
            return 0.0
        self.output = got - self.threshold
        self.charge = min(1.0, self.charge + dt * 2.0)
        self.lit = 1.0
        return self.output

    def idle(self, dt: float) -> None:
        self.output *= 0.86
        self.lit = max(0.0, self.lit - dt * 2.0)
        self.charge = max(0.0, self.charge - dt * 0.5)

    @property
    def running(self) -> bool:
        return self.output > 1e-6


def propeller(pos=(0, 0)) -> Gadget:
    """Low and loud. A blade is a lever against water and levers want a slow
    heavy push, not a fast light one -- so the note that drives it best is
    the note that carries furthest, and a diver who tunes for thrust has
    tuned for range at the same time."""
    return Gadget("propeller",
                  "a low note, pushed hard",
                  "drives you through the water",
                  band=(90.0, 320.0), threshold=0.010, pos=V(pos))


def lamp(pos=(0, 0)) -> Gadget:
    """Very loud, any note. Sonoluminescence: drive water hard enough to tear
    it open and the cavity flashes as it collapses. The same breakdown 4.1
    uses as a logic gate, put to work as a light -- one physical effect, two
    unrelated jobs, which is the interaction density 7 is built on."""
    return Gadget("lamp",
                  "any note, but very loud",
                  "tears the water open and it flashes",
                  band=(60.0, 6000.0), threshold=0.055, pos=V(pos))


def gill(pos=(0, 0)) -> Gadget:
    """One narrow note. It shakes dissolved gas out of solution, and gas comes
    out at the note that matches the bubbles it wants to make -- so this is
    the fussiest gadget and the one you cannot do without."""
    return Gadget("gill",
                  "a chirp, and nothing else",
                  "shakes breathable gas out of the water",
                  band=(1500.0, 2400.0), threshold=0.022, pos=V(pos))


def drill(pos=(0, 0)) -> Gadget:
    """Mid notes, hard. Rock has a note and shaking it at that note is what
    breaks it (8's SHATTER). The gadget only concentrates what you feed it;
    finding the rock's note is still the player's problem."""
    return Gadget("drill",
                  "a middling note, driven hard",
                  "shakes rock apart at its own note",
                  band=(380.0, 1100.0), threshold=0.040, pos=V(pos))


KINDS = {"propeller": propeller, "lamp": lamp, "gill": gill, "drill": drill}
ORDER = ("propeller", "lamp", "gill", "drill")


class Rack:
    """The gadgets bolted to one machine, and the wiring to its mouths."""

    def __init__(self):
        self.gadgets = []

    def add(self, kind, pos):
        g = KINDS[kind](pos)
        self.gadgets.append(g)
        return g

    def remove_at(self, pos, radius=26.0):
        p = V(pos)
        for g in list(self.gadgets):
            if (g.pos - p).length() <= radius:
                self.gadgets.remove(g)
                return True
        return False

    def step(self, emitter, dt) -> dict:
        """Drive every gadget from whichever aperture is close enough.

        An aperture feeds a gadget instead of the water, not as well as it --
        pointing a mouth at a device is a decision about where the energy
        goes, which is the only way placement can matter."""
        totals = {k: 0.0 for k in KINDS}
        if emitter is None:
            for g in self.gadgets:
                g.idle(dt)
            return totals

        for g in self.gadgets:
            best = 0.0
            best_freq = 0.0
            for group in emitter.groups:
                d = (V(group.centre) - g.pos).length()
                if d > COUPLING_RANGE:
                    continue
                fall = (1.0 - d / COUPLING_RANGE) ** 2
                # Intensity, not raw energy: a wide mouth spread over a small
                # device delivers less of itself, exactly as 5 says. And
                # power_now, not accum -- accum is the renderer's batching
                # buffer and reads empty most steps.
                amp = (group.power_now / max(group.span, 1.0)) * fall * 400.0
                if amp > best:
                    best, best_freq = amp, group.last_freq
            if best > 0.0:
                totals[g.kind] += g.drive(best, best_freq, dt)
            else:
                g.idle(dt)
        return totals

    def describe(self) -> list:
        return [(g.kind, g.wants, g.does, g.running) for g in self.gadgets]


