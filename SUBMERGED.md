# SUBMERGED — the third design

`sigil-wave-design.md` specifies a simulation. `GAME_DESIGN.md` specifies
WAVEWRIGHT. `CAMPANARY.md` specifies the second game and an honest
post-mortem of the first. This document specifies the third, and records the
one failure the first two shared.

---

## 1. The one sentence

**Energy is somewhere else. You draw the thing that brings it here, in the
form you need, through water that bends it.**

You do not cast spells. You build transmission.

### 1.1 The view is a cross-section

Side-on, like ONI, like Noita. y increases downward and downward is deeper.

This is not a style choice, it is forced by §7. Every medium system is
vertical: warm water rises, bubbles rise, cold dense water sinks, pressure
climbs with depth, water stratifies into horizontal layers, and the sound
channel is a *depth*. A top-down view makes every one of those invisible and
leaves buoyancy nowhere to go.

It also makes the progression axis literal. Deeper is harder, and deeper is
down.

---

## 2. What was wrong with both previous builds

CAMPANARY correctly diagnosed everything wrong with WAVEWRIGHT and fixed all
of it. It was still not fun. That is the load-bearing fact, so the cause is
something neither post-mortem named.

### 2.1 The drawing was continuous, and continuous systems are unlearnable

ONI is a grid. Noita is a list. Both are **discrete**: you place a *thing*,
the thing has a *name*, the name has a *rule*.

Freehand drawing is continuous. Every degree of freedom maps to a smooth
gradient of behaviour, and a smooth gradient is unlearnable *in principle* —
you can never tell whether a difference is a difference. A slightly bigger
circle felt like nothing because it *was* nothing you could name.

"Water flows down" is learnable because it is one sentence, with no
exceptions, visible every time. The old system contained no sentences.

### 2.2 Everything worked, so nothing taught

Random shapes almost always produced a system that did something. When every
input succeeds, no input is informative, and nothing learned from the last
drawing helps with the next. A system where failure is impossible is a system
where understanding is worthless.

### 2.3 The render showed state, not causality

A drawing lit up with pretty colours. Pretty colours are a picture of *where
energy is*, and what the player needs is *why it went there*. Neither build
ever animated a cause.

### 2.4 The system only did one thing

It was a weapon. So all the depth had to be spent on one verb, the world was
scenery, and every part of the game that was not combat was a menu. A system
that touches one thing can only ever be as interesting as that thing.

### 2.5 Energy came from nowhere

Press the button, a pulse appears. Nothing is scarce, so nothing is a
decision, so efficiency — the only thing understanding can buy — has no
meaning.

---

## 3. Energy

**Energy is never created. It is somewhere, and you move it.**

This single rule is what turns the drawing into a system instead of a spell
list.

### 3.1 Sources

| source | rate | note | where |
|---|---|---|---|
| **Your body** | low | broad | you — **and it burns oxygen** |
| **Vent** | high | low, continuous | fixed, hot, deep |
| **Current** | medium | very low | fixed, moving water |
| **A creature's call** | low, intermittent | that creature's note | wherever it is |
| **A charged loop** | burst | its own note | wherever you built it |

Casting off your own body always works and always costs air. That is the
whole progression curve in one number: **hour one you burn your lungs
casting; hour twenty you are running off a vent three rooms away.** Nobody
has to teach "transmit, do not generate" — the oxygen bar teaches it.

### 3.2 Conservation, and being able to count it

One injection has a visible brightness. It **halves at every fork**, **dims
along every run**, **loses a little per lap** in a loop, and **leaves at a
mouth**. Nothing else happens to it.

That is what makes "why did that not work" answerable by looking. A
forty-junction scribble visibly grinds its pulse to nothing. This is ONI's
mass conservation, and it is the reason a base that floods is diagnosable.

### 3.3 Energy is the currency

Everything costs energy: moving, breathing, digging, seeing, fighting,
keeping the station lit. So every decision in the game is the same kind of
decision, and skill is expressed as one number — **energy per result.**
Understanding becomes literally countable.

---

## 4. The parts

Five. Each has one sentence. Each is visually distinct. Each can be tested
alone. **This list does not grow.**

