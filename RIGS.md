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

Thirteen modules. No knobs. Each is one sentence.

They come as **six opposed pairs and one modifier**, and the pairing is
load-bearing: an opposed pair teaches two things for the price of one, and it
makes "what is the opposite of this" a question the player can always ask.

It was four pairs and *three* singletons for the first build, and that was the
shape of a real hole rather than a stylistic one. A playtester found it from
the outside without knowing the module list:

> the only thing that seems to do nothing is the chirps and groans and sound
> modules i cannot figure out why they are here

Right on all three counts, and the diagnosis was the same for all three
singletons. **PUMP had no opposite**, so there was no way to take energy back
out of moving water. **COIL had no opposite**, so there was no way to take
energy out of a temperature difference — which meant every verb in the game
was a cost and the only decision left to a player was how little to run the
machine. And **RESONATOR was in the list for a completely different reason**:
it is not half of a pair because it is not the same *kind* of thing, and
calling it a singleton hid that instead of saying it. See §5.5.

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
| **PUMP** | Drives the flow. More flow costs more work. |
| **TURBINE** | Takes the push back out of the water, as power. |
| **COIL** | Moves heat between the water inside it and the water outside, toward equal. |
| **THERMOPILE** | Takes power out of a difference in heat — and only a difference. |

### 5.2 The modifier

| module | the one sentence |
|---|---|
| **RESONATOR** | Makes the water ring — and a ringing pressure is still a pressure. |

Every other module *moves* one of the five numbers. This one changes what the
others do to them, which is a different category of thing: in wand-building
terms it is a modifier rather than a projectile, and every game built on
ordered lists has exactly that category. It is allowed to have no opposite
because a modifier does not have one.

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
and focus stays true, and stops being the only thing there is. What it does
*inside* the pipe is §5.5, and that is the part the first build got wrong.

**TURBINE and THERMOPILE are where energy comes back**, and the Second Law
says exactly how much before either of them is described. You cannot get work
out of one temperature however hot it is — Kelvin–Planck — which is why the
first build's turbine-on-expansion was free energy with perfectly balanced
books. You *can* get work out of a **difference**, and only 1 − Tc/Th of the
heat you move through it. So:

- **TURBINE generates nothing.** It is regenerative braking. `ETA_PUMP ×
  ETA_TURBINE` is 0.55, so a pump–turbine loop loses nearly half every time
  round, and the fuzzer checks that no arrangement of them ever comes out
  ahead. What it is *for* is that it is the only way to stop: a PORT throws
  whatever the slug has, and a jet is a wake, a noise, and an arrow pointing
  at you.
- **THERMOPILE is the generator, and it is a place rather than a machine.** In
  water that is all one temperature it produces exactly zero — not a small
  number, zero — and going somewhere is the only thing that changes that. It
  reads `Ambient.sink`, the water the coil line reaches, which `couple.apply`
  has always let the player put somewhere else. A radiator with something
  standing in the heat flow is a power station.

**COIL is the module that makes cooling a design problem.** It is the only
place law III becomes a decision: heat has to go *somewhere*, the coil is
where you choose, and where you choose has consequences you did not ask for.

**FILTER and INJECT are the resource loop, with no new rule.** Filter gas out
of deep water and you have air. Filter heat out and you have a hot tank you
must eventually dump. Inject that heat and you have a flare, a thermal decoy,
a lift bag, and a way to shed the thing that was going to cook you. One pair,
four tools, all consequences.

### 5.5 What sound had to become before it was a module at all

The playtest verdict above was not a balance note, it was a correct reading of
the code. A RESONATOR wrote `note_amp`, carried it to the PORT, and **nothing
in between ever read it.** No ordering involving a RESONATOR changed any
outcome. In a design whose entire claim is §6 — *order is the whole game* —
that means the module was not in the vocabulary; it was an output device with
a frequency label sitting in the module list, and a player was right to say so.

The fix is not a bigger effect. It is noticing what sound physically **is**: a
pressure that is not in the pressure number. A slug at 1 bar carrying a 3 bar
note spends part of every cycle at minus 2 bar, and water does not survive
that. Acoustic cavitation is the whole of how an ultrasonic cleaner works, and
it needed no new law here — the tear check already existed, it was reading the
mean instead of the trough. `Slug.tension` is `pressure − acoustic_pressure`,
and every cavitation test in the game now reads it.

Four things fell out of that one change, and every one of them reaches a
module that is not about sound:

