"""Can rock be identified and broken? SUBMERGED.md 8, 13 step 7.

    python -m sigilwave.selftest_digging
"""

import math

import numpy as np

from .digging import (CRACK_AT, REGION, ROCK_NOTES, TOLERANCE, Seams,
                      resonance)
from .medium.field import Medium

_p = _f = 0


def check(ok, label):
    global _p, _f
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if ok:
        _p += 1
    else:
        _f += 1


def note(t):
    print(f"       {t}")


def _room():
    m = Medium(1200, 800, 16.0)
    m.set_temperature_profile(lambda d: 10.0)
    m.carve(0, 560, 1200, 240)
    return m


def main():
    global _p, _f
    print("--- a note is a region, not a texture ---")
    m = _room()
    s = Seams(m)
    r = int(640 / m.cell_size)
    row = s.note[r]
    runs = 1
    for a, b in zip(row, row[1:]):
        if a != b:
            runs += 1
    note(f"across one row of rock the note changes {runs - 1} times in"
         f" {len(row)} cells")
    check(runs - 1 < len(row) / (REGION - 1),
          "neighbouring rock agrees - a wall is one answer, not noise")
    check(len(set(row.tolist())) > 1,
          "and a room holds more than one answer")

    print("")
    print("--- deeper rock is lower ---")
    shallow = s.note[int(580 / m.cell_size)].mean()
    deep = s.note[int(780 / m.cell_size)].mean()
    note(f"mean note at 580 px: {shallow:6.0f} Hz;  at 780 px: {deep:6.0f} Hz")
    check(deep < shallow,
          "a machine that opens the shallows will not touch the floor")

    print("")
    print("--- identify: the rock answers, it does not tell you ---")
    x, y = 600.0, 640.0
    true_note = s.note_at(x, y)
    answers = [(hz, s.answer(x, y, hz)) for hz in ROCK_NOTES]
    for hz, a in answers:
        note(f"  pinged at {hz:6.0f} Hz -> the wall answers {a:.2f}"
             f"{'   <- its own note' if hz == true_note else ''}")
    best = max(answers, key=lambda kv: kv[1])
    check(best[0] == true_note,
          "sweeping the ladder finds the note, with no readout anywhere")
    check(sum(1 for _, a in answers if a > 0.0) == 1,
          "and exactly one rung answers - the ladder is a set of answers,"
          " not a continuum to hunt through")
    check(s.answer(600.0, 200.0, true_note) == 0.0,
          "open water answers nothing at all")

    print("")
    print("--- resonance is compared in octaves, so the rule travels ---")
    for hz in (ROCK_NOTES[0], ROCK_NOTES[-1]):
        near = resonance(hz * 1.10, hz)
        far = resonance(hz * 1.60, hz)
        note(f"  at {hz:6.0f} Hz: 10% off scores {near:.2f}, 60% off {far:.2f}")
    check(abs(resonance(ROCK_NOTES[0] * 1.1, ROCK_NOTES[0])
              - resonance(ROCK_NOTES[-1] * 1.1, ROCK_NOTES[-1])) < 1e-9,
          "the same proportional miss scores the same at the top and bottom"
          " of the ladder")

    print("")
    print("--- power alone does nothing (8: SHATTER is resonance) ---")
    m2 = _room()
    s2 = Seams(m2)
    want = s2.note_at(600.0, 640.0)
    wrong = [n for n in ROCK_NOTES if n != want][0]
    before = int(m2.solid.sum())
    for _ in range(240):
        s2.strike(600.0, 640.0, 40.0, wrong, 8.0, 1 / 60.0)
    mid = int(m2.solid.sum())
    note(f"four seconds at the WRONG note, eight times the power:"
         f" {before - mid} cells broken")
    check(mid == before, "a drill fed the wrong note breaks nothing at all")

    for _ in range(240):
        s2.strike(600.0, 640.0, 40.0, want, 1.0, 1 / 60.0)
    after = int(m2.solid.sum())
    note(f"four seconds at the RIGHT note, an eighth of the power:"
         f" {mid - after} cells broken")
    check(after < mid, "and at the right note it comes apart")

    print("")
    print("--- what falls away shows you where the next seam is ---")
    m3 = _room()
    s3 = Seams(m3)
    # Strike across a region boundary and check the hole is not a clean disc.
    cx = (REGION * m3.cell_size) * 3.0
    hit = s3.note_at(cx, 640.0)
    for _ in range(400):
        s3.strike(cx, 640.0, 70.0, hit, 2.0, 1 / 60.0)
    broken = s3.broken
    note(f"a 70 px strike across a seam removed {broken} cells")
    check(broken > 0, "the strike broke rock")
    covered = math.pi * 70.0 ** 2 / (m3.cell_size ** 2)
    note(f"a disc of that radius would be about {covered:.0f} cells")
    check(broken < covered,
          "but not a clean disc - rock tuned to a neighbouring note survives,"
          " so the hole's shape is a map")

    print("")
    print("--- a wall is visible even when you cannot name it ---")
    m4 = _room()
    s4 = Seams(m4)
    xs = np.full(24, 600.0)
    ys = np.linspace(570.0, 700.0, 24)
    s4.light(xs, ys, 1.0)                      # a note that suits nothing
    check(s4.lit.max() > 0.0,
          "pinging with the wrong note still shows the rock is there")
    lit_wrong = s4.lit.max()
    s5 = Seams(_room())
    s5.light(xs, ys, s5.note_at(600.0, 640.0))
    note(f"wrong note lights it {lit_wrong:.2f}, right note {s5.lit.max():.2f}")
    check(s5.lit.max() > lit_wrong,
          "and matching it lights it brighter - which is the whole identify UI")

    print("")
    print(f"{_p} passed, {_f} failed.")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
