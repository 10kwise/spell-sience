# WAVEWRIGHT — the game built on Sigil/Wave

`sigil-wave-design.md` specifies a simulation. This document specifies the
game that sits on it, and records what had to change in the simulation to
make a game possible at all.

Run it: `python play.py`

---

## 1. The problem the design doc does not solve

The physics was finished, tested, and had no game in it. That is not a
criticism of the physics — it is very good physics — but the doc's own build
order stops at "steps 1-5 are the vertical slice", and a vertical slice of a
wave simulator is a wave simulator.

The specific thing blocking a game is a timing mismatch, and it is fatal if
ignored:

> **Drawing a circuit takes thirty seconds. Action combat gives you a third
> of one.**

Every design that ignores this produces the same failure: the player draws
one sigil in the first minute and then never draws again, because there is
never a moment where stopping to draw is survivable. The authoring layer —
the entire point — becomes a menu you visit once.

**The resolution, and the spine of everything below: you never draw under
fire. You *play* what you built.**

Drawing is a slow authoring act in a safe mode. Combat asks a completely
different question — *can you operate this instrument?* — and the sim's
strangest property is what makes that question interesting.

## 2. Why that split works here specifically

Most action games are stateless. You fire, the bullet exists, the bullet is
gone. This simulation is not: energy is *stored*. A loop rings for seconds.
Repeated on-beat strikes compound. A sustained drive pumps a resonator until
its junctions fold into saturation.

So a sigil is not a gun, it is an **instrument**, and the skill of playing it
is real and continuous even though the drawing happened minutes ago:

- **Tap** — cheap, broadband, immediate, no risk.
- **Hold** — expensive, ramps into overdrive, narrowband, and chars the ink.
- **Rhythm** — a loop's round-trip time is `L/c`, a real tempo, drawn on
  screen as a sweeping ring. Striking on it compounds. Nothing about that
  reinforcement is faked; the sim genuinely rings.
- **Range** — the hot bands die in the air, so a heat sigil is a decision
  about where you stand.
- **Quench** — dump everything you charged. The panic button, priced.

Measured, the tap/hold split is not cosmetic:

| sigil | tap | hold (3s) | ratio |
|---|---|---|---|
| Shove (262px ring) | 27 dmg | 112 | 4x |
| Tuned band-2 (137px) | 6.5 | 216 | **33x** |
| Spark (33px ring) | 0.2 | 10.5 | **52x** |

Small rings store almost nothing, so a strike barely rings them and they
must be *driven*. Nobody wrote that rule. It is what a small resonator is.

## 3. Structure

A roguelite descent. Two modes, alternating.

**THE FORGE** (safe, slow, unlimited undo)
Draw on a Focus — a bounded canvas with an ink budget. Live while you draw:
the measured spectrum, the assay, the charge/saturation/char meters, a band
ruler, and a test bench firing real pulses at a retunable dummy.

**THE FIELD** (fast, committed)
Move, aim, and play up to four Foci. Clear the room. Between rooms: a
two-option reward, then back to the Forge.

### The Assay

The single most important piece of UI. It states **what was measured**,
never what the game decided:

```
geometry predicts band 1.0 (low) before firing
1 loop, largest 262px -> f0 0.0152 (clockwise, beat 0.66s)
1 terminal(s) -> push / burn
output centred on band 1.3 (low), efficiency 40%
```

If it said "FIRE SPELL" the player would learn a lookup table. Saying this
teaches the machine, and keeps being true in cases nobody anticipated. A
player whose sigil does nothing can read *why* — `open path, no loop - no
resonance to tap into` is a lesson; "it didn't work" is a bug report.

### The band ruler

Six faint circles on the canvas, one per band, at the circumference that
rings at it. This is the bridge between the two ways of understanding the
game: it converts *"I need orange"* into *"draw about this big"*. A new
player uses it as a colour-matching aid; an experienced one has internalised
`f0 = dx/L` and no longer needs it. Same overlay, both readings.

## 4. How the physics became mechanics

Every combat mechanic is a consequence, not an authored effect.

| Mechanic | Comes from | Authored? |
|---|---|---|
| Which enemies you can hurt | spectrum overlap with the target's resonance | curve only |
| Elements | loop circumference → frequency → band | no |
| Push vs pull, burn vs chill | chirality: the sign of the loop's signed area | no |
| Heat is short range | frequency-dependent damping, in ink *and* in air | no |
| Reaching the top band | asymmetric saturation → harmonics | threshold only |
| Burnout | saturation depth accumulating as char | no |
| Parry | antiphase cancellation between overlapping pulses | no |
| Firing pattern | where you put the terminals | no |
| Remote emitters | evanescent coupling across a gap | no |
| Beat damage (Choir) | two loops detuned by \|f1−f2\| | no |
| Material identity | one physics knob per ink, downside included | no |

