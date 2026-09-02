"""Drive every app's REAL main loop with synthetic input.

Written the day the demo shipped a one-line bug that closed the window on the
first frame: a list comprehension in the HUD was assigned to `running`, which
is the main loop's own flag, so `while running:` saw an empty list and
stopped. Every suite passed. Every screenshot rendered. `dive_shots` builds
its own loop and never calls `main()`, so nothing in the project had ever
executed the code the player actually runs.

This does. It is not a test of physics -- there are ten suites for that --
it is a test that the programs start, accept every key they document, and
keep running.

    python -m sigilwave.smoke
"""

import os
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

_p = _f = 0


def check(ok, label):
    global _p, _f
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if ok:
        _p += 1
    else:
        _f += 1


def _events(keys, mouse):
    """A script of inputs: every documented key, then a drag, then a drive."""
    seq = [("key", k) for k in keys]
    seq += [("md", 1, mouse[0]), ("mm", mouse[1]), ("mu", 1, mouse[1]),
            ("md", 3, mouse[2]), ("mu", 3, mouse[2]),
            ("md", 1, mouse[3]), ("mm", mouse[4]), ("mu", 1, mouse[4])]
    return seq


def drive(name, main, keys, mouse, settle=60):
    """Run a real main loop over a scripted input sequence."""
    global _p, _f
    pygame.init()
    seq = _events(keys, mouse)
    idx = [0]
    frames = [0]
    original = pygame.event.get

    def fake_get():
        frames[0] += 1
        if idx[0] >= len(seq):
            if frames[0] > len(seq) + settle:
                return [pygame.event.Event(pygame.QUIT)]
            return []
        it = seq[idx[0]]
        idx[0] += 1
        if it[0] == "key":
            return [pygame.event.Event(pygame.KEYDOWN,
                                       {"key": it[1], "mod": 0, "unicode": ""})]
        if it[0] == "md":
            pygame.mouse.set_pos(it[2])
            return [pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                       {"button": it[1], "pos": it[2]})]
        if it[0] == "mu":
            pygame.mouse.set_pos(it[2])
            return [pygame.event.Event(pygame.MOUSEBUTTONUP,
                                       {"button": it[1], "pos": it[2]})]
        pygame.mouse.set_pos(it[1])
        return [pygame.event.Event(pygame.MOUSEMOTION,
                                   {"pos": it[1], "rel": (1, 1),
                                    "buttons": (1, 0, 0)})]

    pygame.event.get = fake_get
    try:
        main()
        ok = frames[0] > len(seq) and idx[0] == len(seq)
        print(f"       {name}: {frames[0]} frames, {idx[0]}/{len(seq)} inputs")
        check(ok, f"{name} starts, takes every documented key, and keeps running")
        if not ok:
            print("       (it stopped early - something set the loop flag,"
                  " or an input closed it)")
    except Exception:
        traceback.print_exc()
        check(False, f"{name} raised while running")
    finally:
        pygame.event.get = original


def main():
    from .bench.app import main as bench_main
    from .dive_app import main as dive_main
    from .stage.app import main as stage_main

    print("--- the demo ---")
    drive("dive_app", dive_main,
          [pygame.K_1, pygame.K_2, pygame.K_TAB, pygame.K_LEFTBRACKET,
           pygame.K_RIGHTBRACKET, pygame.K_UP, pygame.K_DOWN, pygame.K_COMMA,
           pygame.K_PERIOD, pygame.K_g, pygame.K_x, pygame.K_F1, pygame.K_F5,
           pygame.K_F7, pygame.K_F8, pygame.K_g, pygame.K_r],
          [(120, 300), (280, 420), (700, 400), (100, 200), (200, 500)])

    print("")
    print("--- the bench ---")
    drive("bench.app", bench_main,
          [pygame.K_1, pygame.K_2, pygame.K_SPACE, pygame.K_p,
           pygame.K_LEFT, pygame.K_RIGHT, pygame.K_c, pygame.K_r],
          [(200, 300), (500, 300), (400, 300), (300, 400), (600, 400)])

    print("")
    print("--- the stage ---")
    drive("stage.app", stage_main,
          [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_TAB,
           pygame.K_SPACE, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET,
           pygame.K_c, pygame.K_r],
          [(400, 300), (700, 400), (600, 350), (300, 500), (800, 300)])

    print("")
    print(f"{_p} passed, {_f} failed.")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
