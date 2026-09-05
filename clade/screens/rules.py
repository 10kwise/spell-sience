"""The rules, written down, with your own live numbers in them.

Added after "I cannot tell the rules and what the UI bars show". The game's
whole conceit is that it explains nothing and lets you measure everything,
and that was a good instinct applied far too widely: there is a difference
between *the mechanism*, which the player should absolutely have to find
out, and *the vocabulary*, which they cannot find out because nothing ever
names it.

So this page names things. It says what a humour is, what the bars are,
what is currently costing you, and what kills you — and it says every one
of those with the actual value from the body you are wearing right now, so
it is a readout rather than a manual.

What it still does not say: which order to put your organs in.
"""

import pygame

from .. import config as C
from ..humours import COLORS, GLYPHS, NAMES, N_HUMOURS, strain
from ..render.hud import font, text

HUMOUR_LINES = [
    ("weight, density, pressure",
     "moves things. sinks you. cold, when there is no heat with it."),
    ("fuel, hot blood",
     "burns. shines. and shining is being seen."),
    ("sediment, particulate",
     "hides things. eats them slowly. weighs without burning."),
    ("nerve, potential",
     "quick and precise, and it hurts on the way through."),
]


PAGES = ("what you are looking at", "why you keep coming apart")


def draw(surf, game, page=0):
    """Two pages, three columns, and every section *flows* — it is handed a
    y and returns the y it finished at.

    The first version hardcoded the y of every heading, which looked fine
    against the content I happened to write and collapsed into overlapping
    text the moment a list got one row longer. Anything that reads a live
    value can grow; nothing here may assume a height."""
    w, h = surf.get_size()
    surf.fill((10, 12, 15))
    body = game.body
    world = game.world
    page = page % len(PAGES)

    text(surf, "HOW ANY OF THIS WORKS", (56, 36), 32, (200, 212, 222),
         bold=True)
    for i, name in enumerate(PAGES):
        col = (196, 214, 208) if i == page else (92, 102, 110)
        text(surf, "%d  %s" % (i + 1, name), (470 + i * 330, 44), 19, col)
    text(surf, "left / right to turn the page    ·    H or ESC to go back",
         (56, 74), 17, (100, 110, 120))

    cols = (56, 470, 884)
    top = 112
    if page == 0:
        _humours(surf, body, cols[0], top)
        y = _the_bars(surf, body, cols[1], top)
        _standing(surf, body, cols[2], top)
    else:
        y = _the_loop(surf, body, world, cols[0], top)
        _dying(surf, body, cols[0], y + 18)
        _fighting(surf, cols[1], top)
        _keys(surf, cols[2], top)


COLW = 372


def _head(surf, s, x, y):
    text(surf, s, (x, y), 22, (170, 200, 192), bold=True)
    pygame.draw.line(surf, (48, 62, 60), (x, y + 25), (x + COLW, y + 25))
    return y + 36


def _row(surf, x, y, label, value, note="", col=(190, 202, 210)):
    text(surf, label, (x, y), 18, (140, 150, 160))
    text(surf, value, (x + COLW, y), 18, col, right=True)
    y += 22
    if note:
        y = _wrap(surf, note, x + 10, y, COLW - 10, 15, (100, 110, 118)) + 4
    return y


def _bullets(surf, x, y, rows):
    for label, note in rows:
        text(surf, label, (x, y), 17, (180, 194, 202))
        y = _wrap(surf, note, x + 12, y + 19, COLW - 12, 15,
                  (116, 126, 134)) + 8
    return y


