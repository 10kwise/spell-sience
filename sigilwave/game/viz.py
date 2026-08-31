"""Drawing the invisible.

The design doc calls this the highest-leverage decision in the project and
it is right: a wave simulation renders, by default, as nothing at all. If
the player cannot see energy move, every mechanic in the game reads as
randomness, and the correct conclusion for them to draw is that the game is
broken.

So four quantities are always on screen, and they are always the same four:

    amplitude -> brightness      how much is here
    band      -> hue             what kind
    phase     -> travel          which way, and is it standing
    saturation-> node flash      the moment harmonics start

The last one matters more than its size suggests. Nonlinearity is the only
part of the physics that engages *suddenly*, and a player who cannot see the
instant a junction starts folding will never connect "I held the button a
bit longer" with "my blue sigil started throwing orange". One flash closes
that loop.

Nothing here computes anything. If a readout is wrong, the sim is wrong.
"""

import math

import numpy as np
import pygame

from .bands import BAND_COLORS, N_BANDS, band_color, dominant_band

INK_DARK = (62, 70, 88)
AMPLITUDE_GAIN = 5.5

# On-screen size the carried sigil is normalised to, and the range the
# normalisation is allowed to use.
#
# Drawing sigils at a fixed world scale is the obvious choice and it is wrong.
# A band-4 ring is a 38px circumference by definition — that is what makes it
# band 4 — so at any honest scale the hottest, most interesting instrument in
# the game renders as a ten-pixel smudge while a cold one fills the screen.
# The player then cannot see the waves in exactly the sigil whose behaviour
# is hardest to predict.
#
# Size is redundant information anyway: hue already says which band, and says
# it better. So size is spent on legibility instead, and every sigil is drawn
# at a readable size whatever its physics. Nothing about the simulation
# changes — this is a camera decision, not a model one.
SIGIL_TARGET_PX = 150.0
SIGIL_SCALE_MIN = 0.35
SIGIL_SCALE_MAX = 4.0


def display_scale(sigil, world_scale=1.0):
    """World scale for one sigil, normalised so it is readable on screen."""
    extent = max(1.0, getattr(sigil, "extent", 1.0))
    return max(SIGIL_SCALE_MIN, min(SIGIL_SCALE_MAX, SIGIL_TARGET_PX / extent)) * world_scale


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * max(0.0, min(1.0, t))) for i in range(3))


def sigil_hue(sigil) -> tuple:
    """A sigil is coloured by what it is currently *emitting*, not by what it
    is made of. A player who overdrives a blue sigil into the hot bands
    watches it turn orange in their hands, which is the single clearest
    possible signal that they changed what it does without redrawing it."""
    centre, total = dominant_band(sigil.measured_bands())
    if total < 1e-9:
        return (110, 128, 150)
    return band_color(centre)


def edge_profile(sigil, edge_index):
    """Standing-wave displacement along one edge: the two travelling waves
    superposed, which is what makes a node visibly a node."""
    net_edge = sigil.network.edges.get(edge_index)
    if net_edge is None:
        return None
    forward = net_edge.forward.spatial_profile()
    backward = net_edge.backward.spatial_profile()
    return list(forward[::-1]) + list(backward)


