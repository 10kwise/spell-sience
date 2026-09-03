# RIGS

An underwater survival game where the thing you build is a **pipe**.

```
pip install -r requirements.txt
python -m sigilwave.rig.bench
```

You place modules in a list, left to right. Water enters at one end and
leaves at the other, and every module does one thing to it. There are no
knobs, no sliders and no numbers to tune — **the only decision is which
modules and in what order**, and that turns out to be enough, because a
squeeze followed by a coil followed by an expansion is a refrigerator and the
same three modules in a different order are a heater.

---

## The one sentence

Five numbers cross a list of thirteen transforms, and every machine in the
game — propulsion, sonar, a lamp, a gill, a weapon, a generator — is an
ordering of them that nobody wrote down in advance.

## Why it holds together

Every module writes what it moved into a ledger, and `Ledger.residual()` has
to come back at zero. That is not decoration. It is the difference between a
system whose behaviour composes and a pile of effects that each look plausible
alone, and it has caught **five perpetual-motion machines** that reasoning did
not — every one of them buildable in four to six modules, every one with
perfectly balanced books.

Two consequences worth stating up front:

- **The physics is not a theme.** Cavitation is not a status effect, it is
  what happens when the lowest pressure the water sees goes below what holds
  it together — so a nozzle can cause it, an expansion can cause it, a note
  can cause it, and a filter can prevent it, and none of those four are a
  rule anybody added.
- **Generators take power out of the water.** A thermopile in water that is
  all one temperature produces exactly zero. Not a small number — zero,
  because that is Kelvin–Planck. You have to go somewhere.

## What is here

| | |
|---|---|
| `sigilwave/rig/` | the rig: five numbers, thirteen modules, a list, a ledger, the bench |
| `sigilwave/medium/` | the ocean: heat, gas, bubbles, sound speed, **and now a velocity** |
| `sigilwave/sim/` | the digital waveguide the sound runs on, unchanged from its original spec |
| `sigilwave/diver.py` | a body in water: drag against the water, added mass, trim |
| `sigilwave/sources.py` | where energy comes from, and the pack that stores it |

## Running it

```
python -m sigilwave.rig.bench          the bench: build a rig, watch the slug cross it
python -m sigilwave.rig.bench_shots    photograph the bench, headless
python -m sigilwave.rig.swim_shots     photograph the water moving
```

## The suites

Nothing in this project is believed because it was argued for.

```
python -m sigilwave.rig.selftest_conservation    36   energy, gas, and no free lunch
python -m sigilwave.rig.selftest_sound           24   is sound load-bearing, or decoration
python -m sigilwave.rig.selftest_station         18   home is a place, not a menu
python -m sigilwave.rig.selftest_selfpower       15   nothing powers itself, incl. through the ocean
python -m sigilwave.rig.selftest_couple          25   where the rig meets the real water
python -m sigilwave.rig.selftest_creatures       20   one rule, four species
python -m sigilwave.rig.selftest_density          9   the go/no-go: is the vocabulary dense enough
python -m sigilwave.selftest_swim                28   is this water, or air with the numbers down
python -m sigilwave.selftest_diver               10
python -m sigilwave.selftest_digging             13
python -m sigilwave.medium.selftest_field             the ocean
python -m sigilwave.medium.selftest_front             fronts, refraction, the sound channel
python -m sigilwave.sim.selftest                  9   the waveguide (+7 more suites beside it)
```

## The design

[`RIGS.md`](RIGS.md) is the document the code is written against, and code
cites it by section number. It records the corrections as well as the design —
including the five free-energy machines, why the first thermopile was wrong,
and the two go/no-go tests the whole thing was allowed to fail.

The documents underneath it are the reasoning trail, not dead weight:
[`SUBMERGED.md`](SUBMERGED.md) is the ocean and the build that RIGS replaced,
and [`CAMPANARY.md`](CAMPANARY.md) and [`GAME_DESIGN.md`](GAME_DESIGN.md) are
the two games before that. Their code is gone; the arguments that produced
`units.py` are not.

## Not built yet

The game loop. That is deliberate — the station exists, movement exists, the
water moves, and the last open question is the one a machine cannot answer:
hand somebody `the cooler` with the `COIL` pulled out, let them watch the slug
cross it, and ask why it does nothing.
