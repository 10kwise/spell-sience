# RIGS — the fourth design

`SUBMERGED.md` specifies the ocean and a machine that rings it. The ocean is
right and the machine is wrong. This document keeps the first and replaces the
second.

It is written against the same standard as its predecessors: every part is one
sentence, every claim is meant to be measured, and the places where the design
puts its thumb on the physics are named out loud.

---

## 1. The one sentence

**You build a pipe. Water goes in one end, and what you do to it on the way
through is the whole game.**

Not a spell. Not a waveform. A machine that takes water, changes it, and puts
it back — and because the ocean is made of the same five numbers the pipe
changes, everything you build reaches the world directly instead of four
causal links downstream.

---

## 2. Why the drawing has to go

SUBMERGED diagnosed WAVEWRIGHT and CAMPANARY correctly and then repeated the
core mistake in a new costume. Four counts.

### 2.1 The parts were discretised, the parameters were not

§2.1 of SUBMERGED is right that continuous systems are unlearnable, and the
five parts look like the fix. They are not. A LOOP is not a thing — it is a
circumference in pixels, and its behaviour is a smooth function of that
number. A GAP is a float from 0 to 30. A MOUTH is an arc with a span and a
curvature and a merge distance to its neighbours.

So the player is still handed a smooth gradient of behaviour and still cannot
tell whether a difference is a difference. **Noita's spark bolt has no radius
knob.** That is not a simplification, it is the entire reason a wand is
readable: a spell is a token, tokens are countable, and countable things can
be reasoned about. The vocabulary was made discrete and the state space was
left continuous, which buys none of the legibility and all of the cost.

### 2.2 A graph has no reading order

A Noita wand is a **list, read left to right**. That is doing far more work
than it appears to. It means every machine has a *first thing* and a *next
thing*; it means you can point at a position and name what happens there; it
means removing one item has a locatable effect; and it means the machine can
be described in a sentence with the word "then" in it.

A waveguide network is a graph. Energy goes everywhere at once, arrives by
several paths, and interferes with itself. `Assembly.describe` already
concedes this — past twelve edges it returns *"a tangle"*, and §9.6 says a
machine you cannot name is a system that has already failed. It was failing on
purpose, in code, and got shipped anyway.

**Debuggability is not a nice-to-have here. It is the mechanic.** A sandbox
where knowledge is the progression is a sandbox where the player must be able
to run experiments, and an experiment whose result you cannot read is not an
experiment.

### 2.3 §2.4 was diagnosed and then not fixed

SUBMERGED §2.4 says of the previous build: *"the system only did one thing, so
all the depth had to be spent on one verb."* SUBMERGED then built a system
that makes sound. The six verbs of §8 are not six things — they are one thing
(deliver acoustic energy) observed in six places. Every one of them routes
through the same emitter and differs only in what it happens to hit.

The tell is that heat, the most interesting field in the medium, is reachable
only as **sound → absorption → warming**: three links away, at a rate governed
by a constant (`HEAT_PER_ABSORBED_UNIT`) that had to be tuned specifically so
the player could ever see it happen. When a system needs a fudge factor to
make its own second-order effect visible in human time, that effect is not
really in the game.

### 2.4 Failure had no character

§2.2 asks for failure to be possible and informative. It got the first half. A
bad drawing produces *nothing much*, quietly, and every bad drawing produces
the same nothing.

Noita's failures are famous because they are **specific and spectacular**: you
detonate yourself, your wand takes forty seconds to recharge, you fire your
entire deck at once. Each is a different, nameable, memorable wrongness that
points straight at its cause. A system needs a small set of distinct,
diagnosable ways to be wrong. This one has four (§7).

---

## 3. What flows, and why it is water

The single design decision everything else falls out of.

A rig is a pipe with things along it. The candidates for what travels the pipe
were energy (what SUBMERGED does), an abstract packet, or **water itself**.

Water wins for four reasons and they are not close:

- **It is conserved, and conservation is what makes ONI diagnosable.** What
  goes in comes out. A rig taking in nothing does nothing, visibly, at the
  first module.
