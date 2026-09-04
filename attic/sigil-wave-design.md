# Sigil / Wave — Design & Architecture

A sandbox action game where spells are hand-drawn wave circuits. No spell list, no
recognizer, no hardcoded effects. The player draws ink into the world; ink conducts
waves; waves interfere, reflect, tunnel and distort; whatever radiates out of the ink
is what happens.

---

## 1. Design pillars

**Every effect is a consequence.** There is no table mapping shapes to outcomes. The
player manipulates five physical knobs — topology, path length, curvature, chirality,
and proximity — and the simulation decides the rest. If the designer is never
surprised by a player's sigil, the system has failed.

**Mana is amplitude, efficiency is measurable.** Injected energy either radiates
usefully, dissipates in ink, or leaks. The ratio is a real number the game can show.
This is the min-max surface.

**Understanding transfers.** A player who learns why a tapered emitter doesn't reflect
has simultaneously learned how to build a reflector. Knowledge compounds instead of
accumulating as a list.

**One code path for everything.** Enemies cast with the identical pipeline. Anything
you face is something you could draw. Progression is largely reading defeated enemies'
ink.

---

## 2. The physical model

### 2.1 Substrate: digital waveguides, not FDTD

Each edge of the parsed sigil is a bidirectional transmission line implemented as a
pair of delay lines. Junctions are scattering nodes. This was chosen over
finite-difference time-domain for four reasons:

- **No numerical dispersion.** Harmonics that appear must come from the deliberate
  nonlinearity, not from grid artifacts. This matters because harmonic generation is a
  core mechanic and we need it to be trustworthy.
- **Provable passivity at junctions.** The scattering formulation cannot create energy
  for any number of incident edges. With feedback loops everywhere, this is not
  optional.
- **~50× cheaper.** Propagation is a ring-buffer read/write. Cost concentrates at
  junctions, of which there are few. Dozens of simultaneous sigils are affordable.
- **Directionality is free.** Terminals need an outgoing wave and an emission heading;
  the traveling-wave decomposition hands both over directly.

### 2.2 Uniform wave speed, variable impedance

Impedance mismatch is what produces reflection, and reflection is what produces
shields, resonators and charge storage. But varying wave speed per edge would break
the integer-delay assumption and reintroduce dispersion.

Resolution: for a 1D medium, `Z = √(Tρ)` and `c = √(T/ρ)`. Scaling tension and density
*together* changes impedance while holding speed fixed. So each ink type carries an
impedance `Z` with `c` global and constant.

Junction reflection for two edges is then the standard `r = (Z₂ − Z₁)/(Z₂ + Z₁)`, and
speed stays uniform everywhere. Refraction and lensing are given up. That is a
deliberate trade and probably the right one; revisit only if lensing turns out to be
load-bearing for some mechanic.

### 2.3 Junction scattering

For a node where `N` edges meet with admittances `Y_k = 1/Z_k`, the junction pressure is

```
u_J = 2 · Σ(Y_k · u_k⁺) / Σ(Y_k)
u_k⁻ = u_J − u_k⁺
```

where `u_k⁺` is the wave arriving on edge `k` and `u_k⁻` the wave sent back out.

Sanity checks worth keeping as unit tests:

- `N = 2`, equal impedance → `u₁⁻ = u₂⁺`. Fully transparent. A drawn line with an
  incidental node behaves like an unbroken line.
- `N = 1` → `u⁻ = u⁺`, reflection coefficient `+1`. A free/open end.

### 2.4 Terminals and radiation

A terminal is a degree-1 node with an added virtual resistive port of admittance
`Y_rad`, which is how energy escapes into the world:

```
u_J = 2 · Y·u⁺ / (Y + Y_rad)
radiated = (u_J)² · Y_rad   (per step, into the emission analyzer)
```

`Y_rad` is set by the terminal's geometry — a blunt stroke end radiates hard, a stroke
that tapers to nothing radiates gently. This gives a free tradeoff nobody had to
author: **wide-open terminals leak too fast to charge; nearly-closed terminals store
energy but discharge slowly.**

### 2.5 Damping

