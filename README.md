# CAMPANARY

You are a bell-founder. You cast bells in the foundry, and then you ring them
at the things in the dark.

```
pip install -r requirements.txt
python play.py
```

A big bell is deep. A small bell is high. **That is all size does** — and
everything else in the game is a consequence of it, because the pitch of a
ring really is `c / L` inside one wave simulation and never a lookup table.

---

## The one sentence

Draw a ring twice as wide and it sounds an octave lower, reaches twice as
far, and tolls twice as slow. Draw it the other way round and every impulse
it makes reverses. Ring it hard enough to fold its own metal and it climbs
an octave — and cracks.

Nobody wrote those rules. They are what a resonant loop is, running on the
digital-waveguide simulation in [`sigilwave/sim/`](sigilwave/sim/), which is
unchanged from the original spec and still passes its own 34 checks.

## The loop

**THE FOUNDRY** — draw on a bounded canvas with a metal budget. The note
ladder is printed on the canvas at actual size, so "I want that note" and
"draw this big" are the same instruction. A guitar-tuner readout says which
note you cast and how many cents flat or sharp. The peal of the room ahead —
the notes the things down there are actually tuned to — is on the screen
beside it, so drawing is closing a gap rather than guessing.

**THE BELFRY** — you cannot draw here. Move, toll, swell, dash. Clear the
room. Between waves, **the anvil**: twelve seconds to reshape a bell, under
a clock, with the next room's notes in front of you.

An act is three waves and a boss. Three acts.

## Resonance breaks. Force moves.

Nothing has health. Everything has a **crack meter**.

- An **on-note** ring fills it fast. Fill it and the thing **shatters**.
- An **off-note** ring fills nothing at all — and it *shoves*, hard.

So the wrong note is not weak, it is **a different verb**. Shoving is a real
kill: things thrown into walls and into each other crack against them, and
one enemy has no note at all and can only be killed that way. There is no
penalty for brute force anywhere in the game. There does not need to be one,
because the fast, beautiful kill is the one that matches.

## Controls

| | |
|---|---|
| `WASD` | move |
| `LMB` tap | toll — a ring, centred on you, that reaches as far as your note does |
| `LMB` hold | swell — drive the bell past its fold; it climbs an octave and it chars |
| `LMB` release | let go, all at once |
| `SPACE` / `SHIFT` | dash — i-frames, cancels anything |
| `1`-`3` / `RMB` / wheel | swap bell |

There is no aiming. A ring is omnidirectional, so what you are choosing is
**distance** — and distance is exactly what the note ladder means.

## Reading the room

- **The pool you are standing in** is your bell's reach. Its rim is where the
  ring stops. Anything outside it is a different bell's problem.
- **The ring closing onto you** is the swell. Toll as it lands and the strike
  compounds — that reinforcement is the simulation's, not a bonus. On-beat
  strikes in a row build a **chorus** multiplier.
- **A pulse around a foe** is its note, expanding on exactly the tempo a bell
  of that note tolls at. It is also that colour, and it is also humming that
  pitch. Any one of the three is enough.
- **A foe drawn hatched and grey** has no note. Nothing will ever ring it.
- **Your ring cools as it travels** — it leaves white and arrives blue,
  because the high notes in it die within a body length. That is the whole
  range law, in one animation.

## Verify it

```
python -m sigilwave.campanary.playtest    # four bots of increasing knowledge
                                          # play every wave; proves the gates
python -m sigilwave.campanary.calibrate   # measures the two numbers the game
                                          # is allowed to put its thumb on
python -m sigilwave.campanary.smoke       # drives the real app through a run
python -m sigilwave.campanary.shots       # renders every screen to debug_output/
python -m sigilwave.sim.selftest          # the simulation's own suite
```

The playtest is the one that matters. It reports:

```
   wave                    masher    ringer     tuner   founder
   TOTAL                     2/36     14/36     27/36     36/36
```

A masher who ignores note, beat and range clears 2 of 36. Somebody who
tunes clears all of them. If those two numbers ever converge, the system is
decoration and the harness says so.

## Layout

```
play.py                     entry point
sigilwave/sim/              the wave simulation - unmodified, self-tested
sigilwave/campanary/
  notes.py                  the whole vocabulary: five octaves, and what each means
  bell.py                   drawn metal -> a resonator you can strike
  metals.py                 three metals, one knob each
  rings.py                  the attack: an expanding wavefront that cools
  foes.py                   six designs, each demanding one specific verb
  arena.py                  the Belfry - four verbs, no aiming
  forge.py                  the Foundry and the Anvil: a tuner and a target
  render.py                 drawing the invisible on the floor
  audio.py                  every sound synthesised from the note that made it
  run.py                    acts, waves, rewards
  playtest.py / calibrate.py / smoke.py / shots.py
sigilwave/game/             WAVEWRIGHT, the earlier build on the same sim
                            (python -m sigilwave.game.app)
```

The design, and an account of what was wrong with the previous build and why,
is in [`CAMPANARY.md`](CAMPANARY.md).
