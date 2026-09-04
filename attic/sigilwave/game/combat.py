"""Pulses: radiated energy, loose in the world.

A Pulse is the doc's own idea — a projectile carrying (amplitude, frequency,
phase) so that interference works on incoming attacks too — with the
amplitude/frequency pair replaced by the analyser's band vector, because
that is what the rest of the game already speaks.

Three things fall out of carrying a whole spectrum instead of a damage
number, and all three are load-bearing:

* **Resonance targeting.** Damage is the overlap between what you delivered
  and what the target rings at. Hitting a thing with the wrong band is not
  reduced damage, it is almost no damage, and the fix is to change what you
  drew rather than to hit it more.

* **Range is per-band, in flight as well as in ink.** The hot bands die in
  the air the same way they die in a stroke (doc 2.5). Nobody codes "the
  fire spell is short range" — fire *is* the short-range end of the
  spectrum, in the ink and in the world, for the same reason.

* **Parry is arithmetic.** Two pulses of opposite chirality that overlap
  cancel where their spectra agree. Antiphase cancellation stops being a
  physics curiosity and becomes a defensive verb.
"""

import pygame

from .bands import N_BANDS, band_color, dominant_band, spectrum_match, weighted_match
from sigilwave.sim.coupling import (
    kinetic_drive_from_bands,
    phase_drive_from_bands,
    thermal_drive_from_bands,
)

PULSE_SPEED = 620.0
PULSE_LIFETIME = 3.2
PULSE_RADIUS = 7.0
CANCEL_RADIUS = 26.0

# Per-second survival multiplier per band, travelling through open air.
#
# This list *is* the range/element tradeoff, and the spread between its ends
# has to be violent or the tradeoff is decorative. At PULSE_SPEED a deep mote
# still carries 92% of itself after 620px while a keen one is down to 6% over
# the same distance and has done most of its work inside ~150px. Measured
# against a Ward: a held heat sigil delivers 3.7 Wards of damage at contact,
# 2.3 at mid range, and a fifth of one across a room. Walk in or waste it.
#
# It mirrors the frequency-dependent damping inside the ink (doc 2.5), which
# is the point: heat is short-ranged in a stroke and short-ranged in the air
# for the same reason, so the rule the player learns in the Forge is the same
# rule that governs where they have to stand.
AIR_SURVIVAL = [0.92, 0.84, 0.66, 0.35, 0.06, 0.012]

# One master knob converting analyser band-energy into hit points.
# Calibrated against a full discharge of the starter sigils: one tap of
# Shove should take roughly half a Cinder, and one tap of Spark roughly a
# quarter of a Ward at contact range. Everything downstream of these four
# numbers is physics; these four are the exchange rate.
DAMAGE_SCALE = 1.25
KINETIC_IMPULSE = 900.0
THERMAL_SCALE = 0.35
PHASE_SCALE = 1.2


class Pulse:
    __slots__ = (
        "pos", "vel", "bands", "kinetic_sign", "thermal_sign",
        "age", "hostile", "spent", "center", "total", "radius",
    )

    def __init__(self, pos, vel, bands, kinetic_sign=1.0, thermal_sign=1.0, hostile=False):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.bands = list(bands)
        self.kinetic_sign = kinetic_sign
        self.thermal_sign = thermal_sign
        self.hostile = hostile
        self.age = 0.0
        self.spent = False
        self.radius = PULSE_RADIUS
        self._refresh()

    def _refresh(self) -> None:
        self.center, self.total = dominant_band(self.bands)

    @property
    def color(self) -> tuple:
        return band_color(self.center)

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.age += dt
        for i in range(N_BANDS):
            if self.bands[i] > 0.0:
                self.bands[i] *= AIR_SURVIVAL[i] ** dt
        self._refresh()
        if self.age > PULSE_LIFETIME or self.total < 1e-7:
            self.spent = True

    # -------------------------------------------------------------- effects

    def damage_against(self, vuln_curve: list) -> float:
        return weighted_match(self.bands, vuln_curve) * DAMAGE_SCALE

    def kinetic(self) -> pygame.Vector2:
        mag = abs(kinetic_drive_from_bands(self.bands, None)) * KINETIC_IMPULSE
        direction = self.vel.normalize() if self.vel.length_squared() > 1e-9 else pygame.Vector2(1, 0)
        return direction * mag * self.kinetic_sign

    def thermal(self) -> float:
        return thermal_drive_from_bands(self.bands, None) * THERMAL_SCALE * self.thermal_sign

    def phase(self) -> float:
        return phase_drive_from_bands(self.bands) * PHASE_SCALE


