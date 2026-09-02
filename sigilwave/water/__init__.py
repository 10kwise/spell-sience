"""The water, as a thing worth looking at.

This package is deliberately SEPARATE from `stage/` and `medium/`. It reads
the medium and never writes to it, imports nothing from `medium/front.py`,
and owns no simulation state. The physics can be rewritten underneath it
without this package noticing, and this package can be deleted without the
physics noticing.

The one idea: **the cel bands are the isopycnals.** Cell shading means
quantising a continuous value into flat regions with hard edges, and the
medium already carries the perfect value -- sound speed. Posterise it and the
band boundaries land exactly where sound will refract, a vent's plume bulges
the bands upward, and a bubble curtain punches a hole through them. The
prettiest layer is also the one that teaches the room.

    python -m sigilwave.water.app        # swim around in it
    python -m sigilwave.water.shots      # photograph it
    python -m sigilwave.water.selftest_water
"""