| part | the one sentence | how you see it |
|---|---|---|
| **RUN** — a line | *A signal takes time to cross. Longer is later.* | the pulse visibly takes longer |
| **LOOP** — a ring | *A signal caught in a loop laps forever. Its lap time is its note.* | **you watch it lap.** Small spins fast, big spins slow |
| **FORK** — a junction | *A signal that hits a split shares itself out between the ways on — and a little bounces back.* | dimmer pulses onward, and an echo returning |
| **GAP** — a coupler | *A gap passes a share of what reaches it, and the wider the gap the smaller the share.* | a dimmer copy appears across the gap |
| **MOUTH** — an open end | *A mouth throws energy into the water, and catches what the water brings.* | the only part that touches the ocean |

### 4.0 Two of these sentences were wrong, and the harness caught them

The five sentences above are the game's promise to the player, so the bench
selftest tests one sentence per check. Two failed against the real
simulation, and both are recorded here rather than quietly corrected,
because *how* they were wrong is the useful part.

**FORK did not split in half.** At a three-way junction each branch takes
0.4444 of the energy, not 0.5, and **0.1111 bounces straight back the way it
came** — which the original sentence did not mention at all. "Half as bright"
is exactly true only at a *four*-way junction. The corrected sentence is
better than the wrong one: a back-reflection is a thing the player can see
and use, and hiding it would have made forks feel lossy for no visible
reason.

**GAP was not a threshold, and could not be made into one.** The sentence
said a signal jumps a gap only if it is strong enough. Measured: the crossing
fraction is **0.227046 at every drive from 0.001 to 1000** — identical to six
significant figures across six decades. The coupler is a linear rotation, so
its threshold sharpness is not "gradual", it is *exactly zero*. It is
precisely the leaky wire 2.1 blames for the last build. Worse, the only
amplitude-dependent element in the simulation — the saturating junction — runs
the wrong way: driving a loop 3000x harder makes **ten times less** cross the
gap past it.

So the sentence is now what a gap truly is: **a clean attenuator controlled by
distance**, with 5500:1 of range across the placeable band (a join delivers
0.893 of the energy, a 6 px gap 0.159, 12 px 0.057, 20 px 0.011, 29.5 px
0.00016). That is legible and it is geometry the player places. What it costs
is 6's **LOOP + GAP timer** — "the loop charges until it can jump" — which has
no mechanism and is struck out until one exists. See 4.1.

### 4.1 The missing gate

The system has no way to say *only if*. Everything is proportional, so
nothing can decide. That is a real hole: without a threshold there is no
trigger, no timer, no sequencing, and the machines the player builds can only
ever be filters and delays, never programs.

The honest place to get one is **cavitation**. Water has a real, sharp
pressure threshold (the Blake threshold) above which it tears open into a
bubble, and the collapse radiates broadband — that is the pistol shrimp in
7.3, already in this document. A gap driven past that threshold would break
down and conduct hard, exactly as "arcs across with a spark" always
described. It is physically honest, it is already in the game's vocabulary,
and it lives in the game layer rather than in `sim/`.

It is not built. Until it is, 4's parts make filters, not programs.

### 4.2 And two laws, which are not parts

An earlier draft listed KNOT and REVERSE as parts. They are not: a knot is a
junction *driven hard*, and reversal is a property a loop *has*. Neither is a
thing you place, and pretending otherwise would have broken rule 9.1 on the
first day. They are universal laws instead, which is the more ONI shape
anyway — every junction obeys them, everywhere.

| law | the one sentence |
|---|---|
| **SATURATION** | *Drive anything past its limit and its note jumps an octave.* |
| **WINDING** | *A loop run backwards pushes instead of pulls.* |

Three things the parts list is doing on purpose:

**GAP is a gate, not a leak.** In the old build a coupler was a leaky wire — a
matter of degree, therefore invisible, therefore indistinguishable from a
direct join. As a **threshold** it is categorical: below the strength the
pulse dies at the edge, above it the pulse jumps with a spark. That one change
turns gaps into logic — charge until strong enough, then fire.

**MOUTH is reciprocal.** It radiates *and* it absorbs. That is real physics
(antenna reciprocity), and it means a loop behind a mouth, tuned to a source,
is a collector. No eighth part needed.

**LOOP is also the battery.** "A signal caught in a loop laps forever"
already says it stores. Storage costs no new rule.

---

## 5. Mouths, merging, and the shape of an output