def draw_sigil(surface, sigil, origin, rot_deg=0.0, scale=1.0, alpha=1.0,
               show_nodes=True, width=3, camera=None):
    """Render a live sigil, transformed into wherever it is being carried."""
    if sigil is None or sigil.network is None or not sigil.graph.edges:
        return

    hot = sigil_hue(sigil)
    char_tint = sigil.char
    origin = pygame.Vector2(origin)

    def place(p):
        w = origin + (pygame.Vector2(p) * scale).rotate(rot_deg)
        return camera.world_to_screen(w) if camera else w

    for i, edge in enumerate(sigil.graph.edges):
        prof = edge_profile(sigil, i)
        if not prof:
            continue
        poly = edge.polyline
        n = len(poly)
        if n < 2:
            continue
        last = len(prof) - 1
        pts = [place(p) for p in poly]
        for k in range(n - 1):
            idx = min(last, int(k / max(1, n - 2) * last))
            mag = min(1.0, abs(prof[idx]) * AMPLITUDE_GAIN)
            base = _lerp(INK_DARK, (86, 48, 40), char_tint)
            col = _lerp(base, hot, mag)
            if alpha < 0.999:
                col = _lerp((12, 13, 18), col, alpha)
            # Two passes: a wide dim one under a narrow bright one. Energised
            # ink then reads as *glowing* rather than as a slightly lighter
            # line, which is what makes amplitude legible at a glance from
            # across the arena instead of only when squinting at the stroke.
            if mag > 0.06:
                pygame.draw.line(surface, _lerp((14, 16, 22), col, 0.40 * mag),
                                 pts[k], pts[k + 1], width + 5)
            pygame.draw.line(surface, col, pts[k], pts[k + 1], width)

    _draw_couplers(surface, sigil, place, alpha)

    if not show_nodes:
        return

    for node_id, node in sigil.graph.nodes.items():
        net_node = sigil.network.nodes.get(node_id)
        pos = place(node.pos)
        if node.is_terminal:
            col = (240, 224, 150)
            r = 4
        else:
            col = (150, 160, 178)
            r = 3
        if node_id == sigil.ignition_node:
            col = (255, 240, 190)
            r = 5
        pygame.draw.circle(surface, col, (int(pos.x), int(pos.y)), r)

        # The moment the nonlinearity actually engages — not merely that this
        # junction is capable of it.
        if net_node is not None and net_node.nl_a is not None:
            depth = abs(net_node.last_emitted) * net_node.nl_a
            if depth > 0.45:
                ring = _lerp((255, 220, 120), (255, 120, 90), min(1.0, (depth - 0.45) / 0.55))
                pygame.draw.circle(surface, ring, (int(pos.x), int(pos.y)), r + 5, 2)


def _draw_couplers(surface, sigil, place, alpha):
    """Shimmer across the gap, opacity by kappa. A coupler is invisible in
    the geometry — two strokes that simply do not touch — so if it is not
    drawn, the single most surprising thing in the physics happens for no
    reason the player can see."""
    if not sigil.coupler_sites:
        return
    for site in sigil.coupler_sites:
        try:
            a = sigil.graph.edges[site.edge_a].polyline
            b = sigil.graph.edges[site.edge_b].polyline
        except IndexError:
            continue
        ia = max(0, min(len(a) - 1, int(site.pos_a / 4.0)))
        ib = max(0, min(len(b) - 1, int(site.pos_b / 4.0)))
        pa, pb = place(a[ia]), place(b[ib])
        k = getattr(site, "kappa", 0.3)
        shimmer = 0.55 + 0.45 * math.sin(sigil.time * 7.0 + site.gap)
        col = _lerp((30, 40, 60), (190, 215, 255), k * shimmer * alpha)
        pygame.draw.line(surface, col, pa, pb, max(1, int(1 + 3 * k)))


# ---------------------------------------------------------------------------
# Readouts


def draw_spectrum(surface, rect, bands, peak_hint=None, label_font=None, highlight=None):
    """Six bars, always in the same place, always the same six colours.

    This is the Rosetta stone of the whole game: the bar chart of what a
    sigil emits and the coloured ring around an enemy are the same six hues,
    so "make the bars match the ring" is a complete, correct, and entirely
    wordless statement of the combat system."""
    total = max(sum(bands), 1e-9)
    scale = peak_hint if peak_hint else max(max(bands), 1e-9)
    bw = rect.width / N_BANDS
    pygame.draw.rect(surface, (18, 20, 26), rect, border_radius=3)
    for i in range(N_BANDS):
        frac = min(1.0, bands[i] / scale) if scale > 0 else 0.0
        h = max(1, int(frac * (rect.height - 4)))
        x = int(rect.x + i * bw) + 1
        w = max(1, int(bw) - 2)
        col = BAND_COLORS[i]
        if highlight is not None and abs(i - highlight) < 0.5:
            pygame.draw.rect(surface, (60, 66, 80), (x, rect.y + 2, w, rect.height - 4))
        pygame.draw.rect(surface, col, (x, rect.bottom - 2 - h, w, h))
    pygame.draw.rect(surface, (56, 62, 76), rect, 1, border_radius=3)
    _ = total, label_font


