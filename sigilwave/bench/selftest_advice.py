"""Does the bench answer "why did that not work"? SUBMERGED.md 3.2 and 9.5.

    python -m sigilwave.bench.selftest_advice

Two halves, and the second is the one that matters.

The first half builds a machine with each known failure in it and checks the
right sentence comes back. That is the easy half: a diagnostic that fires on
the thing it was written for is the least you can ask of it.

The second half builds machines that are **fine** and checks that nothing
cries wolf. A warning on a healthy drawing is worse than no warning at all --
it teaches a rule that is not true, and 2.2's whole argument is that a player
learns from which inputs fail. If a good machine draws a red note, the player
learns to distrust the notes, and then the module is decoration with a cost.
So every failure case here is paired with a control that must stay quiet.

Following `selftest_bench` rather than `sim/selftest`: a failure does not
raise, because "which of the notes is a lie" is the output and stopping at the
first one hides the rest. And every check prints the sentence it is testing,
because the sentences *are* the product -- a bare PASS would not show that a
note had degenerated into the readout 9.3 forbids.
"""

import math

from ..sim.network import raised_cosine_burst
from .advice import Note, diagnose
from .cavitation import BLAKE_SURFACE, Cavitation
from .mouths import MERGE_DIST, Emitter
from .parts import LOOP_LADDER, MIN_RUN_LENGTH, Assembly

RANK = {"dead": 0, "wasteful": 1, "fine": 2, "good": 3}

CHIRP = LOOP_LADDER[4]   # 80 px round, so 160 px of mouth aims it
HUM = LOOP_LADDER[2]     # 320 px round, so 640 px of mouth aims it

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


def say(notes, severity=None):
    """Print what the player would be told, which is the thing under test."""
    for n in notes:
        if severity is None or n.severity == severity:
            note(f"  [{n.severity}] {n.text}")


def find(notes, severity, *words):
    """The first note of this severity containing all these words, or None."""
    for n in notes:
        if n.severity == severity and all(w in n.text for w in words):
            return n
    return None


# ------------------------------------------------------------- machines


def a_run(length=300.0, y=400.0):
    a = Assembly()
    a.add_run((100.0, y), (100.0 + length, y))
    return a


def a_ring(rung=HUM):
    a = Assembly()
    a.add_loop((600.0, 400.0), rung.radius)
    return a


def two_runs(gap):
    a = Assembly()
    a.add_run((100.0, 400.0), (400.0, 400.0))
    a.add_run((400.0 + gap, 400.0), (700.0, 400.0))
    return a


def loop_rig(feed_gap):
    """The rig `selftest_cavitation` measured: a hum loop with a feed run on
    one side and an output run on the other. `feed_gap` 0 joins the feed onto
    the ring; 10 leaves it a gap away."""
    a = Assembly()
    a.add_loop((400.0, 300.0), 50.9)
    a.add_run((100.0, 300.0), (349.1 - feed_gap, 300.0))
    a.add_run((461.0, 300.0), (700.0, 300.0))
    return a


def fork_chain(splits, seg=120.0):
    """A spine with a stub hanging off it at each junction, so a pulse
    crossing from one end to the other must pass every one of them."""
    a = Assembly()
    x = 100.0
    for i in range(splits + 1):
        a.add_run((x, 400.0), (x + seg, 400.0))
        if i < splits:
            a.add_run((x + seg, 400.0), (x + seg, 400.0 + seg))
        x += seg
    return a


def fan(n, spacing, rung=None, fork=(350.0, 400.0), nose=600.0):
    """A fork opening into `n` branches whose free ends sit in a straight
    column - a flat aperture, the carry of 5.1. With a rung, a loop is gapped
    onto the feed so the machine has a note to be judged against."""
    a = Assembly()
    if rung is not None:
        a.add_loop((200.0, 400.0), rung.radius)
        a.add_run((200.0 + rung.radius + 10.0, 400.0), fork)
    else:
        a.add_run((150.0, 400.0), fork)
    span = (n - 1) * spacing
    for i in range(n):
        a.add_run(fork, (nose, 400.0 - span / 2.0 + i * spacing))
    return a


