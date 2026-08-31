"""The Field: the arena where drawn sigils get played under pressure.

The whole game rests on one structural decision made here, so it is worth
stating plainly: **you cannot draw in the Field.** Drawing is a slow,
deliberate, careful act and combat is none of those things; a game that asks
for both at once produces neither, and every attempt to freehand a circuit
while dodging turns a design tool into a QTE.

So the Field gives you instruments you already built and asks a completely
different question: *can you play them?* Tap or sustain, which of three, at
what range, in what order, and — because the sim genuinely rings — with what
timing. The physics that makes a sigil interesting to design is the same
physics that makes it interesting to operate, which is why this split does
not feel like two games stapled together.

Mana is the doc's own economy: injected energy. It is the reason spamming
taps is not the answer, and it is the reason efficiency — the fraction of
what you inject that actually radiates — is a stat worth optimising rather
than a number on a readout.
"""

import random

import pygame

from sigilwave.arena import Arena

from .combat import Impact, cancel_overlapping, emissions_to_pulses
from .enemies import Anchor, Choir, Cinder, Drone, Ward, make_choir_pair
from .fields import FieldGrid

PLAYER_RADIUS = 15.0
PLAYER_SPEED = 268.0
PLAYER_MAX_HP = 100.0
# Drawn canvas px -> world px. This was 0.46 and that was a mistake: at that
# scale a compact hot sigil renders about 40px across, which makes the single
# most information-dense object in the game a smudge next to the player. The
# sigil is not decoration on the avatar, it *is* the avatar - the waves
# running through it are how you read charge, band and saturation at a
# glance. It gets to be the biggest thing on screen.
FOCUS_WORLD_SCALE = 0.85

MANA_MAX = 100.0
MANA_REGEN = 16.0
MANA_TAP = 9.0
MANA_HOLD = 26.0              # per second

DASH_SPEED = 900.0
DASH_TIME = 0.16
DASH_COOLDOWN = 0.72
DASH_MANA = 12.0

# Tunnelling from a carried focus into a stamped relay. This is a *modelled*
# relay, not the sim's own evanescent coupler: the real coupler lives inside
# one compiled network, and merging two independently compiled networks every
# time a player walks past their own graffiti would be both expensive and
# fragile. The behaviour that matters is preserved — coupling strength falls
# off with the gap, and the long wavelengths cross better than the short ones
# (doc 2.7) — so the thing the player learns here stays true of the real
# couplers they build inside a single sigil.
RELAY_REACH = 340.0
RELAY_BAND_CROSSING = [1.0, 0.92, 0.72, 0.45, 0.2, 0.06]

# Touching an enemy hurts, but it is not the main threat — it is a nudge to
# keep moving. Set too high it dominates everything, and a game about
# choosing the right frequency turns into a game about not being touched.
CONTACT_DAMAGE = 14.0
CONTACT_COOLDOWN = 0.85

# --- world coupling -------------------------------------------------------
# How hard a charged sigil pushes on the world around it. Tuned so a hot
# sigil held for about a second sets the ground alight (the grid ignites at
# 0.55 and bleeds off at 0.55/sec, so the steady state is roughly
# rate/decay), while a cold one warms the floor and never lights it. The
# separation is the point: starting a fire has to be something you meant.
AURA_RADIUS = 118.0
# Ignition is deliberately steep in band, not linear.
#
# The coupling curve's thermal weights only span 0.03 to 1.0 across the
# spectrum, and charge varies just as much the other way — a fully charged
# cold ring ends up depositing about as much as a half-charged hot one, so
# every sigil in the game hovered near the ignition threshold and cold ones
# routinely tipped over it. The aura therefore squares the thermal term
# (see _apply_aura), turning a 9x spread into an 80x one: a band-1 sigil
# settles around 0.37 against a 0.55 threshold and simply cannot start a
# fire, while a band-3 one is comfortably over. Whether you set the room
# alight becomes a property of what you drew, which is the whole point.
AURA_THERMAL = 26.0
# Below this centroid band a sigil deposits no heat into the world at all.
#
# This is a hard rule rather than another coefficient, and it replaces three
# rounds of failed magnitude tuning. Ignition is a *threshold* process — one
# cell over the line lights, and a lit cell emits nine times what it took to
# light it, so it runs away — which means any scheme where a cold sigil sits
# near the threshold eventually tips over it and burns the room down. There
# is no safe magnitude, only a safe *category*. So: cold sigils make wind,
# hot sigils make fire, and nothing in between quietly sets the floor alight
# while the player is aiming at something else.
AURA_HEAT_BAND_FLOOR = 2.4
AURA_KINETIC = 600.0
AURA_PHASE = 22.0

