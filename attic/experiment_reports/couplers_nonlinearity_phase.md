# Couplers / Nonlinearity / Phase — Experiment Results

All experiments run against `sigilwave/experiment.py`'s harness (`DX=4.0`, `WAVE_SPEED_C=400`,
`FIXED_DT=0.01s`, `SNAP_EPS=8.0`, `COUPLER_G_MAX=30.0`). Filter bank centers (cycles/sample):
`[0.0100, 0.0209, 0.0437, 0.0915, 0.1913, 0.4000]`.

---

## 1. Teleport (short) via evanescent coupling

Two parallel 300px lines (default ink, Z=50), gap swept. Driven with `held_tone` at the
attack-side terminal (freq 0.02 cyc/sample = 2 Hz game-frequency, amplitude 1.0,
attack_steps=300, duration_steps=2500, measured over 4000 steps). "Tunneled fraction" =
actual radiated energy (`u_j² · Y_rad`) at the far stroke's terminals ÷ (that + the near
stroke's own far-end terminal energy).

| gap (px) | couplers | frac. energy tunneled |
|---|---|---|
| 8.5  | 1 | **26.5%** |
| 9.0  | 1 | 24.8% |
| 10.0 | 1 | **21.6%** |
| 12.0 | 1 | 16.3% |
| 15.0 | 1 | 10.3% |
| 20.0 | 1 | 4.2% |
| 25.0 | 1 | 1.1% |
| 29.0 | 1 | 0.13% |
| 29.9 | 1 | 0.05% |
| **30.0** | **0** | **0%** (hard cutoff — confirmed, see Bugs) |
| 35.0 | 0 | 0% |

**Recommendation: gap = 10px, default ink both sides.** 21.6% of the driven energy
crosses to the untouched stroke — unmistakably a deliberate "wireless junction," not
noise. `kappa_for_gap(10, 30) ≈ 0.436`, `lowpass_coef_for_gap(10, 30) ≈ 0.273`. Gaps
under ~12px are all strongly in "clear teleport" territory (>15%); by 20px it reads as
a faint effect; past 25px it's negligible even though a coupler still technically
exists until exactly 30px.

**Wavelength dependence** (gap=10, default ink): confirms §2.7's claim — low
frequencies tunnel further for the same gap.

| freq (cyc/sample) | frac. tunneled |
|---|---|
| 0.010 | 17.9% |
| 0.020 | 21.6% |
| 0.050 | 9.6% |
| 0.100 | 4.5% |
| 0.150 | 2.3% |

**Ink mismatch** (gap=10): matched impedance always gives the same fraction (21.6%)
regardless of absolute Z (a linear scaling effect only, since kappa depends on gap not
Z); an impedance mismatch (Z=50 vs Z=150) roughly halves the tunneled fraction (21.6%
→ 8.4%) on top of the coupler loss, because the mismatch itself reflects some of what
does cross back at the far terminal's own junction.

**Note:** the parser's own snap logic uses `snap_eps=8.0` on *every* resampled point
pair between strokes, not just endpoints — so a gap under `snap_eps` (8px) fuses the
two strokes into a single node instead of forming a coupler at all. Any teleport
scenario needs `8px < gap < 30px`.

---

## 2. Overcharge via nonlinearity

Shape: `loop_with_tail_points((0,0), radius=30, tail_length=40, n=48, clockwise=True)`
— circumference ≈188.5px → 47-sample loop edge, f0 = 0.02128 cyc/sample, which lands
almost exactly on filter-bank band[1] (0.0209) with 2f0=0.0426 landing almost exactly
on band[2] (0.0437). Driven with a sustained `held_tone` at f0 (never a burst — a burst
alone excites every harmonic of a resonant ring regardless of nonlinearity; confirmed
directly, see Methodology note below).

