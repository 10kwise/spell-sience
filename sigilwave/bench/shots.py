"""Photograph the bench headlessly.

Same reason as `sigilwave/stage/shots.py`: the question 10 exists to answer is
answered by looking, and nobody can watch the screen while a test runs.

    python -m sigilwave.bench.shots
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from .app import HEIGHT, WIDTH, Bench, draw
from .parts import SIM_DT

OUT = "debug_output"


def _shot(screen, font, small, bench, name, at, label):
    bench.head = min(at, len(bench.history) - 1) if bench.history else 0
    bench.playing = False
    draw(screen, bench, font, small, (0, 0))
    screen.blit(small.render(label, True, (150, 200, 230)), (16, 34))
    path = os.path.join(OUT, f"bench_{name}.png")
    pygame.image.save(screen, path)
    stored, rad = bench.energy[bench.head] if bench.energy else (0.0, 0.0)
    print(f"  {path:44s} t={bench.head*SIM_DT:5.2f}s  "
          f"wires={stored:7.4f} out={rad:7.4f}")


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    font = pygame.font.SysFont("consolas,menlo,monospace", 16)
    small = pygame.font.SysFont("consolas,menlo,monospace", 13)

    # 1. one run: a pulse crosses, and comes back inverted off the far mouth
    b = Bench()
    b.asm.add_run((200, 300), (900, 300))
    b.fire((200, 300))
    print(f"\n  RUN  -> {b.asm.describe()}")
    for at, tag in ((30, "a"), (90, "b"), (150, "c")):
        _shot(screen, font, small, b, f"1_run_{tag}",
              at, "RUN: longer is later - and a mouth sends it back inverted")

    # 2. a fork: three runs meeting, energy shared out
    b = Bench()
    b.asm.add_run((160, 400), (600, 400))
    b.asm.add_run((600, 400), (1000, 250))
    b.asm.add_run((600, 400), (1000, 550))
    b.fire((160, 400))
    print(f"  FORK -> {b.asm.describe()}")
    for at, tag in ((60, "a"), (130, "b")):
        _shot(screen, font, small, b, f"2_fork_{tag}",
              at, "FORK: shares itself out between the ways on - and a little bounces back")

    # 3. a run into a loop: the pulse gets caught and laps
    b = Bench()
    b.asm.add_loop((720, 380), 101.9)          # groan: 1.60 s lap
    b.asm.add_run((200, 380), (618, 380))
    b.fire((200, 380))
    print(f"  LOOP -> {b.asm.describe()}")
    for at, tag in ((80, "a"), (200, "b"), (360, "c")):
        _shot(screen, font, small, b, f"3_loop_{tag}",
              at, "LOOP: a signal caught in a loop laps forever - lap time is its note")

    # 4. a gap: two ends near but not touching
    b = Bench()
    b.asm.add_run((180, 380), (560, 380))
    b.asm.add_run((572, 380), (960, 380))
    print(f"  GAP  -> {b.asm.describe()}  ({len(b.asm.gaps())} gap)")
    b.fire((180, 380))
    for at, tag in ((70, "a"), (140, "b")):
        _shot(screen, font, small, b, f"4_gap_{tag}",
              at, "GAP: passes a share of what reaches it - wider gap, smaller share")

    # 5. a closed loop with no mouth: 9.5, failure must be visible
    b = Bench()
    b.asm.add_loop((600, 380), 101.9)
    print(f"  SHUT -> {b.asm.describe()}")
    b.fire((600, 380))
    _shot(screen, font, small, b, "5_no_mouth", 100,
          "NO MOUTH: nothing reaches the water, so nothing happens")

    pygame.quit()


if __name__ == "__main__":
    main()
