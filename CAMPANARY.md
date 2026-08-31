# CAMPANARY — the redesign

`sigil-wave-design.md` specifies a simulation. `GAME_DESIGN.md` specifies
WAVEWRIGHT, the first game built on it. This document specifies the second
one, and records what was wrong with the first.

Run it: `python play.py`

---

## 1. What was actually wrong

WAVEWRIGHT worked. Its harness passed, its gates were real, its physics was
excellent, and it was not fun. That combination is the interesting part, so
it is worth being precise about the causes rather than calling it "feel".

### 1.1 The authoring loop had minutes of latency

Drawing happened in the Forge. Consequences happened in the Field, one
descent later. Nothing learned under fire could be acted on under fire, so
the authoring layer — the entire point of the project — was a thing you
visited between the parts of the game where anything happened. A system you
cannot iterate on is a system you cannot learn.

### 1.2 The hands had nothing to do

The attack was a stream of small projectiles resolved by a spectral dot
product against a health bar. A stream has no *moment*: no frame where the
hit happens, nothing to freeze on, nothing to punctuate. All the depth was
in the numbers and none of it was in the input. Four verbs existed (tap,
hold, relay, quench) and none of them had a wind-up, a contact, or a
recovery.

### 1.3 Complexity was presented as instrumentation

The Assay said things like `output centred on band 1.3 (low), efficiency
40%`. Every word true; none actionable. There were roughly fifteen live
systems — six bands, six inks, impedance, saturation, char, glut, surges,
phase, chirality, coupling, relays, barriers, aura, the field grid,
detonation — each costing the player a concept, most of them never used to
make a decision.

### 1.4 "You can draw anything and it is strong" was not a balance bug

It was the absence of a goal. A blank canvas with nothing to aim at makes
every drawing equally valid, so there is no craft to find. WAVEWRIGHT tried
to fix the symptom with **glut** and **surges** — off-band energy healing
and enraging the target. That punishes wrong play, which is not the same as
making right play feel good, and it required three interlocking systems to
enforce something that should have been self-evident.

---

## 2. The fantasy, and why it is the largest single fix

**You are a bell-founder.**

The simulation already *was* a bell and nobody had named it:

| the simulation | a bell | what the player already knows |
|---|---|---|
| `f0 = dx/L` — circumference sets pitch | bell size sets pitch | big bell = deep boom |
| low bands survive the air | low notes carry | the cathedral bell across town |
| high bands die in two body-lengths | high notes don't carry | a handbell down the street |
| junction saturation → harmonics | ring it hard, it sounds its octave | — |
| char / runaway | ring it too hard, it cracks | yes |
| two detuned loops beat | two bells beat | yes |
| resonant shattering | the note that breaks glass | **everyone knows this** |

This is worth more than any UI work. WAVEWRIGHT had to *teach* frequency.
CAMPANARY says "bell" and the intuition is already installed. Same physics,
no tutorial, and a kill fantasy — *things made of resonance, that shatter at
their note* — that rewards understanding with the best moment in the game
rather than punishing its absence.

## 3. The ladder

Five notes, **exact octaves**, chosen from the drawable end backwards.

| | ring | radius | reach | tolls every | audible |
|---|---|---|---|---|---|
| BOURDON | 640px | 102px | 520px | 1.60s | A1 |
| TENOR | 320px | 51px | 360px | 0.80s | A2 |
| TREBLE | 160px | 25px | 240px | 0.40s | A3 |
| CHIME | 80px | 13px | 155px | 0.40s | A4 |
| SPARROW | 40px | 6px | 100px | 0.40s | A5 |

Octaves are load-bearing three times over:

* One note up is one **halving** of the ring, so size and pitch are the same
  visible fact and the ratio is legible on the canvas.
* The saturating junction's strongest product is the **second harmonic**,
  which lands exactly one note up. "Drive it hard and it climbs a note" is
  not authored — it is what doubling is.
* **SPARROW is one octave above the smallest ring a hand can draw.** It is
  reachable only by folding a CHIME upward, so the game's one hard gate
  gates itself.

Five, not WAVEWRIGHT's six: a sixth band bought one more colour and halved
every drawable ring. Four drawable notes an octave apart is a ladder you can
see; six crowded ones is a gradient you read off a chart.

## 4. Resonance breaks. Force moves.

Health is deleted. Everything has a **crack meter**.

A health bar makes every attack partially correct, and partially correct is
survivable — which is the entire mechanism by which WAVEWRIGHT could be
brute-forced. A crack meter makes the wrong note not *weak* but **a
different verb**:

- an on-note ring fills crack fast → **SHATTER**
- an off-note ring fills nothing at all → and **shoves**, hard

Shoving is a real kill path: things thrown into walls or into each other
crack on impact, and DEADWEIGHT has no note and can be killed no other way.