**Methodology trap confirmed for real**: even with the nonlinearity forced off
(`nl_a=None`), FFT of the steady-state ring signal shows a 2nd-harmonic/1st-harmonic
energy ratio of ~5.77, constant at every drive amplitude (0.02 through 2.0) — this
small tight loop is high-Q enough that the drive's own attack ramp (necessarily
broadband over its ramp-up) rings up the ring's own 2nd-harmonic resonant mode, which
then decays very slowly. **Raw 2nd-harmonic energy is not evidence of overcharge by
itself; only the *excess* over a matched linear control is.**

Comparing terminal `thermal`/`kinetic` drive ratio (the actual gameplay-relevant
signal, from `coupling.py`) against a linear control ink (`nl_threshold=1e6`, same
shape/drive — ratio holds flat at **0.1579** for every amplitude, as expected for a
linear system):

| amp | stock ink (nl_threshold=3.0, nl_asymmetry=0.25) excess | hot ink (nl_threshold=0.5, nl_asymmetry=0.4) excess |
|---|---|---|
| 0.02 | 1.00x | 1.07x |
| 0.10 | 1.02x | 1.24x |
| 0.20 | 1.05x | **1.34x** (peak) |
| 0.30 | 1.07x | 1.29x |
| 0.50 | 1.12x | 1.08x |
| 0.70 | 1.16x | 0.95x (below baseline) |
| **1.00** | **1.20x** | 0.87x |
| 1.50 | 1.22x (peak) | 0.83x |
| 2.00 | 1.19x | 0.82x |
| 3.00 | 1.05x | 0.81x |