def arc(n, spacing, radius, rung=CHIRP, fork=(350.0, 400.0), nose=600.0):
    """The same fan, cupped onto a circle of this radius - the sniper of 5.1.
    Placing the ends on a real arc rather than bowing a straight row keeps the
    spacing along the aperture even, which is what decides whether they merge
    into one mouth or break into several."""
    a = Assembly()
    a.add_loop((200.0, 400.0), rung.radius)
    a.add_run((200.0 + rung.radius + 10.0, 400.0), fork)
    focus_x = nose + radius
    dphi = spacing / radius
    for i in range(n):
        phi = (i - (n - 1) / 2.0) * dphi
        a.add_run(fork, (focus_x - radius * math.cos(phi),
                         400.0 - radius * math.sin(phi)))
    return a


# ---------------------------------------------------------- measurements


def radiated(assembly, steps=4000, amplitude=1.0):
    """What actually leaves this machine for the water, from one burst."""
    net = assembly.compile(max_energy=None)
    feed = sorted(net.nodes)[0]
    for sample in raised_cosine_burst(8, amplitude):
        net.step({feed: sample})
    return sum(net.step() for _ in range(steps))


def loop_peak(assembly, steps=2500, drive=0.10, lap=80.0):
    """Drive the machine at its loop's own note and watch how high the wires
    get. This is `selftest_cavitation`'s LOOP + GAP measurement, shortened:
    the joined feed is an open port and never charges, the gapped one builds
    until the water tears."""
    net = assembly.compile()
    cav = Cavitation(net)
    peak = 0.0
    for i in range(steps):
        cav.step()
        net.step({0: drive * math.sin(2.0 * math.pi * i / lap)})
        if i > 200:
            peak = max(peak, max(e.total_energy() for e in net.edges.values()))
    return peak, cav.fired()


# ------------------------------------------------------------ the checks


def test_nothing_will_happen():
    print("\n--- dead: nothing will happen at all")

    notes = diagnose(Assembly())
    say(notes)
    check(len(notes) == 1 and notes[0].severity == "dead",
          "an empty bench says one thing, not nothing")
    check("run" in notes[0].text and "free" in notes[0].text,
          "and what it says is what to do next, not that there is a problem")

    ring = a_ring()
    left = radiated(ring)
    notes = diagnose(ring)
    say(notes, "dead")
    note(f"a closed ring radiates {left:.1f} over 4000 steps - exactly nothing")
    check(left == 0.0, "the measurement the note rests on: a ring with no free"
                       " end radiates exactly 0.0")
    check(find(notes, "dead", "free end") is not None,
          "and a drawing with no mouth is told so, in those words")

    a = a_run()
    a.add_run((100.0, 700.0), (400.0, 700.0))
    notes = diagnose(a)
    say(notes, "dead")
    check(find(notes, "dead", "not touching anything else") is not None,
          "a piece joined to nothing and gapped to nothing is dead weight")

    a = a_run()
    a.add_run((600.0, 600.0), (600.0 + MIN_RUN_LENGTH / 2.0, 600.0))
    notes = diagnose(a)
    say(notes, "dead")
    check(find(notes, "dead", "too short") is not None,
          f"a part under {MIN_RUN_LENGTH:.0f} px never compiles, and is not"
          f" left silently on the canvas")


def test_it_works_but_it_bleeds():
    print("\n--- wasteful: it works, and it is throwing energy away")

    joined_peak, joined_fires = loop_peak(loop_rig(0.0))
    gapped_peak, gapped_fires = loop_peak(loop_rig(10.0))
    note(f"feed joined: wires peak at {joined_peak:.4f}, gate fired {joined_fires}")
    note(f"feed gapped: wires peak at {gapped_peak:.4f}, gate fired {gapped_fires}"
         f"  (threshold {BLAKE_SURFACE:.2f})")
    check(gapped_peak > joined_peak * 5.0 and joined_fires == 0,
          "the measurement the highest-value note rests on: joined to its feed"
          " a loop never charges, gapped off it the same drive builds and fires")

    notes = diagnose(loop_rig(0.0))
    say(notes, "wasteful")
    hit = find(notes, "wasteful", "wired straight to its feed")
    check(hit is not None, "a loop wired to its feed is told exactly that")
    check(hit is not None and "leave a small gap" in hit.text,
          "and told what to do instead, in one sentence")
    check(hit is not None and notes[0] is hit,
          "and it is the first thing said, because it is the difference"
          " between a machine that charges and one that does not")

    notes = diagnose(fork_chain(3))
    say(notes, "wasteful")
    check(find(notes, "wasteful", "splits") is not None,
          "a chain of splits is told how little survives it")

    notes = diagnose(two_runs(25.0))
    say(notes, "wasteful")
    check(find(notes, "wasteful", "gap") is not None,
          "a gap left wider than it needs to be is told how much it is costing")

    notes = diagnose(a_run(2000.0))
    say(notes, "wasteful")
    check(find(notes, "wasteful", "survives the trip") is not None,
          "a very long run is told that length is not free")


