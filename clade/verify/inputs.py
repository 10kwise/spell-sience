"""Press every key on every screen.

This file exists because of a crash the rest of the suite could not have
caught. `shots.py` drew every screen in the game and `selftest.py` checked
every rule, and both passed while pressing ESC at the Bench raised
AttributeError on the first frame a player got there — because everything
verified the *draw* path and nothing verified the *input* path.

So: drive every state through every key and mouse button, twice, and assert
nothing raises. It is a fuzzer with a very small alphabet, and the alphabet
is exactly the one a player has.

    python -m clade.verify.inputs
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

from .. import config as C
from ..app import BENCH, CODEX, DEAD, ENDING, Game, MAPS, PLAY, TITLE

KEYS = [
    pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_TAB,
    pygame.K_BACKSPACE, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT,
    pygame.K_RIGHT, pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
    pygame.K_q, pygame.K_e, pygame.K_f, pygame.K_c, pygame.K_m,
    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
    pygame.K_6, pygame.K_7, pygame.K_l, pygame.K_r, pygame.K_x,
    pygame.K_F1, pygame.K_SLASH, pygame.K_LSHIFT, pygame.K_z,
    pygame.K_0, pygame.K_9,
]

STATES = [
    ("title", TITLE), ("play", PLAY), ("bench", BENCH),
    ("codex", CODEX), ("map", MAPS), ("dead", DEAD), ("ending", ENDING),
]

# Places a click can land at the Bench: sockets, carried list, empty space.
CLICKS = [(95, 165), (173, 243), (251, 320), (329, 399), (407, 476),
          (485, 165), (1000, 164), (1000, 300), (1100, 600), (640, 400),
          (10, 10), (1270, 750)]


# A real display surface, not a bare Surface: room_albedo() calls .convert(),
# which needs a display format to have been set. With the dummy video driver
# this costs nothing and runs anywhere.
_SCREEN = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))


def _fresh(state):
    game = Game(_SCREEN, headless=True)
    game.state = state
    if state == BENCH:
        game.bench._run_assay()
    if state == ENDING:
        game.ending = "abstain"
        game.ending_time = 20.0
    if state == DEAD:
        game.ending_time = 5.0
    return game


def main():
    problems = []
    checked = 0

    for name, state in STATES:
        for key in KEYS:
            for repeat in (1, 2):
                game = _fresh(state)
                try:
                    for _ in range(repeat):
                        game.handle(pygame.event.Event(
                            pygame.KEYDOWN, key=key, unicode="", mod=0))
                        game._dt = 1 / 60.0
                        game.update(1 / 60.0)
                        game.draw()
                    checked += 1
                except Exception as exc:
                    problems.append("%s + key %s x%d -> %s: %s" % (
                        name, pygame.key.name(key), repeat,
                        type(exc).__name__, exc))
                    break

    for name, state in STATES:
        for button in (1, 3):
            for pos in CLICKS:
                game = _fresh(state)
                try:
                    game.handle(pygame.event.Event(
                        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
                    game.handle(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, pos=pos, button=button))
                    game._dt = 1 / 60.0
                    game.update(1 / 60.0)
                    game.draw()
                    checked += 1
                except Exception as exc:
                    problems.append("%s + button %d at %s -> %s: %s" % (
                        name, button, pos, type(exc).__name__, exc))

    # And longer scripted sessions at the Bench, including the exact
    # sequence a player reported as broken: remove something, switch slot,
    # then try to do anything at all.
    sessions = {
        "route/assay/leave": [
            pygame.K_1, pygame.K_BACKSPACE, pygame.K_1, pygame.K_SPACE,
            pygame.K_TAB, pygame.K_2, pygame.K_RETURN, pygame.K_ESCAPE,
            pygame.K_TAB, pygame.K_ESCAPE,
        ],
        "standing slots": [
            pygame.K_5, pygame.K_x, pygame.K_r, pygame.K_RETURN,
            pygame.K_6, pygame.K_BACKSPACE, pygame.K_ESCAPE, pygame.K_SPACE,
        ],
        "shelf": [
            pygame.K_l, pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN,
            pygame.K_l, pygame.K_UP, pygame.K_ESCAPE, pygame.K_SPACE,
        ],
        "auto-route every slot": [
            pygame.K_1, pygame.K_r, pygame.K_RETURN,
            pygame.K_2, pygame.K_r, pygame.K_RETURN,
            pygame.K_5, pygame.K_r, pygame.K_RETURN,
            pygame.K_6, pygame.K_r, pygame.K_RETURN, pygame.K_SPACE,
        ],
        "tutorial toggling": [
            pygame.K_F1, pygame.K_F1, pygame.K_SLASH, pygame.K_SPACE,
        ],
    }
    for label, script in sessions.items():
        game = _fresh(BENCH)
        try:
            for key in script:
                game.handle(pygame.event.Event(pygame.KEYDOWN, key=key,
                                               unicode="", mod=0))
                game._dt = 1 / 60.0
                game.update(1 / 60.0)
                game.draw()
            checked += 1
        except Exception as exc:
            problems.append("bench session %r -> %s: %s"
                            % (label, type(exc).__name__, exc))

    # The reported bug, as a mixed key/mouse script: remove an organ, arm a
    # different slot, then check that selecting and removing still work.
    game = _fresh(BENCH)
    try:
        socket = (2, 1)
        rect = game.bench.cell_rect(*socket)
        game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                       pos=rect.center, button=3))
        game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2,
                                       unicode="", mod=0))
        for cell in ((1, 1), (1, 2), (2, 2)):
            r = game.bench.cell_rect(*cell)
            game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                           pos=r.center, button=1))
            game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                           pos=r.center, button=3))
        game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN,
                                       unicode="", mod=0))
        game._dt = 1 / 60.0
        game.update(1 / 60.0)
        game.draw()
        checked += 1
    except Exception as exc:
        problems.append("reported bench sequence -> %s: %s"
                        % (type(exc).__name__, exc))

    print("CLADE — input sweep")
    print("%d state/input combinations exercised" % checked)
    if problems:
        print()
        for p in problems[:20]:
            print("  CRASH: %s" % p)
        print()
        print("%d failing" % len(problems))
        return 1
    print("nothing raised.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
