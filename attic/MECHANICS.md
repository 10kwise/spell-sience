# WAVEWRIGHT — mechanics pass

This document covers the second build, which locked the mechanics down. The
first build's problems were named accurately: enemies were harmless, the game
had no feel, colour-matching could be forced through, and spells were only
ever projectiles. Each of those is addressed below, with the measurements.

The identity the game is now built toward: **occult-industrial horror at DOOM
pace.** You descend a structure that rings. The dark is full of tuned things
that hunt by resonance. Your ink is the only light — and casting makes you
visible.

---

## 1. Spells stopped being bullets

The largest error in the first build: every sigil was an emitter, every
emission became a mote, and every mote was damage. A wave simulator got
flattened into a gun. Standing waves, storage, reflection, spreading heat and
action at a distance — the whole reason to simulate waves — had nowhere to
land, because the world had no state to land *in*.

**The world now has state.** Three fields on a coarse grid (`fields.py`),
exactly the three the design doc names, plus fuel:

| field | is | does |
|---|---|---|
| kinetic (vector) | wind | shoves everything, including you |
| thermal (scalar) | heat / cold | burns, freezes, **spreads through fuel** |
| phase (scalar) | decoherence | matter here stops interacting |
| fuel (scalar) | what is left to burn | consumed, never replenished |

Fire genuinely propagates. The condition is written down rather than tuned by
feel — a burning cell settles at `BURN_HEAT/(DECAY+DIFFUSE)`, its neighbour
at about a quarter of the diffused share, and the neighbour has to clear
`IGNITE_AT`:

```
THERMAL_DIFFUSE * BURN_HEAT / (4 * (THERMAL_DECAY + THERMAL_DIFFUSE)^2) > IGNITE_AT
             1.5 * 9.0      / (4 * (0.55 + 1.5)^2)              = 0.80  >  0.55
```

Measured: one blast spreads to 35 cells and burns for 12+ seconds, consuming
28% of the room's fuel. A sustained chill sigil freezes a firebreak — **27
cells burning, 0 past the line.**

### Four things a spell can be, none of them chosen from a menu

Archetype is read off the compiled topology and shown in the Forge and the
combat HUD:

- **Emitter** — has terminals, so it radiates. Projectiles, aimed.
- **Capacitor** — a closed loop has no way out, so it *stores*. `Q` releases
  everything at once, and what the release does is read off the spectrum:
  low bands blast, high bands ignite, the top band thins matter, and a
  counter-clockwise winding turns the whole thing inside out so it implodes
  and freezes instead.
- **Aura** — any charged sigil pushes on the world around it, deposited as a
  *ring* because a loop's near field peaks at the ink and is weakest in the
  middle. (Stamped as a disc it set the caster on fire — a geometry error no
  amount of magnitude tuning could fix.)
- **Barrier** — the drawn ink is a physical object incoming energy can hit,
  with the doc's own reflection coefficient `r = (Z₂−Z₁)/(Z₂+Z₁)`. An arc of
  Bonewhite across your front is a shield because of what Bonewhite *is*.
  There is no shield item, block button, or shield stat.

## 2. You cannot force through any more

Wrong-band energy used to be merely *weak*, and weak is survivable — so a
player could stand at range and grind anything down with their opening sigil.
Every gate was advisory.

**Off-band energy is now absorbed, not wasted.** It fills a *glut* meter
drawn as an arc around the enemy in its own colour. Fill it and the thing
**surges**: heals, quickens permanently, and throws out a shockwave. Brute
force visibly makes the problem worse.

The forgiveness threshold is set from measurement, not intuition. A mote
crossing a room loses its upper bands to air decay long before it lands, so a
correctly-matched hit scores a median of **0.194**, not the 0.79 a
point-blank bench reading suggests. Set at 0.5 or 0.62 the *right* answer was
feeding enemies too. At 0.16 it separates cleanly:

| | right band | wrong band |
|---|---|---|
| hit quality | ~0.194 | ~0.02 |
| Ward, 6s sustained | dead in 2.1s, player at 100hp | 88/120 hp, **player dead** |

Room 2 is the proof. The counter (Spark) is in the starting kit from the
first room, so closing this path costs a paying-attention player nothing:

```
room 2, 3 seeds       naive  0/3   DIED @37s   21 surges
                      aware  3/3   CLEAR @11s   0 surges, 100hp
```

## 3. Threat and feel

- **Telegraphs.** Cinders stalk, wind up, and commit to a 780px/s lunge they
  cannot steer out of. Drones wind up visibly before a volley. A telegraph is
  what turns an enemy from a moving obstacle into something you answer, and
  it is the cheapest threat there is.
- **Darkness.** The arena is unlit. Everything visible is radiating: your
  ink, a mote, a fire you started. **Your light grows with your charge**, so
  visibility and power are the same resource — creeping is safe and blind,
  winding up a capacitor makes you a lantern.