**Enemies cast through the identical pipeline.** Drones and Anchors own real
`Sigil` objects — parsed, compiled, analysed the same way yours are. Their
shots superpose with yours. An Anchor's corpse is a real drawing you can
read, edit and carry, which makes progression free content in the strict
sense: no loot system had to exist.

### Enemies are lessons wearing hitboxes

| Enemy | Band | Teaches |
|---|---|---|
| **Cinder** | 1 | baseline: a big ring shoves, and shoving works |
| **Ward** | 4 | bands are a *gate*: it reflects low bands, so bring heat — and heat dies in the air, so walk in |
| **Drone** | 2 | incoming energy is the same stuff: its motes cancel against opposite chirality |
| **Choir** | 2 & 3 | two detuned sources beat; the antinode between them hurts |
| **Anchor** | 3 | phase-locked. Only the top band decoheres it, and no ring is small enough to ring there — you must overdrive into harmonics |

The Ward has no "immune to physical" flag; it has high impedance, so low
bands reflect, because that is what an impedance mismatch does.

## 5. The learning ladder

The explicit requirement was complexity that stays *fun solving* rather than
becoming work. Four guardrails:

1. **Never a blank canvas.** You start with three working instruments and
   spend the first hour *editing*, which is far easier than inventing.
   **Shove and Draw are the same ring wound opposite ways** — identical in
   every respect except the sign of the enclosed area, and one pushes while
   the other pulls. A player who notices that has learned chirality without
   being told it exists, and more importantly has learned that *the
   direction you drew a line is a physical quantity the game reads*. Every
   later discovery is downstream of believing that.
2. **Colour first, physics later.** Enemy weakness is worn on the outside as
   a ring in its band's hue — the same six hues as your spectrum bars. "Make
   the bars match the ring" is a complete and wordless statement of the
   combat system. Understanding *why* orange means a small loop is optional
   for hours.
3. **Being wrong is free.** One-key undo, canvas reset, a test bench that
   costs nothing. A system this deep is only learnable if bad ideas are
   cheap; if a bad idea costs a run, players stop having ideas.
4. **Failure is diagnosable.** See the Assay.

### Verified, not asserted

`python -m sigilwave.game.playtest` plays every room with four bots that
differ only in how much of the system they understand, three seeds each:

```
                      naive  aware  expert  wright
room 1 First Light      3/3    3/3     3/3     3/3
room 2 The Mirror       3/3    3/3     3/3     3/3    (naive survives on 58hp; aware on 100)
room 3 Crossfire        1/3    1/3     1/3     3/3    <-- drawing the right sigil opens this
room 4 The Pair         3/3    3/3     3/3     3/3
room 5 The Anchor       3/3    2/3     2/3     3/3
                       13/15  12/15   12/15   15/15
```

- *naive* taps whatever is equipped and never switches.
- *aware* matches band to target and closes on hot ones.
- *expert* also overdrives past char, vents, and goes again.
- *wright* visits the Forge first and draws a ring for the room.

The opening is forgiving — a player who understands nothing clears room 1
every time. Authoring is what opens the hard rooms.

The suite also asserts the deepest gate is a real lock **with a real key**,
because a gate that fails either way is silent from the inside:

```
low band (Shove, held 4s): phase 0.00  hp 340 -> 336.5   locked
hot band (Spark, held 4s): phase 1.00  hp 340 -> -432.6  UNLOCKED
```

Frame cost with a full room live: **0.19 ms/step, 2.2% of the budget.**

## 6. Progression and monetization

**Within a run** progression is materials and capacity: ink families, ink
budget, focus slots. Six inks, each pulling exactly one physics knob hard,
with the downside as a direct consequence of that same knob — Quicksilver
cannot hold a charge *because* it radiates so freely; Emberglass has a low
ceiling *because* it saturates early; Bonewhite barely emits *because* its
terminals are nearly sealed. No ink is complete alone, so good sigils are
composites: a Slate body that carries energy cheaply, tipped with
Quicksilver that actually lets it out.

**Across runs** progression is *the Codex* — the sigils you drew and named.
This is the deliberate choice. Roguelites normally make you re-earn power
every run, which is fine when power is a list of items and miserable when
power is an idea you had. Making a player redraw a circuit they already
understand is not difficulty, it is typing. So the thing that gets stronger
between runs is the player.

**Monetization** follows from one property: a sigil is strokes plus ink
names, so it serialises to a ~400-1000 character string (`run.share_string`).

- Premium purchase; the Forge alone is a free demo that is genuinely fun and
  converts on its own merits.
- Sigil sharing needs no server. A community, a weekly "hit this spectrum
  with minimum ink" challenge, and efficiency leaderboards all fall out of a
  string. Excellent cost ratio.
- DLC as new Vaults, ink families, and resonance classes — all of which are
  data, because the physics is already general.