def cancel_overlapping(friendly: list, hostile: list) -> list:
    """Antiphase cancellation (doc 3, "parry").

    Only friendly-against-hostile is checked. Same-team pulses interfering
    with each other would be physically consistent but reads as your own
    shots eating each other, which is noise rather than depth.

    Cancellation is per band and proportional: two pulses annihilate exactly
    as much of each other as their spectra actually overlap, so parrying a
    hot attack with a cold one does nothing, and the player who matched the
    band gets the clean block. Opposite chirality cancels; matching
    chirality reinforces, which is why a badly-signed sigil makes an
    incoming attack *worse*.
    """
    events = []
    if not friendly or not hostile:
        return events

    r2 = CANCEL_RADIUS * CANCEL_RADIUS
    for f in friendly:
        if f.spent:
            continue
        for h in hostile:
            if h.spent:
                continue
            if (f.pos - h.pos).length_squared() > r2:
                continue

            opposed = f.kinetic_sign * h.kinetic_sign < 0
            removed = 0.0
            for i in range(N_BANDS):
                fb, hb = f.bands[i], h.bands[i]
                if fb <= 0.0 or hb <= 0.0:
                    continue
                if opposed:
                    overlap = min(fb, hb)
                    f.bands[i] = fb - overlap
                    h.bands[i] = hb - overlap
                    removed += overlap * 2.0
                else:
                    # In phase: they add. The energy has to come from
                    # somewhere, so it comes off the friendly mote — you
                    # just fed the attack that was aimed at you.
                    transfer = min(fb, hb) * 0.5
                    f.bands[i] = fb - transfer
                    h.bands[i] = hb + transfer

            f._refresh()
            h._refresh()
            if f.total < 1e-7:
                f.spent = True
            if h.total < 1e-7:
                h.spent = True
            if removed > 1e-6:
                events.append((pygame.Vector2((f.pos + h.pos) * 0.5), removed, opposed))
    return events


def emissions_to_pulses(emissions, origin, rotation_deg, scale, hostile=False, speed=PULSE_SPEED):
    """Place a sigil's local-space emissions into the world.

    The sigil is drawn in its own frame and then rotated to wherever the
    caster is aiming, which means the drawing *is* the firing pattern: a
    terminal pointing backwards fires backwards, and a sigil with four ends
    at the compass points sprays in four directions. Nobody authored a
    spread shot; somebody drew one.
    """
    out = []
    for em in emissions:
        local = pygame.Vector2(em.local_pos) * scale
        world_pos = pygame.Vector2(origin) + local.rotate(rotation_deg)
        heading = pygame.Vector2(em.local_heading).rotate(rotation_deg)
        if heading.length_squared() < 1e-9:
            heading = pygame.Vector2(1, 0).rotate(rotation_deg)
        out.append(
            Pulse(
                world_pos,
                heading.normalize() * speed,
                em.bands,
                em.kinetic_sign,
                em.thermal_sign,
                hostile,
            )
        )
    return out


class Impact:
    """A hit, kept as data so the renderer and the audio-free feedback layer
    can both read it without the combat code knowing they exist."""

    __slots__ = ("pos", "color", "amount", "resonant", "kind")

    def __init__(self, pos, color, amount, resonant, kind="hit"):
        self.pos = pygame.Vector2(pos)
        self.color = color
        self.amount = amount
        self.resonant = resonant   # 0..1, how well the band matched
        self.kind = kind


def resonance_quality(bands: list, vuln_curve: list) -> float:
    """Fraction of delivered energy that landed where the target is weak.

    This is the number the hit-feedback is keyed to, and it is the single
    most important teaching signal in the game: a dull thud means the right
    idea in the wrong band, a bright shatter means the player found it.
    """
    total = sum(bands)
    if total <= 1e-12:
        return 0.0
    return min(1.0, spectrum_match(bands, vuln_curve) / total)
