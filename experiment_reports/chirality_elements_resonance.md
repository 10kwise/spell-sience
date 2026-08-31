# Chirality / Elements / Resonance — measured parameters

Reference constants used throughout: `DX=4.0px`, `WAVE_SPEED_C=400px/s`, `FIXED_DT=0.01s`.
`FilterBank` band centers (cycles/sample, 6 log-spaced bands from 0.01 to 0.4):

| band | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| center | 0.0100 | 0.0209 | 0.0437 | 0.0915 | 0.1913 | 0.4000 |

A loop's fundamental: `f0 = 1/length_samples`, `length_samples = max(4, round(circumference/DX))`.

**Loop-closure safe zone.** All numbers below use `loop_with_tail_points(center, r, tail_length=40, n=48)`
only for radii where the shape actually closes into a loop+tail (verified via `sim.graph.nodes`
degree — see Bug 2). With these defaults that's roughly **r in [4.5px, 90px]**. Radii outside
that range silently produce an open two-terminal line with no loop at all; those radii are
excluded from the tables below and reported instead as regression cases.

---

## 1. Elements from loop circumference (§2.8, §3)

Driven with `repeated_taps` at each loop's own `period_steps = round(1/f0)` (15 taps,
amplitude 1.0), then peak per-band energy at the terminal weighted by
`KINETIC_BAND_WEIGHTS=[1.0,0.7,0.4,0.2,0.08,0.03]` vs `THERMAL_BAND_WEIGHTS=[0.03,0.08,0.2,0.4,0.7,1.0]`:

| r (px) | f0 (cyc/sample) | nearest band | kin-weighted | therm-weighted | kin/therm |
|---|---|---|---|---|---|
| 5.0  | 0.1250 | between band3/4 | 0.00567 | 0.05468 | **0.10** |
| 8.0  | 0.0769 | band3 (0.0915) | 0.00449 | 0.02412 | 0.19 |
| 10.0 | 0.0625 | band3-ish | 0.00415 | 0.02250 | 0.19 |
| 16.0 | 0.0400 | band2 (0.0437) | 0.01382 | 0.02133 | 0.65 |
| 20.0 | 0.0323 | band1-2 | 0.01433 | 0.02068 | 0.69 |
| 25.0 | 0.0256 | band1-2 | 0.01965 | 0.01839 | **1.07 (crossover)** |
| 31.8 | 0.0200 | band1 (0.0209) | 0.02560 | 0.01721 | 1.49 |
| 40.0 | 0.0159 | band0-1 | 0.03044 | 0.01592 | 1.91 |
| 63.7 | 0.0100 | band0 (exact) | 0.06646 | 0.01481 | 4.49 |
| 80.0 | 0.0079 | below band0 | 0.07094 | 0.01472 | **4.82** |

**Conclusions:**
- **Fire/thermal element:** `r ≈ 5px` (f0=0.125, sitting between bands 3 and 4). kin/therm ratio
  0.10 — thermal channel carries ~10x the kinetic channel. This is close to the small-radius edge
  of the closure-safe zone; don't go below ~r=4.5px with these defaults (Bug 2).
- **Kinetic/force element:** `r ≈ 80px` (f0=0.0079, below band0). kin/therm ratio 4.82. `r=63.7px`
  is an equally clean reference: its `f0=0.01` lands exactly on band0's center.
- **Neutral crossover:** `r ≈ 25px` (f0=0.0256) is the size where the element reads as neither
  clearly fire nor clearly force (ratio ≈ 1.07).
- The transition is smooth and monotonic across the whole tested range — the curve promised by
  §3's "Elements | Loop circumference → frequency → coupling curve" row is real and exactly as
  described, within the closure-safe radius range.

---

## 2. Beat frequencies from two differently-sized loops (§3)

**Topology (real coupled graph, not just superposed sound):** loop A (`r=80px`, 150px tail) and
loop B (`r=90px`, 150px tail, mirrored) both aimed at the same point; a third 60px stub stroke
from that point out to the world. Parser correctly forms a 3-way junction at the shared point
(degree 3) plus each loop's own degree-3 loop-closing junction, with **exactly one true
(degree-1) terminal** — the stub tip — which is where the combined signal is observed.

