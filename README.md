# WAVEWRIGHT

You do not cast spells. You build resonators, and then you play them.

```
pip install -r requirements.txt
python play.py
```

A ring's circumference sets its frequency. Frequency is colour. Colour is
what a thing is weak to. Wind the ring the other way and every impulse it
makes reverses. None of that is a lookup table — it is one wave simulation,
and everything in the game is a consequence of it.

Built on the digital-waveguide simulation specified in
[`sigil-wave-design.md`](sigil-wave-design.md). The game design, and the
seven simulation-layer bugs that had to be fixed before any of it worked,
are in [`GAME_DESIGN.md`](GAME_DESIGN.md).

---

## The loop

**The Forge** — draw sigils on a bounded canvas. Unlimited undo, a live
readout of what your drawing actually measures, and a test bench firing real
pulses at a dummy you can retune. Nothing is at stake here.

**The Field** — you cannot draw here. Take what you built and play it: aim,
strike, sustain, switch, and stand in the right place. Clear the room,
choose a reward, go back to the Forge.

You start with three working sigils, so you can win the first room without
understanding anything at all. Two of them, **Shove** and **Draw**, are the
same ring wound in opposite directions. One pushes. One pulls. Everything
else follows from noticing that.

## Controls

**Forge**

| | |
|---|---|
| `LMB` drag | draw a stroke |
| `RMB` / `Z` | undo |
| `1`-`6` | select ink |
| `TAB` | switch focus slot |
| `G` / `SPACE` | test-strike / test-sustain |
| `[` `]` | retune the dummy's band |
| `,` `.` | move the dummy nearer / further |
| `I` | toggle the band ruler |
| `E` | move the ignition point to the nearest node |
| `N` | name this sigil |
| `C` / `R` | clear canvas / reset bench |
| `ESC` | descend into the room |

**Field**

| | |
|---|---|
| `WASD` | move |
| mouse | aim |
| `LMB` | strike (broadband, cheap) |
| `RMB` hold | sustain (narrowband, ramps into overdrive, chars the ink) |
| `1`-`4` / wheel | switch focus |
| `SHIFT` / `SPACE` | dash |
| `E` | stamp a relay |
| `Q` | quench — dump everything you charged |

## Reading the screen

- **Brightness along a stroke** is amplitude. **Hue** is the band it is
  emitting — which changes live, so overdriving a blue sigil turns it orange
  in your hands.
- **A ring around an enemy** is its resonance, in that band's colour. The
  same six colours as your spectrum bars. Match them.
- **A flashing node** is a junction folding into saturation — the moment
  harmonics start.
- **A shimmer across a gap** is energy tunnelling between two strokes that
  never touch.
- **The three small meters** on each focus are charge, saturation, and char.
  Char is what burns your sigil out.

## Verify it

```
python -m sigilwave.game.playtest    # plays every room with four bots of
                                     # increasing system knowledge, 3 seeds
                                     # each; asserts the gates are real
python -m sigilwave.game.shots       # renders the game to debug_output/
python -m sigilwave.sim.selftest     # the simulation's own suite (34 checks
                                     # across 8 files, all still passing —
                                     # sigilwave/sim/ is unmodified)
```

## Layout

```
play.py                  entry point
sigilwave/sim/           the wave simulation — unmodified, self-tested
sigilwave/game/
  bands.py               the shared vocabulary: six bands, hues, coupling curve
  sigil.py               drawn ink -> a live instrument you can play
  inks.py                six materials, one physics knob each
  combat.py              pulses, resonant damage, antiphase cancellation
  enemies.py             five archetypes, each a lesson wearing a hitbox
  field.py               the arena
  forge.py               the drawing and testing screen
  viz.py                 drawing the invisible (the highest-leverage file)
  rooms.py / run.py      progression, rewards, the persistent codex
  playtest.py            headless balance and regression harness
sigil_lab.py             the original physics bench, still runnable
```