- **It carries the same state the ocean does.** The five numbers below are
  already the fields in `medium/field.py`. There is no conversion layer, no
  units contract to get wrong, and no second universe to keep in sync.
- **Everyone already has the intuition.** Pipes, pumps, pressure, hot and
  cold. The player arrives already knowing four of the six laws.
- **It makes the ocean writable.** You are not ringing the field and hoping it
  warms. You are putting hot water there.

### 3.1 A slug carries five numbers

The thing travelling the pipe is a **slug** of water. It has five properties
and no others.

| | | seen as |
|---|---|---|
| **VOLUME** | how much water this is | the size of the blob |
| **HEAT** | how hot it is | its colour, red to blue |
| **PRESSURE** | how squeezed it is | how tightly it is drawn, taut to slack |
| **GAS** | how much dissolved gas it carries | grain, from invisible to fizzing |
| **NOTE** | what it is ringing at, and how hard | how it shivers |

**Bubbles are not a sixth number.** Bubbles are gas beyond what this pressure
and heat can hold — exactly `_gas_capacity()` in `field.py`, unchanged. That
matters more than it looks: it means "why did my rig suddenly fizz" always has
the same answer, and that answer is a law rather than a module.

---

## 4. The six laws

Everything in the game is a consequence of these. Each is one sentence, has no
exceptions, and is visible every time.

| | law |
|---|---|
| **I** | **Water is conserved.** What goes in comes out. |
| **II** | **Squeeze water and it heats; let it expand and it cools.** |
| **III** | **Heat is moved, never destroyed.** Cooling here means warming there. |
| **IV** | **Warm water is light and fast; cold water is heavy and slow.** |
| **V** | **Pressure holds gas in solution.** Drop it and gas comes out; raise it and bubbles go back in. |
| **VI** | **Sound bends toward slower water.** |

Law VI is `medium/front.py` and is already built. Laws IV and V are
`medium/field.py` and are already built. Laws I, II and III are new, and they
are new *inside the rig only* — about two hundred lines, because a rig is not
a fluid simulation, it is five numbers walked down a list.

### 4.1 Law III is the one that makes the game

II and III together are why this design has depth that SUBMERGED did not.

Squeezing heats and expanding cools, but a squeeze followed by an expansion
returns you exactly where you started. **Nothing has happened.** To get cold
water you must squeeze it, *get rid of the heat somewhere else*, and then
expand it — and now you have cold water here and warm water there, and both of
them are consequences you have to live with.

That is a refrigerator. It is also a heater pointed the other way. It is the
same five modules in the same order and the difference is only which end you
care about. **One machine, two tools, no authored recipe** — and the reason it
works is a law the player already believed before they installed the game.

It also means **waste heat is the ceiling on power**, thermodynamically rather
than by a cooldown timer. A hard-running rig heats itself, and a hot rig is
buoyant, visible to anything that reads temperature, and eventually cooks you.
That is the honest answer to "why can I not just fit eight pumps": you can,
and you will boil.

### 4.2 And a seventh, which is not a law but a promise

> **Everything alive obeys the same six.**

No creature has a special case. See §9.

### 4.3 Five things building it changed, and why each correction is better

The tradition from CAMPANARY and SUBMERGED: record what the measuring changed
rather than quietly fixing it, because *how* it was wrong is the useful part.
All five below were found by making the ledger balance, which is exactly what
a ledger is for.

**Water is not compressible, so law II as first written was false.** Water's
bulk modulus is 2.25 GPa, so squeezing it three times harder heats it by about
a thousandth of a degree, and a constant big enough to rescue that would have
been the pure fudge this project has twice written post-mortems about. The fix
was not a bigger constant but noticing what in the water *is* compressible:
**the gas it carries.** Wood's equation is already in `field.py` saying exactly
this, and `GAS_ADIABATIC = 1.4` was already sitting there. So compression
heating is proportional to dissolved gas — and three things fall out that
nobody designed. Deep water makes better rigs. A hot rig degrades itself,
because warm water holds less gas. And **stripping a room of its gas disables
your own compressor in it.** Measured: the same SQUEEZE moves full water
**+14.59 °C** and filtered water **+7.62 °C**, 52%.

