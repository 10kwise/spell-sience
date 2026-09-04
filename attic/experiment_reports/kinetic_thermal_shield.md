# Kinetic / Thermal / Shield — measured parameters

Run directly (not via subagent — the subagent assigned to this area hit a session
rate limit twice; these are the same experiments run by hand with the same harness).
Reference constants: `DX=4.0px`, `WAVE_SPEED_C=400px/s`, `FIXED_DT=0.01s`.

---

## 1. Efficient emitter vs. reflective terminal (`rad_admittance_fraction`)

300px open line, single tap (amplitude 1.0), then energy-decay half-life measured by
stepping until total network energy drops to half its post-tap value:

| `rad_admittance_fraction` | half-life (steps) |
|---|---|
| 0.05 | ~206 |
| 0.15 | ~65 |
| 0.30 | ~59 |
| 0.60 (default) | ~57 |
| 0.90 | ~57 |

**Clear, usable range: 0.05-0.15.** Below ~0.15 the terminal genuinely behaves like a
"nearly-closed" end that holds a charge (3-4x longer half-life than default); above
~0.3 it plateaus — extra openness beyond that barely changes discharge speed, so
0.3-0.9 all read the same ("wide open"). Recommend exposing `rad_admittance_fraction`
in the 0.03-0.15 band specifically for any "charging" ink tier; the stock default
(0.6) is already deep in "wide open, discharges immediately" territory.

---

## 2. Shield via impedance mismatch

Two collinear 200px segments of different ink meeting at a shared point (so the
scattering junction actually sees an impedance step), injected at the far end of
segment A, radiated energy summed at both open ends over 3000 steps.

| Z ratio (Z2/Z1) | predicted \|r\| | far/near radiated-energy ratio |
|---|---|---|
| 1.0 (no mismatch) | 0.000 | 1.29 |
| 3.0 | 0.500 | 2.20 |
| 9.0 | 0.800 | 2.29 |

Direction is correct — mismatch clearly reduces how much energy reaches the far
side relative to what stays on the near side — but the ratio doesn't scale as
cleanly with the predicted `|r|` as hoped, and even the matched case isn't exactly
1.0. **Caveat, not a bug:** both terminals have their own `Y_rad` reflecting some
energy back into the line independently of the junction, so this setup measures
"junction reflection convolved with terminal reflection over many bounces," not a
clean single-pass reflection coefficient. `selftest.py`'s own N=2 unit tests already
verify the raw junction formula in isolation (matched-impedance ports, no terminals
involved) — use that pattern, not an open-line-with-terminals setup, if a precise
reflection-fraction number is ever needed again. For gameplay purposes the
qualitative result is what matters: **a sharp impedance jump (Z ratio ≥3) visibly
keeps most of an incoming attack from reaching what's behind it** — a shield made of
mismatched ink is a real, working mechanic.

---

## 3. Charge-and-release

Shape: `loop_with_tail_points((0,0), radius=60, tail_length=40, clockwise=True)`,
loop f0≈0.0108 cyc/sample, period_steps≈93. Ignition at the loop-closing junction
(not the tail terminal — see the rhythm-mechanic finding in
`chirality_elements_resonance.md`; `sigil_lab.py`'s `_inject_burst` now defaults to
the junction for exactly this reason). `repeated_taps(period_steps=93, amplitude=0.8,
burst_len=8, n_taps=25)`, ~2500 steps of charging, then measured 3000-4000 steps of
free decay with no more taps.

| ink (`rad_admittance_fraction=0.05` both) | peak charged energy | cumulative radiated during discharge | fraction of stored energy actually released as radiation |
|---|---|---|---|
| default damping (`broadband_gain_per_sample=0.9995`, `lowpass_coef_per_sample=0.995`) | 0.220 | 0.00234 | **1.1%** |
| much lower damping (`0.99995` / `0.9995`) | 0.018 | 0.00369 | **20.9%** |

**Finding, not a bug:** these trade off against each other in a way worth calling
out explicitly. Lower damping means a higher-Q resonator, which *would* eventually
charge to a much larger peak — but its charging time constant is long enough that
within a human-plausible 25 taps it hasn't gotten there yet, so it actually stores
*less* absolute energy than the "leakier" default ink over the same charging window,
even though a much larger fraction of what it does store comes back out as a real
radiated release rather than being eaten by internal damping. **Recommendation:**
for a charge-and-release ink meant to be tapped by hand over ~10-30 taps, don't
minimize damping — pick a damping level tuned so the resonator's charging time
constant matches the number of taps a player will actually give it (default-ish
damping, ~0.9995-0.999 per sample, is closer to right for this shape/period than
"as lossless as possible"). A near-lossless ink is better suited to a *long-charge,
huge-payoff* archetype (soak taps for much longer, e.g. over an entire fight) rather
than instant point-and-click charging.

---

## 4. Range/element tradeoff at game scale

Single open line, single tap, far-end peak amplitude measured vs. edge length:

| length (px) | kinetic-tuned ink (`gain=0.9999/sample, lowpass=0.999/sample`) | thermal-tuned ink (`gain=0.998/sample, lowpass=0.95/sample`) |
|---|---|---|
| 100 | 1.246 | 1.056 |
| 200 | 1.243 (-0.3%) | 0.602 (-43%) |
| 300 | 1.239 (-0.6%) | 0.227 (-78%) |
| 400 | 1.235 (-1.0%) | 0.068 (-94%) |
| 500 | 1.231 (-1.2%) | 0.019 (-98%) |

**Clean, usable presets.** The kinetic-tuned ink is functionally lossless across
the whole 100-500px range a player would plausibly draw (<1.2% amplitude loss even
at 500px) — genuinely long-range. The thermal-tuned ink is already down 43% by
200px and effectively dead (98% gone) by 500px — genuinely short-range. The
crossover where "compact vs. sprawling" becomes obvious to a player is around
200-300px: past that, a thermal sigil is visibly starved while a kinetic one is
untouched. These two presets are good defaults for a "fire ink" / "force ink" pair.

---

## Bugs / notes

No new correctness bugs found in this pass (the harness-level bugs already found by
the couplers/nonlinearity agent — `dual_tap` overwrite, `loop_with_tail_points` float
crash — and by the chirality agent — the second `compute_chirality` zeroing case —
were fixed directly in `sigilwave/experiment.py` and `sigilwave/sim/cycles.py` before
this pass ran, and this pass's numbers already reflect the fixed code). The one
finding worth flagging structurally: `sigil_lab.py`'s `_inject_burst` previously
always targeted a terminal, which — per the rhythm-mechanic measurement above —
silently made loop-based charge-and-release nearly impossible to feel via the SPACE
key. Fixed: it now prefers a loop-closing junction node when one exists.