- `f0_A = 0.007937` cyc/sample (loop length 126 samples, r=80px)
- `f0_B = 0.007092` cyc/sample (loop length 141 samples, r=90px)
- Predicted beat period = `1/|f0_A − f0_B| = 1184 steps` (11.84s sim time)

Driven with simultaneous `held_tone` on each loop's own attach node at its own `f0` (amplitude
0.4, 400-step attack, sustained 7000 steps) so both loops ring continuously rather than decaying.
Measured from the stub terminal's `last_emitted`, carrier-smoothed to extract the envelope:

- **Measured beat period ≈ 1195–1199 steps** — within ~1% of the 1184-step prediction.
- Envelope swings between **~0.21 (near-cancellation trough)** and **~1.10 (near-reinforcement
  peak)** amplitude units — a ~5x, clearly visible slow swell/fade riding on top of the much
  faster ~130-step carrier oscillation (the two loops' own ringing).
- Troughs don't reach zero because the two loops have slightly different steady-state amplitudes
  (different admittance path through the shared junction) — physically expected for
  non-identical resonators, and it's what makes the beat pattern read as "two different loops"
  rather than a single clean sine.

---

## 3. Resonant tapping / rhythm mechanic (§4.3)

Loop `r=80px` (f0=0.007937, `period_steps=126`). **Injection site matters enormously**, more
than initially expected:

- Tapping the **open terminal itself**: on-beat repeated taps barely outperform a single tap
  (peak network_energy ~1.8x at best) because the terminal's own `Y_rad` leak bleeds each burst
  straight back out before it can reinforce anything.
- Tapping the **loop-closing junction node** (the degree-3 node where tail meets loop) instead:
  with a lower-leak ink (`rad_admittance_fraction=0.1`, vs default 0.6), on-beat
  `repeated_taps(period_steps=126, amplitude=0.8, burst_len=8, n_taps=20-30)` builds peak
  `network_energy` from a **0.0887 single-tap baseline up to a 0.207–0.243 plateau (2.3x–2.7x)**,
  saturating after only ~4 in-phase taps (a driven damped oscillator reaching steady state, not
  unbounded growth).
- **Off-beat** (period mismatched by 1.4x, i.e. `176` steps instead of `126`, same amplitude,
  same 20-30 taps): peak `network_energy` reaches only **1.4x–2.1x** the single-tap baseline —
  clearly below the on-beat case, but not full cancellation to baseline. As loop Q is raised
  (lower `broadband_gain`/`lowpass` loss), the gap between on-beat and off-beat narrows somewhat,
  because a high-Q resonance is still partially excited by a nearby-but-wrong drive frequency.

**Tuning implication:** with the *default* ink (`rad_admittance_fraction=0.6`), the rhythm
mechanic barely reads at all if the player taps the visible open end of the sigil (the intuitive
place to tap). To make "amplitude builds enormously for very little mana" (§4.3's own promise)
actually land, resonance-oriented ink should default much closer to a nearly-closed terminal
(`rad_admittance_fraction` ≲ 0.1) and/or lower per-sample damping, or the game should make the
loop-closing junction (not the terminal) a natural place to visually indicate as the "tap here"
point for a rhythm-tuned sigil.

---

## 4. Resonant matching / sharpness (§3 "Resonant shattering")

Loop `r=80px`, driven by `held_tone` at the loop-closing junction, amplitude 0.05 (linear regime,
well under `nl_threshold=3.0`), 800-step attack, steady-state energy averaged over the last
200-300 of ~4000-5000 driven steps, swept across nearby frequencies:

| frequency | steady-state energy | % of true peak |
|---|---|---|
| 0.75×f0 | 0.0111 | 8% |
| 0.86×f0 | 0.0504 | 38% |
| 0.90×f0 | 0.1078 | 81% |
| **0.92×f0 (true peak)** | **0.1331** | **100%** |
| 0.94×f0 | 0.1149 | 86% |
| 0.96×f0 | 0.0818 | 61% |
| 1.00×f0 (nominal, `f0=c/L`) | 0.0383 | 29% |
| 1.06×f0 | 0.0161 | 12% |
| 1.10×f0 | ~0.010 | ~7% |

**The resonance is sharp** — energy falls to under 10% within ±10% of the peak frequency.
Estimated FWHM ≈ 0.095 in relative-frequency units → **Q ≈ 10–11**.

**Notable finding:** the *true* driven peak sits at **≈0.92×f0**, about **8% below** the nominal
`f0 = c/L = 1/length_samples` used everywhere else in the codebase (chirality, harmonic
bookkeeping, the rhythm mechanic's tap period). At the literal nominal `f0` the shape is already
off its own best-response frequency, delivering only 29% of peak energy. This is because the
naive formula only accounts for the closed loop's own circumference — it ignores the tail and the
terminal's finite `Y_rad`, both of which are necessary for the loop to radiate/be observed at all
(§2.4) and both of which measurably shift the real resonance. **If "resonant shattering" needs
better than ~10% frequency accuracy, calibrate target frequencies against the actual driven
response of the full loop+tail+terminal structure, not the bare circumference formula** — or keep
tails short relative to loop circumference to minimize the shift (§4.3 already anticipates
needing a fractional-delay allpass for tuning-critical play; this shift is a second, independent
source of the same kind of error, on top of the ~1% delay-quantization error already documented).

---

## Bugs found

### 1. (Already fixed, verified) `compute_chirality` no-loop default
Confirmed fixed: an open line now returns `[1.0]*6` instead of all-zero; a CW loop returns `+1.0`
per band (where a harmonic reaches that band) and a CCW loop returns `-1.0`. Verified directly.

### 2. Loop self-closure detection is fragile — same class of bug, different trigger, NOT fixed
`loop_with_tail_points` shapes fail to actually close into a loop (self-loop edge + degree-3
junction) outside a narrow, undocumented radius/point-count window:
- **Small radius:** with default `n=48, tail_length=40`, radii **r ≲ 4.5px** fail to close —
  the whole stroke parses as one open two-terminal line (2 nodes, both degree 1, 0 self-loop
  edges). Increasing `n` up to 500 does **not** fix it — `Stroke.resampled`'s
  `smoothing_window=5` box-filter blurs across most or all of a loop this small before the
  self-intersection snap ever runs.
- **Large radius:** radii **r ≳ 92px** (default `n=48`) also fail to close, for the opposite
  reason: wider spacing between the 48 loop vertices means the smoothing pass drags the
  tail/loop corner further than `snap_eps=8px` from the true closure point. Raising `n` to 72+
  fixes r=100px in testing.
- **Very low `n` at otherwise-safe radii** (e.g. `n=3` or `n=4`) doesn't fail cleanly either — it
  can produce a **spurious extra node with degree 4** (a crossing the coarse polyline's own
  vertices accidentally land near each other) or an unexpected **second terminal** where none
  was intended (`r=60px, n=4` → 3 nodes, one degree-4, one spurious second terminal at (60,0)).

**Impact:** a shape that visually looks like a valid closed loop can silently lose its entire
loop-based mechanic (resonance, chirality sign, the loop-closing nonlinearity site) with no error
and no visible topology change apart from inspecting node degrees directly. Confirmed via
`sim.graph.nodes`/`sim.terminals` at r=3, r=100, r=120, n=48, and at r=100/r=3 with n swept from
3 to 500. **Fix direction:** scale point count with circumference inside `loop_with_tail_points`
(or any loop generator), reduce/adapt the smoothing window relative to local point spacing, or
explicitly snap a closed stroke's own start/end point rather than relying on generic
point-proximity self-intersection detection.

### 3. Chirality silently drops to exactly 0.0 for a loop's high-frequency bands — same bug class as #1, second surviving instance
`compute_chirality`'s per-band weight is a sum of Gaussians centered on a loop's harmonics
(`n=1..8`, `sigma=0.03`). For any loop whose fundamental is low enough that `8×f0` still falls
far from a band center, that Gaussian sum underflows to numerical zero and the function's own
`else 0.0` fallback fires — **even though a real, well-defined loop with a real winding sign
exists.** Verified directly:

```
r=  5.0  chirality=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]      (all bands' harmonics reachable)
r= 16.0  chirality=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
r= 25.0  chirality=[1.0, 1.0, 1.0, 1.0, 1.0, 0.0]      <- band5 silently zeroed
r= 40.0  chirality=[1.0, 1.0, 1.0, 1.0, 1.0, 0.0]
r= 63.7  chirality=[1.0, 1.0, 1.0, 1.0, 1.0, 0.0]
r= 80.0  chirality=[1.0, 1.0, 1.0, 1.0, 1.0, 0.0]
```

Because `THERMAL_BAND_WEIGHTS[5] = 1.0` (the single heaviest thermal weight, and also where
`PHASE_BAND_WEIGHTS` peaks), this silently zeroes the **signed** thermal (burn/chill) contribution
from the top band — and with it, a real chunk of "ice is negative thermal coupling from CCW
chirality" (§2.8) — for essentially every loop at or above the ~25px "neutral crossover" size,
i.e. most kinetic-leaning loops in section 1's own table. `phase_drive_from_bands` is unaffected
(phase intentionally passes `chirality=None`, always unsigned by design). **Fix direction:**
increase `max_harmonic` and/or `sigma` so large low-`f0` loops still reach the top band(s), or
replace the hard `else 0.0` with a sign carried over from the nearest harmonic instead of a true
zero when `total_weight` underflows.

### 4. Energy ceiling protects the wave sim but not the analyzer/world-coupling pipeline
The §8 hard per-network energy ceiling (`max_energy=50` default) does exactly what it's supposed
to do to the delay-line buffers — a single `amplitude=1e6` tap is reined in from `network_energy
=50` back down to `~1.65` by step 50 and to `~1.2e-6` by step 500. But `Network._clamp_energy`
only rescales `edge.forward.buffer`/`edge.backward.buffer` *after* that step's `radiated` value
and each node's `last_emitted` have already been computed and returned — and `last_emitted` is
exactly what `Sim.step()` feeds straight into the terminal's `FilterBank` (the analyzer, the
foundation of all world coupling). Result: the analyzer sees the full, unclamped, multi-million
sample directly. Measured downstream `kinetic` drive value: **peaks above 3.0e10**, still **~6e5
at step 500** and **~18 at step 1000** — decaying only via the FilterBank's own slow leaky
integrator (`envelope_coef=0.05`, i.e. ~0.95 per-step retention) long after the wave sim itself
has already recovered. **Impact:** one out-of-range injection (a UI bug, a bad enemy-cast
amplitude, a pathological sigil) can push kinetic/thermal/phase world-coupling many orders of
magnitude out of scale for hundreds of steps even though the numerical-stability mitigation is
working as designed. **Fix direction:** clamp injection amplitude at the injection site, and/or
apply the same energy-ratio scale factor `_clamp_energy` computes to `radiated` and each
terminal's `last_emitted` in the same step, before either reaches the analyzer.

### 5. Minor: unvalidated ink parameters crash at compile time
`InkType(impedance=0.0, ...)` and `InkType(nl_threshold=0.0, ...)` both raise an unhandled
`ZeroDivisionError` from `compile_graph` (`1.0/ink.impedance` and `1.0/ink.nl_threshold`)
rather than failing gracefully or clamping. Any path that lets ink parameters come from
player-authored or randomized (enemy) data should validate/clamp these before compiling.

### 6. Minor: degenerate low-point-count shapes silently produce empty/terminal-less graphs
`circle_points(..., n=1)` produces 0 edges; `circle_points(..., n≤3)` produces a single self-loop
node with **no terminal at all** (which is correct/by-design for a bare circle per §2.4 — a
closed loop has no terminal — but is easy to mistake for a bug when testing small `n` values, so
noting it explicitly here). Not a crash, but worth an explicit minimum-point-count guard or
warning in any UI path that lets `n` shrink this far.

---

## Files
- Report: `c:\Users\HP\Documents\spell sience\experiment_reports\chirality_elements_resonance.md`
- Scenarios: `c:\Users\HP\Documents\spell sience\experiment_reports\chirality_elements_resonance.json`