**Findings:**
- Stock/default ink (`nl_threshold=3.0`, `nl_asymmetry=0.25`) needs drive amplitude
  **≈1.0–1.5** (in the harness's raw tap-amplitude units) before the thermal excess is
  unambiguous (+20%+ over the linear baseline) — a believable "overdrive it and it
  starts generating real heat" threshold for a kinetic-shaped sigil.
- A "hotter" ink (`nl_threshold=0.5`, `nl_asymmetry=0.4`) turns on much earlier
  (amplitude **≈0.1–0.2** for +24–34% excess) but **self-limits past amplitude ≈0.5**
  — the excess ratio actually drops *below* the linear baseline at high drive. This is
  real mode competition (the fundamental itself saturates harder than it feeds the
  2nd-harmonic mode), not a bug — matches the design doc's own "last thing to tune"
  warning. Gameplay reading: a very low-threshold ink gives an early, satisfying
  overcharge spike but punishes players who keep pushing past it — a legitimate skill
  ceiling rather than "more mana = more effect" forever.
- Recommend **`nl_threshold≈1.0, nl_asymmetry≈0.35`** as a middle ground: noticeable
  excess by amplitude ~0.3–0.5, without the hot ink's rollback inside the amplitude
  range a player would plausibly reach by hand-tapping/holding.

---

## 3. Teleport (displacement) via phase + kinetic

A single 400px open line (default ink). No loop, no nonlinearity needed — phase is
driven directly by band energy, not harmonic content. Combined drive at the single
terminal: `low_amp·sin(2π·0.015·i) + high_amp·sin(2π·0.38·i)`, linear attack over 150
steps, `low_amp=1.0` (kinetic, lands near band[0]/[1]), `high_amp=3.0` (phase, lands on
band[5], weight 1.0 in `PHASE_BAND_WEIGHTS`). Token manually stepped with a **tight**
bounds rect (`Token.update`'s realistic use, not `Sim.apply_world_coupling`'s default
200,000px arena) — wall at x=60, token starts at x=0.

Result: phase crosses `PHASE_GHOST_THRESHOLD=0.5` at **step 56 (t=0.56s)**, pos=3.59
(nowhere near the wall yet). Token keeps building velocity while ghosted and crosses
**x=60 at step 104**, phase still pinned at 0.994 — i.e. it passes straight through
where the wall would have stopped it, then keeps accelerating (`v≈1800 px/s` steady
state) long after. This is a clean, unambiguous demonstration of the mechanic: pure
phase-band drive alone does ghost the token (harmlessly, no displacement) but adding
even a modest deliberate low-band component turns that ghost window into real
teleportation-by-displacement.

**Balance finding — kinetic leaks into "pure phase" drives.** `KINETIC_BAND_WEIGHTS =
[1.0, 0.7, 0.4, 0.2, 0.08, 0.03]` — the top band's weight is only 0.03, not 0, and
`apply_world_coupling` scales kinetic by 40000 vs phase's 40 (1000x). Driving the
*same* terminal with **zero** low-frequency component (`low_amp=0.0`, only the
high-frequency phase tone) still produces measurable kinetic drive (0.02 by step 104)
and the token reaches the same wall on its own, only ~25% later (~step 131 vs 104) with
no deliberate kinetic ingredient at all. The intended two-ingredient combo ("phase +
kinetic impulse") is present but weakly differentiated from "just drive it hard" as
currently tuned — recommend either zeroing `KINETIC_BAND_WEIGHTS[-1]` (and the
matching top of `THERMAL_BAND_WEIGHTS[0]`) or narrowing the 1000x kinetic/phase scale
gap in `apply_world_coupling`, so ghosting doesn't come with a free shove.

---

## 4. Parry via antiphase cancellation

Y-junction sigil: three 250px lines (`attack`, `defense`, `world`) meeting at the
origin from angles 180°, 150°, -30° (all lines the same ink → same impedance → the
junction's admittance-weighted sum genuinely cancels when the two incoming waves are
equal-and-opposite, rather than relying on `dual_tap`'s per-node dict, which can
silently overwrite — see Bugs). Edge lengths: 61/61/64 samples — attack and defense
branches equal length (equal time-of-flight to the junction), world branch slightly
longer only because of resampling rounding.

`dual_tap([attack_terminal], [defense_terminal], amplitude=1.0, burst_len=24,
delay_steps=D, sign_b=S)`. Radiated energy measured at the `world` terminal only
(the branch the attack is "trying to reach"):

| scenario | radiated at world terminal | vs. attack-alone |
|---|---|---|
| attack alone | 0.06515884 | 1.00x (baseline) |
| **attack + defense, delay=0, sign=-1 (correct parry)** | **0.00000000** | **∞x suppression** (exact cancellation, machine precision) |
| attack + defense, delay=5 (off by ~20% of burst_len) | 0.03165011 | 0.49x (partial cancel) |
| attack + defense, delay=12 (off by 50%) | 0.10695571 | 1.64x (**worse than no defense**) |
| attack + defense, delay=24 (off by one full burst) | 0.13032229 | 2.00x |
| attack + defense, delay=48/50 | 0.13032 | 2.00x |
| attack + defense, delay=0, sign=+1 (wrong sign — reinforces) | 0.26063536 | 4.00x (exactly `(2A)²`) |

**This is a real skill check, not a freebie.** Exact timing (delay=0 for two
equal-length branches) gives perfect, total cancellation. Being off by even 20% of the
burst length only gets you half the benefit. Being off by a full burst length or more
doesn't just fail to help — the defense burst arrives *after* the attack has already
passed, and its own energy independently reaches the world terminal, making the
combined result **2x worse than doing nothing**. Using the wrong sign (failing to
invert) is unambiguously worse still (4x). The "add half a wavelength of path" trick
from the design doc is the geometric way a player achieves `delay_steps` naturally
(extra edge length between the defense stroke and the junction); `dual_tap`'s
`sign_b=-1.0` stands in for the polarity the ink+topology would otherwise have to
supply on its own.

---

## Bugs / structural issues found

1. **`dual_tap` silently overwrites instead of summing when `node_ids_a` and
   `node_ids_b` share a node.** (`sigilwave/experiment.py`, `dual_tap`). Its injections
   dict does `injections[nid] = burst[step_i]` for the A set, then unconditionally
   `injections[nid] = sign_b * burst[j]` for the B set — if the two sets overlap and
   both bursts are active on the same step, the B value clobbers the A value rather
   than adding to it. Verified directly: `dual_tap([5],[5],...,sign_b=-1.0,
   delay_steps=0)` yields `injections[5] == -burst[i]` every step — the attack's own
   contribution is discarded, not cancelled by superposition. This matters because
   "inject attack and defense at the exact same point" is a natural way to model
   combat (incoming enemy energy striking the same terminal the player's ink already
   occupies, §6). The parry experiment above avoids this by injecting attack and
   defense at physically distinct terminals that meet at a separate junction node — a
   real fix should either document that `node_ids_a`/`node_ids_b` must be disjoint, or
   have `dual_tap` add into the dict (`injections[nid] = injections.get(nid, 0.0) +
   value`) so same-node use doesn't quietly produce wrong physics.

2. **`Token.update`'s un-ghosting can snap the token back across an arbitrarily large
   distance in a single frame.** (`sigilwave/world.py`). While `phase >
   PHASE_GHOST_THRESHOLD` the token can travel any distance outside `bounds` under a
   sustained kinetic push (nothing limits it). The instant `phase` decays to ≤0.5,
   collision resumes and the very first boundary check unconditionally clamps
   position to `bounds.right - radius` (or the matching edge), regardless of how far
   outside it drifted. Verified: token driven 4099px outside a 100px-wide arena while
   ghosted, then snapped back 4009px in one 10ms frame the instant phase crossed 0.5,
   with velocity flipped to -2377 px/s by the `*= -0.5` bounce logic. In a real game
   this reads as the token vanishing off-screen while ghosted and then instantly
   reappearing at the wall moving backward at high speed — a jarring discontinuity
   that undercuts the "ghosting reads as legible displacement" design goal (§2.9).
   Recommend either capping how far the token can travel outside `bounds` while
   ghosted, or re-deriving the clamp target from the token's actual re-entry point
   (e.g. via a raycast against the boundary along its velocity) instead of an
   unconditional snap-to-wall.

3. **Coupler detection has a hard, discontinuous cutoff exactly at `g_max`, not a
   smooth roll-off.** (already flagged in the assignment as a known trap; corroborated
   here). `kappa_for_gap(gap, g_max)` is a smooth exponential in `gap` and is still
   ~0.115 at `gap == g_max`, but `find_coupler_sites` excludes any pair with `d >=
   g_max` outright, so the coupler simply doesn't exist past that point — tunneled
   energy goes from a small-but-real ~0.05% at gap=29.9 to exactly 0% at gap=30.0 with
   no ramp in between. A player tuning blink range right at the edge of `g_max` will
   see a cliff, not a gradual fade.

4. **`loop_with_tail_points(tail_length=<float>)` crashes.** (`sigilwave/experiment.py`).
   `line_points(tip, attach, n=max(2, tail_length // 8))` — floor-division on a float
   `tail_length` (natural given every other geometry helper in the file accepts
   floats, e.g. `radius=80.0`) returns a `float`, and `range(n + 1)` then raises
   `TypeError: 'float' object cannot be interpreted as an integer`. Trivial fix:
   `int(tail_length // 8)`.

5. **Confirmed working correctly (not a bug):** the `compute_chirality` fix described
   in the assignment — verified a plain open line (no closed loop) returns
   `[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]` rather than all-zero, so open-stroke kinetic/thermal
   push is not silently killed.

6. **Energy ceiling stress test passed cleanly.** A pathological ink
   (`nl_threshold=0.01`, `nl_asymmetry=0.9`) on a closed loop driven with amplitude-1000
   broadband-ish injection, at `max_energy` from `1e-6` up to `0.1`, never went
   non-finite and the clamp held the network at essentially exactly the ceiling
   (`peak_energy_seen == max_energy` to 6 decimals) at every level tested — `
   _clamp_energy` in `network.py` is robust even at extreme low ceilings.