This is where output stops being a number and becomes geometry.

> **Mouths close enough together merge into one wider mouth: an arc drawn
> between them. The same energy spread over more width hits softer and covers
> more.**

### 5.1 Width does two opposite things, and that is the whole tradeoff

An earlier draft of this table said "one mouth gives a narrow, intense lance
with long reach." That is geometrically singular — a zero-width mouth is a
division by zero — and physically backwards. A narrow aperture **diffracts**:
the smaller the mouth, the *wider* the beam it throws. A point source is
omnidirectional. It is the wide aperture that is directional.

So width is pulling in two directions at once, and neither wins:

| width does this | and also this |
|---|---|
| **wide is softer at birth** — `intensity = energy ÷ width` | **wide is straighter in flight** — a big aperture holds its beam together |
| **narrow is brutal at birth** — all the energy in no width | **narrow sprays** — it diffracts away within a body length |

That is a real tradeoff with no dominant answer, and it produces three
genuinely different tools out of one number:

| you drew | you get | good for |
|---|---|---|
| **one mouth** | a **spitter** — vicious at arm's length, gone by a body length | close work, digging what you are touching |
| **a long merged arc** | a **carry** — soft at birth but coherent, it goes the distance | mapping, relaying, reaching |
| **a long arc, concave** | a **sniper** — soft at birth, converges to brutal at the focal distance | the hardest thing in the game to aim, and the strongest |
| a **convex** arc | a **wash** — spreads immediately, deliberately | propulsion, warming a patch, area work |
| a closed ring of mouths | an **omni pulse** | sonar, panic, area denial |

The sniper is the one that matters. It is soft everywhere except at exactly
one distance, so using it means **knowing how far away the thing is** — which
is the skill this whole game is trying to teach, expressed as a weapon. And in
water whose sound speed varies, the focal distance moves. Measured: a concave
front reaches **402x its launch intensity**, at the geometric focal distance,
and is unremarkable everywhere else.

An output is therefore four facts, all read off the drawing with no numbers:
**width** (arc length), **intensity at birth** (energy ÷ width),
**direction** (arc normal), and **focus** (arc curvature). Curvature should be
derived from span rather than exposed as a second free knob — the two are not
independent in the physics and must not be independent in the drawing.

CAMPANARY *gave* the player the omnidirectional ring. Here it is a thing you
have to build, and it is the least interesting of the five.

### 5.2 The same law governs the ocean

A ping is not a particle and not a circle. It is a **polyline front whose
vertices each advance along their own normal at the local sound speed**, and

> `intensity = energy ÷ front length`

is evaluated locally, per segment, at every moment of flight. That is the
merging rule from above, applied continuously — and it means the mouth
geometry a front is *born* with and everything the water does to it *in
flight* are the same arithmetic.

Three things fall out that nobody has to author:

- **Spreading dims.** The front stretches as it expands, so intensity drops.
  The inverse-square-ish falloff is geometry, not a curve someone tuned.
- **Convergence brightens.** Where the water bends a front back onto itself
  the vertices bunch and intensity climbs *above* its launch value. Those are
  real caustics — bright focal lines in the dark.
- **The medium re-shapes your output.** A lance fired into the wrong water
  arrives as a wall. Learning which water does what to which shape is a large
  part of what there is to learn.

---

## 6. The combinations

The "poison plus fire makes poison gas" list. It is short on purpose.

| | |
|---|---|
| **LOOP + LOOP**, slightly different size | they **beat** — two fast notes make one slow pulse |
| **FORK + two RUNS of different length** | the same pulse **arrives twice**, late and later. Geometry is timing |
| **LOOP + KNOT** | drive it hard, it **climbs an octave** — a frequency converter |
| ~~**LOOP + GAP**~~ | ~~a timer~~ — **struck out**: the gap has no threshold, see 4.1 |
| **LOOP → RUN → itself** | **echo, then howl, then it tears apart** |
| **MOUTH + LOOP tuned to a source** | a **collector** — it drinks that note out of the water |

Every one of these is true every time. None is a recipe the game knows about;
all of them are simply what the parts are.

---

## 7. The medium

The ocean runs the same physics as the drawing. **That unification is what
makes understanding pay** — every rule learned inside a spell is true outside
it.