So there is no penalty for brute force anywhere in the game. `glut`,
`surges`, `SURGE_HEAL_CAP`, `GLUT_FORGIVE` and the Ward's reflection wall are
all deleted — about 120 lines of anti-player machinery replaced by one rule
that makes the correct play the *attractive* one instead of the mandatory
one.

## 5. The ring

The attack is an expanding annulus centred on the player, and this is the
change that carries most of the feel.

* **It has one moment per target** — the frame its edge crosses them. That
  frame is where the hitstop, the flash and the shatter live.
* **It is omnidirectional**, so the skill is *distance*, which is exactly
  what the note ladder encodes. Aiming is gone. You stand somewhere.
* **It cools as it travels.** High components die within a body length, so
  one ring shows the entire range law in one animation: it leaves white and
  arrives blue.
* **Open ends bias it** rather than becoming projectiles. The drawn shape
  still shapes the attack, but the worst possible drawing produces a ring
  that is merely even — never one that misses everything.

## 6. The beat

Every bell's round trip `L/c` is a real tempo the simulation already had.
Surfaced as a ring collapsing onto the bell; strike as it lands and the loop
genuinely reinforces, so the pool the next ring takes is fuller. None of the
compounding is a bonus applied afterwards.

Forgiving groove: ±0.11s window, off-beat still does 40%, consecutive
on-beat strikes build a chorus multiplier to ×2.0 that is lost on a hit.

Small bells play on every second or fourth swing rather than being clamped
to a floor. That was not cosmetic: a flat 0.26s floor put every strike on a
CHIME a third of a cycle out of phase with its own 0.2s loop, so what
compounded was the *second harmonic* — measured, a tapped CHIME emitted 94%
SPARROW and could not play its own note at all.

## 7. Sound

Every tone is synthesised at runtime from the frequency that produced it,
using real bell partials (hum, prime, tierce, quint, nominal). Foes hum
their note on a slow cycle.

This is not decoration. Reading a note off a coloured bar is a translation
step, and translation steps are where understanding leaks. Pitch needs no
translation, so the identify layer costs no UI and the game is fully
playable with the sound off, without fine colour discrimination, or by a
player who has only noticed one of colour / tempo / pitch.

## 8. The roster

Each foe exists to demand one verb the player would not otherwise use.

| | note | demands |
|---|---|---|
| **Husk** | TENOR | reading a telegraph; the first shatter |
| **Glasswing** | CHIME | letting it come to you — a high note has no reach |
| **Deadweight** | *none* | shoving. Nothing will ever ring it |
| **Twin** ×2 | detuned pair | force *then* resonance — the bond eats every note until you break it apart |
| **Overtone** | SPARROW | the swell. It sits an octave above any drawable ring, and it drags you in |
| **Great Bell** | TREBLE | answering a phrase in its own note; matched fronts annihilate |

The Great Bell is TREBLE rather than BOURDON on purpose: a BOURDON is a
640px ring and costs an entire starting budget, so tuning to it would make
the act-one boss a wall. TREBLE is cheap, is *not* what the player starts
holding, and is named on the anvil beforehand — so the gate is "cast one new
bell", which is what the act was teaching.

## 9. The Foundry has a target

Two changes turn the drawing screen from homework into craft:

1. **The peal of the room ahead is on the screen** — the actual notes of the
   actual things down there. Drawing is closing a gap.
2. **The readout is a tuner** — needle, note name, cents flat or sharp. No
   prose, no efficiency percentage. Everyone can read a guitar tuner, and
   nudge-look-nudge *is* the hill-climb that teaches that circumference is
   pitch.

Plus **the anvil**: the same screen on a twelve-second clock between waves.
Authoring latency drops from minutes to seconds.

The note ladder is printed on the canvas at actual size, so "I want that
note" and "draw this big" are one instruction. Closure is assisted to 30px
(the parser's own snap is 8px, a fine tolerance for a machine and a cruel
one for a mouse) with a live marker saying *let go here and this is a bell*.

## 10. What the simulation gave, and what had to be corrected

`sigilwave/sim/` is **unmodified** and still passes all 34 of its checks.
Four corrections live in the game layer:

**Body radiation.** A closed loop in the raw simulation has no terminal, so
it stores beautifully and radiates nothing — making the first thing every
player draws the one thing that does nothing. A bell is a closed shell that
sounds through its whole body, so the near field is the primary output path
and a fraction of stored energy genuinely *leaves the network* each step.
Without that, output was bookkeeping invented alongside the physics: measured,
a bell struck on its own beat climbed from 2.5 to 132 units in six strikes.
With it, compounding settles around 3× and the meter is conserved.

**A zero-mean strike.** The sim's raised-cosine burst is unipolar, so half
its energy is at DC and every strike landed on BOURDON regardless of what was
drawn. Windowing one full sine cycle keeps the smooth edges and hands note
selection back to geometry.

**Radiated amplitude, not junction pressure.** Radiated amplitude goes as
`u_j·√Y_rad`; a nearly-sealed terminal holds a *large* pressure precisely
because so little escapes, so analysing raw `u_j` inverts every material.

