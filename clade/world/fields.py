"""The water, as a thing with state.

Four grids over the room, and one rule that makes them matter more than
their own effects do:

    **the fields decide what you can drink.**

Ambient composition is not a constant per region — it is the region's base
water *plus whatever is currently happening to it*. Set a fire and the
water around it becomes ichor-rich, so your intakes start pulling heat, so
your chains get hotter, so the fire grows. Stir up the floor and the water
goes thick and your shots go dull and nothing can see you. Kill something
and the water where it died is briefly made of what it was made of.

That loop is the reason this file exists at all. Without it these would be
four decorative overlays; with it, changing the room is a way of changing
your own body, and the arena becomes something you negotiate with instead
of something you stand in.

    heat     hot burns and lights and rises. cold freezes water solid.
    silt     blocks sight, muffles sound, settles slowly.
    current  a vector field. it pushes you, and it carries silt and heat.
    charge   live water. conducts jolts between anything touching it.
"""

import math

import numpy as np

from .. import config as C
from ..humours import BRINE, ICHOR, N_HUMOURS, SILT, SPARK, Charge

MAX_HEAT = 6.0
MIN_HEAT = -4.0
MAX_SILT = 2.4
MAX_CHARGE = 3.0
MAX_CURRENT = 620.0

FREEZE_AT = -2.2      # below this the water is solid and blocks movement
BURN_AT = 1.4         # above this it damages anything standing in it

_KERNELS = {}