**A squeeze-expand round trip comes back hotter, not level.** §6 called the
coil-less cooler "nothing at all". It is worse than that. The compressor puts
*all* of its work into the fluid, so the slug ends up warm and you paid for it.
Measured at 120 m: **+5.74 °C for 5.92 units of energy.** The lesson is
sharper than the one that was designed — you did not merely fail to cool it,
you spent energy heating it — and it is the Second Law teaching itself.

**NARROW obeys Bernoulli, so it drops pressure.** §5 said nothing about this.
A nozzle buys speed by spending pressure, which hands the vocabulary a second
route to cavitation: narrow hard enough and the throat tears open. That is
exactly why real propellers cavitate. So NARROW is both the thruster module
and the cheap way to make a bang, and nobody wrote it down.

**A turbine on the expansion was a perpetual motion machine.** The first
implementation recovered expansion work into the economy, and the gill and the
lamp came out at *negative cost* — four modules that generate energy. The
cause was not a sign error: expanding cools the slug, the slug re-warms from
the ocean at the port, and the cycle was converting ambient heat into work at
100% with no cold sink. A Kelvin-Planck violation whose books balanced
perfectly. Real refrigerators use a *valve* rather than a turbine for exactly
this reason, so EXPAND now rejects that energy to the water instead of
returning it. The cooling — the effect anyone actually wanted — is unaffected.

**A choking nozzle was creating 120 kJ from nothing.** Clamping the pressure
at the tear point while keeping the speed the geometry asked for invented
energy. The honest answer is that the flow simply fails to reach that speed:
a nozzle can only spend the pressure it has, and past that the throat
cavitates and chokes.

**A port that did not re-pressurise made the whole cycle pointless.** The
density search (§12) found this and it was the worst bug of the lot. A bare
`EXPAND` was reported as a cooler — one module, −5.1 °C, 0.17 units — while the
proper refrigerator cost 6.03 units and cooled *less*. The cheapest way to
cool was to skip the entire cycle. The cause: a port released water still
sitting at a third of ambient pressure, which the ocean would simply push back
in. Water has to be handed back **at ambient**, and compressing it back up
re-heats it — undoing exactly the cooling the expansion bought. With that in
place a bare expand-and-release nets to nothing and the COIL is the only thing
that works.

**Water freezes, and that had to be a law.** Without a floor the cold side ran
away: five expansions at 400 m reached −37.65 °C and the return leg then
delivered water at +101 °C. Both ends were nonsense and they were the same
bug. Freezing is the physical answer (0 °C, 334 kJ/kg, neither number chosen)
and it is the better design answer too — **IT BOILS had no partner**, and the
vocabulary is built out of opposed pairs. See §7.

**Freeze and thaw have to be symmetric, and so do nucleation and
re-dissolution.** Two separate versions of the same mistake. Capping the cold
side while still charging full price on the warm side made output swing
**+78.91, −9.98, +16.56 °C as EXPANDs were added one at a time** — precisely
the unlearnable non-monotonicity §2.1 condemns. And letting the working fluid
grow on expansion without shrinking on compression let it ratchet to the
ceiling and stay there, which is where the +155 °C lamp came from.

**A collapsing cavity leaves a cloud.** The collapse restored ambient pressure
and the gas went quietly back into solution, so the loudest thing in the
vocabulary left no trace in the water at all. A real cavitation collapse
shatters into microbubbles that outlast the pressure recovering — which is
what a cavitating propeller's wake looks like, and it is the cover the charge
is supposed to leave behind.

### 4.4 What the books say now

Four suites, **78 checks, all green.**

| | |
|---|---|
| `selftest_conservation` | **26/26** |
| `selftest_couple` | **23/23** |
| `selftest_density` | **9/9** |
| `selftest_creatures` | **20/20** |

| | |
|---|---|
| worst energy residual, every preset at seven depths | **1.5e-8 J** on terms of order 1e8 |
| worst gas residual | **exactly zero** |
| random chains fuzzed for free energy | **8000, no generators** |
| the rig and the ocean agreeing on gas capacity | to float precision |