| | measured |
|---|---|
| **A note is worth two or three EXPANDs**, at every depth | 40 m: 5 alone → 2 with a note. 700 m: 7 → 4. |
| **NARROW and WIDEN are the resonator's knob**, because intensity is power over area | a bare note leaves 4.14 bar of tension; through two NARROWs, 3.28; through two WIDENs, 4.57 |
| **The pipe eats the note, high notes fastest** — the ocean's own `f^1.6` law | through four modules a swell keeps 3985 J and a chirp keeps 820 |
| **A note pulls gas out of solution** (rectified diffusion), so it feeds the compressor behind it | SQUEEZE alone +5.83 °C; with a note in front, +9.72 °C |

And the attenuation gives the vocabulary the one thing it did not have: a
quantity that **decays along the chain**, so *how far a module is from the
port* matters. At 400 m, `EXPAND EXPAND EXPAND EXPAND RESONATOR` tears the
water for 0.49 units; the same five modules with the note moved to the front
do not tear at all and cost **37.75**. Seventy-seven times worse for moving
one module one place, and the reason is legible: the pipe ate the chirp before
it arrived, and a chain that *very nearly* tears has to pay to recompress
everything a collapse would have recompressed for free.

### 5.4 The second set, deliberately withheld

Three more modules exist in the design and must not be built until the thirteen
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
genuinely different machines. Here are eight chains built from the first eleven
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
| ~200 spells | thirteen modules, and three more withheld until these are proven |
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
- New: 13 parts × 0 knobs = a countable space where all the depth is in
  *ordering*, and every experiment differs from the last by one nameable
  change.

That is the actual lesson of Noita, and it is not "have lots of content."
Noita's spells have almost no parameters. Wands are deep because of order,
interaction and cost, and those three are exactly what a list gives you for
free and what a graph destroys.

The second risk is scope, and the answer is that the new simulation is small:
five numbers, thirteen transforms, one list. The ocean — the genuinely hard part
— is already built and already green.

---

## 12. The test, before building anything

Do not build the UI. Do not build the game loop. SUBMERGED §13's *"the stage
comes before the loop"* was right, and this is the same discipline one level
further in.

**Day one, headless.** Five numbers, eleven transforms, a list, and a
`describe()`. (Thirteen now — §5 says which two were added and why the
omission was a hole rather than a shortage.) No rendering, no pygame, no drawing.

Then two questions, both cheap, and either one is allowed to kill it:

**1. Density.** Write down ten chains that produce ten nameable, meaningfully
different results, using only the modules that exist and touching no
transform code. If you need a twelfth module to reach ten results, the vocabulary is
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

**Every module earns its place.** Deleting any one of the body modules makes
between 11 and 71 outcome classes unreachable. There is no dead weight in the
vocabulary, which is the inverse check and the one that would have embarrassed
§5's claim to know the right number — and it is the check that killed the
first version of `Slug.tear_point`, which measured a parcel's nuclei against
its own collapsed capacity, never fired once, and was 1.6 bar of constant
doing nothing.

### 12.2 What is built

| | |
|---|---|
| `sigilwave/rig/units.py` | the constants, and every named lie |
| `sigilwave/rig/slug.py` | the five numbers, and the ledger that must balance |
| `sigilwave/rig/modules.py` | the thirteen transforms |
| `sigilwave/rig/chain.py` | the walk, the sentence, the faults |
| `sigilwave/rig/library.py` | sixteen machines, each with one thing to change |
| `sigilwave/rig/couple.py` | the boundary with the real ocean |
| `sigilwave/rig/creatures.py` | one rule, four species |
| `sigilwave/rig/bench.py` | the bench — `python -m sigilwave.rig.bench` |

`Diver.rig_thrust` is wired and measured. `THRUST_PER_ENERGY` is retired for
rigs and survives only for `impulse_from`, where the thing being thrown really
is sound and the lie really is still necessary. Measured over the same four
seconds SUBMERGED used for its own baseline:

| | at 40 m | at 400 m |
|---|---|---|
| the thruster, 2719 N | **80.9 px** | 80.9 px |
| the charge | **0.0 px** — it tears | **238.8 px** at 10875 N |
| the heater, no jet | 0.0 px | 0.0 px |
| SUBMERGED's drawn machine, for comparison | 101–134 px | |

**The charge is a weapon in shallow water and an engine in deep water, and it
is the same seven modules.** That is §9.1 arriving somewhere nobody aimed it:
ambient pressure decides whether the throat tears, and a torn throat has no
jet left to push with.

### 12.3 Thrust breakdown, which the fuzzer insisted on

The first draft let a nozzle keep the kinetic energy it borrowed from the
ocean's static pressure, and a TURBINE downstream then cashed it — a third
free-energy machine, found in six modules:

```
INTAKE PUMP NARROW NARROW TURBINE PORT        -12.3 kJ from nothing
```