def test_it_emits_but_not_how_you_think():
    print("\n--- shape: it reaches the water, but not in the shape you drew")

    narrow = fan(5, 40.0, rung=HUM)
    notes = diagnose(narrow)
    say(notes, "fine")
    hit = find(notes, "fine", "to aim")
    check(hit is not None,
          "a mouth under two wavelengths wide is told it cannot be aimed")
    check(hit is not None and "twice as wide as the loop" in hit.text,
          "and the rule is stated in the units the player already has -"
          " the mouth must be about twice as wide as the loop that made it")

    notes = diagnose(arc(9, 40.0, 600.0))
    say(notes, "fine")
    check(find(notes, "fine", "come to a point") is not None,
          "a cup too shallow to focus inside the tank is told where it does"
          " converge, not just that it is wrong")

    notes = diagnose(fan(2, MERGE_DIST + 9.0))
    say(notes, "fine")
    check(find(notes, "fine", "merge into one wider mouth") is not None,
          f"two mouths that missed merging by a hair are told the distance"
          f" ({MERGE_DIST:.0f} px) rather than left as two lances")


def test_it_tells_you_when_you_got_it_right():
    print("\n--- good: success has to be as legible as failure")

    notes = diagnose(loop_rig(10.0))
    say(notes, "good")
    check(find(notes, "good", "gapped off its feed") is not None,
          "a loop gapped off its feed is told it will charge")
    check(find(notes, "good", "sits right on the loop") is not None,
          "and a gap the charged loop can trip is named as the trigger it is")

    notes = diagnose(fan(5, 40.0, rung=CHIRP))
    say(notes, "good")
    check(find(notes, "good", "wide enough to point") is not None,
          "a mouth twice as wide as its loop is told it can be aimed")

    notes = diagnose(arc(9, 40.0, 300.0))
    say(notes, "good")
    check(find(notes, "good", "point about") is not None,
          "and a cup that focuses inside the tank is told how far out it does")

    for label, machine in (("a plain run", a_run()),
                           ("a loop gapped off its feed", loop_rig(10.0)),
                           ("an aimable mouth", fan(5, 40.0, rung=CHIRP))):
        notes = diagnose(machine)
        check(any(n.severity == "good" for n in notes),
              f"{label} is told something it got right")


def test_it_does_not_cry_wolf():
    print("\n--- and the half that matters: healthy machines stay quiet")

    healthy = [
        ("one plain run, both ends free", a_run()),
        ("a long run, still inside the length that pays", a_run(600.0)),
        ("two runs gapped at 12 px", two_runs(12.0)),
        ("a fork into three arms", fork_chain(1)),
        ("two forks, which is not yet a chain", fork_chain(2)),
        ("a loop gapped off its feed", loop_rig(10.0)),
        ("a five-mouth arc on a chirp loop", fan(5, 40.0, rung=CHIRP)),
        ("a nine-mouth cup that focuses in the tank", arc(9, 40.0, 300.0)),
        ("two mouths close enough to merge", fan(2, 40.0)),
    ]
    for label, machine in healthy:
        notes = diagnose(machine)
        loud = [n for n in notes if n.severity in ("dead", "wasteful")]
        for n in loud:
            note(f"  cried wolf: [{n.severity}] {n.text}")
        check(not loud, f"{label}: nothing dead and nothing wasteful")

    quiet_pairs = [
        ("a 12 px gap", two_runs(12.0), "gap"),
        ("two forks", fork_chain(2), "splits"),
        ("a 600 px run", a_run(600.0), "survives the trip"),
        ("a loop gapped off its feed", loop_rig(10.0), "wired straight"),
    ]
    for label, machine, phrase in quiet_pairs:
        notes = diagnose(machine)
        check(find(notes, "wasteful", phrase) is None,
              f"{label} does not draw the warning its unhealthy twin does")

    notes = diagnose(fan(5, 40.0, rung=CHIRP))
    check(find(notes, "fine", "to aim") is None,
          "a mouth that IS wide enough is not told it is too narrow")
    notes = diagnose(fan(2, 40.0))
    check(find(notes, "fine", "merge into one wider mouth") is None,
          "two mouths that DID merge are not told to move closer")
    notes = diagnose(a_run())
    check(find(notes, "fine", "to aim") is None,
          "a lone mouth is not scolded for being a lone mouth - a spitter is"
          " a tool, not a mistake")


