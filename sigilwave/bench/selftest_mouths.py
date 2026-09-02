"""Does the drawing shape the output? SUBMERGED.md 5.

Every check here tests one line of 5.1's table. If the shape a player draws
does not visibly change what arrives in the water, then merging is decoration
and the whole output vocabulary collapses back to CAMPANARY's one ring.

    python -m sigilwave.bench.selftest_mouths
"""

import math

from ..sim.network import raised_cosine_burst
from .mouths import (MERGE_DIST, Emitter, aperture_wavelengths,
                     diffraction_curvature, merge_mouths, wavelength_px)
from .parts import Assembly

_passed = 0
_failed = 0


def check(ok, label):
    global _passed, _failed
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if ok:
        _passed += 1
    else:
        _failed += 1


def note(text):
    print(f"       {text}")


def _comb(n, spacing, y=300.0, curve=0.0):
    """n parallel runs ending in a row, so their far ends form an aperture.
    `curve` bows that row: negative cups it toward the water (concave)."""
    asm = Assembly()
    span = (n - 1) * spacing
    for i in range(n):
        oy = y - span / 2.0 + i * spacing
        t = (i - (n - 1) / 2.0) / max(n - 1, 1)
        bow = curve * (1.0 - t * t)
        asm.add_run((200.0, oy), (600.0 + bow, oy))
    return asm


def _out(asm, **kw):
    """The OUTPUT aperture. A comb's runs are free at both ends, so its left
    ends form an aperture too -- the feed side. Everything here is about what
    leaves, so pick the group furthest along the way the runs point."""
    groups = merge_mouths(asm, **kw)
    return max(groups, key=lambda g: g.centre.x)


def _fire(asm, steps=400, amplitude=1.0):
    net = asm.compile()
    em = Emitter(asm, net)
    burst = raised_cosine_burst(6, amplitude=amplitude)
    fronts = []
    feed = sorted(nid for nid, _ in asm.mouth_nodes())[0]
    for i in range(steps):
        net.step({feed: burst[i]} if i < len(burst) else None)
        fronts.extend(em.step())
    return em, fronts


def main():
    print("--- merging: what counts as one mouth ---")
    near = _out(_comb(3, MERGE_DIST * 0.6))
    far = _out(_comb(3, MERGE_DIST * 1.8))
    note(f"3 ends {MERGE_DIST*0.6:.0f} px apart -> one aperture of"
         f" {len(near.node_ids)} mouths, span {near.span:.0f} px")
    note(f"3 ends {MERGE_DIST*1.8:.0f} px apart -> apertures of"
         f" {len(far.node_ids)} mouth, span {far.span:.0f} px")
    check(len(near.node_ids) == 3,
          "mouths close together merge into one wider mouth")
    check(len(far.node_ids) == 1, "mouths far apart stay separate")
    check(near.span > MERGE_DIST, "and the merged aperture is genuinely wider")

    print("\n--- the four facts, read off the drawing ---")
    for n, spacing, curve, expect in ((1, 0.0, 0.0, "spitter"),
                                      (4, 30.0, 0.0, "carry"),
                                      (4, 30.0, -60.0, "sniper"),
                                      (4, 30.0, 60.0, "wash")):
        g = _out(_comb(max(n, 1), spacing or 30.0, curve=curve))
        freq = 600.0
        total = g.drawn_curvature + diffraction_curvature(g.span, freq)
        note(f"  {expect:8s}: span {g.span:6.1f} px   drawn curvature"
             f" {g.drawn_curvature:+.5f}   with diffraction {total:+.5f}"
             f"   -> {g.shape()}")
        check(g.shape() == expect, f"a {expect} reads as a {expect}")

    print("\n--- 5.1: width does two opposite things ---")
    narrow = _out(_comb(1, 30.0))
    wide = _out(_comb(5, 30.0))
    kn = diffraction_curvature(narrow.span, 600.0)
    kw = diffraction_curvature(wide.span, 600.0)
    note(f"narrow aperture {narrow.span:5.1f} px -> diffraction {kn:.5f}"
         f" (spreads over {1/kn:6.1f} px)")
    note(f"wide   aperture {wide.span:5.1f} px -> diffraction {kw:.5f}"
         f" (spreads over {1/kw:6.1f} px)")
    check(kn > kw * 10.0,
          f"a narrow mouth diffracts far harder than a wide one ({kn/kw:.0f}x)"
          " - there is no drawing that makes a point source a lance")

    print("\n--- and low notes will not stay narrow ---")
    for freq in (60.0, 600.0, 3000.0):
        k = diffraction_curvature(wide.span, freq)
        note(f"  {freq:6.0f} Hz off the same {wide.span:.0f} px arc"
             f" -> curvature {k:.5f}")
    check(diffraction_curvature(wide.span, 60.0)
          > diffraction_curvature(wide.span, 3000.0) * 10.0,
          "a low note spreads harder off the same aperture than a high one")

    print("")
    print("--- an aperture narrower than its wavelength cannot be aimed ---")
    note("a loop of circumference L rings at c/L, so its wavelength in bench")
    note("pixels IS L - so the rule states itself in the player's own units:")
    for rung, hz in (("swell", 117), ("hum", 469), ("chirp", 1875), ("whistle", 3750)):
        note(f"  {rung:>8s} {hz:>5d} Hz: wavelength {wavelength_px(hz):5.0f} px,"
             f" needs a {2*wavelength_px(hz):5.0f} px mouth to aim it")
    check(wavelength_px(469) > wavelength_px(3750) * 4.0,
          "a low note has a far longer wavelength than a high one")
    check(aperture_wavelengths(136.0, 117) < 1.0
          and aperture_wavelengths(136.0, 3750) > 2.0,
          "the same 136 px mouth cannot aim a swell and can aim a whistle -"
          " low notes carry and spray, high notes die and can be aimed")

    print("\n--- intensity is energy over width (5, and the merge rule) ---")
    em1, f1 = _fire(_comb(1, 30.0))
    em4, f4 = _fire(_comb(4, 30.0))
    if f1 and f4:
        g1 = max(em1.groups, key=lambda g: g.centre.x)
        g4 = max(em4.groups, key=lambda g: g.centre.x)
        i1 = f1[-1].total_energy() / g1.span
        i4 = f4[-1].total_energy() / g4.span
        note(f"1 mouth : span {g1.span:5.1f} px, birth intensity {i1:.6f}")
        note(f"4 merged: span {g4.span:5.1f} px, birth intensity {i4:.6f}")
        check(g4.span > g1.span * 5.0, "merging widens the aperture")
        check(i4 < i1, "and the same energy over more width hits softer")
    else:
        check(False, "no fronts were born at all")

    print("\n--- energy crosses the boundary intact (3.2) ---")
    asm = _comb(3, 30.0)
    net = asm.compile()
    em = Emitter(asm, net)
    burst = raised_cosine_burst(6, amplitude=1.0)
    feed = sorted(nid for nid, _ in asm.mouth_nodes())[0]
    radiated = 0.0
    carried = 0.0
    for i in range(800):
        radiated += net.step({feed: burst[i]} if i < len(burst) else None)
        for fr in em.step():
            carried += fr.total_energy()
    note(f"the network radiated {radiated:.6f}; the fronts carry {carried:.6f}"
         f" ({carried/max(radiated,1e-12)*100:.1f}%)")
    check(carried <= radiated * 1.001,
          "no energy is invented at the mouth")
    check(carried > radiated * 0.90,
          "and almost none is lost crossing into the water")

    print(f"\n{_passed} passed, {_failed} failed.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
