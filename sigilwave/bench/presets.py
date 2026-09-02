"""Machines that already work, for taking apart. SUBMERGED.md 4, 5, 6, 7.4a.

The player's complaint, verbatim: *"the drawing is too strange for me, I can't
figure out what or how to draw. I tried making random things, they didn't
work -- which is good -- but you can't figure it out right now, maybe by
random chance."*

Both halves of that are correct. Random drawings failing is 2.2 working as
designed: a system where every input succeeds is a system where no input is
informative. But 2.2 only says failure must be *possible*; it does not supply
the thing that makes failure *readable*, which is a known-good machine
standing next to the broken one. Noita never explains a wand. It hands you
one it built, lets you fire it, and lets you pull a spell out of it and watch
what changes. That is what this module is: eight machines that demonstrably
do what they claim, each with one sentence of what, two or three of why, and
-- the part that actually teaches -- **one thing to change and what will
happen when you do.**

Every claim in here is measured by `selftest_presets`, and the rule while
building it was that a preset which cannot earn its description gets its
description changed or gets cut. A library of machines that do not do what
they say is worse than no library, because the player learns wrong rules from
a source they were told to trust.


WHAT THE MEASURING CHANGED
--------------------------
Four things came back different from how they were first written, and all
four are recorded rather than quietly fixed, because the correction is the
interesting part in each case.

**A lone run has two mouths, not one.** "The tapper: one run, one mouth" is
not buildable. A run is a line, a line has two ends, and 4 says a free end is
a mouth -- so the end you drive is a mouth as well, and it radiates. Measured,
a bare run driven at one end puts *more* energy out of the feed end than out
of the far one. The only tree shape with a single mouth is a loop with one
tail, which is 6's flywheel and not a first lesson. So the tapper keeps its
job -- the simplest thing that emits -- and its sentence tells the truth about
the second mouth, which turns out to be the better lesson anyway: it is why
every other preset here feeds from a **fork** instead of from an end.

**A wide aperture has to be a fork, not a comb off a spine.** Both build the
same row of mouths. Only the fork hides its feed end (a junction of three or
more runs is not a free end), and `Assembly.describe` can name a fork in one
sentence, where a spine of ribs runs past its twelve-edge limit and comes back
"a tangle" -- which 9.6 says is the system having already failed.

**The horn is buildable, but only just, and only at the top of the ladder.**
7.4a: an aperture under about two wavelengths across cannot be aimed at all.
At a whistle's 40 px wavelength the widest arc that still survives every other
constraint is 91 px -- **2.27 wavelengths**, with the drawn cupping running
1.75x the diffraction it has to beat. There is no headroom above that: it is
wider mouths that would help and the merge rule (5) forbids them past 46 px
apart, so a wider array is a *deeper* array and a deeper array stops being
nameable. That the horn barely exists is the correct outcome. 7.4b already
concluded the sniper is endgame; this is the same conclusion arriving from
the bench side, and a horn drawn at any lower note would be a point source
wearing a horn's name.

**The flywheel's contrast is bigger than the doc's 18x.** With no pickup run
loading the ring, a gapped feed builds **32x** higher than a joined one and
fires the gate where the joined version never does. That is the single best
"understanding pays" moment available, because the naive move -- connect it
properly -- is the one that fails.


HOW A PRESET IS DRIVEN
----------------------
`drive_hz` is the note in the WATER, which is what a player means by a note;
`Rig.drive` converts it down through `WATER_FREQ_RATIO` to the bench's own
clock. `drive_amp` is the source amplitude at the feed, which `Rig.feed_node`
takes to be the leftmost node -- so every machine here is laid out feed-left,
mouths-right, and the fork-fed ones put a junction at the far left on purpose
so that nothing leaks backwards out of the point you are driving.

All coordinates are BENCH pixels (7.4: one bench pixel is one centimetre) and
everything fits inside the 340 x 760 bench panel with a margin.
"""

import math