# Motes leave their payload where they pass, so a hot beam lays a burning
# line and a kinetic one leaves a gust that shoves the next thing through it.
#
# Both numbers are far smaller than they look like they should be, and the
# threshold below is the important part. A stream of a hundred motes deposits
# a hundred times, so at anything generous *every* spell paves the floor with
# fire — measured, a band-1 shove sigil was setting 76 cells alight and
# killing its own caster in eleven seconds without an enemy ever touching
# them. Only genuinely hot output gets to start fires; a cold mote leaves
# nothing but wind.
PULSE_TRAIL_RADIUS = 26.0
PULSE_TRAIL_THERMAL = 1.1
PULSE_TRAIL_KINETIC = 130.0
PULSE_TRAIL_HEAT_FLOOR = 0.12
PULSE_TRAIL_BAND_FLOOR = 2.4
TRAIL_STRIDE = 4          # only 1 mote in 4 stamps per step
TRAIL_MIN_ENERGY = 0.02

# Release. Radius grows with the square root of stored energy, so a
# half-charged capacitor is meaningfully smaller than a full one.
DETONATE_RADIUS = 74.0
DETONATE_THERMAL = 6.0
DETONATE_KINETIC = 1700.0
DETONATE_PHASE = 16.0
DETONATE_DAMAGE = 34.0

# What the world does back to whoever is standing in it.
#
# Asymmetric, and deliberately so. Fire is area denial and chip: it corners
# things, finishes things, and makes ground expensive to hold. It is not a
# way to kill a tuned creature, because letting it be one re-opens the exact
# hole the whole resonance system exists to close — measured, a band-1 sigil
# was killing a band-4 Ward with 71 points of incidental burn against 49 of
# actual gated damage, so the "wrong tool" was doing most of the work.
#
# Against the player it stays lethal. The threat in this game is the room,
# and a room you set alight has to be a room you are afraid of.
# Standing in fire should cost you two or three seconds of grace, not kill
# you outright: at the grid's cap of ~3.9 thermal this is about 44 dps, so a
# player who walks into their own firestorm has time to walk back out and a
# player who lingers does not.
FIELD_BURN_ENEMY = 0.22
FIELD_BURN_DPS = 12.0
FIELD_WIND = 1.15
BARRIER_HIT_RADIUS = 22.0


class Relay:
    """A stamped sigil, standing in the world, waiting to be lit up.

    It has no ignition of its own. Standing near it lets your focus's output
    tunnel across the gap and come out here instead — which means placing
    relays is placing *emitters*, and a player who rings two of them from
    cover has built the thing the design doc calls success: a remote emitter
    with no visible connection to anything."""

    def __init__(self, sigil, pos):
        self.sigil = sigil
        self.pos = pygame.Vector2(pos)
        self.hp = 60.0
        self.lit = 0.0

    def coupling_to(self, other_pos) -> float:
        d = (self.pos - other_pos).length()
        if d >= RELAY_REACH:
            return 0.0
        t = d / RELAY_REACH
        return (1.0 - t * t) ** 2