A submerged nozzle borrows speed from the local static pressure and gives it
back downstream; the pressure field is **conservative** and the loop closes.
The old collapse broke the loop by letting the ocean pay to restore a pressure
the nozzle had never been charged for lowering. So a collapsing void now eats
**the flow first**, and only asks the ocean for the shortfall.

Which says something true at the same time, and it is the best accident in
this pass:

| nozzles on a two-pump thruster | thrust | sound |
|---|---|---|
| 0 | 1359 N | — |
| 1 | 2719 N | — |
| 2 | **5438 N** | — |
| 3 | **0 N** — tears | 43666 J |
| 4 | 0 N | 20623 J |
| 5 | 0 N | 9740 J |

**A cavitating propeller loses its thrust.** That is thrust breakdown, it is
the single most important practical consequence of cavitation in real water,
and it means the loudest machine in the game is no longer also the fastest.
Every real propeller has that cliff and every real designer works just
underneath it — which is now a thing a player does too, and nobody wrote a
rule for it.

### 12.4 The generators, and the three machines that had to die first

Adding a module that *hands energy back* is the most dangerous thing this
design has done, because every previous conservation bug was a machine that
generated by accident. All three were found by fuzzing rather than by
reasoning, and all three had perfectly balanced books:

| what it was | why it was wrong |
|---|---|
| `INTAKE EXPAND THERMOPILE PORT` → **+343 kJ** | The pile took its difference from the *slug*. EXPAND cools the slug and books the energy as leaving, correctly — so a rig could **manufacture a cold reservoir** and sell it back. A reservoir is something whose temperature does not change when you take heat out of it; a 240 kg slug is not one. The pile now runs on the two temperatures **the ocean** is maintaining. |
| `INTAKE PUMP NARROW NARROW TURBINE PORT` → **−12.3 kJ** | §12.3. |
| four piles with `FILTER`/`INJECT` between them → **185% of Carnot** | Each pile obeys Carnot individually, so stacking is not a violation — it is more hardware. The bound is the **mass flow**: one pass can ferry at most `m·Cp·ΔT` between two temperatures, past which the water leaves hotter than the hot end. That budget is now spent across the chain (`Ledger.pile_heat`), and stacking saturates at 78% — which is `ETA_PILE`, not a number anybody picked. |

What is left is a generator that behaves like one:

| the tap, at 400 m | |
|---|---|
| uniform water | **exactly 0.000** units/s — Kelvin–Planck, not balance |
| sink +5 °C | 0.031 |
| sink +15 °C | 0.270 |
| sink +30 °C | 1.028 |
| sink +55 °C | 3.195 |

A cold sink works exactly as well as a hot one. Against a SQUEEZE at ~4
units/s, a vent-fed pile pays for propulsion, sound and gas indefinitely and
never pays for heavy refrigeration — so the vent is worth walking to and does
not end the economy. And because `couple.apply` writes `heat_from_ocean` back
into the medium as cooling, **tapping a vent cools the vent.** Depletion, with
nobody writing a depletion rule.

`sources.Economy` gained a pack (`CHARGE_MAX`), and could not have had one
before: every verb in the old vocabulary was a cost, so a surplus was not a
state the economy could reach and a battery would have been a box that never
had anything in it. The draw order is world, then pack, then lungs — which is
§3's rule unchanged, with a delay in the middle.

### 12.5 Nothing powers itself, including through the ocean

`selftest_conservation` proves the **ledger** cannot be cheated inside one
evaluation. That is necessary and it is not sufficient, because a rig runs for
minutes against a live ocean and **changes the water it is reading**. There is
a second loop and it does not pass through the ledger at all:

> the rig dumps waste heat into a cell → `couple.apply` writes it into the
> medium → `couple.ambient_from` reads that cell back as the sink → the
> THERMOPILE sees a gradient → it generates

Every step is correct on its own. It is a perpetual motion machine assembled
from four honest parts in four different files, all of which balance, and no
test in this project could have seen it. `selftest_selfpower` closes it by
running the loop against a real `Medium`, and the answer is better than
"balanced" — it is **structurally impossible**:

| self-heating loop, 60 s | net | gradient it built |
|---|---|---|
| 1 × SQUEEZE → COIL → THERMOPILE | −514 units | +1.77 °C |
| 2 × SQUEEZE | −943 | +3.09 |
| 4 × SQUEEZE | −1647 | +6.64 |
| 8 × SQUEEZE | −3091 | +15.77 |

**The harder you try, the worse it gets**, which is the signature of a
Carnot-bounded loop rather than a tuned one. A pile hands back
`ETA_PILE × (1 − Tc/Th)` of the heat crossing it, and a gradient the rig made
itself cost at least a joule per joule. Break-even needs a difference of
**372 K**; water boils at 100 and the rig faults at `IT BOILS` long before. At
a 96 °C self-made gradient the loop still returns only **0.20 per joule**.

