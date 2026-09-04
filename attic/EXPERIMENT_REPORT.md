# Experiment Report — finding meaningful gameplay interactions

This covers three things, in the order they were done: (1) building a way to interact
with and observe the sim, both interactively and headlessly; (2) using that to find
concrete, tested parameter values for every mechanic in the design doc's §3 table
("How the promised feel emerges"); (3) a bug hunt that ran throughout, since several of
the mechanics turned out to be silently broken or unreachable until fixed.

Detailed per-mechanic numbers live in `experiment_reports/*.md` (and matching `.json`
scenario proposals); this file is the synthesis — what was found, what was fixed, and
what's now loaded into the live lab as preloadable scenarios.

## 1. Ways to interact with and observe the system

- **`sigilwave/experiment.py`** — a headless harness with no display dependency: shape
  generators (`circle_points`, `line_points`, `spiral_points`, `zigzag_points`,
  `loop_with_tail_points` — a closed loop needs an open tail to radiate at all, since a
  bare circle has no terminal), drive patterns (`tap`, `held_tone`, `repeated_taps`,
  `dual_tap`), and a `Sim` class that runs the identical pipeline `sigil_lab.py` uses
  and returns full per-step telemetry. This is what let three parallel investigations
  (two agents plus direct work) run fast, repeatable experiments and log real numbers
  instead of eyeballing a window.
- **`sigil_lab.py` gained:**
  - A live efficiency readout (radiated/injected) in the HUD — §7 calls for this
    explicitly and it was missing.
  - **Scenario preload** (keys 1-9) — `sigilwave/scenarios.py` holds named, tested
    stroke+ink+drive combinations; pressing a number key clears the canvas and loads
    one instantly. All 9 below are wired up and verified end-to-end.
  - **HOLD H for a sustained tone**, new alongside the existing SPACE tap. The design
    doc is explicit that "a quick tap is broadband, a held tap is a narrowband tone"
    (§4.3) — but until now there was no way to actually hold one. This turned out to
    be load-bearing: overcharge, resonance buildup, and phase-ghosting are all
    reachable *only* with a sustained tone (verified directly — even 30 rapid re-taps
    with the old SPACE-only mechanic never crossed the phase-ghost threshold). Holding
    H locks to a loop's own resonant frequency automatically when the sigil has one;
    otherwise it drives a combined low+high tone (kinetic band + phase band together —
    proven to be the minimum needed for phase-driven displacement, see scenario 6).

## 2. The 9 preloadable scenarios (press 1-9 in the live lab)

| Key | Name | Mechanic (§3) | Drive |
|---|---|---|---|
| 1 | Straight shove | baseline kinetic push | SPACE |
| 2 | CW loop-with-tail | push + burn (chirality sign) | SPACE |
| 3 | CCW loop-with-tail | pull + chill ("ice") | SPACE |
| 4 | Evanescent tunnel | teleport (short) | SPACE |
| 5 | Overcharge | asymmetric saturation → harmonics | HOLD H |
| 6 | Phase teleport (displacement) | phase field + kinetic impulse | HOLD H |
| 7 | Shield | impedance-mismatch reflection | SPACE |
| 8 | Charge-and-release | loop stores, terminal discharges | HOLD H |
| 9 | Range/element tradeoff | frequency-dependent damping | SPACE |

Two mechanics from §3 are deliberately **not** single-key preloads: **parry**
(antiphase cancellation) needs a precisely-timed two-part drive sequence, not a single
tap, and **beat frequencies** need two loops driven simultaneously and held for many
seconds to see the slow envelope swing. Both are fully verified and quantified via the
harness (see `experiment_reports/couplers_nonlinearity_phase.md` and
`chirality_elements_resonance.md`) — they just don't fit the "press one key" format
without a dedicated input mode the lab doesn't have yet (see Follow-ups).

## 3. Bugs found and fixed

Ranked by how much of the game they were silently breaking:

