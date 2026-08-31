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

**THE FOUNDRY** — cast bells out of **shapes**, not freehand scribbles:

| | |
|---|---|
| `1` **RING** | press at the centre, drag out. The radius **snaps to the notes**, which are printed on the canvas at actual size, so "cast a TENOR" is one gesture that cannot miss. |
| `2` **ARC** | drag out, then sweep the mouse round. The arc follows your hand and the direction you sweep *is* the winding — keep going past a full turn and it closes into a bell. |
| `3` **LINE** | a horn. Snaps to 15° and to the ends of existing strokes. |
| `4` **FREE** | freehand, with assisted closure. |

Nothing is final. **Hover a stroke and the wheel retunes it in place** while
the tuner needle moves under your hand. `F` flips its winding, `X` deletes
it, `SHIFT`+drag moves it.

The readout is a **guitar tuner** — a needle, a note name, cents flat or
sharp — and the notes the next room is actually tuned to are marked on it.
And the wave the simulation is running is drawn *in the metal*: strike the
bell and watch the pulse race round the ring and stand.

**THE BELFRY** — you cannot draw here. Move, toll, swell, dash. Clear the
room, go back up. Waves escalate and keep coming.

## Resonance breaks. Force moves.

Nothing has health. Everything has a **crack meter**.

- An **on-note** ring fills it fast. Fill it and the thing **shatters** — and
  a resonant shatter is the only thing in the game that **heals you**.
- An **off-note** ring fills nothing at all — and it *shoves*, hard.

So the wrong note is not weak, it is **a different verb**. Shoving is a real
kill: things thrown into walls and into each other crack against them, and
one enemy has no note at all and can only die that way. But a slam does not
feed you, so a player who never learns to tune bleeds out however well they
shove. There is no penalty for brute force anywhere in the game — the game
simply pays for the play it wants to teach.

Three or four connected attacks kill you. Everything telegraphs; every
telegraph is dodgeable.

## Controls

| | |
|---|---|
| `WASD` | move |
| `LMB` tap | toll — a ring, centred on you, that reaches as far as your note does |
| `LMB` hold | swell — drive the bell past its fold; it climbs an octave and it chars |
| `LMB` release | let go, all at once |
| `SPACE` / `SHIFT` | dash — i-frames, cancels anything |
| `1`-`3` / `Q` / `RMB` / wheel | swap bell |

There is no aiming. A ring is omnidirectional, so what you are choosing is
**distance** — and distance is exactly what the note ladder means.

## Reading the room

- **The pool you are standing in** is your bell's reach. Its rim is where the
  ring stops. Anything outside it is a different bell's problem.
- **The ring closing onto you** is the swell. Toll as it lands and the strike
  compounds — that reinforcement is the simulation's, not a bonus. On-beat
  strikes in a row build a **chorus** multiplier.
- **The ring closing on a foe** is both its note *and* its attack clock. It
  closes on exactly the tempo a bell of that note tolls at, and the thing
  attacks the frame it lands — so identifying it and knowing when to move are
  one act. A TENOR enemy swings on a slow 0.8s beat; a CHIME one comes at you
  twice as often. It is also that colour and it is also humming that pitch.
- **A bright bracket** collapsing onto a foe is a committed wind-up. Dash it.
- **A foe trailing white** has been shoved hard enough that hitting something
  will crack it. It is a projectile now.
- **An arrow at the screen edge** is something you cannot see, in its own
  colour, brightening as its attack lands.
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
   TOTAL                     2/33     13/33     24/33     31/33
```

A masher who ignores note, beat and range clears 2 of 33. Somebody who tunes
and casts for the room clears 31. If those two numbers ever converge, the
system is decoration and the harness says so.

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
  fx.py                     particles: a matched hit and a wrong one look different
  forge.py                  the Foundry: shape tools, a tuner and a target
  render.py                 drawing the invisible on the floor
  audio.py                  every sound synthesised from the note that made it
  run.py                    the wave list, and deliberately nothing else
  playtest.py / calibrate.py / smoke.py / shots.py
sigilwave/game/             WAVEWRIGHT, the earlier build on the same sim
                            (python -m sigilwave.game.app)
```

The design, and an account of what was wrong with the previous build and why,
is in [`CAMPANARY.md`](CAMPANARY.md).