And the contrast that says what the modules are *for*. Standing 128 m off in
cold water with the coil line run into a vent's plume — which is the play
pattern, because the heat is one cell *above* the vent where buoyancy put it:

| run off a vent, 60 s | |
|---|---|
| the tap | **+5.46 units** |
| sonar | **+5.19** |
| a thruster | **+2.47** |
| a refrigerator | −406.53 |

A vent pays for propulsion, sound and gas indefinitely and never pays for
heavy thermal work — so it is worth walking to and it does not end the
economy. And tapping it **cools it by 1.02 °C** against an untapped one,
because taking power out of the water means the water has less.

### 12.7 Movement, because the ocean had no velocity

The diver flew. It had drag and a buoyancy term and everything else about it
was an object in a vacuum with the numbers turned down — **drag was measured
against the ground**, so the ocean might as well have been still, and it was,
because the medium tracked temperature, gas, bubbles and a sound speed and no
velocity at all. Water that does not move is not water.

**`Medium.flow_at` invents nothing.** The vertical part is the buoyancy
`_buoyancy` already applies to heat, read as a speed instead of as a
transport. The horizontal part is not modelled, it is *deduced*: the flow is
incompressible, so `du/dx = -dv/dy`, and integrating that along each row gives
the only horizontal flow consistent with the vertical one. That single
constraint is what makes a plume a plume — warm water going up over a vent has
to be replaced, so there is an inflow beneath it and **a sinking return limb
beside it**. A test that assumed "away from the vent means nothing happens"
found the diver sinking 90 px. That is not a bug, it is a convection cell, and
a vent is not a hazard at a point but a circulation you have to navigate.

Four things separate swimming from flying, and all four are now there:

| | measured |
|---|---|
| **Drag reads speed through the WATER** | drifting: 5.02 px/s over the ground, 0.65 through the water. The same push carries you 258 px downstream and 163 px up |
| **Added mass** — you drag a comparable mass of water with you, so you accelerate as though twice as heavy while weighing what you weigh | 2.5 s to reach cruise, 5.9 s to coast down |
| **Anisotropy** — a diver is a long thing, and broadside it is a sail | 158 px pointed, 102 px broadside: **pointing is worth 55%** |
| **Trim** — a bladder: slow, free to hold, silent, vertical | 1.8 s to fill, 9.7 px/s climb, and holding costs nothing |

Added mass is the one that matters most and it is the one no amount of drag
tuning reproduces: **drag punishes speed, added mass punishes change.**

And a sheared background drift with a slow tide, which hands §9.1 one more
channel: 5.67 px/s at 40 m, 0.18 px/s at 700 m. **The shallows push you around
and the deep is your own problem** — so travel is a negotiation up top, and
down below the only thing moving you is what you built.

`KICK` had to change. It was 240 px/s² against an honest rig's 30, which made
flailing **four times faster** than the machine §8 exists to make you build,
and that inverted the premise of the entire game. At 4.0 a kick settles at
5.5 px/s against a rig's 23 — and just above the 5.7 px/s surface drift, so
crawling upstream in the shallows is the complete list of things flailing is
for.

**One real bug, and it had been there all along.** `_buoyancy` compared a
*bilinear* density sample against a *single row's* mean. Those are not the
same quantity — they differ by the stratification itself — so an undisturbed
column reported a 7 kg/m³ anomaly that flipped sign twice per cell, and a
diver trimmed to hover bobbed. It was invisible until trim made vertical
motion slow enough to watch. `Medium.density_anomaly_at` is now the one
definition, and still water is still to 1e-9.

### 12.8 The station is a place, not a menu

A place that is simply *safe* is a menu with a position, so the station is
built out of the same physics as everything else and the consequences are
allowed to be inconvenient.

**It is warm**, because a pressurised hull full of people leaks heat, and heat
in water does what heat in water does. So:

| | |
|---|---|
| the water at the door | 6.44 °C against 5.40 °C far off |
| a heat-hunting stalker's comfort there | **1.72**, against 1.00 in open water |
| holding still at the door for 8 s | **+85 px straight up** — home has weather |
| a refrigerator run at home | 3.37 °C out, against 2.72 °C the same rig makes 560 m away |

The safest place in the ocean is therefore the most conspicuous thing in it on
every channel a creature uses, there is a permanent updraft over the door, and
the cold you make at home is not as cold. Nobody authored any of that.

**Free power has a radius, and it is 300 m.** `sources.Source` already said
what a source is; the station is one with a big rate and a short reach. Four
seconds of thrusting leaves you at 97.6 air at the door and 36.9 air six
hundred metres out. That is §3.1's entire progression curve expressed as a
distance, and everything interesting happens outside the circle.

