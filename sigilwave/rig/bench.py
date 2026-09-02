"""THE BENCH -- RIGS.md 8, kept from SUBMERGED 10 and rebuilt on the rig.

RIGS.md 8 names four reasons Noita stays opaque and answers each one with a
promise: "every property of a slug is drawn on the slug", "the bench, kept
from SUBMERGED 10 -- still water, one slug, slow motion, a scrub bar", "eleven
modules", and "the game names your rig back to you in a sentence". This
screen is where all four promises get cashed in one place. There is no other
place they can be checked, because RIGS.md 12.2 states the actual test this
file exists to pass:

    Hand somebody INTAKE -> SQUEEZE -> COIL -> EXPAND -> PORT with the COIL
    taken out, let them watch the slug cross it, and ask why it does nothing.
    If they can work it out from the animation, the system is learnable.

A rig has no time axis worth scrubbing -- RIGS.md 4 walks five numbers down a
list, not a wavefront across a grid -- so "slow motion" becomes "one card per
module, read left to right" instead of a playhead. What survives from the old
bench is the discipline: nothing is explained in prose that the picture
should be saying by itself.

THE CENTREPIECE (RIGS.md 8.2)
------------------------------
Under every stage sit five small bars: heat, pressure, gas, speed, bubbles --
the slug's five numbers, drawn as five visual channels, exactly as 8.2
promises. Heat is the only one on a diverging scale, because heat is the only
one of the five with a natural zero that is not zero: ambient. A slug that
left a module at ambient temperature did nothing to it; RIGS.md 4.1 spends a
whole section on the fact that a squeeze-then-expand round trip is supposed to
look like "nothing happened" and instead comes back warm, and that failure
mode is invisible on a linear scale but obvious the moment warmer-than-here
and colder-than-here are two different colours either side of a neutral
midpoint.

Pressure and gas are drawn against their own natural reference points instead
-- pressure on a log scale with the tear threshold marked (pressure spans six
decades over the course of a chain: 0.02 bar at the throat of a charge, 70 bar
at 700 m, and a linear scale would flatten every reading that matters into a
sliver), gas as saturation against local capacity with the bubbling line
marked at 1.0, because "gas" alone means nothing without knowing how much this
water, at this temperature and pressure, could even hold (units.py:
`working_fraction`, `gas_capacity`). Bubbles are drawn as a scatter of grains
rather than a filled bar on purpose -- RIGS.md 3.1's own table describes gas as
"grain, from invisible to fizzing", and bubbles specifically are gas that has
already left solution, so they get the one bar that looks like something
coming out of the water rather than a level inside it.

RUNNING
-------
    python -m sigilwave.rig.bench
"""

import math

import pygame

from . import library
from .chain import Chain, ambient_at
from .modules import NOTES, PAIRS, SINGLETONS
from .units import TEAR_PRESSURE, gas_capacity

# --- palette: "instrument panel at depth" ------------------------------------
#
# Cool slate neutrals rather than pure grey, because a rig lives underwater
# and the one thing every reading in it has to answer is "warmer or colder
# than where I am standing" -- so the neutrals lean the same blue-grey the
# cold end of the heat scale does, and the two warm accents (hot, brass) are
# kept scarce enough that seeing either one means something.


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


GROUND = _hex("#E7ECED")
SURFACE = _hex("#FBFCFC")
SUNK = _hex("#DCE3E5")
INK = _hex("#0F1619")
SOFT_INK = _hex("#4C5A60")
RULE = _hex("#C6D1D4")
COLD = _hex("#1D6C89")
HOT = _hex("#BC4227")
BRASS = _hex("#96702C")
GREEN = _hex("#2F7A55")
NEUTRAL_HEAT = _hex("#9BA9AD")   # the colour of "no different from ambient"

WIDTH, HEIGHT = 1440, 900
SIDEBAR_W = 300
PAD = 14
TOPBAR_H = 64
CARD_W = 190
CARD_H = 248
CARD_GAP = 14
CHAIN_Y = TOPBAR_H + PAD
CHAIN_H = CARD_H + 2 * PAD + 18   # + a scroll hint line
PRESET_Y = CHAIN_Y + CHAIN_H + PAD
PRESET_H = 58
VERDICT_Y = PRESET_Y + PRESET_H + PAD
VERDICT_H = HEIGHT - VERDICT_Y - PAD

BAR_W = 20
BAR_H = 74
BAR_GAP = 14

MAX_DEPTH = 760.0