The fuzzing is the check that matters. The failure this design is most exposed
to is a five-module combination nobody thought to try that quietly runs a free
heat engine, and **two such bugs were caught exactly this way** — a turbine
recovering work from below ambient, and an expansion valve returning its work
to the economy, which converted ambient ocean heat into work with no cold sink.
A Kelvin-Planck violation whose books balanced perfectly.

---

## 5. The vocabulary

Eleven modules. No knobs. Each is one sentence.

They come as **four opposed pairs and three singletons**, and the pairing is
load-bearing: an opposed pair teaches two things for the price of one, and it
makes "what is the opposite of this" a question the player can always ask.

### 5.1 The pairs

| module | the one sentence |
|---|---|
| **INTAKE** | Water enters here, at the temperature and pressure of wherever it is. |
| **PORT** | Water leaves here, carrying everything it has, in the direction the port faces. |
| **SQUEEZE** | Raises pressure, and heats it. |
| **EXPAND** | Lowers pressure, and cools it — and gas above capacity comes out as bubbles. |
| **NARROW** | The same water through less opening: faster, harder, tighter. |
| **WIDEN** | The same water through more opening: slower, softer, spread. |
| **FILTER** | Takes gas, or heat, or salt out of the water and keeps it in a tank. |
| **INJECT** | Puts what is in a tank back into the water. |

### 5.2 The singletons

| module | the one sentence |
|---|---|
| **PUMP** | Drives the flow. More flow costs more work. |
| **COIL** | Moves heat between the water inside it and the water outside, toward equal. |
| **RESONATOR** | Makes the water passing through it ring at one of five notes. |

### 5.3 What each one is really for

**PORT is the only module that touches the ocean.** That is SUBMERGED's §9.5
kept intact and it is the best rule in that document: energy that never
reaches a port dies inside, so a half-built rig fails visibly rather than
underperforming quietly.

**WIDEN and NARROW are SUBMERGED §5, made discrete.** The whole width tradeoff
survives — narrow is brutal and sprays, wide is soft and carries — but it is
now a token you place rather than a distance you measure. The aperture physics
in `mouths.py` is kept and driven from a count instead of a span.

**RESONATOR is the entire old game, demoted to one module.** The waveguide sim
in `sigilwave/sim/` is what it runs on, and the note ladder from §7.4 — swell,
groan, hum, ping, chirp — becomes five named choices instead of a
circumference. Everything SUBMERGED learned about range, absorption, aperture
and focus stays true, and stops being the only thing there is.

**COIL is the module that makes cooling a design problem.** It is the only
place law III becomes a decision: heat has to go *somewhere*, the coil is
where you choose, and where you choose has consequences you did not ask for.

**FILTER and INJECT are the resource loop, with no new rule.** Filter gas out
of deep water and you have air. Filter heat out and you have a hot tank you
must eventually dump. Inject that heat and you have a flare, a thermal decoy,
a lift bag, and a way to shed the thing that was going to cook you. One pair,
four tools, all consequences.

### 5.4 The second set, deliberately withheld

Three more modules exist in the design and must not be built until the eleven
above are proven fun. Each buys power and costs legibility.

| module | the one sentence | the cost |
|---|---|---|
| **SENSE** | Passes the water on only if a condition on its five numbers holds. | the highest-value module in the design, and the first one to add |
| **HOLD** | Keeps a slug for a beat before letting it on. | timing, which is the thing SUBMERGED never got |
| **SPLIT** | Divides the flow between two chains. | **this is the one that breaks the reading order.** Add last, or never |

SENSE is where the sandbox fantasy actually lives, because its conditions read
the *same five numbers the world runs on* — "pass only if colder than
outside", "pass only if the pressure is above this" — so a rig can be built
that fires itself, in a place, at a thing, without you there.

---

## 6. Order is the whole game

The test of a wand system is whether rearranging the same parts gives
genuinely different machines. Here are eight chains built from the eleven
modules. Nothing below is authored, scripted, or special-cased; every one of
them is what the six laws do to five numbers.

