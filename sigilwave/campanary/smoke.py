"""End-to-end smoke test: drive the real App through a whole run.

    python -m sigilwave.campanary.smoke

The playtest harness exercises combat and the calibration harness exercises
the physics; neither of them ever touches the mode machine, the foundry, the
anvil, the reward screen or the renderer. This does, headlessly, so that
"the game starts, is playable end to end, and draws every screen without
throwing" is a claim something checks rather than a claim somebody makes.
"""

import os
import sys

import pygame


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from . import audio
    from .app import App, FIXED_DT
    from .playtest import DT, Founder

    pygame.init()
    audio.set_enabled(False)
    app = App(pygame.display.set_mode((1280, 800)))
    app.start()

    bot = Founder()
    waves = 0
    seen = set()
    guard = 0
    # Draw periodically rather than every step. The renderer is exercised
    # thousands of times either way; drawing all of a twelve-wave run at 120
    # steps a second is sixty thousand frames of dummy-surface blitting and
    # turns a smoke test into a coffee break.
    draw_every = 17

    limit_waves = 11
    while app.mode != "DEAD" and waves < limit_waves and guard < 400000:
        guard += 1
        seen.add(app.mode)
        if app.mode == "FOUNDRY":
            # Cast whatever the room ahead asks for, then go down.
            _stock(app)
            app.foundry.done = True
            app.update(FIXED_DT)
        elif app.mode == "BELFRY":
            m, s_, h, d, w = bot.act(app.belfry)
            app.belfry.update(DT, m, s_, h, d, w)
            app.camera.follow(app.belfry.player.pos, 0.2)
            if app.belfry.cleared:
                waves += 1
                app.finish_wave()
            elif app.belfry.failed:
                app.mode = "DEAD"
            elif app.belfry.time > 150.0:
                print(f"  !! stuck in {app.belfry.spec['name']}")
                return 1
        if guard % draw_every == 0:
            app.draw()

    ended = app.mode
    for mode in ("TITLE", "DEAD"):
        app.mode = mode
        app.draw()

    print(f"  modes exercised: {sorted(seen | {'TITLE', 'DEAD'})}")
    print(f"  waves cleared:   {waves}")
    print(f"  ended in:        {ended}")
    # The bot dies to the late waves, and should - this checks that the app
    # runs, progresses and draws every screen without throwing, not that a
    # rule-based bot can beat the game.
    ok = waves >= 3
    print("  smoke: PASS" if ok else "  smoke: FAIL")
    return 0 if ok else 1


def _stock(app):
    """Stand in for a player at the foundry: cast a bell for anything in the
    room ahead that nothing in hand can answer."""
    from .playtest import bell_for
    from .run import notes_in

    run = app.session
    spec = run.spec
    if spec is None:
        return
    want = [n for n in notes_in(spec) if 0 <= n < 4]
    have = {round(b.note) for b in run.bells if b.has_loop}
    for n in want:
        if n in have:
            continue
        if len(run.bells) < run.pegs:
            run.bells.append(bell_for(n))
        else:
            run.bells[-1] = bell_for(n)
        have = {round(b.note) for b in run.bells if b.has_loop}


if __name__ == "__main__":
    sys.exit(main())
