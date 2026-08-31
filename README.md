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
[`sigil-wave-design.md`](sigil-wave-design.md). The game design is in
[`GAME_DESIGN.md`](GAME_DESIGN.md); the mechanics pass that added world
fields, spell archetypes, the anti-brute-force rule and the horror
presentation is in [`MECHANICS.md`](MECHANICS.md).

The arena is unlit. Everything you see is radiating — your ink, a mote in
flight, a fire you started — and your light grows with your charge, so
visibility and power are the same resource.

---

## The loop

**The Forge** — draw sigils on a bounded canvas. Unlimited undo, a live
readout of what your drawing actually measures, and a test bench firing real
pulses at a dummy you can retune. Nothing is at stake here.

**The Field** — you cannot draw here. Take what you built and play it: aim,
strike, sustain, release, switch, and stand in the right place. Clear the
room, choose a reward, go back to the Forge.

A sigil is not only a gun. What you drew decides what kind of thing it is:

- **terminals** -> it radiates. Projectiles, aimed.
- **a closed loop** -> it has no way out, so it *stores*. `Q` releases the
  lot at once, and the spectrum decides whether that is a shockwave, a
  firestorm, or an implosion.
- **any charge at all** -> a near field that lays fire, freezes ground,
  raises wind or thins matter, in a ring around you.
- **dense ink in the way** -> incoming energy reflects off it.

Fire spreads through the floor, burns out its fuel, and leaves ash. Freeze
the ground ahead of it and it stops. **You read the same fields everything
else does** — your own firestorm is a room you now have to cross.

Hitting something with the wrong frequency does not merely do less damage.
It is *absorbed*: the meter around the enemy fills, and when it does the
thing heals, quickens, and shoves you off it. Brute force makes the problem
worse.

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
| `L` | **the shelf** - load one of 12 prebuilt working sigils |
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
| `Q` | **release** - dump everything a capacitor is holding, at once |

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
  fields.py              the world as a medium: heat, wind, phase, fuel, fire
  library.py             12 prebuilt working sigils (the shelf)
  enemies.py             five archetypes, each a lesson wearing a hitbox
  field.py               the arena: auras, releases, barriers, world coupling
  forge.py               the drawing and testing screen
  viz.py                 drawing the invisible (the highest-leverage file)
  rooms.py / run.py      progression, rewards, the persistent codex
  playtest.py            headless balance and regression harness
sigil_lab.py             the original physics bench, still runnable
```