# The clamp each bar saturates at. Chosen by hand against library.py's own
# numbers (see the docstring above the module and the sanity check the task
# asked for): a squeeze moves the slug about 11 degC, the heater about 23,
# and the boiler well past 80 -- so 70 degC of span gives every ordinary
# machine visible headroom and still pins the boiler fully red, which is the
# right picture for "cooking itself".
HEAT_SPAN = 70.0
PRESSURE_LOG_MIN, PRESSURE_LOG_MAX = -2.0, 4.0   # bar, decades either side
GAS_SATURATION_SPAN = 1.6                         # x capacity
SPEED_SPAN = 50.0                                 # m/s, sqrt-compressed
BUBBLE_SPAN = 1.0                                 # gas fraction, direct


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(_lerp(c1[i], c2[i], t))) for i in range(3))


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def diverging_heat_colour(delta):
    """Warmer than ambient reads hot, colder reads cold, ambient reads neutral.

    The whole legibility claim in one function. `delta` is stage temp minus
    the water this rig actually opened into, not some fixed reference, so the
    same slug reads differently at the surface and at 700 m -- which is
    correct, because RIGS.md 9.1 says depth is supposed to change what "hot"
    means.
    """
    # A square root, not a straight line: an 11 degC squeeze (a completely
    # ordinary single module, see units.py's own calibration note) is real
    # and has to be visibly not-neutral, but a linear ramp against a span
    # wide enough to also hold the boiler leaves anything under about 20
    # degrees reading as a barely-tinted grey. The root pulls small,
    # everyday deltas up toward visibility without changing where the scale
    # saturates, and it keeps the ordering of a chain that runs hotter with
    # every stage -- which is the thing worth being able to see.
    linear = _clamp(abs(delta) / HEAT_SPAN, 0.0, 1.0)
    t = math.sqrt(linear)
    return _lerp_color(NEUTRAL_HEAT, HOT if delta >= 0 else COLD, t)


# --- text: condensed uppercase tracked labels, monospace aligned numbers ----
#
# SysFont only, per house rule. "Condensed" is faked with a narrow family
# where the platform has one and a plain sans where it does not; "tracked" is
# faked by drawing letters one at a time with a fixed gap, because pygame's
# font objects do not expose real letter-spacing.

_HEAD_FAMILY = "arial narrow,arialnarrow,segoe ui,arial,helvetica,sans-serif"
_BODY_FAMILY = "segoe ui,arial,helvetica,sans-serif"
_MONO_FAMILY = "consolas,menlo,dejavu sans mono,courier new,monospace"


def load_fonts():
    return {
        "title": pygame.font.SysFont(_HEAD_FAMILY, 24, bold=True),
        "head": pygame.font.SysFont(_HEAD_FAMILY, 15, bold=True),
        "head_sm": pygame.font.SysFont(_HEAD_FAMILY, 12, bold=True),
        "micro": pygame.font.SysFont(_HEAD_FAMILY, 9, bold=True),
        "body": pygame.font.SysFont(_BODY_FAMILY, 13),
        "body_sm": pygame.font.SysFont(_BODY_FAMILY, 12),
        "mono": pygame.font.SysFont(_MONO_FAMILY, 14),
        "mono_sm": pygame.font.SysFont(_MONO_FAMILY, 12),
        "mono_xs": pygame.font.SysFont(_MONO_FAMILY, 10),
    }


def _tracked_width(text, font, spacing=1):
    if not text:
        return 0
    return sum(font.size(ch)[0] for ch in text) + spacing * (len(text) - 1)


def draw_tracked(surface, text, font, color, topleft=None, center=None, spacing=1):
    """Letter-spaced text, the poor man's way. Returns the rect it occupied."""
    w = _tracked_width(text, font, spacing)
    h = font.get_height()
    if center is not None:
        x, y = center[0] - w // 2, center[1] - h // 2
    else:
        x, y = topleft
    cx = x
    for ch in text:
        img = font.render(ch, True, color)
        surface.blit(img, (cx, y))
        cx += img.get_width() + spacing
    return pygame.Rect(x, y, w, h)