**A dive that can end came off the list on purpose.** It was on it in §12.2.
A run that ends is a structure imposed on top of the simulation, and
everything good in this project has come from letting the simulation say what
happens instead. The station is a place you want to be near; that is enough of
a rule, and air coming back at a rate rather than instantly is enough of a
clock.

### 12.6 What the suites say now

| suite | |
|---|---|
| `selftest_conservation` | **36/36** — including 6000 chains that cannot generate in uniform water, and 6000 more that never beat Carnot with a gradient |
| `selftest_sound` | **24/24** — the new one, and it exists because a playtester was right |
| `selftest_couple` | **25/25** |
| `selftest_density` | **9/9** |
| `selftest_creatures` | **20/20** |
| `selftest_selfpower` | **15/15** — the loop through the ocean, run rather than argued |
| `selftest_station` | **18/18** |
| `selftest_swim` | **28/28** |
| `selftest_diver` | 10/10 |

**175 checks**, against 80 when this pass started.

The station is built (§12.8), and "a dive that can end" was dropped on purpose.
What is still missing is the loop itself, which §13 designs — and the second
go/no-go question of §12, which is still open because it is the one a machine
cannot answer.

---

## 13. The loop

Everything above is a world. A world answers *what happens if*. A game has to
answer *what should I do*, and that is a different question that none of the
four previous designs ever reached.

The discipline is the one that produced everything good here: **the loop has to
be read off the simulation rather than laid on top of it.** §12.8 threw out "a
dive that can end" for exactly this reason. What follows adds two rules that
are not physics — the umbilical and the bank — and everything else in it is a
consequence of numbers already in the code.

### 13.1 The survival economy is two numbers, and food is not one of them

The test any meter has to pass: **does it create a decision the existing
systems cannot, or is it a second clock ticking while you do the same things?**

- **Air** is not a hunger bar, it is a *leash*. It says how far from home you
  can be, it is spatial, and it interacts with depth honestly.
- **Charge** is what machines eat, and §12.4's generators exist to take it back
  out of the water.

Both answer the same question — *how far out can I be* — from opposite ends,
and that is a complete economy. Hunger and thirst answer a question nobody in
this game is asking, and they pull it toward inventory management, which is the
genre's most generic organ. Iron Lung has **zero** survival meters.

**Food is in the world and not on the HUD.** §13.4 makes eating the thing that
positions the ecosystem, so knowing what eats what and where is how you predict
the ocean. You never eat. You read the things that do.

### 13.2 The umbilical, because air should not teleport

The station currently refills you by proximity, which is a menu with a radius.
It should be a **rope**: a physical line from the station carrying air, paid out
behind you.

| | |
|---|---|
| **the rope is the meter** | its length is your range, it is visible in the world, and it needs no number on screen |
| **it has drag, and the ocean has currents** | §12.7 gave the water a velocity. A long line in a tide pulls, and it pulls harder the more you pay out — so the leash fights you more the further you commit, and it fights *differently* depending on which way the tide is running |
| **it fouls, and it can be cut** | terrain, and teeth |
| **unclipping is the decision** | off the umbilical you are on bottles, and that is the moment the game changes |

That last row is the whole point. The leash is not a restriction, it is the
thing you choose to leave.

### 13.3 Yield is a place, not a depth

**This section is a correction, and the fault was real.** §9.1 says every good
thing gets better with depth, and the first sketch of this loop left it there as
the incentive to go deeper. It does not work, for a reason worth writing down:
**depth is uniform along a row.** If yield is a function of depth alone then
danger and reward are decoupled — you slide sideways along the isobath to
whatever `x` happens to be quietest and collect the same prize. There is never
a reason to push *through* anything.

The physics already disagreed and nobody was listening. §12.4 measured that a
thermopile in uniform water makes **exactly zero**, and that break-even needs a
372 K difference. **Cold water is not a resource. A gradient is** — and a
gradient is a *place*.

| site | what it is | and therefore |
|---|---|---|
| **vent** | a hot point in cold water. The richest, and permanent | it drives a convection cell (§12.7) — a rising plume with a sinking return limb either side — so working one means holding station in water that is actively moving you |
| **seep / brine** | cold, or chemically distinct | a different gradient, different neighbours, a different rig |
| **front** | a moving sheet where two water masses meet (`medium/front.py`) | it **moves**, so a good site found once has to be found again, and navigation beats memorisation |

Four consequences, and not one of them is authored:

1. **A point cannot be dodged sideways.** Reward and risk are finally the same
   coordinate.