### 7.1 Six systems, two or three rules each

| system | its entire ruleset |
|---|---|
| **Energy** | travels at `c`, splits at junctions, leaves at mouths, decays. What is absorbed becomes heat |
| **Heat** | diffuses. Raises `c`. Lowers density. Lowers how much gas water can hold |
| **Density** | = f(temperature, salinity, bubbles). Heavy sinks. Water stratifies into layers |
| **Pressure** | rises with depth. Raises `c`. Compresses bubbles. Forces gas into solution |
| **Gas** | bubbles rise. A bubble resonates at a note set by its size. Bubbles eat sound |
| **Frequency** | set by loop length. High dies fast, low carries far |

### 7.2 The interaction matrix

|  | Heat | Density | Pressure | Gas |
|---|---|---|---|---|
| **Energy** | absorbed sound **warms water** | a density boundary **reflects and bends** it | deep water is faster → **pings bend, spells detune** | bubbles **eat sound**; a bubble at your note **rings with you** |
| **Heat** | — | warm rises → **currents** | a warm anomaly's +Δc **offsets the −Δc of cooling with depth** — this is what carves the channel | warm water **sheds dissolved gas** |
| **Density** |  | — | the two fight over stratification | bubbles lighten water → **a rising column** |
| **Pressure** |  |  | — | bubbles **shrink with depth** — their note changes as they rise |

### 7.3 The engine, in one line

**A wavefront bends toward slower water.**

Refraction, shadow zones, acoustic mirrors and sound channels are all
consequences of that. None of them is authored.

- **The mirror.** Drive a mouth into still water → it warms → warm water is
  less dense → a density boundary → sound reflects off it. You built a
  periscope out of warm water, using three rules you already knew.
- **The channel.** Near the surface `c` falls with depth (colder); deep down
  `c` rises with depth (pressure). Somewhere between is a **minimum**, and
  sound bends toward slow water, so a ping laid into that layer cannot leave
  it. Measured on the real field: a front launched on the axis oscillates
  between 405 m and 693 m, turns 23 times, and is **still trapped after
  300 km** — 37x the range of the same ping launched shallow.

  **It is an angle, not a depth.** The propagator was blunt about this and it
  changes the fantasy: the channel traps any ray whose launch angle is inside
  a cone, and a steep ping punches straight through from the axis itself.
  So "find the channel" is not hunting for a magic depth — it is learning to
  **ping shallow**, which is a skill rather than a location. That is strictly
  better: a location is found once and then known forever, whereas an angle is
  a thing you get good at.

  It also constrains §7: the profile **must stay asymmetric** — steeper above
  the axis than below, which is what the real thermocline-versus-pressure
  split gives anyway. Under a symmetric profile every horizontal ping is
  trapped from everywhere, "outside the channel" stops meaning anything, and
  the revelation never lands because there was never a before.
- **The collapse.** Overdrive a loop into runaway, couple it to a bubble at
  its resonant size, and the bubble collapses. That is a pistol shrimp, and it
  is the loudest thing in the ocean.

---

### 7.4 The numbers the game is allowed to choose

CAMPANARY had a tradition worth keeping: name every place the game puts its
thumb on the physics, and measure rather than argue. There are four here, and
everything else is a consequence.

**`GRADIENT_EXAGGERATION` (= 30).** Real sound-speed gradients bend rays over
kilometres; the room is 1200x800 px. The relationships keep their real sign
and structure and only the *magnitude* of the c-variation is multiplied. At
30x a horizontal ray turns on a 193 px radius, so refraction is a thing you
watch happen rather than a thing you infer. This is the one deliberate lie in
the medium and it is stated out loud in `field.py`.

**The frequency mapping.** `sigilwave/sim` counts in samples; the medium
absorbs in Hz; nothing in either connects them. Pinning that mapping is a
game-design decision, not a physics one, because it decides what is reachable:

- Drawable loops span roughly **40 Hz to 4 kHz** — two decades. Over 500 px
  the low end keeps ~99.9% of its amplitude and the high end almost nothing,
  so the range law is dramatic across the range a hand can draw.
- Bubbles resonate between about **0.8 and 30 kHz**, and the size a bubble is
  born at depends on the depth it was shed at: coarse and low-pitched near the
  surface, fine and high-pitched deep.

