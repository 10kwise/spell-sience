# Handover

Where RIGS is, what is load-bearing, what is half-built, and the traps.
Written to be the first thing read after `README.md`.

Branch `claude/game-feel-fantasy-redesign-7wq6fc`. All suites green.

---

## Start here

```
pip install -r requirements.txt
python -m sigilwave.observatory     # the ocean, live. H for controls
```

Then read [`RIGS.md`](RIGS.md) — the code is written against it and cites it by
section number. §13 is the current frontier; §13.11 is a status table.

---

## The one paragraph

You build machines as **ordered lists of modules** that move heat, pressure,
gas, speed and sound through water. No knobs — the only decision is which
modules and in what order. Every module writes what it moved into a ledger and
`Ledger.residual()` must come back zero, which is what makes the behaviour
compose instead of merely look plausible. The ocean around it is a real field
simulation: heat, gas, bubbles, sound speed, currents, and a food web that
gathers itself. It is a survival-horror game in the Iron Lung / Darkwood
register. **The game loop is not built.**

---

## What is actually built

| | state |
|---|---|
| the rig: 13 modules, 5 numbers, a ledger | **solid.** 352 distinct outcomes measured |
| the ocean: heat, gas, bubbles, sound speed, currents | **solid** |
| trophic channels + advection | **solid** |
| the food web: 5 species, predation, death, recruitment | **solid.** 31/31 |
| the diver: drag, added mass, trim, anisotropy | **solid** |
| the station | built — warm, a power radius, a dock |
| the observatory (the live window) | built |
| the bench (build a rig, watch the slug) | built |
| **the game loop** | **not built, deliberately** |
| the umbilical (§13.2) | not built |
| the scattering layer (§13.6) | not built |
| the rig-as-instrument (§13.5) | not built |
| SENSE / HOLD / SPLIT (§5.4) | deliberately withheld |

---

## The rules that must not be broken

**1. Nothing in a gradient system may have a ceiling.**
Three separate bugs in one pass were the same bug: `min(6.0, v)`,
`clamp(a, -6, 6)`, a saturating comfort response. A clamped region is *flat*, a
flat region has no gradient, and a creature that reads gradients stops dead in
one — **at exactly the place it most wanted to be**, because that is where the
clamp binds. Every response curve is now unbounded and monotone:
`(1 + v) ** gain` for channels, `exp(gain * asinh(a))` for heat.

**2. The ledger is not negotiable.**
`selftest_conservation` has caught five perpetual-motion machines, every one
buildable in four to six modules with perfectly balanced books. Any new module
goes through it before anything else.

**3. Creatures read fields. They do not perceive each other.**
That one rule is what makes herding, luring, hunting, hiding and cover emerge
instead of being authored. The food web is carried by diffusing channels for
this reason. **Predation is the single exception** and it is a collision, not a
perception — see §13.9b for why that line is where it is.

**4. Nothing may read the channel it emits.**
Self-attraction is positive feedback with no opposing term. A creature that can
smell itself stops moving and calls that comfort.

**5. A presence signal must cost less than the food that pays for it.**
`signal_rate * CONDITION_GAIN / condition_decay < 1`. Above 1 the creature is an
amplifier and the food web runs on itself — §12.5's perpetual motion with fins.
The grazer was at 1.05 and nothing caught it, because every measured run had it
starving instead of emitting. Now a check.

**6. Don't tune a test to green.**
Four times in the last pass a test went red because the *test* had stopped
asking the right question. Each was corrected and the reason written down. A
threshold nudged to green is a measurement thrown out.

---

## Traps, all of which have already bitten

- **`Medium.add_heat` is single-cell on purpose** (the acoustic mirror depends
  on it) — but a *rig exhaust* must use `couple.spread_heat` / `spread_bubbles`.
  Dumping an amplified rig-second into one 16 m cell threw the diver 490 px up.
- **The domain edge is open to advection, not a wall.** Zero-flux there turns
  the boundary into a shelf that collects whatever the tide pushes at it.