import pygame

from .mouths import MERGE_DIST, merge_mouths
from .parts import Assembly, snap_radius

V = pygame.Vector2

PANEL_W, PANEL_H = 340.0, 760.0
MARGIN = 20.0
AXIS_Y = 380.0                  # the horizontal the machines are built about

# The loop every timer here uses. A hum is the middle of the drawable ladder:
# big enough that its 320 px circumference is a comfortable 51 px radius on a
# 340 px panel, small enough that 80 sim samples is a lap you can watch go
# round rather than wait out.
HUM_RADIUS = 320.0 / (2.0 * math.pi)

# Both the flywheel and the ticker use this. 10 px is inside GAP_MAX (30) with
# room to spare, passes 0.159 of what reaches it when closed -- weak enough to
# make a resonator, strong enough that a dumped ring gets out -- and is wide
# enough to read as a space at a glance, which JOIN_EPS at 6 px would not.
FEED_GAP = 10.0


class Preset:
    """One machine, and the three sentences that make it teach something.

    `why` is allowed section numbers because it is the bridge back into the
    design doc. `summary` and `try_this` are not: they are the two lines a
    player reads while looking at the drawing, and a section number in either
    of them is the tuner and the readout coming back in through the side door
    (9.3).
    """

    __slots__ = ("name", "summary", "why", "try_this", "build", "drive_hz",
                 "drive_amp")

    def __init__(self, name, summary, why, try_this, build, drive_hz,
                 drive_amp):
        self.name = name
        self.summary = summary
        self.why = why
        self.try_this = try_this
        self.build = build
        self.drive_hz = float(drive_hz)
        self.drive_amp = float(drive_amp)

    def assemble(self) -> Assembly:
        asm = Assembly()
        self.build(asm)
        return asm

    def __repr__(self) -> str:
        return f"<Preset {self.name!r} {self.drive_hz:.0f} Hz>"


# --------------------------------------------------------------- geometry


def _fan(asm, n, spacing, bow=0.0, feed_x=40.0, tip_x=290.0, axis=AXIS_Y):
    """`n` runs out of one shared point, ending in a row `spacing` apart.

    The shared point is the whole trick. With three or more runs meeting there
    it is a FORK -- degree 3 or more, which 4 says is a junction -- and a
    junction is not a free end, so the machine has no mouth on its feed side
    and nothing leaks backwards out of the node being driven. It is also the
    leftmost node, which is where `Rig.feed_node` attaches a source.

    `bow` is the sagitta of the tip row in pixels: how far the middle of the
    row sits ahead of its ends. Positive bulges into the water (a wash),
    negative cups away from it (a sniper), zero is straight (a carry). It is
    one number rather than two because 5.1 is explicit that curvature must be
    derived from the same gesture as width -- the two are not independent in
    the physics and must not be independent in the drawing.

    Spacing must stay under `MERGE_DIST` or the row is not one mouth. That is
    asserted rather than clamped: a preset that silently stopped merging would
    be teaching the opposite of what it claims.
    """
    if spacing > MERGE_DIST:
        raise ValueError(f"{spacing} px apart will not merge (MERGE_DIST {MERGE_DIST})")
    span = (n - 1) * spacing
    for i in range(n):
        u = 0.0 if n == 1 else (2.0 * i / (n - 1)) - 1.0
        asm.add_run((feed_x, axis),
                    (tip_x + bow * (1.0 - u * u), axis - span / 2.0 + i * spacing))