- Cosmetic ink shaders and sigil trails. **Never behavioural.** Selling a
  physics parameter in a game whose entire promise is that the physics is
  honest would poison the well.

## 7. What had to change in the simulation, and why

The sim package (`sigilwave/sim/`) is **unmodified** — all 34 of its
selftests still pass. The findings below were fixed in the game layer, and
each one was silently deleting a mechanic.

1. **Every tap landed in band 0.** The doc's injection shape is a raised
   cosine *window*, which is unipolar — half its energy sits at DC, and the
   lowest analysis band's skirt runs down to DC. A 20px ring and a 400px
   ring both measured as "deep". The elemental system did not exist. Fixed
   with a zero-mean strike (`broadband_tap`); the sim's version is untouched
   because the selftests measure against it.

2. **The top two bands were unreachable by drawing anything.** A band's
   centre frequency *is* a stroke length (`f0 = dx/L`); at the analyser's
   default `f_max = 0.4` band 5 asks for a 10px loop and the parser's
   minimum edge is 16px. Heat, phase, and every enemy tuned to them were
   inert. The game's analyser is capped at 0.20, putting the six bands on
   loops of ~500, 263, 138, 72, 38 and 20px — the first five comfortable to
   draw, the sixth reachable only through harmonics. That gate is now the
   Anchor.

3. **A fixed-width tap only excites one ring size.** Burst length sets
   bandwidth, so a fixed tap put its energy at a fixed frequency and small
   sigils read as broken. The strike is now matched to the instrument's own
   fundamental.

4. **The analyser measured the wrong quantity, in the wrong direction.** It
   read junction pressure `u_j`, but radiated power is `u_j² · Y_rad` — and a
   nearly-sealed terminal holds a *large* pressure precisely because so
   little escapes. Every material was inverted: Slate, whose identity is
   "carries anything, emits almost nothing", measured as the strongest
   emitter in the set. The intended composite lesson was not merely
   unteachable, it was false. Terminals now analyse `u_j · √Y_rad`,
   normalised against Chalk.

5. **Char keyed off stored energy**, which scales with how much ink you
   drew, so a large sigil charred for existing while a small one could be
   flogged forever. It now keys off saturation depth at the junctions, which
   is size-independent and is literally the ink being cooked — and which
   makes an ink's harmonic talent and its fragility the same number.

6. **The coupler cutoff was a step discontinuity** at `g_max` (a known issue
   in the project's own notes). Tuning a gap is exactly what a player
   probing tunnelling does, and they would watch energy vanish for a
   one-pixel change. Kappa is now tapered to zero at the boundary.

7. **The Anchor's phase lock had a silent bypass.** It refunded direct
   damage but not burn, because burn is applied from accumulated temperature
   during `update()` rather than at the moment of impact. A player who
   simply kept tapping their opening sigil cooked a locked Anchor to death
   without ever discovering it had a lock. A gate with a silent bypass is
   worse than no gate: it teaches that the mechanic it exists to teach does
   not matter.

8. **Efficiency was unreadable.** The raw radiated/injected ratio lives
   between 0.006 and 0.04, so every sigil in the game — the good ones
   included — reported "3%", and players would learn to ignore the one
   figure the design most wants them to optimise. It is now graded against a
   good sigil, preserving the measured ordering: 0% (no terminal) → 15%
   (hoards) → 41% → 66% → 80%.

Two further game-layer additions: per-ink coupler reach (materials should
own "how far can I blink"), and `Sigil.predicted_band`, which reads the
output band off geometry alone so the Forge can show it *while you are still
drawing*.

## 8. Deliberate omissions

- **No drawing in combat.** Section 1.
- **Ink is not destructible in the arena.** The doc wants enemies breaking
  your strokes. It is a good idea and it belongs after the core loop is
  proven, because it mostly punishes the authoring the game is trying to
  encourage.
- **Relays are a modelled coupling, not the real one.** Merging two
  independently compiled networks every time a player walks past their own
  graffiti would be expensive and fragile. Falloff with gap and better
  crossing for long wavelengths are preserved, so what the player learns
  here stays true of the real couplers they build inside one sigil.
- **The world stays simple.** Three fields, coarse behaviour, readable
  materials — the doc's own warning that one deep system plus one legible
  system reads as depth, while two deep systems read as noise.

## 9. Where to take it next

1. **Ignition points as first-class design.** The Forge lets you move the
   spark (`E`), and where it goes measurably changes buildup (a loop
   junction reaches 2.3-2.7x against a terminal's 1.8x). It deserves more
   than one keybind.
2. **Two-handed play.** Charge one focus while firing another; the sim
   already supports it, the input scheme does not.
3. **Enemy sigils that are actually interesting to read.** They are rings
   today. Once they are composites, reading a corpse becomes real progression.
4. **Audio.** A simulation whose state variable is literally a waveform, in a
   game with no sound. This is the largest single piece of value left on the
   table.