2. **The best site in the ocean is, by construction, the most attractive place
   in it to the thing that hunts by heat.** `stalker.heat_hunter = 2.2` and its
   comfort is `exp(2.2 × anomaly)` — it climbs *exactly* the quantity that makes
   a vent worth standing on. `lantern.temp_band = (2, 8)` makes the same vent a
   wall. One number each, and no spawn table anywhere.
3. **Depth is the multiplier, not the resource.** Colder surroundings mean a
   bigger ΔT and a better yield, so the sites order themselves by depth — and
   the rich ones are the ones furthest from the umbilical.
4. **Working a site degrades it, and this is already implemented.**
   `Thermopile.apply` takes `q` out of the water and `couple.py` writes the
   consequence back into the medium. Extracting heat from a plume **cools the
   plume**. So the near vents exhaust as you work them, and recover on
   `_diffuse_heat`'s own timescale.

Point 4 is the answer to *why push further*, it costs nothing to build, and it
is the good kind of answer: **the ledger pushes you outward, not a designer.**
It has to be measured and tuned, not written.

### 13.4 The cycle: everything arrives, nothing hunts

The obvious ecosystem — predators seek prey, prey flee predators — is a
**chain**, and a chain has a head attracted to something that only runs and a
tail attracted to nothing. Chains diverge. Prey end up against the map edge,
predators follow, and the player never sees either.

A **closed loop of attraction** has no head and no tail:

> carrion → scavengers → decomposers → filter feeders → prey → predators → carrion

Three rules make it work:

1. **Every link attracts, and the loop closes.** Nobody hunts; everybody
   *arrives*. Predation becomes a consequence of aggregation rather than of
   pursuit, which is how a bait ball actually forms.
2. **Avoidance exists, but only at short range.** Drawn toward the aggregation
   from 400 px, fleeing a predator within 40. Long-range attraction with
   short-range repulsion is the classic flocking rule, and it produces a dense
   knot with panic churning inside it.
3. **It is carried by fields, not by creatures perceiving creatures.** A carcass
   writes `chum` into the medium; it diffuses and decays exactly as heat already
   does. Scavengers read `chum`, their feeding leaves `nutrient`, filter feeders
   read that, and so on round.

Rule 3 is non-negotiable, because it keeps §9's one rule intact — creatures
still read only fields — and it buys two things free: the range laws of §9.0,
and **an instrument that can read the cycle**. A rig that senses chum is a
hunting tool. The ecosystem becomes something the vocabulary can reach.

And it makes **death a resource that propagates**. A kill is not an enemy
removed, it is a dinner bell that stays rung for minutes — so you can *seed* the
cycle, dropping a carcass to pull the whole ecosystem somewhere else and clear
the water where you actually mean to work.

### 13.5 What you actually look at

**A correction: sonar is a sense, not a renderer.** An earlier draft made it the
primary display, which is wrong — nobody wants to watch a line waving for an
hour, and Iron Lung works precisely because its sonar is a *still image you take
occasionally*. The camera stays close to the diver. Four layers, and none of
them is a live sweep:

| range | what it is | and the cost of using it |
|---|---|---|
| **near** | your eyes, and a lamp. Rendered water, where nearly all playtime is | light is safety and exposure on one switch — the Darkwood generator, and `heat_hunter` is already the term a light-hunter would use |
| **readings** | **the rig itself, raised into frame** | it occupies your hands and your view. You cannot see past the thing you are reading — informed and vulnerable become the same action |
| **continuous** | sound. A hydrophone that clicks faster near chum | zero screen space, maximum dread. The station already hums at `STATION_NOTE = 117.0`, and `Station.bearing_from` already exists as "the answer that instrument would give" |
| **far** | a sonar **still** — one frozen, low-information frame you study, and that fades | expensive, deliberate, four times a dive. And §9.0 measured that a groan pulls a shoalfish 260 px, so looking is being found |

The load-bearing idea is in row two: **the instrument face is
`Chain.describe()`.** What your rig is built out of decides what it can tell
you — a thermopile gives you a needle for ΔT, a chum sense gives you a bearing.
**Your interface is a thing you engineered**, which puts navigation, engineering
and whatever the lore turns out to be on a single upgrade path.

### 13.6 Two clocks, and the rule that makes them matter

There is no day at 600 m, and a day/night cycle would be a clock painted on top
of the simulation. But the *structure* of Darkwood's night — a rhythm you can
see coming, that changes the verb, that you choose how to meet, and that
punishes cutting it fine — is reproducible from what is already running:

| | | built? |
|---|---|---|
| **the tide** decides when travel is cheap, and which way | `TIDE_PERIOD_S = 240`, sheared by `DRIFT_DECAY_M` so the shallows carry you and the deep does not | already running |
| **the scattering layer** decides where the ocean is full | a `depth_band` that breathes on a cycle. Real: the diel migration, the largest on Earth, found by wartime sonar as a false bottom that moved | one term |
| **home is night** | the bench *is* the barricade phase — build rigs, and listen | already there |

