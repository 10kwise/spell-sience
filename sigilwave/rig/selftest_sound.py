"""Sound, and whether it is load-bearing. RIGS.md 5.5.

This suite exists because of a playtest verdict, and the verdict was right:

    "the only thing that seems to do nothing is the chirps and groans and
     sound modules i cannot figure out why they are here unless for creature
     behaviour"

It was correct as an observation and it was correct as a diagnosis. A
RESONATOR wrote `note_amp`, carried it to the PORT, and **nothing in between
ever read it**. No ordering involving a RESONATOR changed any outcome, which
in a game whose entire claim is that order is the whole game means the module
was not in the vocabulary at all -- it was an output device with a frequency
label sitting in the module list.

So the tests here are not "does sound have an effect". They are the sharper
question: **does a RESONATOR change what the OTHER modules do?** Every check
below is a measurement of one module against another, and if this file ever
goes quiet the module has gone back to being decoration.

Run:  python -m sigilwave.rig.selftest_sound
"""

from .chain import Chain, ambient_at
from .modules import NOTES
from .units import MAX_WORKING_FRACTION, pipe_loss

DEPTHS = (40.0, 120.0, 250.0, 400.0, 700.0)

_passed = 0
_failed = []


def check(name, condition, detail=""):
    global _passed
    if condition:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed.append((name, detail))
        print(f"  FAIL {name}   {detail}")


def _report(name, value, unit=""):
    print(f"       {name}: {value}{unit}")


def _first_tear(prefix, extra, amb, limit=16):
    """How many of `prefix` it takes before the water lets go."""
    for n in range(0, limit):
        ks = ("INTAKE",) + (prefix,) * n + extra + ("PORT",)
        if Chain(ks).evaluate(amb).tore:
            return n
    return None


# --- 1. sound is a pressure --------------------------------------------------


def test_a_note_lowers_the_tension_without_lowering_the_pressure():
    """The one-line version of the whole redesign. If these two numbers are
    ever equal again, `Slug.acoustic_pressure` has stopped being read."""
    amb = ambient_at(40.0)
    quiet = Chain(("INTAKE", "EXPAND", "PORT")).evaluate(amb)
    loud = Chain(("INTAKE", "EXPAND", "RESONATOR", "PORT")).evaluate(amb)
    check("a RESONATOR does not change the mean pressure",
          abs(loud.min_pressure - quiet.min_pressure) < 1e-9,
          f"{quiet.min_pressure:.4f} -> {loud.min_pressure:.4f} bar")
    check("but it drops the tension the water actually sees",
          loud.min_tension < quiet.min_tension - 0.5,
          f"{quiet.min_tension:.4f} -> {loud.min_tension:.4f} bar")
    _report("mean pressure", f"{loud.min_pressure:.3f}", " bar")
    _report("lowest tension", f"{loud.min_tension:.3f}", " bar")


def test_a_note_is_worth_two_or_three_expansions_at_every_depth():
    """The headline interaction, checked at five depths rather than one so it
    is a rule and not a coincidence at the station."""
    rows = []
    for d in DEPTHS:
        amb = ambient_at(d)
        alone = _first_tear("EXPAND", (), amb)
        with_note = _first_tear("EXPAND", ("RESONATOR",), amb)
        rows.append((d, alone, with_note))
    check("a note tears water that expansion alone cannot, at every depth",
          all(a is not None and b is not None and b < a for _, a, b in rows),
          str(rows))
    saved = [a - b for _, a, b in rows]
    check("and it is consistently worth two or three of them",
          all(2 <= s <= 3 for s in saved), str(saved))
    for d, a, b in rows:
        _report(f"{d:5.0f} m", f"{a} EXPANDs alone, {b} with a note")


def test_narrowing_focuses_a_note_and_widening_spreads_it():
    """NARROW and WIDEN became the RESONATOR's knob, which is what stops it
    being a singleton in effect as well as in the table."""
    # The aperture has to be set BEFORE the note is made, which is the whole
    # point -- intensity is power over area, so what matters is the bore the
    # sound is born into. Putting the WIDENs after the RESONATOR measured
    # nothing, because the lowest tension in the chain had already happened.
    amb = ambient_at(40.0)
    base = Chain(("INTAKE", "RESONATOR", "PORT")).evaluate(amb)
    tighter = Chain(("INTAKE", "NARROW", "NARROW", "RESONATOR", "PORT")).evaluate(amb)
    wider = Chain(("INTAKE", "WIDEN", "WIDEN", "RESONATOR", "PORT")).evaluate(amb)
    check("a note born into a narrower bore pulls the tension further down",
          tighter.min_tension < base.min_tension - 0.5,
          f"{base.min_tension:.3f} -> {tighter.min_tension:.3f} bar")
    check("and a wider one pulls it back up",
          wider.min_tension > base.min_tension + 0.2,
          f"{base.min_tension:.3f} -> {wider.min_tension:.3f} bar")
    _report("bare / narrowed / widened",
            f"{base.min_tension:.3f} / {tighter.min_tension:.3f}"
            f" / {wider.min_tension:.3f} bar")
    hit = None
    for k in range(0, 14):
        ks = ("INTAKE", "RESONATOR") + ("NARROW",) * k + ("PORT",)
        if Chain(ks).evaluate(amb).tore:
            hit = k
            break
    check("enough NARROWs will tear it on the note alone", hit is not None,
          "never tore within 13")
    _report("NARROWs needed after one note at 40 m", hit)