class Player:
    def __init__(self, pos, foci):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(0, 0)
        self.radius = PLAYER_RADIUS
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.mana = MANA_MAX
        self.foci = foci
        self.active = 0
        self.aim = pygame.Vector2(1, 0)
        self.temperature = 0.0
        self.phase = 0.0
        self.hurt_flash = 0.0
        self.dash_t = 0.0
        self.dash_cd = 0.0
        self.dash_dir = pygame.Vector2(1, 0)
        self.hit_cd = 0.0
        self.holding = False

    @property
    def focus(self):
        return self.foci[self.active] if self.foci else None

    @property
    def aim_deg(self) -> float:
        return -self.aim.angle_to(pygame.Vector2(1, 0))

    def try_tap(self) -> bool:
        f = self.focus
        if f is None or f.is_empty or f.disabled or self.mana < MANA_TAP:
            return False
        self.mana -= MANA_TAP
        f.tap()
        return True

    def set_hold(self, on: bool) -> None:
        f = self.focus
        if f is None or f.is_empty or f.disabled:
            self.holding = False
            return
        if on and self.mana <= 0.5:
            on = False
        self.holding = on
        f.set_hold(on)

    def try_dash(self, direction) -> bool:
        if self.dash_cd > 0 or self.mana < DASH_MANA:
            return False
        d = pygame.Vector2(direction)
        if d.length_squared() < 1e-6:
            d = pygame.Vector2(self.aim)
        self.dash_dir = d.normalize()
        self.dash_t = DASH_TIME
        self.dash_cd = DASH_COOLDOWN
        self.mana -= DASH_MANA
        return True

    def switch(self, index: int) -> None:
        if 0 <= index < len(self.foci) and index != self.active:
            if self.focus is not None:
                self.focus.release()
            self.holding = False
            self.active = index

    def update(self, dt, move, arena):
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.hit_cd = max(0.0, self.hit_cd - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 2.5)
        self.temperature *= max(0.0, 1.0 - 0.6 * dt)
        self.phase = max(0.0, self.phase - 0.8 * dt)

        if self.dash_t > 0:
            self.dash_t -= dt
            self.pos += self.dash_dir * DASH_SPEED * dt
        else:
            speed = PLAYER_SPEED * (1.0 - 0.4 * min(1.0, max(0.0, -self.temperature)))
            if move.length_squared() > 1e-9:
                self.vel = move.normalize() * speed
            else:
                self.vel *= 0.75 ** (dt * 60)
            self.pos += self.vel * dt

        self.pos = arena.clamp(self.pos, self.radius)

        drain = MANA_HOLD * dt if self.holding else 0.0
        if drain > self.mana:
            self.set_hold(False)
            drain = self.mana
        self.mana = max(0.0, min(MANA_MAX, self.mana - drain + MANA_REGEN * dt))

        if self.temperature > 0.02:
            self.hp -= 5.0 * self.temperature * dt

    def take_pulse(self, pulse):
        # The player has no resonance of their own — being weak to one band
        # would make half the enemy roster unfair and the other half free —
        # so incoming damage is flat in the spectrum and scaled to leave a
        # full-health player room to make two or three mistakes.
        dmg = pulse.total * 0.22
        self.hp -= dmg
        self.vel += pulse.kinetic() * 0.35
        # Incoming heat is damped hard and clamped. Left at the enemy-facing
        # scale it was quietly the deadliest thing in the game: measured, a
        # couple of drone volleys were doing 74 burn damage against 26 of
        # direct hits, so players were dying to a status effect nothing on
        # screen was drawing attention to. Burn on the player is a nudge to
        # break line of sight, not a second health bar.
        self.temperature = max(-1.0, min(1.0, self.temperature + pulse.thermal() * 0.30))
        self.phase = min(1.0, self.phase + pulse.phase())
        self.hurt_flash = 1.0
        return dmg