| the chain | what it is | why |
|---|---|---|
| `INTAKE → SQUEEZE → COIL → EXPAND → PORT` | **a cooler** | squeeze it hot, dump the heat out through the coil, expand what is left: colder than it started |
| the same rig, standing at the coil | **a heater** | identical machine. You changed which end you cared about |
| `INTAKE → SQUEEZE → EXPAND → PORT` | **nothing at all** | you heated it and cooled it and never let the heat go anywhere. Law III, learned in one failure |
| `INTAKE → EXPAND → EXPAND → PORT` | **a bang, a flash and a cloud** | pressure past the tear point is cavitation: loud, bright, and it leaves bubbles behind |
| `INTAKE → EXPAND → FILTER(gas) → PORT` | **a gill** | law V run backwards. Deep water holds more gas, so this works *better* where it is trying to kill you |
| `INTAKE → PUMP → SQUEEZE → NARROW → PORT` | **a thruster** | a fast hot jet. And it leaves a warm wake, which anything reading temperature can follow |
| `INTAKE → PUMP → RESONATOR(hum) → WIDEN → PORT` | **sonar** | the old game, intact, as one build among many |
| `INTAKE → FILTER(heat) → INJECT(heat) → PORT`, shallow | **a mirror** | warm water is fast (IV), sound bends away from fast (VI). You built a wall out of temperature |

Two things to notice about that table.

**Every row is one sentence of physics.** Not one of them required a rule
about coolers, gills, thrusters or mirrors. They required laws II, III, IV, V
and VI, which the player meets in the first ten minutes.

**Adjacent rows are adjacent chains.** The cooler and the do-nothing differ by
one module. The thruster and the sonar differ by two. That is what makes a
sandbox teach: the space is dense, so every experiment lands near something
else worth knowing.

### 6.1 The couplings nobody has to author

`field.py` already couples every field to every other. So:

- Run the thruster and you leave a **warm wake** — a trail, for anything that
  reads temperature, including whatever is hunting you.
- Warm the water and it **holds less gas** — so heating a room to herd fish
  starves your own gill.
- Warm water is fast, so heating a room **bends your own sonar the wrong way**
  and puts a blind spot exactly where you made the heat.
- Make bubbles for cover and they **slow sound**, so your curtain is a lens as
  well as a wall, and it will focus somebody else's ping onto you.

**Every action has three consequences because every field is coupled to every
other.** That is what "simple rules combining into complex behaviour" means
mechanically, and the coupling matrix in SUBMERGED §7.2 is already built and
already measured. What it was missing was a player who could write to it.

---

## 7. The four failures, which turned out to be four plus an event

The design said four. Building it produced **four faults and one event**, and
the split is better than the original list.

| the fault | looks like | means | first reached by |
|---|---|---|---|
| **IT DOES NOTHING** | the slug stops at a module and sits there | no intake, or no port — the pipe is not open at both ends | any chain missing a bracket |
| **IT BOILS** | the rig glows, then steams, then you cook | heat with nowhere to go. No coil, or a coil in water already hot | **11 × SQUEEZE** |
| **IT FREEZES** | the pipe ices up and blocks | you cooled past freezing and the latent capacity ran out | **9 × EXPAND** |
| **IT STALLS** | the chain runs dry and stutters | you asked for more flow than the intake supplies | **3 × PUMP** |

**IT FREEZES was not designed; the physics demanded it** (§4.3), and it is the
partner IT BOILS never had. The vocabulary is built out of opposed pairs, and
now so are its failures: the hot end and the cold end are the same mistake
reached from opposite directions.

**IT TEARS is not a fault, it is an event.** Cavitation is something you build
on purpose at least as often as you suffer it — the charge and the lamp are
both nothing but a controlled tear — so it is reported alongside the verdict
rather than instead of it. A rig can tear and run perfectly.

All four faults are legible from the slug alone, all four have an obvious
first thing to try, and two of them (**BOILS**, **FREEZES**) are things you
will later build on purpose. That is the §11.1 hazard-to-tool ladder arriving
inside the machine instead of only out in the world.

---

## 8. Learnability, which is the whole risk

The requirement is explicit: the feeling of Noita, without Noita's
impossibility. Noita is opaque for four specific reasons, and each has a
specific answer here.

