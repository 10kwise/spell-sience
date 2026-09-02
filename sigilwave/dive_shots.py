"""Drive the demo headlessly and photograph it.

    python -m sigilwave.dive_shots
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from .bench.mouths import aperture_wavelengths
from .dive_app import BENCH_W, HEIGHT, WIDTH, Dive, _StageView, draw_bench
from .stage import world
from .stage.app import Renderer

OUT = "debug_output"
DT = 1.0 / 60.0


def _preset_rig(dive, preset_name, gadget):
    """Load a library machine and bolt a device to its mouth."""
    from .bench.presets import PRESETS
    idx = [p.name for p in PRESETS].index(preset_name)
    dive.load_preset(idx)
    out = max(dive.emitter.groups, key=lambda g: g.centre.x)
    dive.rack.add(gadget, (out.centre.x + 26.0, out.centre.y))


def _machine(dive, kind):
    """Draw a machine on the bench, in bench coordinates."""
    a = dive.assembly
    if kind == "spitter":
        a.add_run((60, 400), (300, 400))
    elif kind == "carry":
        for i in range(5):
            a.add_run((60, 400), (300, 320 + i * 40))
    elif kind == "loop":
        a.add_loop((190, 380), 50.9)             # hum
        a.add_run((40, 380), (129, 380))         # feed, gapped off it
        a.add_run((252, 380), (330, 380))        # pickup
    dive._rebuild()


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    font = pygame.font.SysFont("consolas,menlo,monospace", 15)
    small = pygame.font.SysFont("consolas,menlo,monospace", 12)
    ocean = pygame.Surface((world.WIDTH, world.HEIGHT))

    for kind, at, label in (
        ("spitter", (430.0, 470.0), "one mouth, burning your own air"),
        ("carry", (430.0, 470.0), "five mouths merged, burning your own air"),
        ("carry", (330.0, 545.0), "the same machine, standing in a vent plume"),
        ("loop", (330.0, 545.0), "a loop gapped off its feed, on a vent"),
        (("preset", "the ticker", "gill"), (330.0, 545.0),
         "a library machine with a gill bolted to its mouth"),
        (("preset", "the thruster", "propeller"), (430.0, 470.0),
         "the thruster preset driving a propeller"),
    ):
        dive = Dive()
        dive.diver.pos.update(*at)
        if isinstance(kind, tuple):
            _preset_rig(dive, kind[1], kind[2])
        else:
            _machine(dive, kind)
        view = _StageView(dive)
        renderer = Renderer((world.WIDTH, world.HEIGHT), dive.medium)
        dive.driving = True
        for _ in range(420):
            dive.step(DT)
            renderer.draw(ocean, view)

        screen.fill((3, 5, 11))
        renderer.draw(ocean, view)
        for v in dive.vents:
            pygame.draw.circle(ocean, (255, 150, 70),
                               (int(v.pos.x), int(v.pos.y)), 6)
            pygame.draw.circle(ocean, (120, 60, 30),
                               (int(v.pos.x), int(v.pos.y)), int(v.reach), 1)
        screen.blit(ocean, (BENCH_W, 0))
        draw_bench(screen, dive, font, small)
        screen.blit(font.render(label, True, (198, 218, 236)), (BENCH_W + 16, 14))
        screen.blit(small.render(dive.economy.report(), True, (150, 180, 205)),
                    (BENCH_W + 16, 36))

        tag = (f"{kind[1].split()[-1]}_{kind[2]}" if isinstance(kind, tuple)
               else f"{kind}_{'vent' if dive.power_here() > 0.4 else 'body'}")
        path = os.path.join(OUT, f"dive_{tag}.png")
        pygame.image.save(screen, path)
        g = max(dive.emitter.groups, key=lambda x: x.centre.x) if dive.emitter else None
        print(f"  {path:34s} air {dive.economy.air:5.1f}"
              f"  power here {dive.power_here():.2f}"
              f"  fronts {len(dive.fronts):2d}"
              f"  {g.shape() if g else '-':8s}"
              f"  gadgets:{[x.kind for x in dive.rack.gadgets if x.running]}"
              f"  {dive.economy.report()}")

    pygame.quit()


if __name__ == "__main__":
    main()
