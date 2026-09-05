"""The instrument panel.

Kept deliberately small and kept out of the middle, because the middle is
where the dark is and the dark is the product. Four readouts, and every one
of them is a thing you can change:

    viability   an arc, not a bar. it does not have a number on it.
    reserve     four stacked bands. this is the most important widget in
                the game and almost nobody will realise it for an hour: it
                is simultaneously your ammunition, your buoyancy, your
                light, your damage type and how fast you are dying of
                strain. one widget, because it is one quantity.
    chains      four slots with heat rings. red means it will not fire.
    threat      the screen edge. no number, no icon, no arrow.
"""

import math

import pygame

from .. import config as C
from ..humours import (
    BRINE, COLORS, GLYPHS, ICHOR, NAMES, N_HUMOURS, SILT, SPARK)

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _fonts[key] = f
    return f


def text(surf, s, pos, size=18, color=(190, 200, 210), bold=False,
         center=False, alpha=255, right=False):
    img = font(size, bold).render(str(s), True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def draw_hud(surf, world, player, notices=None):
    w, h = surf.get_size()
    b = player.body

    _threat_edge(surf, world.threat_level(), world)
    _viability(surf, b, (78, h - 78))
    text(surf, "%d" % int(max(0, b.viability)), (78, h - 78), 20,
         (200, 212, 222), center=True)
    _reserve(surf, b, (128, h - 128))
    _standing(surf, b, (128, h - 172))
    _chains(surf, b, (w - 26, h - 30))
    _hazard(surf, world, (w // 2, h - 96))
    _sense(surf, b, (24, 68))
    _hurting(surf, b, (w // 2, h - 128))
    _events(surf, world, (w // 2, 74))
    if notices:
        _notices(surf, notices, (w // 2, h - 168))
    _room_label(surf, world, (24, 22))


def _sense(surf, body, pos):
    mode = body.sense_mode
    if mode is None:
        return
    name, _blurb, _k = mode
    text(surf, name, pos, 19, (150, 186, 200))


def _hurting(surf, body, center):
    """What is taking you apart, while it is taking you apart."""
    if body.recent_cause is None or body.recent_cause_t < 0.04:
        return
    a = int(min(230, 90 + body.recent_cause_t * 900))
    text(surf, body.recent_cause, center, 21, (222, 146, 122), center=True,
         alpha=a)


def _viability(surf, body, center):
    frac = max(0.0, body.viability / C.VIABILITY_MAX)
    r = 34
    rect = pygame.Rect(center[0] - r, center[1] - r, r * 2, r * 2)
    pygame.draw.arc(surf, (40, 44, 50), rect, 0, math.tau, 4)
    col = (210, 222, 232) if frac > 0.34 else (232, 120, 110)
    if frac > 0.001:
        pygame.draw.arc(surf, col, rect, -math.pi / 2,
                        -math.pi / 2 + frac * math.tau, 4)
    # Strain: the inner ring. It fills as your composition spikes, and when
    # it is full you are losing viability just by being what you are.
    from ..humours import strain
    st = strain(body.reserve) * (body.reserve.magnitude / body.reserve_cap)
    if st > 0.02:
        r2 = r - 8
        rect2 = pygame.Rect(center[0] - r2, center[1] - r2, r2 * 2, r2 * 2)
        pygame.draw.arc(surf, (200, 150, 90), rect2, -math.pi / 2,
                        -math.pi / 2 + min(1.0, st) * math.tau, 3)


def _reserve(surf, body, topleft):
    """Four bands: composition by proportion, brightness by how full you
    are. Reading this widget correctly is most of the skill in the game."""
    x, y = topleft
    total_w = 116
    hgt = 15
    res = body.reserve
    fill = min(1.0, res.magnitude / body.reserve_cap)
    f = res.fractions()

    pygame.draw.rect(surf, (26, 30, 34), pygame.Rect(x, y, total_w, hgt * 4 + 6),
                     border_radius=3)
    for i in range(N_HUMOURS):
        yy = y + 3 + i * hgt
        bw = int(total_w * f[i] * (0.30 + 0.70 * fill))
        col = COLORS[i]
        pygame.draw.rect(surf, (int(col[0] * 0.22), int(col[1] * 0.22),
                                int(col[2] * 0.22)),
                         pygame.Rect(x + 2, yy, total_w - 4, hgt - 2))
        if bw > 1:
            pygame.draw.rect(surf, col, pygame.Rect(x + 2, yy, bw, hgt - 2))
        text(surf, "%s %s" % (GLYPHS[i], NAMES[i]),
             (x + total_w + 6, yy - 2), 15,
             (col[0] // 2 + 60, col[1] // 2 + 60, col[2] // 2 + 60))

    # Neutral buoyancy marker on the brine band: where you stop sinking.
    mx = x + 2 + int((total_w - 4) * C.NEUTRAL_BRINE)
    pygame.draw.line(surf, (200, 210, 220), (mx, y + 2), (mx, y + hgt),  1)
    text(surf, "RESERVE", (x, y - 17), 15, (110, 122, 130))
    text(surf, "%d" % int(res.magnitude), (x - 8, y - 15), 18,
         (150, 162, 172), right=True)

    # What it is costing you to be the thing you currently are. Ambient
    # uptake covers the base rate and nothing more, so any number here
    # above about 0.5 is a promise that you will be hunting shortly.
    up = body.upkeep
    col = (150, 160, 170) if up < 1.0 else (
        (210, 170, 110) if up < 1.6 else (232, 130, 110))
    text(surf, "upkeep -%.1f/s" % up, (x, y + hgt * 4 + 10), 16, col)
    text(surf, "H  the rules", (x, y + hgt * 4 + 28), 15, (92, 112, 118))


def _standing(surf, body, topleft):
    """The two chains that are always running.

    Drawn above the reserve bars rather than beside the firing slots on
    purpose: what you are *running* belongs with what you are made of, not
    with what you are shooting."""
    x, y = topleft
    fx = body.standing_fx
    for i, ch in enumerate(body.standing):
        rect = pygame.Rect(x + i * 62, y, 56, 30)
        ok, _ = body.validate(ch, standing=True)
        organs = body.chain_organs(ch) if ok else None
        pygame.draw.rect(surf, (22, 26, 30), rect, border_radius=3)
        pygame.draw.rect(surf, (120, 150, 140) if ok else (46, 44, 44), rect,
                         1, border_radius=3)
        text(surf, str(5 + i), (rect.x + 4, rect.y + 2), 14,
             (110, 130, 125) if ok else (66, 68, 72))
        if organs:
            text(surf, "".join(o.glyph for o in organs),
                 (rect.centerx + 4, rect.centery + 1), 18, (170, 205, 195),
                 center=True)

    marks = []
    if fx["heat"] > 0.3:
        marks.append(("burning", (226, 148, 90)))
    elif fx["heat"] < -0.3:
        marks.append(("cold", (130, 180, 220)))
    if fx["murk"] > 0.3:
        marks.append(("hazed", (168, 152, 120)))
    if fx["gentle"] > 0.3:
        marks.append(("tended", (150, 205, 175)))
    if fx["lift"] > 0.6:
        marks.append(("buoyant", (150, 190, 215)))
    elif fx["lift"] < -0.6:
        marks.append(("heavy", (140, 150, 165)))
    if fx["jolt"] > 0.5:
        marks.append(("quick", (196, 158, 236)))
    mx = x + 2 * 62 + 8
    for i, (word, col) in enumerate(marks[:3]):
        text(surf, word, (mx, y + i * 11), 15, col)


def _hazard(surf, world, center):
    """The region, working on you. Named, so the answer is findable."""
    bite = getattr(world, "hazard_bite", 0.0)
    if bite < 0.12:
        return
    from .. import config as C
    hz = C.HAZARD.get(world.atlas.rooms[world.room_key]["region"], {})
    if not hz:
        return
    a = int(90 + 150 * bite)
    text(surf, hz["note"], center, 21, (216, 150, 120), center=True, alpha=a)


def _chains(surf, body, bottomright):
    x, y = bottomright
    size = 40
    keys = ("1", "2", "3", "4")
    for i in range(4):
        cx = x - (3 - i) * (size + 8) - size
        cy = y - size
        rect = pygame.Rect(cx, cy, size, size)
        ch = body.chains[i]
        ok, why = body.validate(ch)
        organs = body.chain_organs(ch) if ok else None

        pygame.draw.rect(surf, (22, 26, 30), rect, border_radius=4)
        if not ok:
            pygame.draw.rect(surf, (48, 44, 44), rect, 1, border_radius=4)
            text(surf, keys[i], (cx + 5, cy + 3), 16, (70, 74, 80))
            continue

        hot = max(o.heat for o in organs) / C.ORGAN_SEIZE_AT
        seized = any(o.seized for o in organs)
        cooling = ch.timer > 0.0

        edge = (232, 110, 90) if seized else (
            (110, 120, 130) if cooling else (180, 195, 208))
        pygame.draw.rect(surf, edge, rect, 1, border_radius=4)

        # The organs in the chain, as glyphs, in order. This is the only
        # place in play where you can see what a slot actually is.
        gl = "".join(o.glyph for o in organs)
        text(surf, gl, (cx + size // 2, cy + size // 2 - 2), 19,
             (215, 225, 235) if not seized else (240, 150, 140), center=True)
        text(surf, keys[i], (cx + 4, cy + 2), 15, (110, 120, 130))

        if hot > 0.05:
            bar = int((size - 8) * min(1.0, hot))
            col = (230, 120, 80) if hot > 0.7 else (170, 140, 90)
            pygame.draw.rect(surf, col,
                             pygame.Rect(cx + 4, cy + size - 5, bar, 3))
        if cooling:
            k = 1.0 - min(1.0, ch.timer / max(0.01, ch.cooldown))
            pygame.draw.rect(surf, (90, 110, 130),
                             pygame.Rect(cx, cy + size - 2,
                                         int(size * k), 2))


def _threat_edge(surf, level, world):
    """How watched you feel. It is the disturbance value and nothing else,
    which means the player can learn to read it and then learn to control
    it, which is the entire stealth loop expressed as a colour."""
    if level < 0.04:
        return
    w, h = surf.get_size()
    band = 46
    a = int(min(190, level * 210))
    col = (150, 40, 36) if level > 0.55 else (90, 70, 40)
    edge = pygame.Surface((w, band), pygame.SRCALPHA)
    for i in range(band):
        k = 1.0 - i / band
        edge.fill((col[0], col[1], col[2], int(a * k * k)),
                  pygame.Rect(0, i, w, 1))
    surf.blit(edge, (0, 0))
    surf.blit(pygame.transform.flip(edge, False, True), (0, h - band))
    side = pygame.transform.rotate(edge, 90)
    sw = side.get_width()
    surf.blit(pygame.transform.smoothscale(side, (sw, h)), (0, 0))
    surf.blit(pygame.transform.flip(
        pygame.transform.smoothscale(side, (sw, h)), True, False), (w - sw, 0))

    if world.apex is not None and not world.apex.dead:
        from ..creatures import HUNT, STRIKE
        if world.apex.state in (HUNT, STRIKE):
            text(surf, "something has stopped waiting", (w // 2, 30), 22,
                 (220, 140, 130), center=True,
                 alpha=int(150 + 90 * math.sin(world.time * 3.0)))


def _events(surf, world, center):
    y = center[1]
    for (msg, pos, age) in world.events[-3:]:
        a = int(255 * max(0.0, min(1.0, (4.5 - age) / 1.6)))
        text(surf, msg, (center[0], y), 21, (200, 190, 175), center=True,
             alpha=a)
        y += 26


def _notices(surf, notices, center):
    y = center[1]
    for (msg, age) in notices[-3:]:
        a = int(255 * max(0.0, min(1.0, (5.0 - age) / 1.8)))
        text(surf, msg, (center[0], y), 20, (170, 200, 190), center=True,
             alpha=a)
        y += 24


def _room_label(surf, world, pos):
    spec = world.atlas.rooms[world.room_key]
    from ..world.atlas import REGIONS
    reg = REGIONS[spec["region"]]
    text(surf, spec["name"], pos, 24, (150, 162, 172))
    text(surf, reg["name"].lower(), (pos[0], pos[1] + 20), 17, (86, 96, 104))