And the one rule that turns all of it into a bet:

> **The pack banks only when you dock.**

Charge generated at depth rides in the field pack and enters the station's
reserve at the door, or not at all. That single rule is what makes *one more
minute* a decision, and it is the only part of Darkwood's night worth copying.

Because the station **consumes** — light, pump, heat — home is a drain rather
than a safe room, and every dive has a quota. The loop closes:

| | already built |
|---|---|
| the station burns charge, so you must dive | `Station`, `Economy.charge` |
| charge needs a gradient, and gradients are sites (§13.3) | §12.4, `Thermopile` |
| generating means running a rig, which is hot and loud | `couple.py` writes it into the water |
| heat and noise call the cycle, so the water gets busy where you work | `heat_hunter`, §9.0's range laws |
| the swim home is priced by the tide | `TIDE_PERIOD_S` |
| **and none of it counts until you dock** | one rule |

The greed moment writes itself: *the pack is at 32 of 40, the station needs 35,
you have been generating on this vent for four minutes, and the tide turns in
forty seconds.* One design requirement follows — **greed must be informed.** The
pack filling and the water getting busy have to be legible at the same time, or
the bet is a coin flip.

### 13.7 Performance, measured rather than feared

`METRES_PER_PIXEL = 1.0` and the ocean bottoms out at **792 m**, so depth is
capped by design and cell count grows in one dimension only. Measured, with the
medium stepped at 15 Hz:

| ocean | cells | field + flow | cost |
|---|---|---|---|
| 1.2 km × 800 m | 3,750 | 0.55 ms | 0.8% of a core |
| 4.8 km × 800 m | 15,000 | 3.02 ms | 4.5% |
| 9.6 km × 800 m | 30,000 | 5.06 ms | 7.6% |
| **19.2 km × 800 m** | 60,000 | 9.51 ms | **14.3%** |

Creatures cost **0.016 ms each** — a hundred of them is 1.6 ms a frame. And
§13.4's extra channels are nearly free: one more diffusing scalar is **0.274
ms**, or **0.41% of a core** at 15 Hz, so six of them stay under 3%.

**One decision falls out of this: the medium is not stepped at the frame rate.**
At 15 Hz a 4.8 km ocean costs 4.5% of a core; at 60 Hz the same ocean costs 18%
and recomputes `flow_field` four times for a field that has not meaningfully
changed. Nothing in `_diffuse_heat` moves in 16 ms. The decoupling is
physically right and it is worth a factor of four.

The concern was reasonable, and the answer is that a **nineteen-kilometre**
ocean runs in a seventh of one core. Performance is not what will kill this.

### 13.8 What could, and the tests that are allowed to say so

In the discipline of §12 — cheap, headless, and permitted to fail:

1. **Does the cycle aggregate on its own, or does it smear?** Run §13.4 with no
   player for ten minutes and measure clustering. If a closed attraction loop
   does not form a travelling knot, everything above it is decoration.
2. **Does a worked vent exhaust on a timescale that moves anybody?** §13.3's
   point 4 is the entire reason to go further, and it is currently a prediction
   about `Thermopile` and `_diffuse_heat` rather than a measurement.
3. **Diagnosis**, still open from §12, and still the one a machine cannot
   answer.

### 13.9 Building the cycle, and the five ways it failed first

§13.8's first test is built and green — `selftest_cycle`, **24/24**. It failed
five times on the way, and every failure was a different wrong idea about the
same system, so they are worth more than the working version.

| | what happened | what it cost |
|---|---|---|
| **1. Total collapse** | comfort used `exp(gain · min(6, v))` by analogy with the bubble and heat terms. Channels reach 10 where creatures pile up, so the response **saturated**, and a saturated region is flat | every species at a radius of gyration under 2 px, all five on one centroid. Grazers could not tell which way was away from a hunter because `menace` was clamped too |
| **2. Nothing to eat** | fifty creatures feeding at 1 unit/s against a world fed 1.4 | every channel stripped to ~0.001, where `(1+v)^gain` is 1.001 and the ocean's temperature structure decides everything |
| **3. Nothing to smell** | fixing (2) by making channels tighter than heat | detection range ~200 px. Past it the field is under `CHANNEL_FLOOR`, the gradient is **exactly** zero, and a creature *freezes* — `step` only accelerates on a gradient and drag takes the rest |
| **4. Nowhere better to be** | the cycle fed by snow falling at uniform random | nothing clustered, in three separate tunings |
| **5. A signal that pays for nothing** | presence channels are written whether or not a creature ate — but a hunter *eats* `shoal` and turns it into `chum` | **60 units of channel became 722 with nothing feeding the world at all.** A food web running on itself, which is §12.5's perpetual motion machine with fins |