class Field:
    """One room. Owns the arena, the entities, the loose energy, and the
    bookkeeping that turns "everything is dead" into "you may leave"."""

    def __init__(self, player, spec, seed=None):
        self.rng = random.Random(seed)
        self.arena = Arena(spec.get("width", 2000), spec.get("height", 1400), 64)
        import numpy as _np

        self.grid = FieldGrid(self.arena.width, self.arena.height,
                              _np.random.default_rng(seed or 0))
        self.detonations = []
        self.player = player
        self.player.pos = pygame.Vector2(self.arena.width / 2, self.arena.height - 220)
        self.spec = spec

        self.enemies = []
        self.friendly = []
        self.hostile = []
        self.relays = []
        self.impacts = []
        self.drops = []
        self.time = 0.0
        self.cleared = False
        self.failed = False
        self.banner = spec.get("banner", "")
        self.banner_t = 3.4
        self._spawn(spec)

    # -------------------------------------------------------------- spawning

    def _spawn(self, spec):
        for kind, count in spec.get("enemies", {}).items():
            for _ in range(count):
                pos = self._spawn_point()
                if kind == "cinder":
                    self.enemies.append(Cinder(pos))
                elif kind == "ward":
                    self.enemies.append(Ward(pos))
                elif kind == "drone":
                    self.enemies.append(Drone(pos))
                elif kind == "anchor":
                    self.enemies.append(Anchor(pos))
                elif kind == "choir":
                    self.enemies.extend(make_choir_pair(pos))

    def _spawn_point(self):
        margin = 200
        return pygame.Vector2(
            self.rng.uniform(margin, self.arena.width - margin),
            self.rng.uniform(margin, self.arena.height * 0.55),
        )

    # ---------------------------------------------------------------- actions

    def stamp_relay(self, pos) -> bool:
        focus = self.player.focus
        if focus is None or focus.is_empty or len(self.relays) >= 3:
            return False
        clone = focus.clone()
        clone.ignition_node = None      # a relay has no spark of its own
        self.relays.append(Relay(clone, pos))
        return True

    # ----------------------------------------------------------------- update

    def update(self, dt, move):
        self.time += dt
        self.banner_t = max(0.0, self.banner_t - dt)
        p = self.player
        p.update(dt, move, self.arena)

        focus = p.focus
        if focus is not None and not focus.is_empty:
            emissions = focus.advance(dt)
            if emissions:
                self.friendly.extend(
                    emissions_to_pulses(emissions, p.pos, p.aim_deg, FOCUS_WORLD_SCALE)
                )
                self._drive_relays(emissions)
            self._apply_aura(focus, p.pos, dt)

        for relay in self.relays:
            relay.lit = max(0.0, relay.lit - dt * 2.0)
            ems = relay.sigil.advance(dt)
            if ems:
                self.friendly.extend(
                    emissions_to_pulses(ems, relay.pos, p.aim_deg, FOCUS_WORLD_SCALE)
                )

        for e in self.enemies:
            e.update(dt, self.arena, p, self.hostile)
            shock = e.take_shock()
            if shock is not None:
                # A surge is not just a buff on a stat sheet: it shoves the
                # room. You feel the mistake before you read the meter.
                spos, sradius = shock
                for ang in range(0, 360, 30):
                    d = pygame.Vector2(1, 0).rotate(ang)
                    self.grid.add_kinetic(spos + d * sradius * 0.5, sradius * 0.6,
                                          d * 900.0)
                # No heat. A surge is a mechanical shove, and giving it a
                # thermal component made every surge an ignition source —
                # which is how a room full of correctly-matched Cinders was
                # setting itself on fire and killing the player who was
                # beating it. Fire in this game comes from what the player
                # drew, never from a side effect of an enemy reaction.
                self.detonations.append(
                    (pygame.Vector2(spos), sradius, (255, 190, 110), 0.34))
                off = p.pos - spos
                if 1e-6 < off.length_squared() < sradius * sradius:
                    p.vel += off.normalize() * 420.0
                    p.hp -= 8.0
                    p.hurt_flash = 1.0

        self._update_pulses(dt)
        self._deflect_at_barrier()
        self._collide()
        self._choir_beats(dt)
        self.grid.update(dt)
        self._apply_world_to(p, dt, is_player=True)
        for e in self.enemies:
            self._apply_world_to(e, dt)
        self.detonations = [(q, r, c, t - dt) for q, r, c, t in self.detonations if t > dt]
        self._cull()

    # ------------------------------------------------------------ the world

    def _apply_aura(self, sigil, pos, dt):
        """A charged sigil pushes on its surroundings whether or not it has
        anywhere to radiate. This is the channel that makes a spell something
        other than a bullet."""
        k, t, ph, band = sigil.field_payload()
        if abs(k) < 1e-4 and abs(t) < 1e-4 and ph < 1e-4:
            return
        if band < AURA_HEAT_BAND_FLOOR:
            t = 0.0
        if abs(t) > 1e-4:
            # Signed square: keeps the chill/burn sign, steepens the band
            # dependence. See the note on AURA_THERMAL. Deposited as a ring,
            # so the caster stands in the quiet middle of their own field.
            self.grid.add_thermal_ring(pos, AURA_RADIUS, t * abs(t) * AURA_THERMAL * dt)
        if ph > 1e-4:
            self.grid.add_phase_ring(pos, AURA_RADIUS, ph * AURA_PHASE * dt)
        if abs(k) > 1e-4:
            # Chirality decides whether the near field blows outward or drags
            # inward. A counter-clockwise ring is a vacuum; nobody wrote that.
            for ang in range(0, 360, 45):
                d = pygame.Vector2(1, 0).rotate(ang)
                self.grid.add_kinetic(pos + d * AURA_RADIUS * 0.55, AURA_RADIUS * 0.5,
                                      d * k * AURA_KINETIC * dt)

    def _apply_world_to(self, ent, dt, is_player=False):
        """Everything reads the same fields, including you.

        This is where the threat comes from. A room you set alight is a room
        you now have to cross, and a gale you raised shoves you as readily as
        it shoves them. Exempting the player would turn the entire field
        layer back into a damage stat with extra steps."""
        pos = ent.pos
        heat = self.grid.sample_thermal(pos)
        wind = self.grid.sample_kinetic(pos)
        ph = self.grid.sample_phase(pos)

        if heat > 0.25:
            dmg = FIELD_BURN_DPS * (heat - 0.25) * dt
            ent.hp -= dmg * (1.0 if is_player else FIELD_BURN_ENEMY)
            if is_player:
                ent.hurt_flash = max(ent.hurt_flash, min(1.0, heat * 0.5))
        elif heat < -0.25:
            ent.temperature = min(ent.temperature, heat * 0.5)

        if wind.length_squared() > 1.0:
            ent.vel += wind * FIELD_WIND * dt

        if ph > 0.05:
            ent.phase = min(1.0, ent.phase + ph * dt * 1.4)

        if not is_player and ent.hp <= 0:
            ent.dead = True

    def detonate(self, sigil, pos):
        """Release everything the ink is holding, in one frame.

        What the release does is read off the spectrum rather than chosen
        from a list: low bands blast, high bands ignite, the top band thins
        matter, and a counter-clockwise winding turns the whole thing inside
        out so it implodes and freezes instead."""
        from .bands import band_color, vulnerability_curve

        energy, k, t, ph, band = sigil.detonation_payload()
        if energy < 0.05:
            return False
        scale = min(3.0, energy ** 0.5)
        radius = DETONATE_RADIUS * scale

        self.grid.add_thermal(pos, radius, t * DETONATE_THERMAL * scale)
        self.grid.add_phase(pos, radius, ph * DETONATE_PHASE * scale)
        for ang in range(0, 360, 30):
            d = pygame.Vector2(1, 0).rotate(ang)
            self.grid.add_kinetic(pos + d * radius * 0.5, radius * 0.6,
                                  d * k * DETONATE_KINETIC * scale)

        curve = vulnerability_curve(band)
        for e in self.enemies:
            off = e.pos - pos
            d = off.length()
            if d > radius:
                continue
            fall = 1.0 - d / radius
            # Resonance still rules: a release carries its own spectrum, so
            # it shatters what it is tuned to and merely shoves the rest.
            match = sum(c * w for c, w in zip(curve, e.vuln))
            e.hp -= DETONATE_DAMAGE * scale * fall * match
            e.hit_flash = 1.0
            if off.length_squared() > 1e-6:
                e.vel += off.normalize() * k * 900.0 * fall * scale
            if e.hp <= 0:
                e.dead = True

        self.detonations.append((pygame.Vector2(pos), radius, band_color(band), 0.42))
        sigil.quench()
        return True

    def _deflect_at_barrier(self):
        """The shape you drew is a physical object that incoming energy can
        hit.

        A dense arc across the front of a sigil turns shots away because that
        is what an impedance mismatch does to a wave (doc 2.2). There is no
        shield item, no block button and no shield stat. There is ink, and
        ink has an impedance."""
        from . import viz

        p = self.player
        focus = p.focus
        if focus is None or focus.is_empty or not self.hostile:
            return
        strength = focus.barrier_strength
        if strength < 0.08:
            return
        pts = focus.barrier_points()
        if not pts:
            return

        scale = viz.display_scale(focus)
        rot = p.aim_deg
        world = [p.pos + (pygame.Vector2(q) * scale).rotate(rot) for q in pts]
        r2 = BARRIER_HIT_RADIUS * BARRIER_HIT_RADIUS

        for q in self.hostile:
            if q.spent:
                continue
            if (q.pos - p.pos).length_squared() > 62500:
                continue
            for w in world:
                if (q.pos - w).length_squared() < r2:
                    q.vel = -q.vel * 0.7
                    q.hostile = False
                    for i in range(len(q.bands)):
                        q.bands[i] *= strength
                    q.kinetic_sign *= -1.0
                    q._refresh()
                    if q.total < 1e-7:
                        q.spent = True
                    self.impacts.append(
                        Impact(q.pos, (200, 226, 255), q.total, strength, "parry")
                    )
                    break

    def _drive_relays(self, emissions):
        """Tunnel a copy of the focus's output into any relay in reach.

        Copied rather than moved: the coupling is weak and per-band, so what
        arrives is a filtered shadow of what left, and the long bands cross
        far better than the short ones. Trying to run heat through a relay
        barely works, which is the same lesson the ink teaches."""
        p = self.player
        for relay in self.relays:
            k = relay.coupling_to(p.pos)
            if k <= 1e-3:
                continue
            relay.lit = min(1.0, relay.lit + k * 0.4)
            for em in emissions:
                bands = [b * k * c for b, c in zip(em.bands, RELAY_BAND_CROSSING)]
                if sum(bands) < 1e-8:
                    continue
                self.friendly.extend(
                    emissions_to_pulses(
                        [_Reemit(em, bands)], relay.pos, p.aim_deg, FOCUS_WORLD_SCALE
                    )
                )

    def _update_pulses(self, dt):
        self._trail_phase = (self._trail_phase + 1) % TRAIL_STRIDE
        phase = self._trail_phase
        for i, q in enumerate(self.friendly):
            q.update(dt)
            if i % TRAIL_STRIDE == phase:
                self._pulse_trail(q, dt)
        for q in self.hostile:
            q.update(dt)

        for pos, amount, opposed in cancel_overlapping(self.friendly, self.hostile):
            self.impacts.append(
                Impact(pos, (220, 235, 255) if opposed else (255, 170, 90), amount, 1.0, "parry")
            )

    _trail_phase = 0

    def _pulse_trail(self, q, dt):
        """A mote leaves its payload where it passed. A hot beam lays a
        burning line down the floor that keeps working after you have moved
        on; a cold one freezes a firebreak."""
        if q.total < TRAIL_MIN_ENERGY:
            return
        t = q.thermal() if q.center >= PULSE_TRAIL_BAND_FLOOR else 0.0
        if abs(t) > PULSE_TRAIL_HEAT_FLOOR:
            # Subtract the floor so a mote just over the line lays a trace
            # rather than a bonfire — no cliff at the threshold.
            over = t - PULSE_TRAIL_HEAT_FLOOR if t > 0 else t + PULSE_TRAIL_HEAT_FLOOR
            self.grid.add_thermal(q.pos, PULSE_TRAIL_RADIUS, over * PULSE_TRAIL_THERMAL * dt)
        # Kinetic trails are stamped on a rotating subset of motes rather
        # than all of them every step. Profiled, this single call was 65% of
        # the entire simulation cost — 38 deposits per step, two array writes
        # each — and the wind it lays is a slow, wide field that no player can
        # tell apart at a quarter of the sample rate.
        k = q.kinetic()
        if k.length_squared() > 1e-6:
            self.grid.add_kinetic(q.pos, PULSE_TRAIL_RADIUS,
                                  k.normalize() * PULSE_TRAIL_KINETIC * dt
                                  * TRAIL_STRIDE * min(1.0, q.total * 4))

    def _collide(self):
        p = self.player

        for q in self.friendly:
            if q.spent:
                continue
            for e in self.enemies:
                if e.dead:
                    continue
                if (q.pos - e.pos).length_squared() < (e.radius + q.radius) ** 2:
                    quality = e.take_pulse(q, self.hostile)
                    self.impacts.append(Impact(e.pos, q.color, q.total, quality))
                    q.spent = True
                    break

        for q in self.hostile:
            if q.spent:
                continue
            if (q.pos - p.pos).length_squared() < (p.radius + q.radius) ** 2:
                if p.phase <= 0.5:
                    p.take_pulse(q)
                    self.impacts.append(Impact(p.pos, q.color, q.total, 0.0, "player"))
                q.spent = True
            for relay in self.relays:
                if (q.pos - relay.pos).length_squared() < 26 ** 2:
                    relay.hp -= q.total * 30.0
                    q.spent = True
                    break

        if p.hit_cd <= 0:
            for e in self.enemies:
                if e.dead:
                    continue
                if (e.pos - p.pos).length_squared() < (e.radius + p.radius) ** 2:
                    p.hp -= CONTACT_DAMAGE
                    p.hurt_flash = 1.0
                    p.hit_cd = CONTACT_COOLDOWN
                    knock = p.pos - e.pos
                    if knock.length_squared() > 1e-6:
                        p.vel += knock.normalize() * 340.0
                    break

    def _choir_beats(self, dt):
        """A bonded Choir's beat envelope is a real |f1-f2| swing, and where
        it constructively interferes it hurts. The damage band is drawn as a
        standing wave between the pair, so the player can see the node they
        are safe in and the antinode they are not."""
        p = self.player
        for e in self.enemies:
            if not isinstance(e, Choir) or e.dead or e.partner is None or e.partner.dead:
                continue
            if id(e) > id(e.partner):
                continue
            a, b = e.pos, e.partner.pos
            seg = b - a
            L2 = seg.length_squared()
            if L2 < 1e-6:
                continue
            t = max(0.0, min(1.0, (p.pos - a).dot(seg) / L2))
            closest = a + seg * t
            dist = (p.pos - closest).length()
            if dist < 96.0:
                env = e.beat_envelope()
                if env > 0.55:
                    p.hp -= 26.0 * env * dt
                    p.hurt_flash = max(p.hurt_flash, 0.5)

    def _cull(self):
        for e in self.enemies:
            if e.dead:
                d = e.drop()
                if d is not None:
                    self.drops.append(d)
        self.enemies = [e for e in self.enemies if not e.dead]
        self.friendly = [q for q in self.friendly if not q.spent]
        self.hostile = [q for q in self.hostile if not q.spent]
        self.relays = [r for r in self.relays if r.hp > 0]
        self.impacts = [i for i in self.impacts if i.amount > 0]

        # Hard caps. A pathological sigil can emit faster than anything can
        # consume, and the frame budget is not negotiable.
        if len(self.friendly) > 900:
            self.friendly = self.friendly[-900:]
        if len(self.hostile) > 600:
            self.hostile = self.hostile[-600:]
        if len(self.impacts) > 120:
            self.impacts = self.impacts[-120:]

        if not self.enemies and not self.cleared:
            self.cleared = True
        if self.player.hp <= 0:
            self.failed = True

    # ------------------------------------------------------------------ intel

    def scan_target(self):
        """The nearest enemy to the crosshair, for the readout panel. Always
        on — a scan *button* would just be a tax on already knowing."""
        p = self.player
        best, best_d = None, 1e9
        ray = p.pos + p.aim * 300
        for e in self.enemies:
            d = (e.pos - ray).length()
            if d < best_d:
                best, best_d = e, d
        return best if best_d < 420 else None


class _Reemit:
    """Adapter so a relay can re-emit a filtered copy of an emission without
    the pulse builder needing to know relays exist."""

    __slots__ = ("local_pos", "local_heading", "bands", "kinetic_sign", "thermal_sign", "energy")

    def __init__(self, em, bands):
        self.local_pos = em.local_pos
        self.local_heading = em.local_heading
        self.bands = bands
        self.kinetic_sign = em.kinetic_sign
        self.thermal_sign = em.thermal_sign
        self.energy = sum(bands)