**The exchange rate applied once, not per band.** A loop genuinely rings at
its harmonics, so a TENOR carries a few percent of its energy an octave up.
Multiplying that few percent by the small bells' 21× exchange rate made
leakage lethal — measured, a TENOR killed a CHIME-tuned Glasswing in four
strikes, and the gate the whole game rests on was leaking through the balance
table. Matching the normalised *shape* and scaling by the ring's own note
keeps "how right is this note" and "how much of it is there" apart.

## 11. The two numbers the game is allowed to choose

Everything else is physics. These two are measured, not opinions:

- `notes.NOTE_POWER` — the measured inverse of energy-per-strike across the
  ladder, so an on-note strike is worth about the same wherever it lands.
  The *difficulty* of the small bells is not expressed here and must not be:
  it is already expressed as reach, on the floor, where it can be seen.
- `rings.CRACK_SCALE` — one number, set so a settled on-beat strike from the
  right bell takes a third of its target.

`python -m sigilwave.campanary.calibrate` prints what they should be.

## 12. Does understanding pay?

`python -m sigilwave.campanary.playtest` plays every wave with four bots,
three seeds each. Each bot knows exactly one more thing than the last.

```
   wave                    masher    ringer     tuner   founder
   First Toll                2/3      3/3      3/3      3/3
   Dead Metal                0/3      0/3      3/3      3/3
   Glass Air                 0/3      3/3      3/3      3/3
   THE GREAT BELL            0/3      0/3      0/3      3/3
   The Pair                  0/3      3/3      3/3      3/3
   Weight and Wing           0/3      3/3      3/3      3/3
   The Overtone              0/3      0/3      3/3      3/3
   THE SECOND BELL           0/3      0/3      0/3      3/3
   Full Peal                 0/3      1/3      3/3      3/3
   Twin Overtone             0/3      0/3      3/3      3/3
   Dead Choir                0/3      1/3      3/3      3/3
   THE LAST BELL             0/3      0/3      0/3      3/3
   TOTAL                     3/36     12/36     27/36     36/36
```

- **masher** ignores note, beat and range: 3/36. It clears the tutorial,
  which is the point of a tutorial.
- **ringer** adds the beat: 12/36.
- **tuner** adds matching the note and closing to its reach: 27/36. It
  cannot beat a boss, because it never casts the bell the boss demands.
- **founder** adds casting for the room and swelling for the octave: 36/36.

Monotone at every step. If the first and last columns ever converge, the
system is decoration and the harness says so out loud.

Frame cost in the worst room: **0.08 ms/step**, 1% of a 120Hz budget.

## 13. Complexity budget

| | WAVEWRIGHT | CAMPANARY |
|---|---|---|
| notes / bands | 6 | 5 (4 drawable) |
| materials | 6 inks | 3 metals |
| carried instruments | 4 foci | 2 bells (3 with a reward) |
| combat verbs | tap, hold, relay, quench, dash, aim | toll, swell, dash, swap |
| live systems | ~15 | 4 |
| anti-brute-force systems | 3 (glut, surge, reflection) | 0 |

The four that remain: **size is pitch**, **winding is push or pull**, **ring
it hard and it climbs an octave then cracks**, **three metals**.

Cut from the surface, not from the simulation: relays, drawn barriers, the
aura, the fire/wind/phase field grid, glut, surges, efficiency percentages,
impedance prose.

## 14. The metals, measured

| | first strike | settled | still ringing after 1.2s | octave in |
|---|---|---|---|---|
| **Bronze** | 4.0 | 32.7 | 163% | 1.11s |
| **Silver** | 8.5 | 30.0 | 57% | 1.37s |
| **Blackglass** | 3.1 | 9.8 | 13% | 0.91s |

Bronze rings on after you stop. Silver opens twice as loud and is empty by
the next bar. Blackglass is poor at everything except reaching the octave,
which it does soonest, sitting at 0.75 char while it does it.

That table took a units fix to become true. The network measures stored
energy as `sum(buffer²)·admittance`, so reading the radiated amount straight
off it counted admittance twice — once in the energy and once in the
radiating fraction — and handed every low-impedance metal a flat multiplier
for free. Silver measured 4.8× louder than Bronze on the first strike *and*
5.7× louder settled: not a tradeoff, just the best metal, and the exact
opposite of the one thing it is supposed to be.

## 15. What is still open

- **The Overtone takes ~27s solo** in the harness. That is a long elite; its
  cap or the swell's payout could come down.
- **Twins never appear more than one pair at a time**, so their lesson is
  taught once and never tested under pressure.
- **Silver is still the best swell metal** (it releases hardest), which is
  arguably right for "everything at once" but means the rhythm/burst choice
  only really bites when tapping.
- **No run-to-run persistence of bells.** The codex has a `kept` list and
  nothing writes to it.