Per-sample loss consolidated into one filter per delay line at the junction end
(standard waveguide practice — don't attenuate per sample).

- Broadband: `g_total = g^N` for delay length `N`.
- Frequency-dependent: a one-pole lowpass per delay line, so high frequencies die over
  distance.

The second one is doing real design work. It means high-frequency (thermal) energy
cannot travel far through ink, so **heat sigils must be compact and short-range while
kinetic sigils can be long and sprawling** — a range/element tradeoff that emerges from
one filter coefficient.

### 2.6 Nonlinearity

Sited at junctions (every closed loop necessarily has at least one node, including a
plain circle, whose start meets its end). Above an amplitude threshold set by the ink
type, apply an **asymmetric** saturating map:

```
u_out = (tanh(a·(u + d)) − tanh(a·d)) / a
```

The offset `d` is essential. A symmetric `tanh` produces only odd harmonics (3f, 5f),
which would mean no frequency doubling — and doubling into the thermal band was a
promised mechanic. The asymmetry buys even harmonics.

This is the deepest well in the design and the last thing to tune. It's also the main
instability risk (see §8).

### 2.7 Evanescent coupling — tunneling

Two edges that pass close without touching exchange energy. Detected at compile time:
any non-adjacent edge pair whose closest approach is under `g_max` gets a **coupler**
at that point.

Physically, evanescent decay length scales with wavelength, so long wavelengths tunnel
further. Implemented as a frequency-dependent 2×2 rotation in the cross path —
i.e. a lowpass filter on the coupling coefficient, with cutoff set by gap width:

```
A_out = √(1−κ²)·A_in + κ·B_in
B_out = √(1−κ²)·B_in − κ·A_in
```

with `κ = κ(gap, frequency)` realized as one biquad per coupler.

Consequences, all emergent: a small gap is a wireless junction; a large gap tuned to a
long wavelength is a blink; there is a gap width past which nothing crosses at any
tuning; and long-wavelength tunneling costs more mana because low bands carry more
energy per unit amplitude. Blink range becomes an equation the player pushes on rather
than a number in a config file.

**Caution:** filter approximation slightly breaks the exact passivity of the rotation.
Clamp with a per-coupler energy check (§8).

### 2.8 Chirality

Chirality decides the *sign* of world coupling — push vs. pull, heat vs. chill. Ice is
not implemented; ice is what negative thermal coupling looks like.

But chirality is a property of loops, not of waves (a wave takes all paths). Resolution
— compute it once at compile time as a band-weighted attribution:

1. Build a cycle basis via spanning tree (one fundamental cycle per non-tree edge).
2. For each cycle `c`: signed area by shoelace → `sign(A_c)`; circumference `L_c` →
   fundamental `f_c = c_wave / L_c`.
3. For each analysis band `b`, weight cycles by how near the band sits to their
   harmonics:

```
w(b,c) = Σ_n exp(−((f_b − n·f_c)/σ)²)
χ_b    = Σ_c sign(A_c)·w(b,c) / Σ_c w(b,c)
```

This is a small `bands × cycles` matrix computed once per sigil edit, then a lookup at
runtime. Cheap and defensible.

### 2.9 World coupling

Radiated signal at each terminal is run through a **filter bank** (8–12 log-spaced
bands, Goertzel or biquad bandpass) giving per-band energy per frame. Prefer this to
an FFT: cheaper, and it directly yields the quantity we want.

A data-driven matrix `M[band][field]` maps band energy onto three world fields:

| Field | Driven by | Reads as |
|---|---|---|
| **Kinetic** | Low bands | Force, shove, pull (sign from χ) |
| **Thermal** | High bands | Burn, chill (sign from χ) |
| **Phase** | One narrow upper band | Matter becomes partly non-interacting |

Three fields, not five. Keep the coupling curve in a data file so it can be tuned
without a rebuild.

The phase field is the mystical one, and it should be *one* deep thing rather than
three shallow ones. Matter with high phase-field value stops colliding: pass through
walls, ghost through enemies, and — combined with a kinetic impulse — displace without
collision, which reads as teleportation by a completely different mechanism than
tunneling. Two unrelated routes to the same fantasy is a good sign the physics is
carrying the design.

---

## 3. How the promised feel emerges

| Mechanic | Emerges from | Authored? |
|---|---|---|
| Shield | Impedance mismatch reflects incoming energy | No |
| Efficient emitter | Gradual taper → no reflection | No |
| Teleport (short) | Evanescent coupling across a gap | No |
| Teleport (displacement) | Phase field + kinetic impulse | No |
| Parry | Antiphase cancellation; add half a wavelength of path | No |
| Elements | Loop circumference → frequency → coupling curve | Curve only |
| Ice | Negative thermal coupling from CCW chirality | No |
| Charge-and-release | Loop stores, terminal `Y_rad` sets discharge rate | No |
| Overcharge | Asymmetric saturation → harmonics | Threshold only |
| Resonant shattering | Object resonance matched by tuned sigil | Resonances only |
| Range/element tradeoff | Frequency-dependent damping over distance | No |
| Beat frequencies | Two loops of differing circumference | No |

---

## 4. Architecture

One-way data flow, with two deliberate back-edges (world→ink for damage, world→sim for
incoming enemy energy).

```
  Input ──▶ Ink Layer ──▶ Parser ──▶ Compiler ──▶ Sim ──▶ Analyzer ──▶ Coupler ──▶ World
                 ▲                                  ▲                                │
                 └────────── damage ────────────────┴──── incoming energy ───────────┘
```

### 4.1 Layers

**Ink Layer.** Owns strokes as world-space objects. Each stroke: polyline, ink type,
durability, etched flag. Ink is physical — enemies break it, it burns, it can be
etched into stone for permanence at a cost.

**Parser.** Strokes → `SigilGraph`. Pure and deterministic. Runs on edit, not per frame.

**Compiler.** `SigilGraph` → `SimNetwork`. Allocates delay lines, precomputes junction
admittance sums, detects couplers, builds the cycle basis and chirality matrix. Also
edit-time only.

**Sim.** Fixed-step waveguide update. The only hot loop.

**Analyzer.** Filter bank per terminal → band energies.

**Coupler.** Band energies × chirality × `M[band][field]` → world field impulses.

**World.** Fields on a coarse grid, entities, projectiles carrying `(amplitude,
frequency, phase, position, velocity)` so interference works on incoming attacks too.

**Viz.** Not a debug view. The main view. See §7.

### 4.2 Core data structures

```
Stroke      { points[], inkType, durability, etched }
InkType     { Z, alpha, lowpassCoef, nlThreshold, nlAsymmetry, cost, durability }

SigilGraph  { nodes[], edges[], terminals[], ignitionPoints[] }
Node        { pos, incidentEdges[], isTerminal, isIgnition }
Edge        { nodeA, nodeB, polyline, lengthSamples, inkType }

SimNetwork {
  delayLines[]    // 2 per edge: ring buffer + write ptr + loss filter state
  junctions[]     // edge indices, admittances, precomputed 2/ΣY, NL state
  couplers[]      // (edgeA, posA, edgeB, posB, biquad state)
  terminals[]     // edge index, Y_rad, emission heading, filter bank state
  cycles[]        // circumference, signedArea, fundamental
  chiralityMatrix // [bands][1]  precomputed χ_b
  energyBudget    // running totals for the efficiency readout
}
```

### 4.3 Pipeline detail

**Parse.**
1. Resample every stroke to uniform arclength `dx` — must equal the sim's `dx`.
2. Find self- and cross-intersections via spatial hash.
3. Snap near-crossings within `ε ≈ 8px` into real nodes. Merge nearby endpoints.
   *Sloppy drawings must parse the way they look, or players blame themselves instead
   of experimenting.*
4. Enforce a minimum node separation so no edge quantizes to a delay length below ~4
   samples.
5. Emit nodes (intersections + endpoints + designated ignition taps) and edges.

**Compile.**
1. `lengthSamples = round(L/dx)`. Quantization shifts resonance by up to `0.5·dx/L` —
   about 1% for a 50px edge at `dx = 1`. If resonant shattering proves tuning-critical,
   add a one-pole allpass for fractional delay.
2. Precompute per-junction `2/ΣY` and per-edge `Y_k`.
3. Coupler detection: closest approach over non-adjacent edge pairs, spatial hash, hard
   cap on coupler count for perf.
4. Cycle basis, signed areas, chirality matrix.

**Sim step** (per fixed timestep):
```
for each delay line:  read tail → apply loss filter → hold
for each coupler:     exchange via filtered rotation
for each junction:    scatter (§2.3), apply nonlinearity if over threshold
for each terminal:    scatter with Y_rad, push radiated sample to analyzer
for each ignition:    inject active source sample
write heads, advance pointers
```

**Injection.** A tap injects a raised-cosine burst into both directions at an ignition
node. Burst *length* sets bandwidth: a quick tap is broadband, a held tap is a
narrowband tone. Repeated tapping at a loop's `f₀ = c/L` drives it resonantly, so
amplitude builds enormously for very little mana and off-beat tapping cancels the
player's own buildup. That's a rhythm skill layer inside a drawing game, and it makes
the same sigil weak in bad hands.

---

## 5. Numerical parameters

Starting values, all expected to move:

| Parameter | Value | Note |
|---|---|---|
| `dx` | 1 px | must match parser resampling |
| `c` | 400 px/s | wave speed, global |
| `dt` | 2.5 ms | `= dx/c`, sim at 400 Hz |
| Nyquist | 200 Hz | |
| Useful band range | ~1–50 Hz | loop of 100px rings at 4 Hz; 20px at 20 Hz |
| Analysis bands | 8–12 | log-spaced |
| Max edges/sigil | 64 | soft cap |
| Max total samples | ~20k | across all delay lines |

Cost: ~8M sample-ops/sec at full budget. Trivial in a compiled language, workable in JS
with typed arrays. Sim runs fixed-step and decoupled from render; the renderer
interpolates.

Frequencies here are *game* frequencies, not audio — visible pulsing, not sound. If the
band range feels cramped once nonlinearity is generating harmonics, raise `c` rather
than shrinking `dx`.

---

## 6. Game systems on top

**Mana.** Injected energy. The HUD tracks the split: radiated in the target band
(useful) / dissipated in ink / lost at couplers / reflected back into the injection
point. Efficiency = useful ÷ injected. This number is the min-max readout, and it
should be visible while drawing, not only after casting.

**Ink.** Drawing costs ink, casting costs mana — two separate economies. Ink types vary
in `Z`, damping, nonlinearity threshold, durability and price. Ink is a physical object
in the arena: enemies break it, fire chars it, and etching into stone makes it
permanent at a cost. A run therefore has a spatial dimension — arenas are places you
fortify, not just spaces you fight in.

**Combat.** Enemy attacks are wave packets carrying frequency and phase, superposed on
contact. Incoming energy that strikes player ink couples in — which means a badly
designed sigil can be turned against its owner, and a well-designed one can harvest.
Parrying is arithmetic under pressure.

**Progression.** Defeated enemies leave readable ink. Inspecting it is the main way new
ideas enter the player's vocabulary — and since enemies run the identical pipeline,
this is free content. A spellbook stores named discoveries; naming converts an accident
into an owned tool. A sigil serializes to stroke polylines plus ink types, so sharing
is nearly free and you get a community without building multiplayer.

**Determinism.** Parse and compile are deterministic. Floating-point variation across
platforms will break exact replay sharing; if that matters, fix the sim to a soft-float
or fixed-point path. Decide before shipping replays, not after.

---

## 7. Visualization

The single highest-leverage decision in the project. Players optimize only what they
can see, and this simulation is invisible by default.

- **Amplitude → brightness** along the ink, updated per frame.
- **Frequency → hue.** Low kinetic bands cool, thermal bands hot, phase band distinct.
- **Phase → moving pattern** travelling along the stroke, so direction and standing
  waves are readable at a glance.
- **Couplers** drawn as a shimmer across the gap, opacity by current `κ`.
- **Nodes** flash when the nonlinearity engages — the player must be able to see the
  moment a sigil starts generating harmonics.
- **Live efficiency meter** while drawing, before committing mana.

---

## 8. Risks and mitigations

**Nonlinearity + feedback loops → runaway.** The most likely way this project dies.
Mitigate with a hard per-network energy ceiling and a graceful failure that is also a
mechanic: an overdriven sigil chars its ink and burns out. Test with a pathological
sigil — many nested loops, maximum drive, lowest threshold ink — as a permanent
regression case.

**Coupler passivity.** Filtered rotation is only approximately lossless. Add a
per-coupler energy check that scales output down if energy out exceeds energy in.

**Delay quantization vs. tuning-critical play.** If resonant shattering demands better
than ~1% accuracy, add fractional-delay allpass filters. Don't do it preemptively.

**Discoverability.** Without §7, no one learns anything and the whole design reads as
random. If playtesters can't articulate *why* something worked, the visualization is
wrong, not the players.

**Depth on both sides.** One deep system plus one legible system reads as depth; two
deep systems read as noise. Keep the world simple — three fields, coarse grid, readable
materials. Resist making the world as clever as the ink.

---

## 9. Build order

Staged with kill criteria, because the early stages tell you whether the rest is worth
building.

1. **Two-edge waveguide, one junction, no game.** Watch reflection and interference on
   screen. *Kill criterion: if this doesn't read as alive and legible in a single
   evening, the visualization approach is wrong and everything downstream inherits the
   problem.*
2. **Parser + compiler.** Hand-drawn strokes → graph → network. Overlay the parse.
   Verify a plain circle rings at `c/L`.
3. **Junction scattering for arbitrary N**, with the two unit tests from §2.3.
4. **Damping, both broadband and frequency-dependent.** Confirm the range/element
   tradeoff appears without being coded.
5. **Terminals, filter bank, one world field** (kinetic). First time something in the
   world moves because of a drawing.
6. **Chirality and the full coupling matrix.** Three fields.
7. **Couplers.** Tunneling. Expect this to be the most fun day of the project.
8. **Nonlinearity.** Last, because it eats tuning time and destabilizes everything
   before it.
9. **Combat, ink economy, enemy sigils, spellbook.**

Steps 1–5 are the vertical slice. If the slice isn't compelling, no amount of 6–9 will
rescue it.

---

## 10. What success looks like

Someone builds a sigil that pumps a loop resonantly, harmonic-doubles into the thermal
band, tunnels the output across a gap into a second loop with no ignition point of its
own, and gets a remote emitter with no visible connection to anything.

You will not have designed that. That's the point.