- **Enemies glow in their own band colour.** The dark stays fair, and the
  colour language becomes a horror mechanic: what you see first is a hue in
  the black, and the hue already tells you what kills it.
- **Hitstop and shake** on heavy landings; ash marks ground that has burned.
- **The world hurts you too.** You read the same fields everything else does.
  Fire is lethal to the player and only 0.22x against enemies — deliberately
  asymmetric, because letting fire kill tuned creatures re-opens the exact
  hole the resonance system exists to close.

## 4. The shelf — prebuilt spells

`L` in the Forge opens a library of twelve finished, working sigils. Every
one is a legal drawing with no privileged construction, and each demonstrates
one idea in its cleanest form. Load one, fire it, then cut bits off it.

| | kind | teaches |
|---|---|---|
| Lance | emitter | slate body carries, quicksilver tip lets go |
| Fork | emitter | three terminals = three directions; the drawing *is* the firing pattern |
| Needle | emitter | band-4 knife: devastating at contact, useless at range |
| Kiln | emitter | early-folding ink; harmonics push output hotter than the ring |
| Cask | capacitor | sealed low ring — charge, release, shockwave |
| Pyre | capacitor | sealed small ring — release is a firestorm |
| Hearth | aura | a standing fire you carry. hold, do not release |
| Rime | aura | Hearth wound backwards — freezes, and frozen ground will not light |
| Maw | aura | counter-clockwise low ring — wind blows inward, gathers a crowd |
| Aegis | barrier | a dense arc reflects incoming energy |
| Lantern | conduit | two rings that never touch; energy crosses anyway |
| Chord | emitter | two detuned rings beat against each other |

All twelve are asserted to behave as labelled by the test suite.

Pyre's comment is worth reading: the obvious ink for a fire capacitor is
Emberglass, and it is the *wrong* one — a junction saturating at 0.85 clips
every crest, so it tops out around 10% charge at any ring size. Emberglass is
for throwing, not holding. That is a material fact the library teaches by
being built correctly.

## 5. Bugs found in this pass

1. **Diffusion ran per step, not per second.** At 120Hz the blur ran 120
   times a second, and the kernel was not conservative, so an isolated hot
   cell lost ~17% of itself per step and fire could never spread at all.
2. **`_stamp`'s falloff was squared**, which at 34px cells drove every
   neighbour to exactly zero — a "radius 40" deposit landed in one cell.
3. **Light sprites rendered as squares.** The blends used (`RGBA_SUB`,
   `RGB_ADD`) read colour channels and ignore alpha, so a white sprite with
   only an alpha ramp subtracts a hard rectangle.
4. **World coupling was driven off the near-field centroid**, which is
   broadband and does not track the ring that produced it — a band-1 shove
   sigil measures ~2.9 in live play. It set rooms on fire and resisted three
   rounds of magnitude tuning, because the *input* was wrong. It now reads
   the geometric `predicted_band`: stable, monotone in ring size, and already
   the number shown to the player.
5. **The surge shockwave deposited heat**, making every enemy reaction an
   ignition source — rooms of correctly-matched Cinders were setting
   themselves alight and killing the player who was beating them.
6. **Ignition needed to be categorical, not numeric.** Ignition is a
   threshold process and a lit cell emits nine times what lit it, so any
   scheme where a cold sigil sits *near* the threshold eventually tips over.
   There is no safe magnitude, only a safe category: below band 2.4 a sigil
   deposits no heat at all.
7. **Performance: 6.9ms/step, 83% of budget.** Profiled rather than guessed:
   `_pulse_trail → add_kinetic → _stamp` was 65% of it, plus 120k scalar
   `np.clip` calls in `cell_of`. Cached the falloff kernel, replaced clip
   with plain min/max, and stamped kinetic trails on a rotating quarter of
   motes. **6.915ms → 1.461ms.**

## 6. Where it stands

```
                      naive  aware  expert  wright
room 1 First Light      3/3    3/3     3/3     3/3
room 2 The Mirror       0/3    3/3     3/3     3/3   <-- band matching opens this
room 3 Crossfire        3/3    3/3     3/3     1/3
room 4 The Pair         3/3    2/3     2/3     2/3
room 5 The Anchor       0/3    3/3     3/3     3/3   <-- band matching opens this
                       9/15  14/15   14/15   12/15
```

Room 1 is still cleared every time by a bot that understands nothing. Rooms 2
and 5 are closed to it entirely. That is the shape the design wants.

## 7. Still open

- **Audio.** A simulation whose state variable is literally a waveform, in a
  game with no sound. Still the largest single piece of value on the table.
- **The `wright` bot regressed on room 3** (1/3) — it builds a band-2 ring
  and fights at the wrong range with it. A bot-quality issue, not a game one,
  but worth confirming against a human.
- **Ink is still not destructible in the arena**, and enemies still do not
  read the fields for pathing — they will walk into a fire.
- **Relays remain a modelled coupling**, not the sim's real evanescent one.