| why Noita is opaque | the answer |
|---|---|
| hidden numbers you cannot see | every property of a slug is drawn on the slug: colour, size, tautness, grain, shiver |
| no way to test without dying | the bench, kept from SUBMERGED §10 — still water, one slug, slow motion, a scrub bar |
| ~200 spells | eleven modules, and three more withheld until the eleven are proven |
| interactions nobody names | the game names your rig back to you in a sentence |

### 8.1 The rig names itself

A chain is a sentence, so the machine can always say what it is:

> *"Takes water in, squeezes it, dumps the heat outside, expands it. Cold
> water out the front."*

This is SUBMERGED's §9.6 requirement, which a graph could not satisfy and a
list satisfies trivially. **If the game can name your machine, you can name
it, and if you can name it you can reason about it.** The failure case is not
"a tangle" — it is a sentence that sounds wrong when you read it, which is
itself the diagnosis.

### 8.2 The slug is the protagonist

SUBMERGED §9.4 is right that something must be watched crossing the machine,
and a slug of water is a better protagonist than a pulse of energy because it
**has properties you can colour**. You watch it enter cool and slack, go taut
and red through the squeeze, bleed red into the coil, go slack and blue and
start to fizz through the expansion, and leave.

Five numbers, five visual channels, one animation, and every law in the game
legible in it.

### 8.3 The first creature is a teacher

Do not explain law IV. Put a fish in the first room that visibly drifts toward
warm water, and let the player watch it for thirty seconds. They will build
their first heater for a reason they invented, which is the only kind of
reason that teaches.

---

## 9. Creatures are field-readers

The requirement is that fish react to temperature and pressure consistently,
so that knowing the world is what lets you act on it. That needs exactly one
rule.

> **Everything alive swims toward where it is more comfortable.**

A creature is not a state machine. It is a set of preferences over the same
five numbers, and a body that climbs the gradient of its own comfort:

- a temperature band it likes
- a pressure band it likes, which is a depth
- what bubbles do to it — blind it, choke it, attract it
- a note it flees, a note it approaches, and the notes it cannot hear at all
- what it eats

From that single rule, with no AI code:

| you do | it does | and this is |
|---|---|---|
| build a warm wall across a passage | a cold-lover will not cross it | **herding** |
| put a cold pocket in an open space | a cold-lover comes to it | **luring** |
| lure it, then tear the water | it is inside the cavity when it collapses | **hunting** |
| match your own thermal signature to the water | the thing hunting *you* by heat loses you | **hiding** |
| lay a bubble curtain | sonar-hunters go blind, sight-hunters do not | **cover, conditionally** |

Note the last two. **If creatures read fields, so does whatever is hunting
you**, and the same rig that finds prey advertises you to a predator. Defence
and offence are the same verb aimed differently, which is the property that
makes a sandbox worth living in rather than a toolbox worth clearing.

All five are built and measured (`selftest_creatures`, 20/20). `creatures.py`
contains no code for any of them: one comfort function, one gradient climb, and
four species that differ only in their numbers.

### 9.0 Two things the measuring found, both better than what was designed

**Heat herds. Sound calls.** Nobody designed a range law, and there is one.
`field.py` diffuses heat at 60 px²/s, so a patch spreads about 17 px in five
seconds and the usable gradient around it is gone by 140 px. Measured on a cold
pocket:

| distance | comfort | |
|---|---|---|
| 220 px | 5.196e-04 | nothing to read |
| 140 px | 5.204e-04 | 0.2% — still nothing |
| 90 px | 6.638e-04 | the gradient begins |
| 40 px | 6.546e-02 | strong |

Sound falls off as `1/(1+(d/120)²)` instead, and a shoalfish crosses 260 px to
a groan. So **thermal tools are local and slow, and acoustic tools reach across
a room** — which means the sonar a player builds for navigation is also the
only thing that can call something from a distance. Two of the six verbs
divided their labour without being told to.

**A bubble curtain is not thermally silent.** Bubbles lighten water, lighter
water rises, and warm water follows it up. Measured across a curtain's own row
after ten seconds: **+0.16 °C at the centre**, +0.02 °C at 60 px. So a
heat-hunter finds your curtain too — by the convection it drives rather than by
the bubbles themselves. Cover from one sense advertises you to another, through
a coupling nobody wrote: `field.py` was already doing it and the creature was
already reading it. That is §6.1 arriving unprompted, and it means bubble cover
has a real cost.