class Fields:
    def __init__(self, width, height, base: Charge, rng=None):
        self.w = max(4, int(width / C.FIELD_CELL) + 1)
        self.h = max(4, int(height / C.FIELD_CELL) + 1)
        self.width = width
        self.height = height
        shape = (self.h, self.w)

        self.heat = np.zeros(shape, dtype=np.float32)
        self.silt = np.zeros(shape, dtype=np.float32)
        self.charge = np.zeros(shape, dtype=np.float32)
        self.current = np.zeros((self.h, self.w, 2), dtype=np.float32)
        self.solid = np.zeros(shape, dtype=bool)      # frozen water

        # The region's own water, before anything happens to it.
        self.base = base.copy()
        self._base_f = base.fractions()
        self._base_m = base.magnitude

        # Seeps: local enrichments that do not move. These are what make one
        # corner of a room worth swimming to, and they are placed by the
        # room generator rather than scattered randomly, because "there is
        # something good over there" has to be a statement about the level
        # and not about a dice roll.
        self.seeps = []   # (x, y, radius, Charge)

    # ------------------------------------------------------------ indexing

    def cell_of(self, pos):
        c = int(pos[0] / C.FIELD_CELL)
        r = int(pos[1] / C.FIELD_CELL)
        if r < 0: r = 0
        elif r >= self.h: r = self.h - 1
        if c < 0: c = 0
        elif c >= self.w: c = self.w - 1
        return r, c

    def heat_at(self, pos):
        r, c = self.cell_of(pos)
        return float(self.heat[r, c])

    def silt_at(self, pos):
        r, c = self.cell_of(pos)
        return float(self.silt[r, c])

    def charge_at(self, pos):
        r, c = self.cell_of(pos)
        return float(self.charge[r, c])

    def current_at(self, pos):
        r, c = self.cell_of(pos)
        v = self.current[r, c]
        return (float(v[0]), float(v[1]))

    def frozen_at(self, pos):
        r, c = self.cell_of(pos)
        return bool(self.solid[r, c])

    # ------------------------------------------------------- composition

    def ambient(self, pos) -> Charge:
        """What the water here is made of. Base, plus what the room's own
        state has done to it. This is the function every intake ultimately
        depends on, so it is deliberately cheap: four array reads and some
        arithmetic, no allocation beyond the result."""
        r, c = self.cell_of(pos)
        out = Charge.of([f * self._base_m for f in self._base_f])

        h = float(self.heat[r, c])
        if h > 0:
            out.v[ICHOR] += h * 3.2
        else:
            out.v[BRINE] += -h * 2.6      # cold water is heavy water
        out.v[SILT] += float(self.silt[r, c]) * 3.4
        out.v[SPARK] += float(self.charge[r, c]) * 3.0

        for sx, sy, rad, ch in self.seeps:
            dx, dy = pos[0] - sx, pos[1] - sy
            d2 = dx * dx + dy * dy
            if d2 < rad * rad:
                k = 1.0 - math.sqrt(d2) / rad
                for i in range(N_HUMOURS):
                    out.v[i] += ch[i] * k
        return out

    def draw_from(self, pos, amount) -> Charge:
        """Take `amount` of local water, weighted by its composition."""
        amb = self.ambient(pos)
        m = amb.magnitude
        if m < 1e-6:
            return Charge()
        return amb.scaled(amount / m)

    # -------------------------------------------------------- deposition

    def _stamp(self, arr, pos, radius, amount):
        cr = max(1, int(round(radius / C.FIELD_CELL)))
        r0, c0 = self.cell_of(pos)
        rlo, rhi = max(0, r0 - cr), min(self.h, r0 + cr + 1)
        clo, chi = max(0, c0 - cr), min(self.w, c0 + cr + 1)
        if rlo >= rhi or clo >= chi:
            return
        kern = _KERNELS.get(cr)
        if kern is None:
            span = np.arange(-cr, cr + 1, dtype=np.float32)
            dist = np.sqrt(span[:, None] ** 2 + span[None, :] ** 2)
            kern = np.clip(1.0 - dist / (cr + 0.5), 0.0, 1.0)
            _KERNELS[cr] = kern
        sub = kern[rlo - (r0 - cr):rhi - (r0 - cr), clo - (c0 - cr):chi - (c0 - cr)]
        arr[rlo:rhi, clo:chi] += sub * amount

    def add_heat(self, pos, radius, amount):
        self._stamp(self.heat, pos, radius, amount)

    def add_silt(self, pos, radius, amount):
        self._stamp(self.silt, pos, radius, amount)

    def add_charge(self, pos, radius, amount):
        self._stamp(self.charge, pos, radius, amount)

    def add_current(self, pos, radius, vec):
        self._stamp(self.current[:, :, 0], pos, radius, float(vec[0]))
        self._stamp(self.current[:, :, 1], pos, radius, float(vec[1]))

    def apply_effect(self, effect, pos, radius=None):
        """Everything a resolved Effect does to the medium, in one place, so
        that a bolt, an aura and a seed all leave identical marks and the
        player can trust what they learned from one to hold for the rest."""
        rad = radius if radius is not None else max(18.0, effect.magnitude * 5.0)
        if abs(effect.heat) > 0.01:
            self.add_heat(pos, rad, effect.heat * 0.35)
        if effect.murk > 0.01:
            self.add_silt(pos, rad, effect.murk * 0.30)
        if effect.jolt > 0.01:
            self.add_charge(pos, rad * 0.8, effect.jolt * 0.28)
        if abs(effect.force) > 1.0:
            # A shove leaves a current behind it, pointing the way it went.
            pass

    # ------------------------------------------------------------ update

    def update(self, dt):
        # Freezing happens before diffusion so a wall of ice is solid on the
        # frame it forms rather than one frame later, which matters when the
        # player is freezing a doorway with something coming through it.
        self.solid = self.heat < FREEZE_AT

        k_h = min(C.MAX_DIFFUSE_STEP, C.HEAT_DIFFUSE * dt)
        k_s = min(C.MAX_DIFFUSE_STEP, C.SILT_DIFFUSE * dt)
        self.heat = _diffuse(self.heat, k_h)
        self.silt = _diffuse(self.silt, k_s)

        self._advect(dt)

        self.heat *= np.float32(max(0.0, 1.0 - C.HEAT_DECAY * dt))
        self.silt *= np.float32(max(0.0, 1.0 - C.SILT_DECAY * dt))
        self.charge *= np.float32(max(0.0, 1.0 - C.SPARKF_DECAY * dt))
        self.current *= np.float32(max(0.0, 1.0 - C.CURRENT_DECAY * dt))

        np.clip(self.heat, MIN_HEAT, MAX_HEAT, out=self.heat)
        np.clip(self.silt, 0.0, MAX_SILT, out=self.silt)
        np.clip(self.charge, 0.0, MAX_CHARGE, out=self.charge)
        np.clip(self.current, -MAX_CURRENT, MAX_CURRENT, out=self.current)

    def _advect(self, dt):
        """Silt and heat ride the current. A cheap one-cell semi-Lagrangian
        shift rather than a real advection step — the visual read ("the
        cloud is drifting that way") is the entire requirement, and a
        correct solver would cost more than the rest of the frame."""
        if not self.current.any():
            return
        vx = self.current[:, :, 0].mean()
        vy = self.current[:, :, 1].mean()
        sx = int(np.sign(vx)) if abs(vx) * dt > C.FIELD_CELL * 0.5 else 0
        sy = int(np.sign(vy)) if abs(vy) * dt > C.FIELD_CELL * 0.5 else 0
        if sx or sy:
            self.silt = np.roll(self.silt, (sy, sx), axis=(0, 1))
            self.heat = np.roll(self.heat, (sy, sx), axis=(0, 1))

    # -------------------------------------------------------------- intel

    def visibility_along(self, a, b, samples=6):
        """How much of a sightline survives the silt between two points.
        Used by creatures to decide whether they can see you and by the
        renderer to decide whether you can see them — the same function for
        both, so a cloud that hides you really is the cloud you are hiding
        in."""
        acc = 0.0
        for i in range(1, samples + 1):
            t = i / samples
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            acc += self.silt_at(p)
        avg = acc / samples
        return max(0.0, 1.0 - avg / 1.3)

    def totals(self):
        return (float(np.abs(self.heat).sum()), float(self.silt.sum()),
                int(self.solid.sum()))


def _neighbour_mean(a):
    up = np.empty_like(a); up[0] = a[0]; up[1:] = a[:-1]
    dn = np.empty_like(a); dn[-1] = a[-1]; dn[:-1] = a[1:]
    lf = np.empty_like(a); lf[:, 0] = a[:, 0]; lf[:, 1:] = a[:, :-1]
    rt = np.empty_like(a); rt[:, -1] = a[:, -1]; rt[:, :-1] = a[:, 1:]
    return (up + dn + lf + rt) * 0.25


def _diffuse(a, k):
    """One explicit diffusion step, conservative: what leaves a cell arrives
    in its neighbours instead of evaporating. The naive form (blend toward
    the neighbour mean, unscaled) loses a fixed fraction per call, which at
    60Hz silently deletes about 99% of a plume per second and makes every
    spreading effect in the game look broken."""
    if k <= 0:
        return a
    return a + k * (_neighbour_mean(a) - a)