def _humours(surf, body, x, y):
    y = _head(surf, "THE FOUR HUMOURS", x, y)
    y = _wrap(surf, "everything you fire, everything alive, and the water "
                    "itself is a mixture of these four.", x, y, COLW, 16,
              (120, 130, 140)) + 10
    f = body.reserve.fractions()
    for i in range(N_HUMOURS):
        pygame.draw.rect(surf, COLORS[i], pygame.Rect(x, y + 4, 11, 11))
        text(surf, "%s  %s" % (GLYPHS[i], NAMES[i].upper()), (x + 20, y), 19,
             COLORS[i])
        text(surf, "%d%% of you" % round(f[i] * 100), (x + COLW, y + 2), 16,
             (130, 140, 150), right=True)
        text(surf, HUMOUR_LINES[i][0], (x + 20, y + 21), 16, (150, 160, 170))
        y = _wrap(surf, HUMOUR_LINES[i][1], x + 20, y + 39, COLW - 20, 15,
                  (104, 114, 122)) + 10

    y += 6
    text(surf, "SPIKE OR BALANCE", (x, y), 20, (204, 210, 218), bold=True)
    y = _wrap(surf, "one humour on its own is a weapon, and it is loud. all "
                    "four in balance does no damage at all, makes no noise, "
                    "and is the only thing a grown door will open to.",
              x, y + 26, COLW, 16, (140, 150, 160)) + 8
    return _row(surf, x, y, "your mixture sits",
                "%.2f from even" % body.reserve.divergence,
                "0 is perfectly even. 1 is a single humour.")


def _the_bars(surf, body, x, y):
    y = _head(surf, "WHAT THE BARS MEAN", x, y)
    return _bullets(surf, x, y, [
        ("the ring, bottom left",
         "how much of you is left. it does not come back on its own."),
        ("the arc inside it",
         "strain: what it is costing you to be as lopsided as you are."),
        ("the four stacked bars",
         "your reserve, by humour. this one widget is your ammunition, your "
         "buoyancy, your light and your damage type at the same time."),
        ("the pale notch on the top bar",
         "neutral buoyancy. less weight than that and you rise."),
        ("the number under them",
         "upkeep: what you burn every second just by being what you are."),
        ("four boxes, bottom right",
         "chains you fire. a red edge means too hot."),
        ("two boxes above the bars",
         "chains you run, and the words beside them are what they are "
         "doing to you."),
        ("the screen edge going red",
         "how much this room has noticed. something is listening to it."),
    ])


def _the_loop(surf, body, world, x, y):
    y = _head(surf, "WHY YOU ARE ALWAYS HUNGRY", x, y)
    y = _wrap(surf, "you burn reserve every second just by being awake, and "
                    "more for every standing chain. the water covers the "
                    "base rate and nothing beyond it.", x, y, COLW, 17,
              (150, 160, 170)) + 6
    y = _wrap(surf, "the rest has to come out of something that was alive. "
                    "hold F on a corpse.", x, y, COLW, 17, (186, 202, 190)) + 12

    give = body.absorb_rate * max(0.15, 1 - body.clog)
    y = _row(surf, x, y, "upkeep", "%.2f / sec" % body.upkeep)
    y = _row(surf, x, y, "the water gives back", "%.2f / sec" % give)
    net = body.upkeep - give
    y = _row(surf, x, y, "net", "%+.2f / sec" % -net,
             ("that is about %d seconds a tank" % (100 / net)) if net > 0.01
             else "sustainable, here",
             (226, 150, 120) if net > 0 else (150, 200, 172))
    y = _row(surf, x, y, "pressure at this depth", "x%.2f" % body.pressure,
             "everything costs more the deeper you go")

    reg = world.atlas.rooms[world.room_key]["region"]
    hz = C.HAZARD.get(reg, {})
    y += 8
    text(surf, "THIS REGION", (x, y), 20, (204, 210, 218), bold=True)
    y += 26
    if not hz:
        return _wrap(surf, "the nursery asks nothing of you.", x, y, COLW,
                     17, (140, 170, 155))
    y = _wrap(surf, hz["note"] + ".", x, y, COLW, 17, (216, 158, 128)) + 6
    have = body.standing_fx.get(hz["answer"], 0.0)
    y = _row(surf, x, y, "it wants, from a standing chain",
             "%s %.1f" % (hz["answer"], hz["need"]))
    return _row(surf, x, y, "you are making", "%.2f" % have, "",
                (150, 200, 172) if have >= hz["need"] else (226, 150, 120))