### 9.1 Depth flips the sign on almost everything

This is where the survival fantasy and the engineering fantasy become one
system. Every module's behaviour is a function of ambient pressure and
temperature, so **a rig tuned at the station is wrong at 700 m**, and the
redesign forced by depth is the content.

| deep water does this to you | and it is a tool because |
|---|---|
| pressure crushes you | pressure is stored work — deep water can *drive* your rig |
| it is cold | your coil dumps heat far better down there. Coolers get stronger with depth |
| it holds more gas | your gill runs better the deeper you are |
| bubbles are small and stiff | your bubble cloak stops working, and your bubble *bomb* gets louder |
| it is dark | sound is the only sense you have, and you build it |

SUBMERGED already found one instance of this honestly — cavitation gets harder
with depth, so *"a machine tuned at the station simply refuses to trip at
depth"* (§4.1). This design generalises that finding across the whole
vocabulary, and it costs nothing, because ambient pressure and temperature are
already what every one of these modules reads.

---

## 10. What survives

Being explicit, because "move away from the current system completely" should
not mean throwing away the part that works. Roughly four thousand lines of
simulation live; roughly two thousand lines of authoring UI die.

**Kept, untouched:**

- `medium/field.py` — the coupled ocean. It is the game. Laws IV and V are
  already in it, measured.
- `medium/front.py` — the wavefront propagator. Law VI, already measured,
  including the sound channel.
- `sigilwave/sim/` — the waveguide network. Demoted from *the whole game* to
  *what RESONATOR runs on*, which is a promotion in disguise: it stops having
  to carry the design by itself.
- `diver.py`, `sources.py`, `digging.py` — the diver, the energy economy, the
  rock notes. All still correct.

**Kept, repurposed:**

- `bench/mouths.py` — the aperture physics becomes what PORT, WIDEN and NARROW
  do. Driven from a token count instead of a measured span.
- `bench/cavitation.py` — becomes EXPAND past the tear point. The Blake
  threshold rising with depth is now a property of a *module*, which is
  exactly what §9.1 needs.
- `bench/app.py` — the bench screen survives as a concept and gets a new
  inside: still water, one slug, slow motion, a scrub bar.
- The preset library *idea* from `bench/presets.py` — eight machines that
  demonstrably do what they claim, each with one thing to change. That was the
  right answer to the playtest complaint and it transfers directly; a chain is
  far easier to hand somebody than a drawing.

**Dies:**

- `bench/parts.py` — placing RUN, LOOP, FORK, GAP as geometry.
- Arc merging as an authoring gesture. The physics survives; the drawing does
  not.
- `bench/advice.py` — diagnostics for a machine you could not read. A readable
  machine does not need them.
- `bench/gadgets.py` as a separate layer. Gadgets were the right idea in the
  wrong place: they are not receivers bolted to the end of a sound machine,
  they are the vocabulary itself.

---

## 11. The risk, stated plainly

**This design has more systems than the one it replaces, and the one it
replaces failed for being unlearnable.** That objection deserves an answer
rather than optimism.

The answer is that the complexity moved from **parameters** to
**combinations**.

- Old: 5 parts × roughly 4 continuous knobs each = an unnamed, uncountable
  space where no two experiments are comparable.
- New: 11 parts × 0 knobs = a countable space where all the depth is in
  *ordering*, and every experiment differs from the last by one nameable
  change.

That is the actual lesson of Noita, and it is not "have lots of content."
Noita's spells have almost no parameters. Wands are deep because of order,
interaction and cost, and those three are exactly what a list gives you for
free and what a graph destroys.

The second risk is scope, and the answer is that the new simulation is small:
five numbers, eleven transforms, one list. The ocean — the genuinely hard part
— is already built and already green.

---

## 12. The test, before building anything

Do not build the UI. Do not build the game loop. SUBMERGED §13's *"the stage
comes before the loop"* was right, and this is the same discipline one level
further in.

**Day one, headless.** Five numbers, eleven transforms, a list, and a
`describe()`. No rendering, no pygame, no drawing.

