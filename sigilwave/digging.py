"""Rock has a note. SUBMERGED.md 8, the SHATTER verb, and 13 step 7.

This is the calmest complete loop in the game and the reason it is step 7
rather than step 2: it exercises everything -- ping, identify, build, tune,
deliver -- with nothing hunting you while you get it wrong.

    ping the rock  ->  hear which note it answers on
    build for that note  ->  a loop of the right size, gapped so it charges
    aim it  ->  a mouth twice as wide as that loop
    deliver it  ->  a drill, close enough to be fed

**Identify costs no interface.** 9.3 forbids a readout, so the rock does not
tell you its note -- it simply lights up more brightly when your ping matches
it. Sweeping the note ladder and watching which wall answers *is* the
identify act, and it is a thing you do rather than a number you read.

**A note is a region, not a texture.** Rock notes are assigned in coarse
blocks so neighbouring cells agree. Per-cell noise would make identification
a lottery with no transferable knowledge, which is 2.1's failure wearing a
geology costume: you could learn nothing from one wall that helped with the
next.

**Deeper rock is lower.** The note falls with depth, so a machine that opens
the shallows will not touch the floor and descending forces you to rebuild --
the same pressure 4.1's Blake threshold already applies to gates, arriving
independently from the other side.
"""

import math

import numpy as np

# The drawable ladder, in water Hz, from the loop sizes a hand can make.
# Rock is only ever tuned to notes a player can actually produce; a wall you
# cannot ring is not a puzzle, it is a wall.
ROCK_NOTES = (3750.0, 1875.0, 937.0, 469.0, 234.0)

# One region is this many cells across. Big enough that a ping lights a
# recognisable patch, small enough that one room holds several answers.
REGION = 6

# How near a note has to be to count. Half a rung either side, so the ladder
# is a set of distinguishable answers rather than a continuum to hunt through.
TOLERANCE = 0.22

# Damage per unit of matched drive per second, and what it takes to break.
CRACK_RATE = 2.4
CRACK_AT = 1.0


def resonance(freq: float, rock_freq: float) -> float:
    """How well a note suits this rock: 1.0 dead on, 0 outside tolerance.

    Compared in octaves rather than Hz, because the ladder is octaves: a
    100 Hz miss is nothing at the top of the ladder and everything at the
    bottom, and a rule that means different things at different depths is not
    a rule the player can carry down with them."""
    if freq <= 0.0 or rock_freq <= 0.0:
        return 0.0
    octaves = abs(math.log2(freq / rock_freq))
    if octaves >= TOLERANCE:
        return 0.0
    return 1.0 - octaves / TOLERANCE