The overlap is deliberate and partial. **Shallow bubbles are directly
reachable by a drawn loop; deep ones are not, and must be reached by driving a
loop into SATURATION to climb an octave.** So "ring a bubble to amplify
yourself" is a beginner's trick at 100 m and an advanced one at 700 m, and the
difficulty gradient is a consequence of the gas physics rather than a tuning
table. That is the CAMPANARY "SPARROW gates itself" trick, arrived at
honestly.

**`HEAT_PER_ABSORBED_UNIT`.** §7.1 says "what is absorbed becomes heat" and
never says how much. One measured constant, set so that a sustained mouth
builds a usable density boundary in a handful of seconds — the mirror has to
be reachable in the time a player will actually hold a beam.

**`CRACK_NOTE_TOLERANCE`.** How near a body's own note counts as its note.
Deferred until digging exists, and it must be measured against how precisely
the drawing tools can actually place a loop, not chosen.

### 7.5 Known limits, accepted on purpose

- **Buoyancy stalls.** Warm water rises a couple of cells and stops, because
  exchange-based buoyancy dilutes the very inversion driving it. A tall
  coherent plume needs a velocity field, and a velocity field is a second
  fluid simulation nobody can hold in their head. Stratification and the layer
  boundaries the mirror depends on come out correct, which is what §7.3 needs.
- **Nothing pushes a bubble down**, so bubbles shrinking with depth shows up
  as *birth* radius rather than as transport.
- **Buoyancy had to be taught about bubbles.** `density` subtracts a bubble
  term, but the first version of `_buoyancy` exchanged only temperature,
  salinity and gas -- so a bubble cloud made its own cell permanently lighter
  than the water above it and created an inversion that could never resolve.
  The pair ground against each other forever, stirring temperature, warming
  cells, shedding more gas (warm water holds less), making more bubbles.
  Measured: a cloud nobody touched drove a 0.29 C spread to 2.52 C and grew
  itself from 5.4 to 7.1 units. Exchanging bubbles closes the loop and is
  also what "bubbles lighten water -> a rising column" actually means -- the
  cloud now rises 225 px as a coherent column instead of sitting still and
  churning.
- **Warm is measured per depth, not against a snapshot.** Comparing a cell to
  the starting profile conflates heat the player added with the background
  gradient being stirred by convection. The second is real, but it is not a
  warm patch, and drawing it as one made heat look like it smeared and
  drifted on its own. A cell is warm when it is warmer than the rest of the
  water at its own depth.
- **A bench tank has no sound channel.** The thermocline is specified as a
  fraction of depth while pressure is in real metres, so a small tank
  compresses one and not the other. This is correct rather than broken: the
  bench is still water for learning parts, and the channel is a thing you go
  down to find.

---

## 8. Universality — the six verbs

The drawing is not a weapon. A mouth delivers **energy into water at a
frequency, a width, and a direction**, and what that *does* depends on what it
meets. Six verbs fall out. None is a special case.

| the verb | the mechanism | what it is in play |
|---|---|---|
| **HEAT** | absorbed energy warms water | currents, mirrors, sound channels, melting, keeping the station alive |
| **FORCE** | low frequency at high amplitude is a pressure shove | **propulsion** — swimming, dashing, shoving things |
| **SHATTER** | energy at a body's own resonance shakes it apart | **digging** — every rock has a note, found by pinging it |
| **GAS** | driving dissolved gas out of solution, or driving bubbles | **oxygen** — you make your own air with the same drawing |
| **SIGNAL** | creatures hear frequency and pattern | lure, mimic, mask, panic, overwhelm |
| **TRANSFER** | a mouth aimed at a distant collector | **the power grid** — relaying energy across the map |

**Propulsion deserves a note.** Movement is drawn. A wide convex mouth firing
behind you is a gentle sustained push; a point mouth is a kick. The dash that
Hades and Nuclear Throne would hand you as a button is here a thing you
designed — and it spends the same energy budget as everything else, so fleeing
costs what you would have spent fighting.

**Digging deserves a note.** Rock has a note. You ping it, you hear what comes
back, you build the machine that delivers that note, you deliver it. That is
the entire system exercised in one loop, and it is the safest, calmest place
to learn it.

---

### 8.1 Hot pushes sound away. Bubbles pull it in.