1. **Every open-ended stroke was inert.** `compute_chirality` returned all-zero
   chirality for any shape with no closed loop, and `kinetic_drive_from_bands`/
   `thermal_drive_from_bands` multiply band energy by that value as a *signed
   multiplier* — so a plain line (the exact shape stage 5 used to prove "something
   moves") produced **zero** push and **zero** heat once chirality was wired in.
   Fixed: no-loop case now defaults to +1.0 (plain outward push/burn) instead of 0.

2. **The same bug, second instance:** for a loop whose fundamental frequency sits far
   below a given analysis band, `compute_chirality`'s Gaussian weighting for that band
   numerically underflows to zero — so large, "kinetic-sized" loops silently lost
   their *signed* thermal contribution on the top band specifically (the single
   heaviest-weighted thermal band), quietly killing "ice" for most force-sized loops.
   Fixed: falls back to the nearest cycle's real sign instead of a neutral zero.

3. **Loop-based rhythm/charge mechanics were unreachable via SPACE.** Tapping a loop's
   own terminal barely builds resonance — the terminal's leak bleeds each tap back out
   before it can reinforce anything (measured: ~1.8x after 20+ on-beat taps vs. 2.3-
   2.7x when tapping the loop-closing junction instead). Fixed: `_inject_burst` and
   the new held-tone ignition now both prefer the loop junction over the terminal.

4. **No way to hold a sustained tone at all** (see §1 above) — meant overcharge,
   resonance buildup, and phase-ghosting were physically implemented but practically
   undemonstrable through the actual game input. Fixed by adding HOLD H.

5. **Token teleport-in-reverse bug.** A ghosted token (phase > threshold) under a
   sustained push could drift arbitrarily far outside the arena bounds; the instant
   phase decayed back down, the very next collision check snapped it straight back —
   verified at 4009px in a single 10ms frame. Fixed with a bounded overshoot margin
   (`world.GHOST_OVERSHOOT_MARGIN`) so the eventual snap is small, not arbitrary.
   Locked in with a permanent regression test.

6. **Three harness bugs** (found while investigating the above, fixed directly):
   `dual_tap` silently overwrote instead of summed when two ignition sets shared a
   node; `loop_with_tail_points` crashed on a float `tail_length`; both fixed in
   `sigilwave/experiment.py`.

**Also stress-tested and confirmed working correctly (no bug):** the §8 energy
ceiling holds exactly at the configured cap even under a pathological nested-loop
sigil at maximum drive, and even down to `max_energy=1e-6`; degenerate/self-
intersecting/disconnected strokes and extreme ink parameters (near-zero impedance,
near-zero nonlinearity threshold) all stay finite; parse/compile is verified
deterministic (§6's requirement for replay sharing). Full regression suite: **8 test
files, 34 test functions, all passing** — the new `selftest_edgecases.py` adds 7 of
those, covering everything above that had no prior coverage.

## 4. Noted but not fixed (follow-ups, not blocking)

- **Coupler cutoff is a hard cliff at `g_max`, not a fade.** Tunneled energy goes from
  a small-but-real fraction at gap=29.9px to exactly 0 at 30.0px. A player tuning
  "blink range" right at the edge sees a cliff, not a gradual loss of reliability.
- **`loop_with_tail_points`'s loop-closure detection is fragile outside roughly
  r∈[4.5px, 90px]** at its default point count — a shape that looks like a valid loop
  can silently lose its whole resonance/chirality mechanism with no visible symptom
  besides inspecting node degrees directly. Only affects this one generator function,
  not the real mouse-drawn parser path (which uses actual continuous mouse points, not
  a fixed small vertex count).
- **The energy ceiling clamps delay-line buffers but not that same step's `radiated`/
  `last_emitted`.** One extreme injected sample (e.g. amplitude=1e6, not reachable via
  normal drawing/tapping) can flood the analyzer's own envelope-follower state for
  hundreds of steps even though the wave sim itself recovers almost immediately.
- **`InkType(impedance=0)` / `InkType(nl_threshold=0)` raise `ZeroDivisionError`** at
  compile time rather than failing gracefully — only matters if ink parameters are
  ever generated/randomized (e.g. procedurally-authored enemy sigils) rather than
  hand-picked constants.
- **No input mode for parry or beat-frequency scenarios** — both are real, verified
  mechanics with no way to trigger them from the keyboard yet (see §2 above).

None of these affect the 9 scenarios above; they're recorded here so they're not
rediscovered from scratch later.

## Files

- `sigilwave/experiment.py` — the harness
- `sigilwave/scenarios.py` — the 9 preloadable scenarios
- `sigilwave/sim/selftest_edgecases.py` — new bug-hunt regression suite
- `experiment_reports/kinetic_thermal_shield.{md,json}` — emitter/shield/charge/range
- `experiment_reports/chirality_elements_resonance.{md,json}` — elements/beats/rhythm/resonance
- `experiment_reports/couplers_nonlinearity_phase.{md,json}` — tunneling/overcharge/phase/parry