# --- 2. the pipe eats the note, and the note decides how fast ---------------


def test_high_notes_die_in_the_pipe_and_low_notes_do_not():
    """The only quantity in the rig that decays along the chain, which is what
    makes distance-from-the-port worth thinking about."""
    amb = ambient_at(40.0)
    out = {}
    for note in ("swell", "groan", "hum", "ping", "chirp"):
        ks = ["INTAKE", ("RESONATOR", note)] + ["WIDEN"] * 4 + ["PORT"]
        out[note] = Chain(ks).evaluate(amb).out_acoustic
    order = ["swell", "groan", "hum", "ping", "chirp"]
    vals = [out[n] for n in order]
    check("every rung up the ladder arrives quieter than the one below",
          all(a > b for a, b in zip(vals, vals[1:])),
          str([f"{n} {out[n]:.0f}" for n in order]))
    check("and a chirp loses most of itself where a swell loses almost none",
          out["chirp"] < out["swell"] * 0.35,
          f"chirp {out['chirp']:.0f} J vs swell {out['swell']:.0f} J")
    for n in order:
        _report(f"{n:6s} through four modules", f"{out[n]:7.0f}",
                f" J   ({pipe_loss(NOTES[n]) * 100:4.1f}% eaten per module)")


def test_what_the_pipe_eats_becomes_heat_and_not_nothing():
    """Attenuation is a conversion, so the energy has to turn up somewhere."""
    amb = ambient_at(40.0)
    long_way = Chain(["INTAKE", ("RESONATOR", "chirp")] + ["WIDEN"] * 5
                     + ["PORT"]).evaluate(amb)
    short_way = Chain(["INTAKE"] + ["WIDEN"] * 5 + [("RESONATOR", "chirp"),
                                                   "PORT"]).evaluate(amb)
    check("the note placed early arrives much quieter",
          long_way.out_acoustic < short_way.out_acoustic * 0.4,
          f"{long_way.out_acoustic:.0f} J vs {short_way.out_acoustic:.0f} J")
    check("and the missing sound is in the water as heat",
          long_way.delta_temp > short_way.delta_temp,
          f"{long_way.delta_temp:+.4f} C vs {short_way.delta_temp:+.4f} C")
    lost = short_way.out_acoustic - long_way.out_acoustic
    gained = (long_way.delta_temp - short_way.delta_temp) * 240.0 * 4186.0
    check("and the two numbers are the same energy",
          abs(lost - gained) < max(1.0, 0.02 * lost),
          f"{lost:.1f} J lost as sound, {gained:.1f} J found as heat")


def test_where_the_note_goes_changes_whether_it_tears_and_what_it_costs():
    """`the lance` in one assertion. Four modules, one moved, and the bill
    changes by two orders of magnitude."""
    # Measured at 400 m rather than at the station, and the depth is not
    # decoration: shallow water tears so easily that both orderings tear and
    # the lesson disappears. The deep case is where one module of pipe is the
    # difference between a machine and a bill.
    amb = ambient_at(400.0)
    late = Chain(("INTAKE",) + ("EXPAND",) * 4
                 + (("RESONATOR", "chirp"), "PORT")).evaluate(amb)
    early = Chain(("INTAKE", ("RESONATOR", "chirp"))
                  + ("EXPAND",) * 4 + ("PORT",)).evaluate(amb)
    check("the note placed last tears the water", late.tore)
    check("the same note placed first does not", not early.tore)
    check("and not-quite-tearing is the expensive one",
          early.cost > late.cost * 50,
          f"{late.cost:.3f} vs {early.cost:.3f} units")
    _report("note last", f"{late.cost:8.3f} units, tore")
    _report("note first", f"{early.cost:8.3f} units, did not")
    _report("ratio", f"{early.cost / max(late.cost, 1e-9):.0f}x")


# --- 3. the note reaches modules that are not about sound at all ------------