def flywheel_assembly(feed_gap: float = FEED_GAP, pickup_gap: float | None = None,
                      centre_x: float = 170.0, axis: float = AXIS_Y) -> Assembly:
    """A hum ring, fed across a gap, optionally tapped across a second one.

    Exposed rather than hidden inside `build` because the flywheel's entire
    claim is a *comparison* -- gapped against joined -- and the selftest has
    to be able to build the losing version from the same code that builds the
    winning one, or the comparison is two different machines being compared.
    `feed_gap=0` joins the feed run onto the ring, which is the naive move.
    """
    asm = Assembly()
    left = centre_x - HUM_RADIUS
    right = centre_x + HUM_RADIUS
    asm.add_loop((centre_x, axis), HUM_RADIUS, rung=snap_radius(HUM_RADIUS))
    asm.add_run((40.0, axis), (left - feed_gap, axis))
    if pickup_gap is not None:
        asm.add_run((right + pickup_gap, axis), (300.0, axis))
    return asm


# ----------------------------------------------------------------- builds


def _build_tapper(asm):
    _fan(asm, 1, MERGE_DIST, feed_x=60.0, tip_x=230.0)


def _build_fan(asm):
    _fan(asm, 3, 40.0, feed_x=50.0, tip_x=270.0)


def _build_lance(asm):
    _fan(asm, 1, MERGE_DIST, feed_x=40.0, tip_x=300.0)


def _build_carry(asm):
    _fan(asm, 4, 44.0, feed_x=40.0, tip_x=290.0)


def _build_horn(asm):
    # 91 px of aperture, cupped 17.5 px. Every number here is against a wall:
    # wider needs a fifth mouth and loses the name, deeper loses the cupping
    # to the diffraction term, and the runs cannot get much longer before
    # `describe` stops being able to tell them apart. See the module docstring.
    _fan(asm, 3, 42.0, bow=-17.5, feed_x=100.0, tip_x=197.5)


def _build_flywheel(asm):
    for part in flywheel_assembly().parts:
        _copy(asm, part)


def _build_ticker(asm):
    for part in flywheel_assembly(pickup_gap=FEED_GAP).parts:
        _copy(asm, part)


def _build_thruster(asm):
    # 7 mouths, bulged 17.5 px into the water: 8.2's wash, which 8 says is
    # what propulsion wants -- "a wide convex mouth firing behind you is a
    # gentle sustained push". Convex is also the one bow that survives this
    # many runs converging on one fork with every part still nameable.
    _fan(asm, 7, 40.0, bow=17.5, feed_x=40.0, tip_x=287.5)


def _copy(asm, part):
    if part.kind == "run":
        asm.add_run(part.p0, part.p1)
    else:
        asm.add_loop(part.centre, part.rung.radius, rung=part.rung)


# ---------------------------------------------------------------- library


