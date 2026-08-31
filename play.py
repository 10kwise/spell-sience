"""CAMPANARY - entry point.

    python play.py

A bell-founder's roguelite built on the digital-waveguide simulation in
`sigilwave/sim/`, which is unchanged and still has its own selftests. A
ring's circumference is its pitch; everything else in the game is a
consequence of that one fact.

The earlier build on the same simulation, WAVEWRIGHT, is still here and
still runnable:

    python -m sigilwave.game.app
"""

from sigilwave.campanary.app import main

if __name__ == "__main__":
    main()
