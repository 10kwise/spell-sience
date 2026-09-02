"""Does every preset earn its description? SUBMERGED.md 4, 5, 5.1, 4.1.

A library of machines that do not do what they claim is worse than no
library, because it teaches the player wrong rules -- and wrong rules are
exactly what three rewrites have been spent escaping. So every preset's
`summary` is a claim, and each claim is measured here.

    python -m sigilwave.bench.selftest_presets
"""

import math

from .cavitation import Cavitation
from .mouths import Emitter, WATER_FREQ_RATIO, aperture_wavelengths
from .parts import SIM_DT, Assembly
from .presets import PRESETS, build

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


def _feed(asm):
    graph = asm.to_graph()
    return min(graph.nodes.items(), key=lambda kv: kv[1].pos[0])[0]


def run(preset, steps=2600):
    """Drive a preset the way it asks to be driven, and report what it did."""
    asm = build(preset.name)
    net = asm.compile()
    cav = Cavitation(net)
    em = Emitter(asm, net)
    feed = _feed(asm)
    period = max(3.0, 1.0 / ((preset.drive_hz / WATER_FREQ_RATIO) * SIM_DT))
    fronts = 0
    energy = 0.0
    peak_wire = 0.0
    for i in range(steps):
        cav.step()
        net.step({feed: preset.drive_amp * math.sin(2.0 * math.pi * i / period)})
        for fr in em.step():
            fronts += 1
            energy += fr.total_energy()
        if i > 200:
            peak_wire = max(peak_wire, max(
                abs(e.forward.peek(j))
                for e in net.edges.values()
                for j in range(0, e.length_samples, 7)))
    out = max(em.groups, key=lambda g: g.centre.x) if em.groups else None
    return dict(asm=asm, em=em, cav=cav, fronts=fronts, energy=energy,
                peak_wire=peak_wire, out=out)


def main():
    global _p, _f
    print("--- every preset compiles, is nameable, and emits ---")
    results = {}
    for preset in PRESETS:
        r = run(preset)
        results[preset.name] = r
        desc = r["asm"].describe()
        note(f"  {preset.name:14s} {desc[:58]:58s} {r['fronts']:3d} fronts")
        check(r["out"] is not None, f"{preset.name}: has a mouth")
        check("tangle" not in desc,
              f"{preset.name}: can be named in one sentence")
        check(r["fronts"] > 0, f"{preset.name}: actually emits when driven")

    print("")
    print("--- the fan really is ONE mouth, not three (5) ---")
    fan = results["the fan"]["out"]
    tap = results["the tapper"]["out"]
    note(f"the fan's aperture: {len(fan.node_ids)} mouths merged,"
         f" {fan.span:.0f} px wide")
    note(f"the tapper's:      {len(tap.node_ids)} mouth, {tap.span:.0f} px wide")
    check(len(fan.node_ids) > 1, "the fan's ends merged into one aperture")
    check(fan.span > tap.span * 3.0, "and it is far wider than a single mouth")

    print("")
    print("--- the lance is brutal and short, the carry is soft and long ---")
    lance = results["the lance"]
    carry = results["the carry"]
    li = lance["energy"] / max(lance["out"].span, 1.0)
    ci = carry["energy"] / max(carry["out"].span, 1.0)
    note(f"the lance: {lance['out'].span:5.1f} px wide,"
         f" birth intensity {li:.5f}")
    note(f"the carry: {carry['out'].span:5.1f} px wide,"
         f" birth intensity {ci:.5f}")
    check(lance["out"].span < carry["out"].span,
          "the lance is the narrower mouth")
    check(li > ci, "and hits harder at birth for the same energy")

    print("")
    print("--- the horn can actually be aimed (7.4a) ---")
    horn = results["the horn"]
    wl = aperture_wavelengths(horn["out"].span, PRESETS[4].drive_hz)
    k = horn["out"].drawn_curvature
    focus = (1.0 / abs(k)) if abs(k) > 1e-9 else float("inf")
    note(f"the horn: {horn['out'].span:.0f} px wide at"
         f" {PRESETS[4].drive_hz:.0f} Hz = {wl:.1f} wavelengths")
    note(f"drawn curvature {k:+.5f} -> focus about {focus:.0f} px out")
    check(wl > 2.0,
          "wider than two wavelengths, so it is not merely a point source")
    check(k < 0.0, "and it is genuinely cupped, not flat")

    print("")
    print("--- the flywheel charges because it is GAPPED, not joined ---")
    fly = results["the flywheel"]
    from .presets import flywheel_assembly
    joined = flywheel_assembly(feed_gap=0.0)
    jnet = joined.compile()
    jcav = Cavitation(jnet)
    jfeed = _feed(joined)
    period = max(3.0, 1.0 / ((PRESETS[5].drive_hz / WATER_FREQ_RATIO) * SIM_DT))
    jpeak = 0.0
    for i in range(2600):
        jcav.step()
        jnet.step({jfeed: PRESETS[5].drive_amp
                   * math.sin(2.0 * math.pi * i / period)})
        if i > 200:
            jpeak = max(jpeak, max(
                abs(e.forward.peek(j))
                for e in jnet.edges.values()
                for j in range(0, e.length_samples, 7)))
    note(f"gapped off its feed: wires peak at {fly['peak_wire']:.4f}")
    note(f"the same loop JOINED: wires peak at {jpeak:.4f}")
    check(fly["peak_wire"] > jpeak * 3.0,
          f"the gap is the whole point - it charges"
          f" {fly['peak_wire']/max(jpeak,1e-9):.0f}x higher")

    print("")
    print("--- the ticker fires, repeatedly ---")
    tick = results["the ticker"]
    note(f"the ticker tore the water open {tick['cav'].fired()} times")
    check(tick["cav"].fired() > 1,
          "a charged loop trips its gap again and again - a trigger")
    check(results["the flywheel"]["cav"].fired()
          <= tick["cav"].fired(),
          "and it fires more than the flywheel it is built from")

    print("")
    print("--- the thruster is a shove, not a beam ---")
    thr = results["the thruster"]
    car = results["the carry"]
    note(f"the thruster: {thr['out'].span:.0f} px wide,"
         f" curvature {thr['out'].drawn_curvature:+.5f}"
         f" ({thr['out'].shape()})")
    note(f"the carry:    {car['out'].span:.0f} px wide,"
         f" curvature {car['out'].drawn_curvature:+.5f}"
         f" ({car['out'].shape()})")
    # An earlier version of this check asserted the thruster FACES backwards.
    # It does not and never claimed to: the whole machine is turned to the
    # diver's aim in play, and thrust is always opposite the aperture, so
    # which way it points on the bench is not a fact about the preset. What
    # it does claim is a wash - wide, convex, everything dumped nearby.
    check(thr["out"].drawn_curvature > 0.0,
          "the thruster bulges into the water rather than cupping away from it")
    check(thr["out"].span > car["out"].span * 0.9,
          "and it is a wide mouth, not a point")
    check(thr["out"].shape() == "wash",
          "which is a wash - 5.1's shape for putting everything nearby")

    print("")
    print(f"{_p} passed, {_f} failed.")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