def _dying(surf, body, x, y):
    y = _head(surf, "WHAT IS ACTUALLY KILLING YOU", x, y)
    worst = body.worst_causes(5)
    if not worst:
        return _wrap(surf, "nothing has hurt you yet.", x, y, COLW, 17,
                     (120, 150, 138))
    total = sum(v for _, v in worst) or 1.0
    for cause, amount in worst:
        text(surf, cause, (x, y), 17, (198, 188, 182))
        text(surf, "%.0f" % amount, (x + COLW, y + 1), 16, (130, 140, 148),
             right=True)
        pygame.draw.rect(surf, (28, 32, 36), pygame.Rect(x, y + 21, COLW, 7))
        pygame.draw.rect(surf, (206, 128, 110),
                         pygame.Rect(x, y + 21, int(COLW * amount / total), 7))
        y += 36
    return y


def _fighting(surf, x, y):
    y = _head(surf, "FIGHTING", x, y)
    return _bullets(surf, x, y, [
        ("a ring closing on something",
         "it is winding up. when the ring reaches it, its aim locks and "
         "cannot change. move now."),
        ("a bright line out of it",
         "committed. that is where it is going, and it cannot turn."),
        ("a broken white ring",
         "recovering. a quarter of its armour, double the damage. hit it."),
        ("things that charge",
         "bait them into rock. they stun themselves far longer than they "
         "stun you."),
        ("things that latch on", "SHIFT surges, and that tears them off."),
        ("things that brighten when hit",
         "they are eating what you throw. give them something even, or let "
         "them burn out."),
        ("a hole in the water",
         "something outside your light. you are seeing where it is not."),
    ])


def _standing(surf, body, x, y):
    y = _head(surf, "WHAT YOU ARE RUNNING", x, y)
    mode = body.sense_mode
    fx = body.standing_fx
    if mode is None:
        y = _wrap(surf, "nothing. you see by your own dim glow and that is "
                        "all of it.", x, y, COLW, 17, (120, 130, 138)) + 10
    else:
        name, blurb, _k = mode
        text(surf, name.upper(), (x, y), 21, (176, 216, 204), bold=True)
        y = _wrap(surf, blurb, x, y + 26, COLW, 16, (150, 176, 168)) + 12

    for label, value, note in (
            ("speed", "%+.0f%%" % (fx["speed"] * 100),
             "nerve quickens you, weight slows you"),
            ("lure", "%.1f" % fx["lure"],
             "burning and shouting draws them to you"),
            ("ward", "%.1f" % fx["ward"],
             "rot and live nerve push them off you"),
            ("lift", "%+.1f" % fx["lift"],
             "inverted weight is the only way up"),
            ("warmth", "%.1f" % fx["heat"], "the only answer to the sill"),
            ("cover", "%.1f" % fx["murk"],
             "hides you, and earths the lattice"),
            ("tending", "%.1f" % fx["gentle"], "the only real healing")):
        text(surf, label, (x, y), 18, (150, 160, 170))
        text(surf, value, (x + 92, y), 18, (200, 212, 220))
        text(surf, note, (x + 152, y + 2), 15, (104, 114, 122))
        y += 25
    y += 8
    return _wrap(surf, "all of it is built at the bench, and all of it is "
                       "paid for out of things you kill.", x, y, COLW, 16,
                 (150, 176, 168))


def _keys(surf, x, y):
    y = _head(surf, "KEYS", x, y)
    for k, v in (("WASD", "swim"), ("mouse", "aim"),
                 ("LMB RMB Q E", "fire chains 1-4"),
                 ("SHIFT", "surge — costs weight, tears things off you"),
                 ("hold F", "feed on a corpse"),
                 ("TAB", "the bench"), ("H", "this page"),
                 ("C", "the codex"), ("M", "the map"),
                 ("ESC", "back")):
        text(surf, k, (x, y), 18, (186, 200, 208))
        text(surf, v, (x + 120, y + 1), 17, (128, 138, 146))
        y += 25
    return y


def _wrap(surf, s, x, y, width, size, color):
    f = font(size)
    line = ""
    for word in str(s).split():
        trial = (line + " " + word).strip()
        if f.size(trial)[0] > width and line:
            text(surf, line, (x, y), size, color)
            y += size + 2
            line = word
        else:
            line = trial
    if line:
        text(surf, line, (x, y), size, color)
        y += size + 2
    return y