- **`OCEAN_RELAX` is the only heat sink.** Remove it and the ocean warms
  forever and the currents grow all session.
- **The seabed is a place, not an edge.** Carcasses sink; scavengers work the
  floor. Don't write a test that calls that a failure.
- **Grazers eat `swarm` as a field and that is correct.** Continuous grazing on
  distributed biomass is a field interaction. Only large-animal predation is a
  collision.
- **A vent does not exhaust.** Measured flat over ten minutes. Any design that
  needs sites to run down needs a different mechanism.
- **Heat is short-range (~140 px), sound is long-range (~260 px).** Nobody
  designed that; it falls out of the diffusion constants. Stage thermal tests at
  about 100 px or they measure nothing.
- **Bash heredocs break on apostrophes in this environment.** Write patch
  scripts to a file and run them.

---

## The suites

Nothing here is believed because it was argued for.

```
python -m sigilwave.rig.selftest_conservation    36   energy, gas, no free lunch
python -m sigilwave.rig.selftest_cycle           31   does the ecosystem gather itself
python -m sigilwave.rig.selftest_couple          25   where the rig meets real water
python -m sigilwave.rig.selftest_sound           24   is sound load-bearing
python -m sigilwave.rig.selftest_creatures       20   one rule, four species
python -m sigilwave.rig.selftest_station         18   home is a place, not a menu
python -m sigilwave.rig.selftest_selfpower       15   nothing powers itself
python -m sigilwave.rig.selftest_density          9   is the vocabulary dense enough
python -m sigilwave.selftest_swim                28   is this water, or air turned down
python -m sigilwave.selftest_diver               10
python -m sigilwave.selftest_digging             13
python -m sigilwave.medium.selftest_field             the ocean
python -m sigilwave.medium.selftest_front             fronts, refraction, sound channel
python -m sigilwave.sim.selftest                  9   the waveguide (+7 suites beside it)
```

---

## The three go/no-go questions

§12 set two; §13.8 added a third. They were all allowed to kill the design.

1. **Density** — is the vocabulary wide enough? **Passed.** Asked for ten
   distinct outcomes, found 352.
2. **Aggregation** — does the food web gather itself with no player in the
   water? **Passed**, after five separate failures (§13.9).
3. **Vent exhaustion** — does a worked site run down? **Failed.** It does not,
   and §13.3 is struck through in place. What replaced it is measured: the yield
   does not fall, **the risk rises** — running a heater for ten minutes drew all
   four stalkers and took local density from 20 to 27.

**Still open, and the one a machine cannot answer:** hand somebody `the cooler`
with the `COIL` pulled out, let them watch the slug cross it, and ask why it
does nothing. If they can work it out from the animation, the system is
learnable.

---

## What I would do next

In order, and none of it is the loop.

1. **Run go/no-go 3 on a human.** It is the last test allowed to kill the
   design and it needs a person, not a suite.
2. **The umbilical (§13.2).** The single highest-value unbuilt mechanic: a
   physical air line whose *length is the meter*, with real drag in a real tide,
   and where unclipping is the decision that starts the game.
3. **Gadget legibility (§13.5).** The rig raised into frame as the instrument,
   so that what you built determines what you can perceive. Currently only the
   heater has feedback a player can read.
4. **Walls and currents.** Never measured. `_advect_channels` and
   `_compute_flow` both zero flux at solid faces, so walls *should* block scent
   and steer flow — but "should" is not a measurement.
5. **The loop**, once 1–4 are answered.

---

## Design documents

[`RIGS.md`](RIGS.md) is current. [`SUBMERGED.md`](SUBMERGED.md),
[`CAMPANARY.md`](CAMPANARY.md), [`GAME_DESIGN.md`](GAME_DESIGN.md) and
[`sigil-wave-design.md`](sigil-wave-design.md) describe code that is gone —
they are kept because they are the arguments that produced the constants, and
`units.py` still cites them.
