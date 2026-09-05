"""Render the game to PNGs without a display.

    python -m clade.verify.shots

Existing partly so the game can be *looked at* from a machine with no
screen, and partly because a renderer is the one part of a codebase where
the tests all pass and the output is still wrong. Every shot here is a real
frame: a real world, stepped for real time, with real creatures in it.
"""

import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

from .. import config as C
from ..app import BENCH, CODEX, ENDING, Game, MAPS, PLAY, TITLE
from ..humours import Charge
from ..organs import make

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "shots")


def _settle(game, seconds, dt=1 / 60.0):
    for _ in range(int(seconds / dt)):
        game._dt = dt
        game.update(dt)


def _save(game, name):
    game.draw()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".png")
    pygame.image.save(game.screen, path)
    print("  %s" % path)
    return path


def _goto(game, key):
    game.world.enter_room(key)
    game.player.pos = list(game._spawn_point())
    game.player.vel = [0.0, 0.0]
    game.world.transition_lock = 9e9   # stay put while we pose the shot


def main():
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    game = Game(screen, seed=4, headless=True)
    print("rendering to %s" % OUT)

    game.state = TITLE
    _save(game, "01_title")

    # --- the first room. dark, empty, one thing worth walking to.
    game.state = PLAY
    _goto(game, "n_caul")
    _settle(game, 1.0)
    _save(game, "02_the_caul")

    # --- a populated cavern, lit only by you and by what lives there.
    _goto(game, "n_gallery")
    _settle(game, 2.5)
    _save(game, "03_the_gallery")

    # --- fire in water. the heat field, doing all three of its jobs at
    #     once: light, damage, and enriching the water you drink.
    _goto(game, "n_ward")
    f = game.world.room.fields
    p = game.player.pos
    for k in range(5):
        f.add_heat((p[0] + 150 + k * 70, p[1] + 30), 70, 5.0)
    _settle(game, 1.6)
    _save(game, "04_heat")

    # --- silt. you are invisible in it and so is everything else.
    _goto(game, "c_bloom")
    f = game.world.room.fields
    p = game.player.pos
    for k in range(7):
        f.add_silt((p[0] - 200 + k * 90, p[1] + 40), 120, 2.4)
    _settle(game, 1.2)
    _save(game, "05_silt")

    # --- ice. a wall you made out of a weapon.
    _goto(game, "c_deep")
    f = game.world.room.fields
    p = game.player.pos
    for k in range(9):
        f.add_heat((p[0] + 190, p[1] - 180 + k * 46), 46, -22.0)
    _settle(game, 0.9)
    _save(game, "06_ice")

    # --- something in flight, and the room reacting to it.
    _goto(game, "n_creche")
    game.player.aim = [1.0, -0.15]
    for _ in range(3):
        game._fire(0)
        _settle(game, 0.14)
    _settle(game, 0.25)
    _save(game, "07_firing")

    # --- deep water. a different palette and a much worse neighbourhood.
    _goto(game, "l_core")
    _settle(game, 3.0)
    _save(game, "08_the_lattice")

    # --- something winding up. the whole point of the combat rewrite:
    #     a tell you can see and a heading that locks before it fires.
    _goto(game, "c_mouth")
    _settle(game, 0.6)
    winding = None
    for _ in range(2400):
        _settle(game, 1 / 60.0)
        winding = next((c for c in game.world.creatures
                        if c.phase == "windup" and c.phase_frac > 0.45), None)
        if winding is not None:
            break
    _save(game, "08b_windup")

    # --- and a region working on a body that cannot answer it.
    _goto(game, "l_rack")
    _settle(game, 2.0)
    _save(game, "08c_hazard")

    # --- the bench, with a real body and a real assay on screen.
    for key in ("gullet", "ember_gland", "salt_node", "muffle", "harmonic",
                "fork", "sieve"):
        game.body.pack.append(make(key))
    b = game.body
    for cell, key in (((4, 1), "ember_gland"), ((4, 2), "fork"),
                      ((3, 3), "muffle"), ((1, 3), "harmonic")):
        if cell not in b.cells:
            b.unlock(cell)
        if b.organ_at(cell) is None:
            b.install(cell, make(key))
    from ..body import Chain
    trial = Chain([(1, 1), (1, 2), (2, 2), (2, 1), (3, 1)])
    ok, _ = b.validate(trial)
    if ok:
        b.chains[0] = trial
    # A real standing chain, so the half of the screen that stops this
    # being a gun menu is actually populated.
    for cell, key in (((0, 3), "siphon"), ((1, 3), "harmonic")):
        if cell not in b.cells:
            b.unlock(cell)
        if b.organ_at(cell) is not None:
            b.uninstall(cell)
        b.install(cell, make(key))
    standing = Chain([(0, 3), (1, 3)])
    if b.validate(standing, standing=True)[0]:
        b.standing[0] = standing
    b.recompute_standing()
    game.state = BENCH
    game.bench.assay_chain = 0
    game.bench._run_assay()
    game.bench.sel_cell = (2, 1)
    game.bench.show_tutorial = False
    _save(game, "09_the_bench")

    # The tutorial, on its first step.
    game.bench.show_tutorial = True
    game.bench.tutorial.step = 3
    game.bench.sel_cell = None
    _save(game, "09b_tutorial")

    # Mid-edit: the state that used to break every other control.
    game.bench.show_tutorial = False
    game.bench._arm(1, False)
    game.bench.route = [(1, 1), (1, 2), (2, 2)]
    game.bench.sel_cell = (1, 2)
    game.bench._run_assay()
    _save(game, "09c_editing")

    # The shelf, on a sandbox body — otherwise almost every entry reads
    # "missing", which is correct in play and useless as a picture of what
    # the screen is for.
    shelf_game = Game(screen, seed=4, headless=True, sandbox=True)
    shelf_game.state = BENCH
    shelf_game.bench.show_tutorial = False
    shelf_game.bench._load_preset(__import__(
        "clade.shelf", fromlist=["x"]).BY_KEY["lance"])
    shelf_game.bench.shelf_open = True
    shelf_game.bench.shelf_index = 2
    _save(shelf_game, "09d_the_shelf")
    game.bench.shelf_open = False
    game.bench.sel_cell = None
    game.bench._run_assay()
    _save(game, "10_the_assay")

    # --- the map, part-explored, with locks showing.
    for k in ("n_caul", "n_crib", "n_ward", "n_font", "n_run", "n_gallery",
              "n_creche", "n_quiet", "n_stair", "c_mouth", "c_span",
              "c_still", "c_sink"):
        game.world.discovered.add(k)
    game.state = MAPS
    _save(game, "11_the_map")

    # --- the codex, with something actually in it.
    for key in ("caul", "intake_plate", "candidate_note", "ledger_a",
                "husbandry", "organ_note"):
        game.codex.find_fragment(key)
    for key in ("kiln", "salt_node", "muffle", "harmonic"):
        game.codex.use_organ(key, 18)
    game.state = CODEX
    game.codex_page = 0
    _save(game, "12_codex_fragments")
    game.codex_page = 1
    _save(game, "13_codex_tissue")

    # --- the room it ends in.
    game.state = PLAY
    _goto(game, "s_axis")
    _settle(game, 2.0)
    _save(game, "14_the_sill")

    # --- and the ending nobody is told about.
    for key in ("escalation", "pass", "attendant_note", "last_log",
                "your_number", "mark_three"):
        game.codex.find_fragment(key)
    game.ending = "abstain"
    game.state = ENDING
    game.ending_time = 14.0
    _save(game, "15_ending")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