PRESETS = [
    Preset(
        name="the tapper",
        summary="One line. Drive one end, and sound leaves the other.",
        why=(
            "The smallest thing that emits at all. A run carries a signal and"
            " a free end throws it into the water, and that is the entire"
            " machine (SS4). It is also the one place the second rule is"
            " unavoidable: a line has two free ends, so the end you drive is a"
            " mouth too, and measurably more comes out of the back than out of"
            " the front. Every other preset here feeds from a junction"
            " instead, and this is why."
        ),
        try_this=(
            "Draw the line twice as long. The tap arrives later and quieter --"
            " delay is the only thing a line does, and you can see it happen."
        ),
        build=_build_tapper,
        drive_hz=937.0,
        drive_amp=0.5,
    ),
    Preset(
        name="the fan",
        summary="Three lines out of one point, ending close together: one wide mouth, not three.",
        why=(
            "SS5's merge rule. Mouths within 46 px of each other stop being"
            " separate outputs and become a single arc drawn between them, so"
            " three ends 40 px apart are one 80 px mouth. The shared point at"
            " the left is a fork, and a fork is not a free end, so unlike the"
            " tapper nothing leaks out the back."
        ),
        try_this=(
            "Drag the three ends further apart until they are more than a"
            " mouth's width from each other. They snap back into three"
            " separate narrow mouths, and the one wide beam becomes three"
            " weak sprays."
        ),
        build=_build_fan,
        drive_hz=937.0,
        drive_amp=0.55,
    ),
    Preset(
        name="the lance",
        summary="One narrow mouth at a high note: brutal at arm's length, gone by a body length.",
        why=(
            "All the energy in almost no width, so intensity at birth is as"
            " high as it goes (SS5). It buys that with two losses. A narrow"
            " aperture diffracts -- SS5.1 -- so it sprays instead of aiming,"
            " and a high note is eaten by the water fast (SS7.4b), so what is"
            " left at range is nothing. The drawing is the same line as the"
            " tapper. Only the note is different, and the note is half of what"
            " a machine is."
        ),
        try_this=(
            "Drive it at a low note instead of a high one. The same line"
            " suddenly reaches -- low notes carry, high notes die close."
        ),
        build=_build_lance,
        drive_hz=3750.0,
        drive_amp=0.8,
    ),
    Preset(
        name="the carry",
        summary="Four merged mouths at a low note: soft where it starts, still there at the far wall.",
        why=(
            "The other end of SS5.1's trade. The same energy spread over 132 px"
            " of mouth is far weaker at birth than the lance's, but a wide"
            " aperture holds its beam together instead of diffracting away,"
            " and a low note is barely absorbed on the way. Width and note are"
            " pulling the same direction here, which is why it reaches."
        ),
        try_this=(
            "Drive it at a high note instead. Nothing about the drawing"
            " changes and the far wall goes quiet -- the note was doing half"
            " the work."
        ),
        build=_build_carry,
        drive_hz=234.0,
        drive_amp=0.8,
    ),
    Preset(
        name="the horn",
        summary="A cupped mouth at the highest note: soft everywhere except where it converges.",
        why=(
            "SS7.4a's rule and its price. A cupped arc births a front that"
            " converges at one distance, but an aperture narrower than about"
            " two of its own wavelengths cannot be aimed at all -- the"
            " diffraction spreading swamps whatever cupping was drawn. This"
            " mouth is 91 px across and a whistle's wavelength is 40 px, so it"
            " clears the rule by a quarter and no more. That is why the horn"
            " is the smallest drawing here and still the fussiest: focus is"
            " only available at the top of the note ladder."
        ),
        try_this=(
            "Drive the same cup at a low note. It stops focusing entirely and"
            " goes back to being a plain spray -- the cup you drew is smaller"
            " than the wave coming out of it, so the wave never sees it."
        ),
        build=_build_horn,
        drive_hz=3750.0,
        drive_amp=0.8,
    ),
    Preset(
        name="the flywheel",
        summary="A ring that does not touch its feed charges thirty times higher than one that does.",
        why=(
            "The gap is the whole machine. Join a run onto a ring and the run"
            " is an open port: energy leaves the way it came and the ring"
            " never fills. Leave it 10 px short and the ring is coupled"
            " weakly, which is the definition of a resonator -- the same drive"
            " builds and builds until it is strong enough to tear the water"
            " open (SS4.1). Measured, gapped peaks at 32x the joined version"
            " and trips the gate where joined never does."
        ),
        try_this=(
            "Close the gap. Drag the feed line until it touches the ring, the"
            " way it looks like it ought to be. The ring stops charging"
            " altogether -- the obvious repair is the thing that breaks it."
        ),
        build=_build_flywheel,
        drive_hz=469.0,
        # Calibrated, not guessed. At 0.10 the ring charges to 0.156 against a
        # breakdown threshold of 0.34, so the machine whose entire claim is
        # "it charges" measurably did not. At 0.35 it reaches 1.90 and the
        # gapped-versus-joined ratio settles around 5x.
        drive_amp=0.35,
    ),
    Preset(
        name="the ticker",
        summary="A charged ring with a second gap to fire through: it tears the water open again and again.",
        why=(
            "The flywheel plus a pickup, which is SS6's LOOP + GAP line and"
            " SS4.1's trigger. The ring charges past the point where water"
            " holds together, the gap breaks down and conducts, the ring dumps"
            " through it into the far mouth, and the whole thing starts over."
            " Two parts and no new rule produce the first thing in the game"
            " that DECIDES rather than filters. It repeats, but it is not yet"
            " a clock: the interval is set by where the drive happens to cross"
            " the threshold, so it is uneven."
        ),
        try_this=(
            "Widen the pickup gap a few pixels at a time. Each step passes"
            " less, and past about 30 px the ring charges and dumps into"
            " nothing -- a trigger with no output."
        ),
        build=_build_ticker,
        drive_hz=469.0,
        drive_amp=0.35,
    ),
    Preset(
        name="the thruster",
        summary="A wide bulged mouth at a low note and full power: a shove, not a beam.",
        why=(
            "SS8's FORCE verb -- low frequency at high amplitude is a pressure"
            " shove, and you go the other way. A convex arc spreads"
            " immediately and deliberately (SS5.1's wash), which is what a"
            " push wants and a weapon does not: no reach, no aim, all of it"
            " dumped into the water right behind you. Point the mouth where"
            " you came from."
        ),
        try_this=(
            "Cup the row the other way instead of bulging it. The push"
            " collapses into a thin hard beam a long way in front of you,"
            " which shoves nothing."
        ),
        build=_build_thruster,
        drive_hz=234.0,
        drive_amp=0.9,
    ),
]