Then two questions, both cheap, and either one is allowed to kill it:

**1. Density.** Write down ten chains that produce ten nameable, meaningfully
different results, using only the eleven modules and touching no transform
code. If you need a twelfth module to reach ten results, the vocabulary is
wrong and no amount of art will fix it.

**2. Diagnosis.** Hand somebody `INTAKE → SQUEEZE → COIL → EXPAND → PORT` with
the COIL taken out, let them watch the slug cross it, and ask why it does
nothing. If they can work it out from the animation, the system is learnable.
If they cannot, it is SUBMERGED again in better costumes, and it should die on
day one instead of day forty.

The metric from SUBMERGED §14 stands and gets easier to measure here:
**solution diversity** — how many structurally different chains solve the same
problem, and how far apart they are. A list is trivially diffable. A graph was
not.

### 12.1 Both tests were run. Both passed, and not narrowly.

`python -m sigilwave.rig.selftest_density` — **9/9.** The search touches no
transform code and invents no module.

**Test 1, density. Asked for ten; found 352.** Distinct outcome classes at
200 m, clustered on measured outputs rather than on the modules used, so two
chains that do the same thing collapse to one class. All four faults reachable
by a well-formed machine.

**Test 2, solution diversity. 143 structurally distinct machines solve one
task**, over a **275× cost spread** (0.23 to 62.03 units). The task was
"deliver water at least 8 °C colder than ambient at 200 m", and structurally
distinct means a different *bag* of modules, not a reordering. That is the
number that separates a system from a puzzle, and CAMPANARY's harness could
never have produced it.

**Order is the whole game, measured.** One bag of three modules — SQUEEZE,
COIL, EXPAND — gives four different machines across six orderings:

| the order | what it is | |
|---|---|---|
| `SQUEEZE COIL EXPAND` | **a cooler** | −2.72 °C |
| `SQUEEZE EXPAND COIL` | does nothing | +0.70 °C |
| `EXPAND SQUEEZE COIL` | does nothing | +0.94 °C |
| `COIL SQUEEZE EXPAND` | a heater | +7.05 °C |
| `EXPAND COIL SQUEEZE` | **a heater** | +14.31 °C |

Same three parts, same cost, 17 °C apart. And the cascade's own claim holds:
coils *between* the squeezes give −7.10 °C, the same modules with both coils
moved to the end give **+0.11 °C**.

**Every module earns its place.** Deleting any one of the nine body modules
makes between 11 and 71 outcome classes unreachable. There is no dead weight
in the vocabulary, which is the inverse check and the one that would have
embarrassed §5's claim that eleven is the right number.

### 12.2 What is built

| | |
|---|---|
| `sigilwave/rig/units.py` | the constants, and every named lie |
| `sigilwave/rig/slug.py` | the five numbers, and the ledger that must balance |
| `sigilwave/rig/modules.py` | the eleven transforms |
| `sigilwave/rig/chain.py` | the walk, the sentence, the faults |
| `sigilwave/rig/library.py` | eleven machines, each with one thing to change |
| `sigilwave/rig/couple.py` | the boundary with the real ocean |
| `sigilwave/rig/creatures.py` | one rule, four species |
| `sigilwave/rig/bench.py` | the bench — `python -m sigilwave.rig.bench` |

`Diver.rig_thrust` is wired and measured. `THRUST_PER_ENERGY` is retired for
rigs and survives only for `impulse_from`, where the thing being thrown really
is sound and the lie really is still necessary. Measured over the same four
seconds SUBMERGED used for its own baseline:

| | moved |
|---|---|
| the thruster, 2719 N | **80.9 px** |
| the charge, 10875 N | **238.8 px** |
| the heater, no jet | **0.0 px** |
| SUBMERGED's drawn machine, for comparison | 101-134 px |

The charge out-thrusts the thruster three to one, because nozzles multiply
exit velocity and thrust is `mdot x v`. So the best way to travel is also a
weapon that shoves you off your aim, which is a tradeoff nobody placed.

Still missing before this is a game: the station, and a dive that can end.
And the second go/no-go question in 12 is still open, because it is the one a
machine cannot answer.