def wrap_text(text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.size(trial)[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(surface, text, font, color, rect, line_gap=2, max_lines=None):
    lines = wrap_text(text, font, rect.width)
    if max_lines is not None:
        lines = lines[:max_lines]
    y = rect.top
    for line in lines:
        surface.blit(font.render(line, True, color), (rect.left, y))
        y += font.get_height() + line_gap
    return y


def fmt_num(x, decimals=1):
    if x is None:
        return "--"
    return f"{x:.{decimals}f}"


# --- the bench, as state --------------------------------------------------


class Bench:
    """Everything the screen needs to remember between frames.

    Click targets are rebuilt every draw and cached here, then read back by
    the event handler -- the same shape `bench/app.py` uses (`begin`/`drag`/
    `commit`), because a rig has editing gestures too (append, remove, pick a
    note) even though it has no geometry to drag.
    """

    def __init__(self):
        p = library.get("the cooler")
        self.chain: Chain = p.build()
        self.loaded_preset = p
        self.depth = 40.0
        self.scroll_x = 0
        self.dragging_depth = False

        # populated by draw(), consumed by handle_click()
        self.module_hits = []    # (rect, kind, option)
        self.card_hits = []      # (rect, index)
        self.preset_hits = []    # (rect, name)
        self.clear_hit = None    # rect
        self.depth_track = None  # rect

    def ambient(self):
        return ambient_at(_clamp(self.depth, 0.0, MAX_DEPTH))

    def result(self):
        return self.chain.evaluate(self.ambient())

    def append(self, kind, option=None):
        self.chain.append(kind, option)

    def remove(self, i):
        self.chain.remove(i)

    def clear(self):
        self.chain = Chain(())
        self.loaded_preset = None
        self.scroll_x = 0

    def load_preset(self, name):
        p = library.get(name)
        self.chain = p.build()
        self.loaded_preset = p
        self.scroll_x = 0

    def set_depth_from_x(self, x):
        if self.depth_track is None:
            return
        t = (x - self.depth_track.left) / max(1, self.depth_track.width)
        self.depth = _clamp(t, 0.0, 1.0) * MAX_DEPTH

    def handle_click(self, pos):
        x, y = pos
        if self.depth_track is not None and self.depth_track.collidepoint(pos):
            self.dragging_depth = True
            self.set_depth_from_x(x)
            return
        for rect, kind, option in self.module_hits:
            if rect.collidepoint(pos):
                self.append(kind, option)
                return
        for rect, i in self.card_hits:
            if rect.collidepoint(pos):
                self.remove(i)
                return
        for rect, name in self.preset_hits:
            if rect.collidepoint(pos):
                self.load_preset(name)
                return
        if self.clear_hit is not None and self.clear_hit.collidepoint(pos):
            self.clear()
            return

    def scroll(self, dx):
        self.scroll_x = max(0, self.scroll_x - dx)


# --- drawing: the sidebar ---------------------------------------------------


def draw_sidebar(screen, bench, fonts):
    rect = pygame.Rect(0, 0, SIDEBAR_W, HEIGHT)
    pygame.draw.rect(screen, SUNK, rect)
    pygame.draw.line(screen, RULE, (SIDEBAR_W, 0), (SIDEBAR_W, HEIGHT), 1)

    bench.module_hits = []
    x0, y = PAD, PAD
    inner_w = SIDEBAR_W - 2 * PAD

    draw_tracked(screen, "THE VOCABULARY", fonts["head"], INK, topleft=(x0, y))
    y += 22
    draw_wrapped(screen, "Eleven modules, no knobs. Click to append.",
                 fonts["body_sm"], SOFT_INK, pygame.Rect(x0, y, inner_w, 30))
    y += 32

    half = (inner_w - 8) // 2

    def pair_row(kind_a, kind_b, y):
        ra = pygame.Rect(x0, y, half, 32)
        rb = pygame.Rect(x0 + half + 8, y, half, 32)
        _module_button(screen, fonts, ra, kind_a)
        _module_button(screen, fonts, rb, kind_b)
        bench.module_hits.append((ra, kind_a, None))
        bench.module_hits.append((rb, kind_b, None))
        return y + 40

    for kind_a, kind_b in PAIRS:
        y = pair_row(kind_a, kind_b, y)
        if kind_a == "FILTER" or kind_b == "FILTER":
            y = _option_chips(screen, bench, fonts, x0, y, inner_w,
                               "FILTER", ("gas", "heat", "both"))

    y += 6
    pygame.draw.line(screen, RULE, (x0, y), (x0 + inner_w, y), 1)
    y += 10

    for kind in SINGLETONS:
        r = pygame.Rect(x0, y, inner_w, 32)
        _module_button(screen, fonts, r, kind)
        bench.module_hits.append((r, kind, None))
        y += 40
        if kind == "RESONATOR":
            y = _option_chips(screen, bench, fonts, x0, y, inner_w,
                               "RESONATOR", tuple(NOTES.keys()))

    y += 10
    pygame.draw.line(screen, RULE, (x0, y), (x0 + inner_w, y), 1)
    y += 14

    draw_tracked(screen, "THE LIBRARY", fonts["head"], INK, topleft=(x0, y))
    y += 22
    draw_wrapped(screen, "A working machine to take apart.",
                 fonts["body_sm"], SOFT_INK, pygame.Rect(x0, y, inner_w, 20))
    y += 24

    bench.preset_hits = []
    loaded_name = bench.loaded_preset.name if bench.loaded_preset else None
    for preset in library.PRESETS:
        r = pygame.Rect(x0, y, inner_w, 24)
        active = preset.name == loaded_name
        pygame.draw.rect(screen, SURFACE if active else GROUND, r, border_radius=3)
        pygame.draw.rect(screen, BRASS if active else RULE, r, 1, border_radius=3)
        label = preset.name.upper()
        col = INK if active else SOFT_INK
        draw_tracked(screen, label, fonts["head_sm"], col,
                     topleft=(r.left + 8, r.top + 5), spacing=1)
        bench.preset_hits.append((r, preset.name))
        y += 27


def _module_button(screen, fonts, rect, kind):
    pygame.draw.rect(screen, SURFACE, rect, border_radius=4)
    pygame.draw.rect(screen, RULE, rect, 1, border_radius=4)
    draw_tracked(screen, kind, fonts["head_sm"], INK, center=rect.center, spacing=1)


def _option_chips(screen, bench, fonts, x0, y, inner_w, kind, options):
    """RESONATOR's five notes, and FILTER's target -- a module with an option
    gets a row of chips directly under its button rather than a dropdown, so
    every choice this rig can make is visible at once instead of hidden a
    click deeper."""
    n = len(options)
    gap = 4
    w = (inner_w - gap * (n - 1)) // n
    x = x0
    for opt in options:
        r = pygame.Rect(x, y, w, 22)
        pygame.draw.rect(screen, GROUND, r, border_radius=3)
        pygame.draw.rect(screen, RULE, r, 1, border_radius=3)
        label = opt.upper()
        f = fonts["micro"] if _tracked_width(label, fonts["head_sm"]) > w - 6 else fonts["head_sm"]
        draw_tracked(screen, label, f, SOFT_INK, center=r.center, spacing=0)
        bench.module_hits.append((r, kind, opt))
        x += w + gap
    return y + 28


# --- drawing: the depth slider ----------------------------------------------


def draw_topbar(screen, bench, fonts, amb):
    rect = pygame.Rect(SIDEBAR_W, 0, WIDTH - SIDEBAR_W, TOPBAR_H)
    pygame.draw.rect(screen, GROUND, rect)
    pygame.draw.line(screen, RULE, (SIDEBAR_W, TOPBAR_H), (WIDTH, TOPBAR_H), 1)

    x0 = SIDEBAR_W + PAD
    draw_tracked(screen, "DEPTH", fonts["head_sm"], SOFT_INK, topleft=(x0, 10), spacing=1)

    track = pygame.Rect(x0, 30, 420, 10)
    bench.depth_track = track
    pygame.draw.rect(screen, SUNK, track, border_radius=5)
    t = bench.depth / MAX_DEPTH
    fill = pygame.Rect(track.left, track.top, int(track.width * t), track.height)
    pygame.draw.rect(screen, BRASS, fill, border_radius=5)
    hx = track.left + int(track.width * t)
    pygame.draw.circle(screen, SURFACE, (hx, track.centery), 8)
    pygame.draw.circle(screen, BRASS, (hx, track.centery), 8, 2)

    depth_label = f"{bench.depth:5.0f} m"
    screen.blit(fonts["mono"].render(depth_label, True, INK), (track.right + 14, 22))

    readout = (f"ambient  {amb.temp:6.2f} C   {amb.pressure:6.2f} bar   "
               f"gas {amb.gas:5.3f} / cap {amb.capacity:5.3f}")
    screen.blit(fonts["mono_sm"].render(readout, True, SOFT_INK),
               (track.right + 120, 25))

    # a clear-chain button lives here rather than in the sidebar, because it
    # acts on the chain, not on the vocabulary
    cr = pygame.Rect(WIDTH - 110, 16, 96, 32)
    pygame.draw.rect(screen, SURFACE, cr, border_radius=4)
    pygame.draw.rect(screen, RULE, cr, 1, border_radius=4)
    draw_tracked(screen, "CLEAR", fonts["head_sm"], SOFT_INK, center=cr.center, spacing=1)
    bench.clear_hit = cr


# --- drawing: the chain, and the bars underneath each stage -----------------


def draw_chain(screen, bench, fonts, result):
    outer = pygame.Rect(SIDEBAR_W + PAD, CHAIN_Y, WIDTH - SIDEBAR_W - 2 * PAD, CHAIN_H)
    pygame.draw.rect(screen, SURFACE, outer, border_radius=6)
    pygame.draw.rect(screen, RULE, outer, 1, border_radius=6)

    bench.card_hits = []
    stages = result.stages

    if not stages:
        draw_tracked(screen, "AN EMPTY BENCH", fonts["head"], SOFT_INK,
                     center=outer.center, spacing=1)
        y2 = outer.centery + 16
        draw_wrapped(screen, "Click a module on the left to begin.",
                     fonts["body_sm"], SOFT_INK,
                     pygame.Rect(outer.left, y2, outer.width, 20))
        return

    content_w = len(stages) * (CARD_W + CARD_GAP) - CARD_GAP
    max_scroll = max(0, content_w - (outer.width - 2 * PAD))
    bench.scroll_x = min(bench.scroll_x, max_scroll)

    prev_clip = screen.get_clip()
    inner = outer.inflate(-2 * PAD, -2 * PAD)
    inner.height -= 18
    screen.set_clip(inner)

    x = inner.left - bench.scroll_x
    for st in stages:
        card = pygame.Rect(x, inner.top, CARD_W, CARD_H)
        if card.right >= inner.left and card.left <= inner.right:
            _draw_card(screen, fonts, card, st, result)
            bench.card_hits.append((pygame.Rect(x, inner.top, CARD_W, CARD_H), st.index))
        x += CARD_W + CARD_GAP

    screen.set_clip(prev_clip)

    hint_y = inner.bottom + 4
    if max_scroll > 0:
        hint = "scroll to see the rest of the chain -- click a card to remove it"
    else:
        hint = "click a card to remove it"
    screen.blit(fonts["body_sm"].render(hint, True, SOFT_INK), (inner.left, hint_y))


def _card_label(st):
    return f"{st.kind}({st.option})" if st.option else st.kind


def _draw_card(screen, fonts, rect, st, result):
    dead = st.dead
    bg = SUNK if dead else SURFACE
    pygame.draw.rect(screen, bg, rect, border_radius=5)
    pygame.draw.rect(screen, RULE, rect, 1, border_radius=5)

    ink = RULE if dead else INK
    soft = RULE if dead else SOFT_INK

    pad = 10
    x0 = rect.left + pad
    y = rect.top + pad
    inner_w = rect.width - 2 * pad

    # index, so "second module" is a thing you can point at (RIGS.md 2.2)
    idx_txt = f"{st.index + 1:02d}"
    screen.blit(fonts["mono_xs"].render(idx_txt, True, soft), (rect.left + 6, rect.top + 6))
    # a small close mark, the affordance for "click to remove"
    xr = fonts["micro"].render("REMOVE", True, soft)
    screen.blit(xr, (rect.right - xr.get_width() - 6, rect.top + 6))

    draw_tracked(screen, _card_label(st), fonts["head_sm"], ink, topleft=(x0, y), spacing=1)
    y += 20

    y = draw_wrapped(screen, st.line, fonts["body_sm"], soft,
                     pygame.Rect(x0, y, inner_w, 40), max_lines=3)
    y += 4

    if dead:
        note = "dead -- carried, untouched" if st.temp is not None else "dead -- no water yet"
        screen.blit(fonts["micro"].render(note.upper(), True, soft), (x0, y))
        y += 14
    elif st.events:
        tag = "  ".join(e.upper() for e in st.events)
        screen.blit(fonts["micro"].render(tag, True, BRASS), (x0, y))
        y += 14
    else:
        y += 14

    bars_top = rect.bottom - pad - 14 - BAR_H - 22
    draw_tracked(screen, "AS IT LEFT", fonts["micro"], soft,
                 topleft=(x0, bars_top - 14), spacing=1)
    _draw_bars(screen, fonts, pygame.Rect(x0, bars_top, inner_w, BAR_H), st, result, dead)


def _draw_bars(screen, fonts, rect, st, result, dead):
    """Five bars, five channels, one law each. See the module docstring for
    why each scale is what it is."""
    cols = ["H", "P", "G", "S", "B"]
    n = len(cols)
    total_bars_w = n * BAR_W + (n - 1) * BAR_GAP
    x0 = rect.left + (rect.width - total_bars_w) // 2
    base_y = rect.top + BAR_H

    if st.temp is None:
        # no water has reached this stage at all -- draw the tracks hollow
        for i, label in enumerate(cols):
            bx = x0 + i * (BAR_W + BAR_GAP)
            track = pygame.Rect(bx, rect.top, BAR_W, BAR_H)
            pygame.draw.rect(screen, RULE, track, 1, border_radius=3)
            draw_tracked(screen, label, fonts["micro"], RULE,
                         center=(track.centerx, rect.bottom + 8), spacing=0)
        screen.blit(fonts["micro"].render("NO WATER", True, RULE), (rect.left, rect.bottom + 20))
        return

    alpha_mul = 0.42 if dead else 1.0

    def shade(c):
        return tuple(int(round(_lerp(SUNK[i], c[i], alpha_mul))) for i in range(3))

    ref_temp = result.ledger.reference_temp

    # HEAT -- bipolar around ambient, the diverging scale itself
    bx = x0
    track = pygame.Rect(bx, rect.top, BAR_W, BAR_H)
    pygame.draw.rect(screen, GROUND, track, border_radius=3)
    mid = track.centery
    pygame.draw.line(screen, RULE, (track.left - 2, mid), (track.right + 2, mid), 1)
    delta = st.temp - ref_temp
    frac = _clamp(abs(delta) / HEAT_SPAN, 0.0, 1.0)
    half_h = int((BAR_H / 2 - 2) * frac)
    colour = shade(diverging_heat_colour(delta))
    if delta >= 0:
        r = pygame.Rect(track.left + 2, mid - half_h, BAR_W - 4, half_h)
    else:
        r = pygame.Rect(track.left + 2, mid, BAR_W - 4, half_h)
    if half_h > 0:
        pygame.draw.rect(screen, colour, r, border_radius=2)
    pygame.draw.rect(screen, RULE, track, 1, border_radius=3)
    _bar_caption(screen, fonts, track, rect, "H", f"{st.temp:.1f}",
                 shade(HOT if delta >= 0 else COLD) if abs(delta) > 0.5 else SOFT_INK,
                 column=0)

    # PRESSURE -- log scale, tear threshold marked
    bx = x0 + (BAR_W + BAR_GAP)
    track = pygame.Rect(bx, rect.top, BAR_W, BAR_H)
    pygame.draw.rect(screen, GROUND, track, border_radius=3)
    p_frac = _log_frac(st.pressure)
    fh = int(BAR_H * p_frac)
    if fh > 0:
        pygame.draw.rect(screen, shade(BRASS),
                         pygame.Rect(track.left + 2, track.bottom - fh, BAR_W - 4, fh),
                         border_radius=2)
    tear_y = track.bottom - int(BAR_H * _log_frac(TEAR_PRESSURE))
    pygame.draw.line(screen, HOT, (track.left - 2, tear_y), (track.right + 2, tear_y), 1)
    pygame.draw.rect(screen, RULE, track, 1, border_radius=3)
    _bar_caption(screen, fonts, track, rect, "P",
                 f"{st.pressure:.1f}" if st.pressure >= 1.0 else f"{st.pressure:.2f}",
                 SOFT_INK, column=1)

    # GAS -- saturation against local capacity, bubbling line at 1.0
    bx = x0 + 2 * (BAR_W + BAR_GAP)
    track = pygame.Rect(bx, rect.top, BAR_W, BAR_H)
    pygame.draw.rect(screen, GROUND, track, border_radius=3)
    capacity = gas_capacity(st.pressure, st.temp)
    saturation = st.gas / capacity if capacity > 1e-9 else 0.0
    g_frac = _clamp(saturation / GAS_SATURATION_SPAN, 0.0, 1.0)
    fh = int(BAR_H * g_frac)
    if fh > 0:
        pygame.draw.rect(screen, shade(COLD),
                         pygame.Rect(track.left + 2, track.bottom - fh, BAR_W - 4, fh),
                         border_radius=2)
    cap_y = track.bottom - int(BAR_H * _clamp(1.0 / GAS_SATURATION_SPAN, 0.0, 1.0))
    pygame.draw.line(screen, BRASS, (track.left - 2, cap_y), (track.right + 2, cap_y), 1)
    pygame.draw.rect(screen, RULE, track, 1, border_radius=3)
    _bar_caption(screen, fonts, track, rect, "G", f"{saturation * 100:.0f}%",
                 SOFT_INK, column=2)

    # SPEED -- sqrt-compressed, so a 4 m/s pump shove is still legible next to
    # a 45 m/s charge jet
    bx = x0 + 3 * (BAR_W + BAR_GAP)
    track = pygame.Rect(bx, rect.top, BAR_W, BAR_H)
    pygame.draw.rect(screen, GROUND, track, border_radius=3)
    s_frac = _clamp(math.sqrt(max(0.0, st.speed) / SPEED_SPAN), 0.0, 1.0)
    fh = int(BAR_H * s_frac)
    if fh > 0:
        pygame.draw.rect(screen, shade(GREEN),
                         pygame.Rect(track.left + 2, track.bottom - fh, BAR_W - 4, fh),
                         border_radius=2)
    pygame.draw.rect(screen, RULE, track, 1, border_radius=3)
    _bar_caption(screen, fonts, track, rect, "S", f"{(st.speed or 0.0):.1f}",
                 SOFT_INK, column=3)

    # BUBBLES -- grains, not a fill: gas that has already left solution,
    # drawn the way RIGS.md 3.1 describes it rather than as one more level
    bx = x0 + 4 * (BAR_W + BAR_GAP)
    track = pygame.Rect(bx, rect.top, BAR_W, BAR_H)
    pygame.draw.rect(screen, GROUND, track, border_radius=3)
    b_frac = _clamp((st.bubbles or 0.0) / BUBBLE_SPAN, 0.0, 1.0)
    _draw_grain(screen, track, b_frac, shade(BRASS) if b_frac > 0 else SOFT_INK)
    pygame.draw.rect(screen, RULE, track, 1, border_radius=3)
    _bar_caption(screen, fonts, track, rect, "B", f"{(st.bubbles or 0.0):.2f}",
                 SOFT_INK, column=4)


def _log_frac(p):
    p = max(1e-6, p)
    lo, hi = PRESSURE_LOG_MIN, PRESSURE_LOG_MAX
    return _clamp((math.log10(p) - lo) / (hi - lo), 0.0, 1.0)


def _draw_grain(screen, track, frac, colour):
    """Gas beyond capacity, drawn as grains rather than a fill -- see the
    module docstring. Filled from the bottom, denser as the fraction grows,
    so a fizzing slug visibly speckles rather than just filling a level."""
    if frac <= 0.0:
        return
    rows = max(1, int(BAR_H / 6))
    filled_rows = max(1, int(rows * frac))
    cols = 3
    for row in range(filled_rows):
        yy = track.bottom - 3 - row * 6
        for c in range(cols):
            xx = track.left + 4 + c * ((BAR_W - 8) / max(1, cols - 1))
            pygame.draw.circle(screen, colour, (int(xx), int(yy)), 1)


def _bar_caption(screen, fonts, track, panel_rect, letter, value, value_colour,
                 column=0):
    """One bar's label and reading.

    The values are STAGGERED onto two rows and carry no unit suffix, and both
    of those are bug fixes rather than style. A column is 34 px pitch and
    "29.3c" renders at about 30 px, so adjacent readings collided and the
    squeeze stage rendered as `29.3c15.00b` -- unreadable, in the one row of
    the screen that carries the entire legibility claim (RIGS.md 8.2). The
    letter above each bar already says which quantity it is, so the unit
    letter on the number was doing no work and costing the space that made it
    illegible.
    """
    draw_tracked(screen, letter, fonts["micro"], SOFT_INK,
                 center=(track.centerx, panel_rect.bottom + 8), spacing=0)
    img = fonts["mono_xs"].render(value, True, value_colour)
    dy = 18 if column % 2 == 0 else 29
    screen.blit(img, (track.centerx - img.get_width() // 2, panel_rect.bottom + dy))


# --- drawing: the preset panel ----------------------------------------------


def draw_preset_panel(screen, bench, fonts):
    rect = pygame.Rect(SIDEBAR_W + PAD, PRESET_Y, WIDTH - SIDEBAR_W - 2 * PAD, PRESET_H)
    pygame.draw.rect(screen, GROUND, rect, border_radius=6)
    pygame.draw.rect(screen, RULE, rect, 1, border_radius=6)

    p = bench.loaded_preset
    x0, y = rect.left + 12, rect.top + 8
    if p is None:
        screen.blit(fonts["body_sm"].render(
            "no preset loaded -- this chain was built by hand",
            True, SOFT_INK), (x0, y + 10))
        return

    draw_tracked(screen, p.name.upper(), fonts["head_sm"], BRASS, topleft=(x0, y), spacing=1)
    line_w = rect.width - 24
    y2 = y + 18
    screen.blit(fonts["body_sm"].render(p.summary, True, INK), (x0, y2))
    y2 += 16
    try_line = "TRY THIS: " + p.try_this
    draw_wrapped(screen, try_line, fonts["body_sm"], SOFT_INK,
                pygame.Rect(x0, y2, line_w, 16), max_lines=1)


# --- drawing: the verdict ----------------------------------------------------


def draw_verdict(screen, bench, fonts, result):
    rect = pygame.Rect(SIDEBAR_W + PAD, VERDICT_Y, WIDTH - SIDEBAR_W - 2 * PAD, VERDICT_H)
    pygame.draw.rect(screen, SURFACE, rect, border_radius=6)
    pygame.draw.rect(screen, RULE, rect, 1, border_radius=6)

    x0 = rect.left + 18
    y = rect.top + 16

    fault = result.fault
    if fault:
        headline_colour = HOT if fault.kind == "IT BOILS" else BRASS
    else:
        headline_colour = GREEN

    name = bench.chain.name(result)
    draw_tracked(screen, name.upper(), fonts["title"], headline_colour, topleft=(x0, y), spacing=1)
    y += 34

    sentence = bench.chain.describe()
    y = draw_wrapped(screen, sentence, fonts["body"], INK,
                     pygame.Rect(x0, y, rect.width - 340, 40), max_lines=3)
    y += 8

    # badges: RUNS / the fault kind, and TORE independently -- chain.py keeps
    # tearing as its own boolean rather than a fourth Fault kind (see the
    # report at the end of this file's companion notes), so the two are drawn
    # as two separate pills instead of collapsing them into one.
    bx = x0
    by = y
    if fault is None:
        bx = _badge(screen, fonts, (bx, by), "RUNS", GREEN)
    else:
        bx = _badge(screen, fonts, (bx, by), fault.kind, HOT if fault.kind == "IT BOILS" else BRASS)
    if result.tore:
        bx = _badge(screen, fonts, (bx + 8, by), "TORE", HOT)
    y += 30

    if fault is not None:
        y = draw_wrapped(screen, fault.why, fonts["body_sm"], SOFT_INK,
                         pygame.Rect(x0, y, rect.width - 340, 44), max_lines=3)
        y += 6

    # the numbers, monospace, digits aligned -- a two-column stat block
    stats_x = rect.right - 320
    stats_y = rect.top + 16
    led = result.ledger
    rows = [
        ("COST", f"{result.cost:8.3f}", "econ. units"),
        # TEMP IN reads the ambient the bench is standing in, not the
        # ledger's reference_temp -- that field only gets set inside
        # Intake.apply() and stays at its dataclass default of 0.0 for a
        # chain with no INTAKE, which would print a false "0.00 C" for an
        # empty or all-dead chain instead of the water actually around it.
        ("TEMP IN", f"{result.ambient.temp:8.2f}", "C"),
        ("TEMP OUT", fmt_num(result.out_temp, 2).rjust(8), "C" if result.out_temp is not None else ""),
        ("HEAT -> OCEAN", f"{led.heat_to_ocean / 1000.0:8.2f}", "kJ"),
        ("GAS IN TANK", f"{led.tank_gas:8.3f}", "kg"),
        ("SPEED OUT", f"{result.out_speed:8.2f}", "m/s"),
    ]
    ry = stats_y
    for label, value, unit in rows:
        draw_tracked(screen, label, fonts["micro"], SOFT_INK, topleft=(stats_x, ry), spacing=1)
        vimg = fonts["mono"].render(value, True, INK)
        screen.blit(vimg, (stats_x + 150, ry - 2))
        if unit:
            screen.blit(fonts["mono_xs"].render(unit, True, SOFT_INK),
                       (stats_x + 150 + vimg.get_width() + 6, ry))
        ry += 22


def _badge(screen, fonts, pos, text, colour):
    label = text.upper()
    w = _tracked_width(label, fonts["head_sm"], 1) + 16
    r = pygame.Rect(pos[0], pos[1], w, 22)
    pygame.draw.rect(screen, colour, r, border_radius=11)
    draw_tracked(screen, label, fonts["head_sm"], SURFACE, center=r.center, spacing=1)
    return r.right


# --- the whole frame ---------------------------------------------------------


def draw(screen, bench, fonts):
    screen.fill(GROUND)
    result = bench.result()
    amb = result.ambient

    draw_topbar(screen, bench, fonts, amb)
    draw_chain(screen, bench, fonts, result)
    draw_preset_panel(screen, bench, fonts)
    draw_verdict(screen, bench, fonts, result)
    draw_sidebar(screen, bench, fonts)   # last: it sits on top, and it is opaque
    return result


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("RIGS -- the bench")
    clock = pygame.time.Clock()
    fonts = load_fonts()
    bench = Bench()

    running = True
    while running:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    bench.handle_click(e.pos)
                elif e.button == 4:
                    bench.scroll(-40)
                elif e.button == 5:
                    bench.scroll(40)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                bench.dragging_depth = False
            elif e.type == pygame.MOUSEMOTION:
                if bench.dragging_depth:
                    bench.set_depth_from_x(e.pos[0])
            elif e.type == pygame.MOUSEWHEEL:
                bench.scroll(e.y * 40)

        draw(screen, bench, fonts)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