_BY_NAME = {p.name: p for p in PRESETS}


def get(name: str) -> Preset:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise KeyError(f"no preset named {name!r}; have {sorted(_BY_NAME)}") from None


def build(name) -> Assembly:
    """The named machine, placed and ready to compile."""
    preset = name if isinstance(name, Preset) else get(name)
    return preset.assemble()


def preview_points(preset, box) -> dict:
    """The machine's geometry, scaled to fit `box`, for drawing a thumbnail.

    `box` is anything shaped like (x, y, w, h), a `pygame.Rect` included. The
    fit is uniform and centred, because a preset stretched to fill a card
    would be showing the player a curvature and a spacing it does not have --
    and both of those are the things it is trying to teach (SS5.1).

    Returns the placed geometry and the emergent parts separately, since a
    thumbnail wants to draw a mouth differently from a wire. Everything comes
    off one `Assembly`, so the picture on the card and the physics behind the
    card are the same object.
    """
    preset = preset if isinstance(preset, Preset) else get(preset)
    asm = preset.assemble()
    parts = [[(p.x, p.y) for p in part.points()] for part in asm.parts]

    xs = [x for poly in parts for x, _y in poly]
    ys = [y for poly in parts for _x, y in poly]
    if not xs:
        return {"name": preset.name, "parts": [], "mouths": [], "forks": [],
                "gaps": [], "apertures": [], "scale": 1.0, "offset": (0.0, 0.0)}

    bx, by, bw, bh = (box.x, box.y, box.width, box.height) if hasattr(box, "width") else box
    w = max(max(xs) - min(xs), 1e-6)
    h = max(max(ys) - min(ys), 1e-6)
    scale = min(bw / w, bh / h)
    ox = bx + (bw - w * scale) * 0.5 - min(xs) * scale
    oy = by + (bh - h * scale) * 0.5 - min(ys) * scale

    def to_box(p):
        x, y = (p.x, p.y) if hasattr(p, "x") else p
        return (x * scale + ox, y * scale + oy)

    return {
        "name": preset.name,
        "parts": [[to_box(p) for p in poly] for poly in parts],
        "mouths": [to_box(p) for p in asm.mouths()],
        "forks": [to_box(p) for p in asm.forks()],
        "gaps": [(to_box(a), to_box(b), g * scale) for a, b, g in asm.gaps()],
        "apertures": [
            {"centre": to_box(g.centre), "span": g.span * scale,
             "shape": g.shape(), "mouths": len(g.node_ids),
             "outward": (g.outward.x, g.outward.y)}
            for g in merge_mouths(asm)
        ],
        "scale": scale,
        "offset": (ox, oy),
    }
