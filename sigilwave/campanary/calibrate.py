"""Measure the game rather than guess at it.

Every number in `notes.NOTE_POWER` and `rings.CRACK_SCALE` is set from what
comes out of here, because they are the only two places the game is allowed
to put its thumb on the physics and both of them are corrections for a
measurable inequality rather than opinions about balance.

    python -m sigilwave.campanary.calibrate
"""

import pygame

from sigilwave.ink import Stroke

from . import notes, shapes
from .bell import Bell
from .metals import ALL_METALS, BRONZE


def bell_at(note, metal=BRONZE):
    return Bell("cal", [Stroke(points=shapes.ring_for_note(note), ink_type=metal)])


def steady_output(note, metal=BRONZE, strikes=8):
    """Energy per strike once a bell struck on its own beat has settled."""
    b = bell_at(note, metal)
    period = max(0.28, b.period)
    last = 0.0
    for _ in range(strikes):
        b.strike()
        t = 0.0
        while t < period:
            b.advance(1 / 120)
            t += 1 / 120
        bands, total = b.take_output()
        last = (bands, total)
    return last


def swell_release(note, metal=BRONZE, hold=1.4):
    """Everything a swelled bell dumps when it is let go."""
    b = bell_at(note, metal)
    b.set_swell(True)
    t = 0.0
    while t < hold:
        b.advance(1 / 120)
        t += 1 / 120
    b.set_swell(False)
    b.strike()
    t = 0.0
    while t < 0.09:
        b.advance(1 / 120)
        t += 1 / 120
    bands, total = b.take_output()
    return bands, total, b.char


def main():
    pygame.init()
    print("=" * 74)
    print("CAMPANARY calibration")
    print("=" * 74)

    print("\n[1] energy per settled on-beat strike, by note")
    base = {}
    for n in range(4):
        bands, total = steady_output(n)
        centre, _ = notes.note_from_bands(bands)
        shape = [round(x / max(total, 1e-9), 3) for x in bands]
        base[n] = total
        print(f"  {notes.NOTE_NAMES[n]:9s} E={total:8.2f}  centroid={centre:5.2f}  shape={shape}")

    print("\n    implied NOTE_POWER (TENOR = 1.0):")
    ref = base[1]
    implied = [round(ref / max(base[n], 1e-9), 2) for n in range(4)]
    print(f"      {implied}   (in use: {notes.NOTE_POWER[:4]})")

    print("\n[2] the swell: does a CHIME climb to SPARROW, and what does it cost?")
    for metal in ALL_METALS:
        bands, total, char = swell_release(3, metal)
        centre, _ = notes.note_from_bands(bands)
        shape = [round(x / max(total, 1e-9), 3) for x in bands]
        print(f"  {metal.name:11s} E={total:8.2f} centroid={centre:5.2f} char={char:4.2f} shape={shape}")
    bands, total, _ = swell_release(3)
    print(f"    implied NOTE_POWER[4] for parity with TENOR: "
          f"{ref / max(total, 1e-9):.2f}   (in use: {notes.NOTE_POWER[4]})")

    print("\n[3] cross-matching: every bell against every target note")
    print("       " + "".join(f"{notes.NOTE_SHORT[t]:>9s}" for t in range(5)))
    for n in range(4):
        bands, total = steady_output(n)
        row = ""
        for t in range(5):
            v = notes.strike_value(bands, notes.match_curve(t))
            row += f"{v:9.1f}"
        print(f"  {notes.NOTE_SHORT[n]:5s}{row}")
    bands, total, _ = swell_release(3)
    row = "".join(f"{notes.strike_value(bands, notes.match_curve(t)):9.1f}" for t in range(5))
    print(f"  {'SWELL':5s}{row}")

    print("\n[4] strikes to shatter (crack scale check)")
    from .rings import CRACK_SCALE
    # Read straight off the classes, so this cannot quietly go stale when a
    # cap is retuned - which it had, reporting an Overtone at 2.6 long after
    # it was 2.0.
    from .foes import Glasswing, Husk, Overtone
    caps = {f.label: (f.note, f.cap) for f in (Husk, Glasswing, Overtone)}
    for label, (tn, cap) in caps.items():
        line = f"  {label:11s} (cap {cap}):  "
        for n in range(4):
            bands, _ = steady_output(n)
            per = notes.strike_value(bands, notes.match_curve(tn)) * CRACK_SCALE
            hits = cap / per if per > 1e-9 else 999
            line += f"{notes.NOTE_SHORT[n]}={hits:6.1f}  "
        bands, _, _ = swell_release(3)
        per = notes.strike_value(bands, notes.match_curve(tn)) * CRACK_SCALE
        line += f"SWELL={cap / per if per > 1e-9 else 999:6.1f}"
        print(line)


if __name__ == "__main__":
    main()