Failure 1 replaced the exponential with **`(1 + v)^gain`** — 1.0 at zero,
monotone forever, never flat, and it cannot overflow at any value a channel can
reach, so there is no clamp and therefore no flat spot.

Failure 3 is the one that changed the medium. **A smell in water is not spread,
it is carried**, so `Medium._advect_channels` puts every channel on the
current in conservative upwind flux form (measured drift over 600 steps:
4.3e-16). Which means **the tide of §13.6 decides what you can smell and from
where**, and approaching a thing from downstream is a different proposition
from approaching it from upstream. That coupling did not have to be written; it
is one flux term. A creature with nothing to read also had to start *searching*
rather than stopping — `WANDER`, gated on foraging so §9's four species stay
exactly as `selftest_creatures` measured them.

Failure 4 is the important one, because it is §13.3 arriving from the other
side. **Evenly distributed food cannot produce an aggregation** — there is
nowhere better to be. The base of a food web has to be a *place*, so `Seep`
exists: chemosynthesis, which is what a real vent community runs on. And now
the thing this design has been circling is true by construction rather than by
arrangement:

> **The best generator site, the most attractive place in the ocean to a
> heat-hunter, and the base of the food web are the same coordinate.**

Nobody made that true. It is three systems reading the same hole.

Failure 5 forced the distinction the model was missing. `chum`, `nutrient` and
`bloom` are **substances** — produced by working on something else, so they
attenuate down the pyramid the way trophic transfer does. `swarm` and `shoal`
are **presence** — the fact that there are drifters or grazers here, findable
because they exist. Routed through substance they arrived at the top at a fifth
of readable strength and the hunters ended up *more dispersed than random*.
Given away free, they were a doorway from nothing into the substance chain. The
fix is `condition` — a creature only advertises while it is fed — plus holding
every signal rate below the feed rate of whatever emits it. `menace` is exempt
and louder, because **nothing eats it**, and a channel that is never consumed
cannot leak.

`condition` also buys §13.3's point 4 for the ecosystem: **work a place hard
enough and it goes quiet**, because the things living there thin out, not
because anybody set a timer.

#### And one measurement mistake, which cost a whole tuning pass

Clustering was first measured as a **radius of gyration** — spread about a
single centre. With food at three seeps, perfect aggregation still reads as a
large number, so a working ecosystem was scored as a failure and "fixed" twice.
Everything is now a mean nearest-neighbour distance against a random-placement
control, and nearest-neighbour is only read where n ≥ 6, because with four
hunters in a 900×700 ocean it measures geometry rather than behaviour.

#### What it does now

| | measured against a random control |
|---|---|
| decomposers | **3.4× clumped**, 3.6× closer to a seep |
| grazers | **3.5× clumped** |
| hunters | 3.2× closer to a seep |
| **grazers keep off the seeps the hunters sit on** | the long-range/short-range split of §13.4 at ecosystem scale |
| a pinned hunter thins a shoal | **+176 px** of standoff, with no code for fleeing |
| scavengers cross the map to a carcass | and a body **sinks** while they do it, so the shallows feed the deep |
| a plume | **2.6× lopsided** along its row — the tide decides who smells it |
| taking the seeps away | removes **x1.58** of the aggregation |

That last row is the thinnest margin in the suite and it is honest about why:
**uniform food is not achievable in water that moves.** The same mass added to
every cell gets carried by the tide and piled up wherever the flow converges,
so a perfectly even snowfall is a patchy field two minutes later and the
decomposers gather on it at twice chance. Convergence zones concentrate food —
which is why a front is worth anything in a real ocean — and it arrived out of
a flux term written for a different reason entirely.

#### One correction to §13.7

That section predicted an extra diffusing channel at **0.41% of a core**, from
measuring `_diffuse_heat` alone. Six real channels cost more than six times
that, because advection is not free:

| ocean | bare | with 6 channels | at 15 Hz |
|---|---|---|---|
| 1.2 km | 0.27 ms | 1.52 ms | 2.3% of a core |
| 4.8 km | 1.05 ms | 4.50 ms | **6.8%** |
| 9.6 km | 2.06 ms | 8.76 ms | 13.1% |

So the real figure is about **1.4% of a core per channel** at 4.8 km, not 0.41%
— three and a half times my estimate. The conclusion of §13.7 survives it
comfortably: a 4.8 km ocean with a full ecosystem in it runs in under a
fifteenth of one core, and the decoupling from the frame rate is what pays for
it.
