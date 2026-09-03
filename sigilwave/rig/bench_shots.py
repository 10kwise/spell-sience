"""Photograph the rig bench headlessly. RIGS.md 12.2, the same reasoning as
`sigilwave/bench/shots.py`: nobody can watch the screen while a test runs, and
the question this screen exists to answer -- can you see where in the chain
something went wrong -- is answered by looking at it, not by asserting on it.

    python -m sigilwave.rig.bench_shots
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from .bench import HEIGHT, WIDTH, Bench, draw, load_fonts
from .chain import Chain

OUT = "debug_output"


def _shot(screen, fonts, bench, name, label):
    result = draw(screen, bench, fonts)
    tag = f"{result.fault.kind if result.fault else 'runs'}"
    if result.tore:
        tag += "+tore"
    small = fonts["mono_xs"]
    screen.blit(small.render(label, True, (20, 30, 34)), (16, HEIGHT - 18))
    path = os.path.join(OUT, f"rigbench_{name}.png")
    pygame.image.save(screen, path)
    print(f"  {path:38s} depth={bench.depth:6.1f}m  {tag:20s}  "
          f"cost={result.cost:8.3f}  out_temp={result.out_temp}")


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    fonts = load_fonts()

    # 1. the cooler at 40 m -- the baseline diagnosis test from RIGS.md 12.2
    b = Bench()
    b.load_preset("the cooler")
    b.depth = 40.0
    _shot(screen, fonts, b, "1_cooler_40m",
          "the cooler at 40m: cold at the port, a warm patch at the coil")

    # 2. the same rig with the COIL taken out -- RIGS.md 12.2's actual test.
    # Removing the coil should visibly flip the machine from a cooler into a
    # heater, and the bars under the EXPAND card are where that has to read.
    b2 = Bench()
    b2.load_preset("the cooler")
    b2.depth = 40.0
    coil_index = b2.chain.kinds().index("COIL")
    b2.remove(coil_index)
    _shot(screen, fonts, b2, "2_cooler_no_coil",
          "the cooler with COIL removed: heats instead of cools -- law III")

    # 3 & 4. the charge, shallow and deep -- the sanity check the task asked
    # for by hand: it should tear at 40 m and stop tearing by 400 m, because
    # the tear threshold is an ABSOLUTE pressure and ambient rises with depth
    # (units.py TEAR_PRESSURE, RIGS.md 9.1).
    b3 = Bench()
    b3.load_preset("the charge")
    b3.depth = 40.0
    r3 = b3.result()
    _shot(screen, fonts, b3, "3_charge_40m",
          f"the charge at 40m: tore={r3.tore} -- a bang, a flash, a cloud")

    b4 = Bench()
    b4.load_preset("the charge")
    b4.depth = 400.0
    r4 = b4.result()
    _shot(screen, fonts, b4, "4_charge_400m",
          f"the charge at 400m: tore={r4.tore} -- tuned shallow, refuses deep")

    # 5. the boiler, boiling -- IT BOILS, the fault whose badge and colour
    # need to read as unambiguously wrong.
    b5 = Bench()
    b5.load_preset("the boiler")
    b5.depth = 40.0
    _shot(screen, fonts, b5, "5_boiler_boiling",
          "the boiler at 40m: seven squeezes, nowhere for the heat to go")

    # 7 & 8. the generator, off the gradient and on it. The same chain twice
    # with one slider moved, because that is the whole claim: a THERMOPILE is
    # not a module that makes power, it is a module that makes power SOMEWHERE.
    b7 = Bench()
    b7.load_preset("the wellspring")
    b7.depth = 400.0
    b7.sink_offset = 0.0
    r7 = b7.result()
    _shot(screen, fonts, b7, "7_wellspring_flat",
          f"the wellspring with the line not run: cost {r7.cost:+.3f} -- a plain thruster")

    b8 = Bench()
    b8.load_preset("the wellspring")
    b8.depth = 400.0
    b8.sink_offset = 40.0
    r8 = b8.result()
    _shot(screen, fonts, b8, "8_wellspring_vent",
          f"the same rig, coil line run to a vent: cost {r8.cost:+.3f} -- it charges")

    # 9. the lance. A tear caused by SOUND rather than by pressure, which is
    # the case the LOWEST TENSION row exists for: the mean pressure never gets
    # near the tear point and the water tears anyway.
    b9 = Bench()
    b9.load_preset("the lance")
    b9.depth = 40.0
    r9 = b9.result()
    _shot(screen, fonts, b9, "9_lance",
          f"the lance: mean pressure {r9.min_pressure:.2f} bar, tension "
          f"{r9.min_tension:.2f} bar -- the note tore it, not the pressure")

    # 6. an empty chain -- must never crash, and must say something sensible
    # rather than drawing broken bars for stages that do not exist.
    b6 = Bench()
    b6.clear()
    _shot(screen, fonts, b6, "6_empty",
          "an empty bench: no modules, no crash, no water")

    pygame.quit()


if __name__ == "__main__":
    main()