def test_a_note_feeds_the_compressor():
    """Rectified diffusion: an oscillating field pulls gas out of solution, so
    a RESONATOR in front of a SQUEEZE hands it more working fluid."""
    amb = ambient_at(40.0)
    plain = Chain(("INTAKE", "SQUEEZE", "PORT")).evaluate(amb)
    primed = Chain(("INTAKE", "RESONATOR", "SQUEEZE", "PORT")).evaluate(amb)
    check("a note before a SQUEEZE makes it heat harder",
          primed.delta_temp > plain.delta_temp * 1.3,
          f"{plain.delta_temp:+.2f} C -> {primed.delta_temp:+.2f} C")
    check("and the compressor is doing more work for it, not less",
          primed.ledger.work_in > plain.ledger.work_in,
          f"{plain.ledger.work_in:.0f} J -> {primed.ledger.work_in:.0f} J")
    after = [st for st in primed.stages if st.kind == "RESONATOR"][0]
    check("the working fraction really did grow",
          after.working > primed.stages[0].working,
          f"{primed.stages[0].working:.4f} -> {after.working:.4f}")
    check("and it still cannot exceed its ceiling",
          all(st.working is None or st.working <= MAX_WORKING_FRACTION + 1e-12
              for st in primed.stages))


def test_stripping_the_nuclei_makes_the_water_hard_to_tear():
    """FILTER quietly became a cavitation-proofing module, because Blake's
    threshold is a property of what is IN the water rather than of water."""
    amb = ambient_at(400.0)
    hit = None
    for n in range(0, 10):
        ks = ("INTAKE",) + ("FILTER",) * n + ("EXPAND",) * 5 + ("RESONATOR", "PORT")
        if not Chain(ks).evaluate(amb).tore:
            hit = n
            break
    check("enough FILTERs will stop a chain cavitating", hit is not None,
          "still tearing after 9 filters")
    check("but not one or two of them -- it is a cost, not a switch",
          hit is None or hit >= 3, f"took only {hit}")
    _report("FILTERs needed to run silent at 400 m", hit)


def test_the_collapse_eats_the_sound_that_caused_it():
    """Self-limiting, and it is the real cavitation limit on real projectors:
    an over-driven rig goes quiet and hot instead of getting louder forever."""
    amb = ambient_at(40.0)
    rows = []
    for n in (1, 2, 3, 4, 5, 6):
        ks = ("INTAKE", "PUMP", "PUMP") + ("NARROW",) * n + ("PORT",)
        r = Chain(ks).evaluate(amb)
        rows.append((n, r.out_acoustic, r.tore))
    torn = [(n, a) for n, a, t in rows if t]
    check("past the tear point, more nozzles make it QUIETER",
          len(torn) >= 2 and all(b[1] < a[1] for a, b in zip(torn, torn[1:])),
          str([(n, f"{a:.0f}") for n, a in torn]))
    for n, a, t in rows:
        _report(f"{n} x NARROW", f"{a:8.0f} J" + ("  tore" if t else ""))


def test_cavitating_costs_you_the_jet():
    """Thrust breakdown. The loudest machine in the game is not the fastest,
    and the two are mutually exclusive rather than merely different."""
    from . import couple

    amb = ambient_at(40.0)
    rows = []
    for n in range(0, 6):
        ks = ("INTAKE", "PUMP", "PUMP") + ("NARROW",) * n + ("PORT",)
        r = Chain(ks).evaluate(amb)
        rows.append((n, couple.thrust_from(r), r.tore))
    intact = [t for _, t, tore in rows if not tore]
    check("thrust rises with every nozzle right up to the tear point",
          all(b > a for a, b in zip(intact, intact[1:])),
          str([f"{t:.0f}" for t in intact]))
    check("and falls to nothing the moment it tears",
          all(t < 1e-6 for _, t, tore in rows if tore),
          str([f"{t:.0f}" for _, t, tore in rows if tore]))
    for n, t, tore in rows:
        _report(f"{n} x NARROW", f"{t:8.0f} N" + ("   TORE" if tore else ""))


def main():
    print("=" * 72)
    print("RIGS -- is sound load-bearing, or is it decoration")
    print("=" * 72)
    print("\n[1] sound is a pressure")
    test_a_note_lowers_the_tension_without_lowering_the_pressure()
    test_a_note_is_worth_two_or_three_expansions_at_every_depth()
    test_narrowing_focuses_a_note_and_widening_spreads_it()
    print("\n[2] the pipe eats the note, and the note decides how fast")
    test_high_notes_die_in_the_pipe_and_low_notes_do_not()
    test_what_the_pipe_eats_becomes_heat_and_not_nothing()
    test_where_the_note_goes_changes_whether_it_tears_and_what_it_costs()
    print("\n[3] the note reaches modules that are not about sound")
    test_a_note_feeds_the_compressor()
    test_stripping_the_nuclei_makes_the_water_hard_to_tear()
    test_the_collapse_eats_the_sound_that_caused_it()
    test_cavitating_costs_you_the_jet()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
