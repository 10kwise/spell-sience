ssssss"""WAVEWRIGHT — entry point.

    python play.py

The physics package (sigilwave/sim) is unchanged and still has its own
selftests; this is the game built on top of it.
"""

from sigilwave.game.app import main

if __name__ == "__main__":
    main()
