# attic

A previous prototype that used to be this repository: a roguelite about
drawing sigils, built on a digital-waveguide simulation (bidirectional delay
lines, scattering junctions, evanescent couplers, a filterbank analyser,
chirality from a cycle basis).

It is kept because the simulation in `sigilwave/sim/` is genuinely good and
still passes its own 34 checks:

```
python -m attic.sigilwave.sim.selftest
```

**Nothing in CLADE imports any of it.** It is here as salvage, not as a
foundation.