class Seams:
    """Which note each patch of rock answers on, and how cracked it is."""

    def __init__(self, medium, seed: int = 7):
        self.medium = medium
        ny, nx = medium.solid.shape
        ry = (ny + REGION - 1) // REGION
        rx = (nx + REGION - 1) // REGION

        # Deterministic, not random: the same room always has the same seams,
        # so knowledge of it is worth having. Depth sets the note and a cheap
        # hash breaks the ties, which keeps regions legible without making
        # them a grid of stripes.
        rows = np.arange(ry).reshape(-1, 1)
        cols = np.arange(rx).reshape(1, -1)
        depth = rows / max(ry - 1, 1)
        jitter = ((rows * 73856093) ^ (cols * 19349663) ^ (seed * 83492791))
        jitter = (jitter % 1000) / 1000.0
        # Deeper is lower: index climbs into the low notes with depth.
        idx = np.clip(
            (depth * (len(ROCK_NOTES) - 1) + (jitter - 0.5) * 1.1
             ).round().astype(int), 0, len(ROCK_NOTES) - 1)
        self.region_note = np.array(ROCK_NOTES)[idx]

        self.note = np.repeat(np.repeat(self.region_note, REGION, axis=0),
                              REGION, axis=1)[:ny, :nx]
        self.damage = np.zeros((ny, nx))
        self.lit = np.zeros((ny, nx))
        self.broken = 0

    # -- reading it ----------------------------------------------------
    def note_at(self, x, y) -> float:
        cs = self.medium.cell_size
        r = int(min(max(y / cs, 0), self.note.shape[0] - 1))
        c = int(min(max(x / cs, 0), self.note.shape[1] - 1))
        return float(self.note[r, c])

    def answer(self, x, y, freq) -> float:
        """How brightly this rock answers a ping at this note. The identify
        layer, and the whole of it."""
        if not self.medium.is_solid(x, y):
            return 0.0
        return resonance(freq, self.note_at(x, y))

    def light(self, xs, ys, freq, strength=1.0) -> None:
        """Mark rock that a ping just touched, brightened by how well the note
        suits it."""
        cs = self.medium.cell_size
        r = np.clip((np.asarray(ys) / cs).astype(int), 0, self.note.shape[0] - 1)
        c = np.clip((np.asarray(xs) / cs).astype(int), 0, self.note.shape[1] - 1)
        solid = self.medium.solid[r, c]
        if not solid.any():
            return
        rr, cc = r[solid], c[solid]
        ratio = np.abs(np.log2(np.maximum(freq, 1e-6) / self.note[rr, cc]))
        fit = np.clip(1.0 - ratio / TOLERANCE, 0.0, 1.0)
        # A miss still shows the wall is there -- you can always SEE rock by
        # pinging it. What matching buys is knowing which rock you are looking
        # at, which is a different question and the one worth paying for.
        np.maximum.at(self.lit, (rr, cc), 0.25 + 0.75 * fit * strength)

    def fade(self, keep=0.985) -> None:
        self.lit *= keep

    # -- breaking it ---------------------------------------------------
    def strike(self, x, y, radius, freq, power, dt) -> int:
        """Drive rock at its own note and it comes apart. Returns cells broken.

        Power alone does nothing: 8's SHATTER is resonance, not force, and a
        drill fed the wrong note is a drill politely warming the water."""
        fit = resonance(freq, self.note_at(x, y))
        if fit <= 0.0 or power <= 0.0:
            return 0
        cs = self.medium.cell_size
        r0 = int(max((y - radius) / cs, 0))
        r1 = int(min((y + radius) / cs + 1, self.note.shape[0]))
        c0 = int(max((x - radius) / cs, 0))
        c1 = int(min((x + radius) / cs + 1, self.note.shape[1]))
        if r1 <= r0 or c1 <= c0:
            return 0

        rows = (np.arange(r0, r1).reshape(-1, 1) + 0.5) * cs - y
        cols = (np.arange(c0, c1).reshape(1, -1) + 0.5) * cs - x
        near = (rows ** 2 + cols ** 2) <= radius ** 2
        patch = self.medium.solid[r0:r1, c0:c1] & near
        if not patch.any():
            return 0

        # Each cell is judged against its OWN note, so a seam boundary breaks
        # unevenly and the shape of what falls away tells you where the next
        # region starts.
        own = np.abs(np.log2(max(freq, 1e-6) / np.maximum(
            self.note[r0:r1, c0:c1], 1e-6)))
        cell_fit = np.clip(1.0 - own / TOLERANCE, 0.0, 1.0)
        self.damage[r0:r1, c0:c1] += np.where(
            patch, cell_fit * power * CRACK_RATE * dt, 0.0)

        gone = patch & (self.damage[r0:r1, c0:c1] >= CRACK_AT)
        n = int(gone.sum())
        if n:
            sub = self.medium.solid[r0:r1, c0:c1]
            sub[gone] = False
            self.medium.solid[r0:r1, c0:c1] = sub
            self.medium._dirty = True
            self.broken += n
        return n

    def progress_at(self, x, y) -> float:
        cs = self.medium.cell_size
        r = int(min(max(y / cs, 0), self.note.shape[0] - 1))
        c = int(min(max(x / cs, 0), self.note.shape[1] - 1))
        return float(min(1.0, self.damage[r, c] / CRACK_AT))
