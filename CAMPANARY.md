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

Each foe exists to punish one specific habit. The first cut of the roster was
polite - everything telegraphed, everything dodgeable, and nothing at all
happened if you ignored all of it, because contact did 13 damage against 100
health on a 0.8s cooldown. They were busywork with a colour.

**The pulse is now the attack clock.** Every foe already showed a ring on its
own note's tempo as an identify cue; that ring now *closes* and the foe acts
the frame it lands. So the thing telling you which bell to bring is the same
thing telling you when to move, and reading a room is one act instead of two.
Cadence is separated from the clock by `attack_every`, because a
SPARROW-tuned enemy ticks five times a second and a room-covering shockwave
five times a second is weather, not a fight.

| | note | clock | punishes |
|---|---|---|---|
| **Husk** | TENOR | 0.8s | **standing still.** Commits to a lunge it cannot steer out of; the lunge is a quarter of your health |
| **Glasswing** | CHIME | 0.4s, dives on every 2nd | **keeping your distance.** Its note reaches 155px, so it cannot be answered from safety by anyone |
| **Deadweight** | *none* | 1.6s | **forgetting where it is.** Cannot be shattered at all; stomps a shockwave that owns the ground it stands on |
| **Twin** ×2 | detuned pair | 0.8s, beams on every 2nd | **standing between things.** Bonded, they eat every note; they actively straddle you with a live standing wave. Shove them apart and the bond breaks *for good* |
| **Overtone** | SPARROW | 0.4s, tolls on every 4th | **greed.** Drags you in; crack a bell inside its reach and it feeds - heals and quickens |
| **Great Bell** | TREBLE | 3.2s | **carrying one bell.** Tolls a phrase; matched fronts cancel; answering it all opens the only crack window |

The counterweight is the health economy: three or four connected attacks
kill, and a resonant shatter heals 7. That pairing is the whole thing - the
game pays for the play it wants to teach rather than punishing the play it
wants to discourage.

Two numbers in that system were simply broken and only measurement found
them. A point-blank TENOR ring threw a Deadweight at **543px/s against a
560px/s slam threshold**, so the only kill the unshatterable enemy has could
not be triggered by the bell the player starts holding - not hard, off by
three percent, and the symptom was a foe that never died. And the Twins'
bond was recomputed from live distance every frame, so a pair shoved apart
snapped back together a third of a second later and "break them apart" named
something that could not be done.

## 9. The Foundry: shapes, a target, and the wave in the metal

The first version of this screen asked you to draw a circle freehand with a
mouse and then told you, accurately, that you had failed. That is a dexterity
test standing between the player and the system, and the system is the point.

**Drawing is made of shapes now, and the shapes snap to the note ladder.**
RING is press-centre-drag-out with the radius sticking to the notes already
printed on the canvas. ARC is drag out then sweep, where the direction you
sweep *is* the winding and going past a full turn closes it into a bell -
chirality taught by the gesture that produces it. LINE snaps to 15° and to
existing stroke ends, because a horn that does not quite touch the ring is a
horn that does nothing and finding that out used to cost a trip downstairs.

**And nothing is final.** Hovering a stroke highlights it; the wheel retunes
a ring in place while the tuner needle moves under your hand. That is the
nudge-look-nudge loop the whole design wants, and it was previously
impossible - you could only delete and redraw.

Two things it has that the old screen did not:

1. **A target.** The peal of the room ahead - the actual notes of the actual
   things down there - is on the screen. Drawing is closing a gap. That is
   also the real fix for the old build's brute-force problem, because "you
   can draw anything and it works" was never a balance failure; it was the
   absence of anything to aim at.
2. **The wave, drawn in the metal.** `Bell.wave_samples()` maps the
   simulation's own delay-line buffers onto the polyline the player drew, so
   striking a bell makes the pulse visibly race round the ring, meet itself
   and stand. That is not an illustration of resonance. It is the buffer.

## 9a. Effects

The old build had a shake, a hitstop and seven kinds of expanding circle.
Circles are good at saying *where* and terrible at saying *what*: a
wrong-note thud and a correct-note crack were two circles of different
colours, so the most important teaching signal in the game arrived as a hue
change on a shape you had seen a hundred times.

`fx.py` is a flat particle list whose job is to make three things feel
physically different - a matched hit throws bright shards of the target's own
colour, a wrong note puffs dull grey and dies, a shatter empties the thing
into the room. Damage feedback is an **edge vignette** rather than a
full-screen wash, because a tint covering everything arrives at exactly the
moment the player most needs to see the arena; and washes are combined into
one capped blit, since blitting each separately meant N good moments tinted
the screen N times over and the cost of a kill was not seeing the next one.

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
   TOTAL                     2/33     13/33     24/33     31/33
```

- **masher** ignores note, beat and range: 2/33. It clears the tutorial,
  which is the point of a tutorial.
- **ringer** adds the beat: 13/33.
- **tuner** adds matching the note and closing to its reach: 24/33. It
  cannot beat the Great Bell, because it never casts the bell it demands.
- **founder** adds casting for the room and swelling for the octave: 31/33.
  The two it loses are the peak of the curve, and it dies to them rather
  than running out of time.

Monotone at every step. If the first and last columns ever converge, the
system is decoration and the harness says so out loud.

Frame cost in the worst room: **0.12 ms/step**, 1.4% of a 120Hz budget.

## 13. Complexity budget

| | WAVEWRIGHT | CAMPANARY |
|---|---|---|
| notes / bands | 6 | 5 (4 drawable) |
| run structure | 3 acts, rewards, an anvil clock | a list of waves |
| materials | 6 inks | 3 metals |
| carried instruments | 4 foci | 3 bells, from the first second |
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

## 15. Structure, and what it is not

This was a roguelite: three acts, a reward screen, metals as loot, an anvil
on a twelve-second clock. That structure is not what the game is for and it
was absorbing effort that belongs in the two things that carry it - shaping a
bell and fighting with it.

It is now a list. Everything is unlocked from the first second, you carry
three bells, the budget never changes, the Foundry is open between every wave
with no timer, and past the end of the list the waves keep coming with more
in them. The only rule the ordering obeys is dependency: a wave may not
introduce a foe whose answer has not already been available. That is not
level design, it is just not teaching things in the wrong order.

The arena also shrank, from 1750x1180 to 1520x980. There is no aiming in this
game, so what the player chooses is *where to stand* - and a room they cannot
see is a room they cannot choose a place in. Anything still off the edge gets
an arrow at the screen border in its own colour, brightening as its attack
lands.

## 16. What is still open

- **The playtest bot is a floor, not a ceiling.** It dashes reactively off a
  single rule and never plans a slam, so its 31/33 understates what a person
  can do and its two losses (TWIN OVERTONE, THE LAST BELL) are the two waves
  where several demands conflict at once. That conflict is the point; the
  numbers around it are the least trustworthy in the harness.
- **Silver is still the best swell metal** - it releases hardest, which is
  arguably right for "everything at once", but it means the rhythm/burst
  choice only really bites when tapping.
- **The Great Bell is the only foe that does not fit the punish-a-habit
  frame.** It punishes carrying one bell, which is a loadout decision rather
  than a moment-to-moment one, so it reads as a puzzle in the middle of a
  brawl.
- **Nothing carries between sittings.** The codex saves the bells you were
  holding and nothing reads them back.