def draw_meter(surface, rect, frac, color, bg=(24, 27, 34), border=(60, 66, 80)):
    pygame.draw.rect(surface, bg, rect, border_radius=2)
    w = int(rect.width * max(0.0, min(1.0, frac)))
    if w > 0:
        pygame.draw.rect(surface, color, (rect.x, rect.y, w, rect.height), border_radius=2)
    pygame.draw.rect(surface, border, rect, 1, border_radius=2)


def draw_beat_ring(surface, center, radius, phase, on_beat_flash=0.0, color=(150, 200, 240)):
    """The loop's own round-trip time, drawn as a sweeping ring.

    The tempo is L/c — not a designer's number, the loop's actual period —
    so a player tapping to this ring is tapping the sigil's resonance, and
    the reinforcement they get is real. Making the rhythm visible converts a
    physics property into a skill."""
    if radius <= 2:
        return
    cx, cy = int(center[0]), int(center[1])
    pygame.draw.circle(surface, (40, 46, 58), (cx, cy), radius, 1)
    end = -math.pi / 2 + phase * math.tau
    pygame.draw.arc(
        surface, color,
        pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2),
        -math.pi / 2, end, 2,
    )
    if on_beat_flash > 0:
        glow = int(120 * min(1.0, on_beat_flash / 0.35))
        pygame.draw.circle(surface, (200 + glow // 4, 240, 255), (cx, cy), radius + 3, 2)


def draw_resonance_ring(surface, center, radius, resonance, pulse_t=0.0, thickness=2):
    """An enemy's weakness, worn on the outside.

    No scan button, no bestiary lookup, no hidden information: the colour of
    the ring is the colour of the energy that kills it, and its size is
    proportional to the ring you would have to draw to make that energy. A
    player eventually stops reading it as a colour and starts reading it as
    a circumference."""
    col = band_color(resonance)
    r = int(radius + 7 + 1.5 * math.sin(pulse_t * 3.0))
    cx, cy = int(center[0]), int(center[1])
    pygame.draw.circle(surface, col, (cx, cy), r, thickness)


def hp_bar(surface, center, width, frac, color=(215, 90, 80)):
    x = int(center[0] - width / 2)
    y = int(center[1])
    pygame.draw.rect(surface, (26, 22, 26), (x, y, width, 4))
    pygame.draw.rect(surface, color, (x, y, max(0, int(width * frac)), 4))


def draw_pulse(surface, pulse, camera):
    p = camera.world_to_screen(pulse.pos)
    if not (-40 <= p.x <= surface.get_width() + 40 and -40 <= p.y <= surface.get_height() + 40):
        return
    col = pulse.color
    strength = min(1.0, pulse.total * 8.0)
    r = int(2 + 4 * strength)
    trail = pulse.vel.normalize() * -(6 + 14 * strength) if pulse.vel.length_squared() > 1 else pygame.Vector2()
    pygame.draw.line(surface, _lerp((14, 16, 22), col, 0.45), p, p + trail, max(1, r - 1))
    pygame.draw.circle(surface, col, (int(p.x), int(p.y)), r)
    if pulse.hostile:
        pygame.draw.circle(surface, (255, 210, 210), (int(p.x), int(p.y)), r + 2, 1)


def draw_impact(surface, impact, camera, age):
    p = camera.world_to_screen(impact.pos)
    t = max(0.0, 1.0 - age / 0.35)
    if t <= 0:
        return
    # A resonant hit blooms; an off-band hit is a dull, small tick. The
    # difference has to be visible at a glance, because it is the game's
    # main teaching signal during combat.
    r = int((6 + 26 * impact.resonant) * (1.2 - t))
    col = _lerp((90, 96, 110), impact.color, impact.resonant)
    pygame.draw.circle(surface, col, (int(p.x), int(p.y)), max(1, r), max(1, int(1 + 2 * t)))

# ---------------------------------------------------------------------------
# The world, drawn


def _radial(radius, colour, power=1.7):
    """A soft radial sprite, built once and reused.

    The gradient has to be written into the *colour* channels as well as
    alpha, not just alpha. Both blends this sprite is used with — RGBA_SUB to
    punch a hole in the dark, RGB_ADD to bloom — read the colour channels and
    ignore alpha entirely, so a sprite that is uniformly white with only a
    soft alpha ramp subtracts and adds a hard white *square*. That is exactly
    what it did: every light in the game rendered as a rectangle.
    """
    d = max(2, int(radius * 2))
    xs = np.arange(d, dtype=np.float32)[:, None] - radius
    ys = np.arange(d, dtype=np.float32)[None, :] - radius
    grad = np.clip(1.0 - np.sqrt(xs * xs + ys * ys) / radius, 0.0, 1.0) ** power

    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    for i in range(3):
        rgb[:, :, i] = (grad * colour[i]).astype(np.uint8)
    del rgb
    alpha = pygame.surfarray.pixels_alpha(surf)
    alpha[:, :] = (grad * 255).astype(np.uint8)
    del alpha
    return surf


_LIGHT_CACHE = {}


def light_sprite(radius, colour):
    key = (int(radius), colour)
    sprite = _LIGHT_CACHE.get(key)
    if sprite is None:
        sprite = _radial(max(8, int(radius)), colour)
        _LIGHT_CACHE[key] = sprite
    return sprite


def draw_fields(surface, grid, camera, time=0.0):
    """Paint the three world fields as one additive layer.

    Built at grid resolution — about 48x33 — and scaled up, which is both
    fast and the right look: the fields are a continuum, and crisp cell edges
    would read as a tile map rather than as heat and wind.

    This is most of what the game looks like. Before it existed the arena was
    an empty grid with two circles on it, and no amount of enemy tuning was
    going to make that feel like anything.
    """
    h, w = grid.h, grid.w
    rgb = np.zeros((w, h, 3), dtype=np.float32)

    thermal = grid.thermal.T
    phase = grid.phase.T
    burning = grid.burning.T
    fuel = grid.fuel.T

    hot = np.clip(thermal, 0.0, 3.0) / 3.0
    cold = np.clip(-thermal, 0.0, 2.0) / 2.0

    # Heat: deep red at the edges of a fire, white-yellow at its heart.
    rgb[:, :, 0] += hot * 235.0
    rgb[:, :, 1] += (hot ** 2.1) * 165.0
    rgb[:, :, 2] += (hot ** 4.0) * 105.0

    if burning.any():
        flicker = 0.72 + 0.28 * math.sin(time * 17.0)
        b = burning.astype(np.float32) * flicker
        rgb[:, :, 0] += b * 90.0
        rgb[:, :, 1] += b * 70.0
        rgb[:, :, 2] += b * 24.0

    # Chill reads as a pale blue rime rather than as "negative fire".
    rgb[:, :, 0] += cold * 60.0
    rgb[:, :, 1] += cold * 130.0
    rgb[:, :, 2] += cold * 205.0

    ph = np.clip(phase, 0.0, 1.2) / 1.2
    shimmer = 0.65 + 0.35 * math.sin(time * 9.0)
    rgb[:, :, 0] += ph * 150.0 * shimmer
    rgb[:, :, 1] += ph * 90.0 * shimmer
    rgb[:, :, 2] += ph * 215.0 * shimmer

    # Ash: ground that has already burned stays dark for the rest of the
    # fight, so a room visibly remembers what you did to it.
    spent = np.clip(0.35 - fuel, 0.0, 0.35) / 0.35
    rgb[:, :, 0] += spent * 16.0
    rgb[:, :, 1] += spent * 13.0
    rgb[:, :, 2] += spent * 13.0

    # Two blur passes before the upscale. The grid is 34px cells blown up
    # ~34x, and bilinear interpolation over that ratio still reads as square
    # tiles — which makes fire look like a spreadsheet. Blurring at grid
    # resolution costs almost nothing and is what turns cells into flame.
    for _ in range(2):
        rgb = 0.5 * rgb + 0.5 * _blur3(rgb)

    np.clip(rgb, 0, 255, out=rgb)
    small = pygame.Surface((w, h))
    pygame.surfarray.blit_array(small, rgb.astype(np.uint8))

    from .fields import CELL

    tl = camera.world_to_screen(pygame.Vector2(0, 0))
    big = pygame.transform.smoothscale(small, (int(w * CELL), int(h * CELL)))
    surface.blit(big, (tl.x, tl.y), special_flags=pygame.BLEND_RGB_ADD)


def _blur3(a):
    """Cheap separable-ish 3x3 blur on a (w, h, 3) float array."""
    out = a.copy()
    out[1:, :] += a[:-1, :]
    out[:-1, :] += a[1:, :]
    out[:, 1:] += a[:, :-1]
    out[:, :-1] += a[:, 1:]
    return out / 5.0


def field_lights(grid, camera, viewport):
    """Where the world is glowing brightly enough to light the dark."""
    out = []
    from .fields import CELL

    rows, cols = np.nonzero(grid.burning)
    if len(rows) > 64:
        step = len(rows) // 64 + 1
        rows, cols = rows[::step], cols[::step]
    for r, c in zip(rows, cols):
        wpos = pygame.Vector2((c + 0.5) * CELL, (r + 0.5) * CELL)
        sp = camera.world_to_screen(wpos)
        if -140 <= sp.x <= viewport[0] + 140 and -140 <= sp.y <= viewport[1] + 140:
            out.append((sp, 130, (255, 150, 60)))
    return out


def draw_darkness(surface, lights, ambient=232):
    """Punch holes in the dark.

    The arena is unlit by default and everything you can see, you are seeing
    because something is radiating — your own ink, a mote in flight, a fire
    you started. It gives the game its identity in one stroke, and it makes
    casting a *tell*: light is energy, energy is you, and the things out
    there are looking.
    """
    w, h = surface.get_size()
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    shade.fill((6, 7, 11, ambient))
    for pos, radius, colour in lights:
        sprite = light_sprite(radius, colour)
        shade.blit(sprite, (pos[0] - radius, pos[1] - radius),
                   special_flags=pygame.BLEND_RGBA_SUB)
    surface.blit(shade, (0, 0))


def draw_glow(surface, pos, radius, colour, strength=1.0):
    """Additive bloom, for anything that should read as a light source."""
    if strength <= 0.01:
        return
    sprite = light_sprite(radius, colour)
    if strength < 0.999:
        sprite = sprite.copy()
        sprite.set_alpha(int(255 * max(0.0, min(1.0, strength))))
    surface.blit(sprite, (pos[0] - radius, pos[1] - radius),
                 special_flags=pygame.BLEND_RGB_ADD)


def draw_shockwave(surface, pos, radius, colour, t):
    """An expanding ring for a release. t runs 1 -> 0."""
    grow = radius * (1.25 - t)
    alpha = max(0.0, min(1.0, t * 2.2))
    width = max(1, int(2 + 7 * t))
    ring = pygame.Surface((int(grow * 2) + 8, int(grow * 2) + 8), pygame.SRCALPHA)
    c = (*colour, int(220 * alpha))
    pygame.draw.circle(ring, c, (ring.get_width() // 2, ring.get_height() // 2),
                       max(2, int(grow)), width)
    surface.blit(ring, (pos[0] - ring.get_width() // 2, pos[1] - ring.get_height() // 2),
                 special_flags=pygame.BLEND_RGB_ADD)