Building the stage turned up a pairing nobody designed, and it is the
cleanest example so far of what 7 is for.

| | what it does to `c` | so sound | and it is |
|---|---|---|---|
| **warm water** | speeds it up | **bends away** | a repeller — a shield, a wall you push sound off |
| **bubbles** | slows it down (Wood) | **bends toward** | an attractor — a lens, a trap, a collector |

Two opposite instruments out of the same single verb (deliver energy into
water), each stateable in one sentence with no exceptions. Measured on the
real field: a second of heating gives a 1.28x contrast, and a second of
bubbling gives 1.93x the other way.

And bubbles have a **second** axis for free, because absorption rises with
thickness while the refraction is already strong when thin:

| curtain | does |
|---|---|
| **thin** (~0.2 void fraction) | bends hard, 60% gets through — a **lens** |
| **thick** (saturated) | bends harder, 7% gets through — a **wall** |

So thickness is a knob the player already has, and one system yields three
tools. This is the interaction density the whole design is betting on, and it
cost no new mechanic at all.

### 8.2 Every boundary has a critical angle, and that is the skill

A sound-speed contrast reflects only beyond a critical angle,
`asin(c_slow / c_fast)`:

| contrast | critical angle | reads as |
|---|---|---|
| 1.05x | 72° | a usable mirror |
| 1.2x | 56° | a usable mirror |
| 4x | 14.5° | a wall |
| 3000x | ~0° | sound simply never goes there |

**A mirror only works if you ping shallow.** That is the same skill the sound
channel teaches (7.3), arrived at from the other direction, and the two
reinforce each other rather than being two things to learn.

It also sets a hard design rule: **contrast must stay in the 1.05-1.5x band.**
Past it, every boundary becomes a perfect wall at every angle, the critical
angle stops existing, and the skill it was supposed to teach evaporates. The
first build of the stage got this wrong -- an unbounded heat key reached
3085x and produced exactly that: a region sound refused to enter, with no
readable reason.

### 8.3 Dose, not presence

That bug generalises. Both world-verbs were applied once per *frame* while a
key was held, so a tap did nothing and a tenth of a second did something
absurd. A mechanic whose output has no legible relationship to its input is
unlearnable no matter how good the physics under it is (9.1).

**Every verb that changes the world is a rate per second, and its useful band
must be reachable by about a second of holding.** Heat now plateaus around
1.4x through diffusion, so the player cannot accidentally build a wall;
bubbles climb from lens to wall over about three seconds, deliberately,
because that traversal is a tool.

---

## 9. The legibility rules

Non-negotiable, because breaking them is what killed the last two builds.

1. **Every part has one sentence and no exceptions.** If a part needs a
   paragraph, it is two parts, or it is cut.
2. **Nothing ambiguous in the middle.** An arc 90% closed snaps to open or
   closed. Ambiguous middles are where legibility dies.
3. **No property readable only from a number.** Every fact must be readable
   from motion or shape. There is no tuner, no readout, no assay. If you need
   a number to know what your drawing does, the drawing is wrong.
4. **The pulse is the protagonist.** Render a discrete travelling blob, not a
   glow. It enters, crosses the run, splits at the fork into two dimmer blobs,
   one laps in the loop, one dies at a gap. Every rule in the game is legible
   in that one animation.
5. **Failure must be visible, common, and diagnosable.** Only a mouth touches
   the water; energy that never reaches one dies inside. A scribble lights up,
   fades, and the ocean stays silent.
6. **You must be able to name what you drew.** "A fork into a long run and a
   small loop, gapped to a mouth." If the only available description is "a
   squiggle," the system has already failed.

---

## 10. The bench

You cannot learn a system you cannot single-step. Neither previous build had
this screen, and it is probably the most important one in the game.

**A test tank at the station.** Still water. Draw a thing. Fire **one** pulse
in slow motion. Scrub the timeline back and forth. Watch it split, lap, jump,
die, or leave.

This is Noita's "fire the wand once and see," and it is the difference between
a system and a mystery.

---

## 11. Structure

- **The station** — a moored habitat. You draw here, safely. Your best
  machines are bolted in as **fixtures**: a collector on a vent, a resonator
  holding back the dark, an oxygen plant, a relay mast. They stay built, and
  they draw continuous energy, so the station is a standing bill you have to
  cover.