def test_the_worst_thing_is_said_first():
    print("\n--- ordering: the most important thing first, every time")

    machines = [Assembly(), a_run(), a_ring(), loop_rig(0.0), loop_rig(10.0),
                fork_chain(3), two_runs(25.0), a_run(2000.0),
                fan(5, 40.0, rung=HUM), arc(9, 40.0, 300.0), arc(9, 40.0, 600.0)]
    ordered = True
    for machine in machines:
        ranks = [RANK.get(n.severity, 9) for n in diagnose(machine)]
        ordered = ordered and ranks == sorted(ranks)
    check(ordered, "every machine's notes come back most severe first")

    a = a_ring()
    a.add_run((100.0, 700.0), (100.0 + MIN_RUN_LENGTH / 2.0, 700.0))
    notes = diagnose(a)
    say(notes)
    check(notes and notes[0].severity == "dead",
          "a machine that is both dead and untidy leads with the death")

    check(all(isinstance(n, Note) and n.severity in RANK and n.text
              for n in diagnose(loop_rig(0.0))),
          "and every note is a severity, a sentence and somewhere to point")


def test_the_sentences_are_sentences():
    print("\n--- 9.3: no property readable only from a number")

    seen = []
    for machine in (Assembly(), a_ring(), loop_rig(0.0), loop_rig(10.0),
                    fork_chain(3), two_runs(25.0), a_run(2000.0),
                    fan(5, 40.0, rung=HUM), arc(9, 40.0, 300.0),
                    arc(9, 40.0, 600.0), fan(2, MERGE_DIST + 9.0)):
        seen.extend(diagnose(machine))
    note(f"{len(seen)} notes across eleven machines")

    banned = ("§", "coefficient", "kappa", "admittance", "impedance",
              "coupler", "curvature", "amplitude", "sample")
    offenders = [n.text for n in seen if any(w in n.text for w in banned)]
    for text in offenders:
        note(f"  jargon: {text}")
    check(not offenders, "no note reaches for a word out of the physics")

    units = ("px", "%", "times", "part in", "Hz")
    numeric = [n.text for n in seen if any(c.isdigit() for c in n.text)]
    bare = [t for t in numeric if not any(u in t for u in units)]
    for text in bare:
        note(f"  bare number: {text}")
    check(not bare,
          f"every number that appears is a quantity the player can act on -"
          f" {len(numeric)} of {len(seen)} notes carry one, all of them with"
          f" something to do about it")
    check(all(len(n.text) < 260 for n in seen),
          "and says it in one sentence a person would actually say")


def test_it_can_read_a_machine_that_has_been_fired():
    print("\n--- the note a machine is really making beats a guess at it")

    machine = fan(5, 40.0, rung=CHIRP)
    net = machine.compile()
    em = Emitter(machine, net)
    feed = sorted(nid for nid, _ in machine.mouth_nodes())[0]
    burst = raised_cosine_burst(6, amplitude=1.0)
    for i in range(600):
        net.step({feed: burst[i]} if i < len(burst) else None)
        em.step()
    heard = [g.history[-1][2] for g in em.groups if g.history]
    note(f"the emitter measured {len(heard)} aperture(s) radiating"
         f"{'' if not heard else ' at ' + ', '.join(f'{f:.0f} Hz' for f in heard)}")

    notes = diagnose(machine, network=net, emitter=em)
    say(notes)
    check(any(n.severity == "good" for n in notes),
          "a fired machine still reads, and still says what it got right")
    check(not [n for n in notes if n.severity in ("dead", "wasteful")],
          "and firing it does not invent a fault that was not there")

    forced = diagnose(machine, note_hz=117.0)
    check(find(forced, "fine", "to aim") is not None,
          "and told to aim a swell instead, the same mouth is correctly"
          " reported as far too narrow for it")


def main():
    for test in (test_nothing_will_happen,
                 test_it_works_but_it_bleeds,
                 test_it_emits_but_not_how_you_think,
                 test_it_tells_you_when_you_got_it_right,
                 test_it_does_not_cry_wolf,
                 test_the_worst_thing_is_said_first,
                 test_the_sentences_are_sentences,
                 test_it_can_read_a_machine_that_has_been_fired):
        test()

    print(f"\n{_passed} passed, {_failed} failed.")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