- **The dive** — six to ten minutes, hard oxygen clock. Depth is the
  difficulty axis and the content axis at once. You always surface with
  something; a *reading* is loot.
- **The antagonist is the ocean.** Pressure, cold, dark, and air. Creatures
  are second, and they are resonant systems you read by pinging and disrupt by
  driving.

### 11.1 The hazard-to-tool ladder

The ONI signature is not "you feel clever." It is that every hazard becomes a
tool once understood.

| hazard, hour one | tool, hour twenty |
|---|---|
| cold deep water detunes your spells | cold water is the floor of a sound channel you can build |
| your own bubbles give you away | a bubble curtain hides you; a tuned one amplifies you |
| overdriven loops waste energy as heat | heat is how you make mirrors and currents |
| pressure crushes you | pressure raises `c` — depth *extends* your reach |
| feedback howl tears your spell apart | controlled feedback is your amplifier |
| a creature's call finds you in the dark | a creature's call is a power source |

---

## 12. What we keep, and what dies

**Keep:**

- `sigilwave/sim/` — the waveguide network, unmodified. Delay lines,
  junctions, couplers, saturating nonlinearity, chirality, radiating
  terminals. It already *is* the seven parts.
- The shape-snapping draw tools and the runtime audio synthesis from
  `sigilwave/campanary/`.
- `Bell.wave_samples()` — mapping real buffers onto the drawn polyline. It is
  the best thing in the build, and it becomes the pulse render.
- The bot-harness *idea*.

**Dies:**

- The tuner, the needle, the note names on the canvas, the printed target
  peal, the assay. All of it is rule 9.3.
- The note-matching kill: crack meters, on-note versus off-note as the whole
  combat system.
- Freehand strokes with continuous properties.
- Energy that appears when you press a button.

---

## 13. Build order

Strictly one at a time, and each one is allowed to kill the project.

**The stage comes before the loop.** There is no survival, no oxygen clock, no
death and no objective until the thing you do second-to-second is already
worth doing. A game loop built on top of a dull core mechanic only hides it.

1. **The water.** The field from §7: temperature, salinity, gas, bubbles, `c`
   per cell, diffusion and buoyancy — headless, with a selftest that proves
   the sound-speed minimum exists. No rendering.
2. **The front.** The propagator from §5.1: polyline fronts bending toward
   slower water, intensity from arc length, absorption, reflection — headless,
   with a selftest that proves refraction, trapping in the channel, shadow
   zones and caustics all emerge from the one law. No rendering.
3. **The stage.** A dark cross-section you can swim around. Click to ping.
   **No drawing system at all.** The world is drawn *by* your sound and fades
   back to darkness. *The test: is firing pings into the dark and watching
   them bend hypnotic on its own, with no goal whatsoever?* If not, nothing
   downstream saves it, and we have spent days rather than another rewrite.
4. **The bench.** The five parts, one pulse, slow motion, a scrub bar, still
   water. *The test: is watching a pulse split at a fork and get caught in a
   loop immediately satisfying and obvious?*
5. **Mouths and merging.** Arc formation, width, focus, fronts born from the
   drawing rather than from a mouse click. *The test: can you feel the
   difference between a lance and a wall without being told?*
6. **Sources and the energy economy.** Body versus vent. *The test: does the
   player discover "transmit, do not generate" on their own?*
7. **Digging.** The calmest complete loop: ping the rock, hear the note, build
   for it, deliver it.
8. Only now, the game loop — creatures, the station, oxygen, depth.

---

## 14. How we will know it is working

CAMPANARY's harness measured `masher 2/33 → founder 31/33` and called it
success. That proves **one correct answer exists and knowledge finds it** —
which is the shape of a puzzle, not of a system.

The metric changes: **solution diversity.** For each task, how many
structurally different machines solve it, and how far apart are they? A system
where one build wins is decoration with extra steps. A system where a lance, a
focused arc, and a resonance-shatter all solve the same rock — at different
energy costs, in different water — is the thing we are trying to build.

The second metric is honest and unautomatable: **does drawing in the bench,
with no goal at all, hold attention for thirty minutes?** If a goalless
sandbox of this system is not compelling, no amount of roguelite structure
will rescue it — and the answer costs one day instead of one more rewrite.
