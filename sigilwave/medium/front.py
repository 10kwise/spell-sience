"""A propagating acoustic wavefront, held as a polyline of vertices
(SUBMERGED §5, §7.3).

The whole module exists to serve one sentence — **a wavefront bends toward
slower water** — and to make the second sentence of §5 a consequence rather
than a feature: *the same energy spread over more width hits softer.*

Why a polyline and not particles or a grid:

- A **particle** cloud has no width, so "energy divided by width" is not a
  thing you can read off it. Intensity would have to be a number someone
  assigns, and §9.3 forbids properties that are only readable from a number.
- A **grid solver** would give correct intensity, but the front stops being
  an object you can point at. §9.4 wants the pulse to be the protagonist:
  a thing that enters, crosses, folds, and dies on screen.
- A **polyline** has arc length for free. `intensity = energy / arc_length`
  is then geometry, not a multiplier. Stretch the line and every segment
  dims because the same energy now covers more of it; bunch the line and
  it brightens. Caustics, shadow zones and focal lines are not authored —
  they are what a line does when the medium pushes on it unevenly.

The step is the eikonal ray equation, one vertex at a time. For a unit
tangent t and arc length s,

    dt/ds = -(1/c) * (grad c - (grad c . t) t)

i.e. the direction rotates at a rate set by the component of grad c
*perpendicular* to travel, turning toward lower c. Since ds = c*dt, the
c cancels and the per-unit-*time* turn rate is simply

    dtheta/dt = -(grad c . n_hat),      n_hat = t rotated +90 degrees

which is the entire physics of this file. In a constant gradient g it
integrates to a circular ray of radius c0/g, which is what
`selftest_front` checks against.

Energy bookkeeping uses a Voronoi split of the arc: vertex i owns the half
of each adjacent segment nearest to it, so its owned length is
L_i = (len(i-1) + len(i))/2 and the sum of owned lengths is exactly the
front's arc length. Vertex intensity is I_i = e_i / L_i, segment intensity
is the mean of its endpoints', and therefore

    sum_over_segments(intensity * segment_length) == sum_over_vertices(e_i)

holds identically, not approximately. That identity is what lets
resampling be provably lossless: splitting a segment leaves every vertex
position alone and merely re-derives energies from unchanged intensities,
so the sum telescopes back to the same total.

**Folding policy.** In a strong gradient a front folds through itself.
That is not a failure — it is a caustic, and §7.3 says caustics are not to
be authored, so they are not to be prevented either. The policy is
therefore *permissive*: the polyline is allowed to become non-simple, no
topological surgery is attempted, and vertices are allowed to pass through
one another. Two things keep that from becoming an infinity:

1. `seg_min` merging collapses the vertices that pile up, so the achievable
   intensity is limited by resolution rather than by zero. A real caustic
   is finite for the same kind of reason (wavelength rather than mesh),
   so the model's brightest possible line is a resolution-limited stand-in
   for a physical one rather than a lie about it.
2. Owned arc length is floored before it is divided by. A vertex sitting
   exactly on a focus owns *no* arc, and the only defensible reading of
   energy over zero length is "as bright as this front gets" — never zero.
   Getting that backwards is how a perfectly-converging front annihilates
   itself at its own focus, which it did, once.

The one place the sum-of-intensity-times-length identity is not exact is
that instant of total collapse, when the front has no length to spread
energy over. Energy is still conserved; it just is not a line density for
one step.

Dependencies are numpy and the standard library. No rendering, no game.
"""

from __future__ import annotations

import math

import numpy as np

_TWO_PI = 2.0 * math.pi
_EPS = 1e-12

# A mouth of literally zero width would have infinite intensity. §5 wants
# `arc_span=0` to read as "one mouth -> a lance", so zero is floored to a
# small but finite aperture instead of being rejected: the lance is then
# the brightest thing the model can emit, without being a division by zero.
MIN_ARC_SPAN = 1e-2

# Weighted 8-neighbour stencil for reading a surface normal out of a
# boolean solid field. Diagonals are half-weighted so a flat wall returns
# an exactly axis-aligned normal (Sobel's reason, same as Sobel's weights).
_R2 = 0.7071067811865476
_NORMAL_STENCIL = (
    (1.0, 0.0, 1.0),
    (-1.0, 0.0, 1.0),
    (0.0, 1.0, 1.0),
    (0.0, -1.0, 1.0),
    (_R2, _R2, 0.5),
    (_R2, -_R2, 0.5),
    (-_R2, _R2, 0.5),
    (-_R2, -_R2, 0.5),
)


def _solid_normal(is_solid, x: float, y: float, h: float):
    """Outward normal of the solid field at (x, y), or None if the point is
    boxed in on all sides (a one-cell pocket, or the inside of a wall).

    Read from `is_solid` probes rather than from `medium.solid` directly so
    this works against an analytic medium as happily as a gridded one, and
    so digging (§8 SHATTER) changes the normal the instant it changes the
    field, with nothing cached in between."""
    ax = 0.0
    ay = 0.0
    for ox, oy, w in _NORMAL_STENCIL:
        if is_solid(x + ox * h, y + oy * h):
            ax -= ox * w
            ay -= oy * w
    m = math.hypot(ax, ay)
    if m < 1e-9:
        return None
    return ax / m, ay / m


class Vertex:
    """A handle onto one vertex of a front.

    The front stores positions, directions and energies as three packed
    numpy arrays, because the step loop touches every vertex every frame
    and a list of objects would spend its life chasing pointers. This proxy
    exists so the rest of the game still gets the `.pos / .dir / .energy`
    interface it was promised, without the storage having to pay for it.
    Handles are live views: writing `v.energy = 0.0` writes the array. They
    are invalidated by the next resample, which is to say, by the next
    `step()`."""

    __slots__ = ("_front", "_index")

    def __init__(self, front: "Front", index: int) -> None:
        self._front = front
        self._index = index

    @property
    def index(self) -> int:
        return self._index

    @property
    def pos(self) -> np.ndarray:
        return self._front._P[self._index]

    @property
    def dir(self) -> np.ndarray:
        return self._front._D[self._index]

    @property
    def energy(self) -> float:
        return float(self._front._E[self._index])

    @energy.setter
    def energy(self, value: float) -> None:
        self._front._E[self._index] = float(value)

    @property
    def intensity(self) -> float:
        """Energy per unit of the arc this vertex owns — the physical
        quantity. Per-vertex energy on its own is a resolution artefact:
        resampling halves it without anything getting quieter."""
        lv = self._front._voronoi_lengths()[self._index]
        return float(self._front._E[self._index] / max(lv, _EPS))

    def __repr__(self) -> str:
        p = self.pos
        return f"Vertex(pos=({p[0]:.3f}, {p[1]:.3f}), energy={self.energy:.4g})"


class Front:
    """One acoustic wavefront: a polyline that walks itself through a
    medium and dims as it stretches.

    Construction is the whole of §5. A front is born as an arc, and the arc
    it is born as decides what it does:

        arc_span      how wide the emitting mouth is, as arc length in
                      world units. Intensity at birth is energy/arc_span,
                      so a short arc is a lance and a long arc is a wall.
        arc_curvature signed 1/radius. Convex (> 0) puts the centre of
                      curvature behind the front, so it spreads at once —
                      the wash. Concave (< 0) puts it a distance 1/|k|
                      ahead, so the front converges there and the caustic
                      is real geometry, not a lighting effect. Flat (0) is
                      a collimated slab that neither spreads nor focuses
                      until the water bends it.

    `arc_span >= 2*pi*radius` closes the arc into a ring, which is §5's
    omni pulse; `Front.omni()` is the shorthand.
    """

    def __init__(
        self,
        origin,
        direction,
        arc_span: float,
        arc_curvature: float,
        energy: float,
        freq: float,
        n_vertices: int = 48,
        *,
        seg_min: float | None = None,
        seg_max: float | None = None,
        max_vertices: int = 512,
        intensity_floor_frac: float = 1e-6,
        death_energy_frac: float = 1e-4,
        vertex_energy_floor: float = 0.0,
        max_turn_per_step: float = 0.05,
        max_substeps: int = 8,
        intensity_cap_frac: float = 1e6,
    ) -> None:
        origin = np.asarray(origin, dtype=np.float64).reshape(2)
        u = np.asarray(direction, dtype=np.float64).reshape(2).copy()
        un = float(np.hypot(u[0], u[1]))
        if not np.isfinite(un) or un < _EPS:
            raise ValueError("front direction must be a non-zero finite vector")
        u /= un

        energy = float(energy)
        if not np.isfinite(energy) or energy < 0.0:
            raise ValueError("front energy must be finite and non-negative")

        self.freq = float(freq)
        self.energy0 = energy
        self.age = 0.0
        self.steps = 0

        self.max_vertices = max(4, int(max_vertices))
        self.max_turn_per_step = float(max_turn_per_step)
        self.max_substeps = max(1, int(max_substeps))
        self.vertex_energy_floor = float(vertex_energy_floor)

        # Resolution is deliberately left unset until the front first sees a
        # medium: the right segment length is a property of the water's own
        # cell size, not of the caller's taste, and the front has no business
        # being finer than the field that steers it.
        self.seg_min = seg_min
        self.seg_max = seg_max
        self._probe_h = 0.5

        self._closed = False
        self._dead = False
        self._roll = 0
        self._lv_cache: np.ndarray | None = None

        span = max(float(arc_span), MIN_ARC_SPAN)
        kappa = float(arc_curvature)
        n = max(2, int(n_vertices))

        normal = np.array([-u[1], u[0]], dtype=np.float64)

        if abs(kappa) * span < 1e-9:
            # Flat: a slab of parallel rays. It will never spread on its
            # own, which is correct — only the medium can bend it.
            s = np.linspace(-0.5 * span, 0.5 * span, n)
            P = origin[None, :] + s[:, None] * normal[None, :]
            D = np.repeat(u[None, :], n, axis=0)
        else:
            radius = 1.0 / abs(kappa)
            if span >= _TWO_PI * radius:
                span = _TWO_PI * radius
                self._closed = True
                n = max(3, n)
                theta = np.linspace(-math.pi, math.pi, n, endpoint=False)
            else:
                half = 0.5 * span / radius
                theta = np.linspace(-half, half, n)
            ct = np.cos(theta)
            st = np.sin(theta)
            D = np.empty((len(theta), 2), dtype=np.float64)
            D[:, 0] = u[0] * ct - u[1] * st
            D[:, 1] = u[0] * st + u[1] * ct
            if kappa > 0.0:
                centre = origin - radius * u  # behind: the front spreads
                P = centre[None, :] + radius * D
            else:
                centre = origin + radius * u  # ahead: the front converges there
                P = centre[None, :] - radius * D

        self._P = np.ascontiguousarray(P, dtype=np.float64)
        self._D = np.ascontiguousarray(D, dtype=np.float64)
        self._E = np.zeros(len(self._P), dtype=np.float64)

        # Uniform intensity at birth: every vertex gets energy in proportion
        # to the arc it owns, so E/arc_length is flat across the front and
        # §5's "intensity = energy / width" is true from step zero.
        lv = self._voronoi_lengths()
        total = float(lv.sum())
        self.arc_span = total
        self.launch_intensity = energy / total if total > _EPS else 0.0
        if total > _EPS:
            self._E[:] = energy * (lv / total)
        else:
            self._E[:] = energy / len(self._E)

        self.intensity_floor = self.launch_intensity * float(intensity_floor_frac)
        self.intensity_cap = self.launch_intensity * float(intensity_cap_frac)
        self.death_energy = energy * float(death_energy_frac)

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def omni(
        cls,
        origin,
        energy: float,
        freq: float,
        radius: float = 1.0,
        n_vertices: int = 64,
        **kwargs,
    ) -> "Front":
        """§5's closed ring of mouths. A ring is not a special case in here:
        it is a convex arc whose span has come all the way round, so it
        obeys exactly the same stretch-and-dim law as every other front."""
        radius = max(float(radius), MIN_ARC_SPAN)
        origin = np.asarray(origin, dtype=np.float64).reshape(2)
        # The general constructor takes the point on the arc, not the centre
        # of curvature; for a ring the caller means the centre, so offset by
        # one radius along the reference heading to put it there.
        apex = origin + np.array([radius, 0.0])
        return cls(
            apex,
            (1.0, 0.0),
            _TWO_PI * radius,
            1.0 / radius,
            energy,
            freq,
            n_vertices,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # public state
    # ------------------------------------------------------------------

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def vertices(self) -> list:
        """Live handles onto the vertices, rebuilt on demand. Cheap enough
        for the renderer and the tests; the step loop never calls it."""
        return [Vertex(self, i) for i in range(len(self._E))]

    def __len__(self) -> int:
        return len(self._E)

    def total_energy(self) -> float:
        return float(self._E.sum())

    def arc_length(self) -> float:
        return float(self._segment_lengths().sum())

    def intensity(self) -> np.ndarray:
        """Per-vertex intensity, energy divided by owned arc.

        Capped, because a fold can drive a segment length to zero and the
        cap is what stops a caustic from becoming an infinity. The cap is
        physically honest as well as numerically necessary: a real caustic
        is finite too, limited by wavelength rather than by our
        resolution."""
        lv = self._voronoi_lengths()
        return np.minimum(self._E / np.maximum(lv, _EPS), self.intensity_cap)

    def segments(self) -> list:
        """`(p0, p1, intensity)` per segment, for the renderer.

        Positions are live views into the front's arrays: valid until the
        next `step()`, which resamples and reallocates them."""
        if self._dead:
            return []
        n = len(self._E)
        if n < 2:
            return []
        inten = self.intensity()
        P = self._P
        count = n if self._closed else n - 1
        out = []
        for j in range(count):
            k = (j + 1) % n
            out.append((P[j], P[k], 0.5 * float(inten[j] + inten[k])))
        return out

    def is_dead(self) -> bool:
        return self._dead

    # ------------------------------------------------------------------
    # geometry
    # ------------------------------------------------------------------

    def _segment_lengths(self) -> np.ndarray:
        P = self._P
        n = len(P)
        if n < 2:
            return np.zeros(0, dtype=np.float64)
        if self._closed:
            d = np.roll(P, -1, axis=0) - P
        else:
            d = P[1:] - P[:-1]
        return np.hypot(d[:, 0], d[:, 1])

    def _voronoi_lengths(self) -> np.ndarray:
        """How much of the arc each vertex owns: half of each neighbouring
        segment. Sums to the total arc length exactly, which is the whole
        reason the energy bookkeeping closes."""
        if self._lv_cache is not None:
            return self._lv_cache
        n = len(self._P)
        lv = np.zeros(n, dtype=np.float64)
        seg = self._segment_lengths()
        if n >= 2:
            if self._closed:
                lv += 0.5 * seg
                lv += 0.5 * np.roll(seg, 1)
            else:
                lv[:-1] += 0.5 * seg
                lv[1:] += 0.5 * seg
        self._lv_cache = lv
        return lv

    def _invalidate(self) -> None:
        self._lv_cache = None

    # ------------------------------------------------------------------
    # the step
    # ------------------------------------------------------------------

    def step(self, medium, dt: float) -> None:
        """Advance the whole front by `dt` of wall-clock ocean.

        Order matters. Advection first (every vertex moves and turns and
        loses what the water absorbs), then retirement of anything too
        faint or non-finite, then resampling. Resampling last means the
        merge pass sees the post-fold geometry and gets to collapse the
        coincident vertices a caustic produces, rather than leaving them
        for the intensity calculation to divide by."""
        if self._dead:
            return
        self._ensure_resolution(medium)
        self._advect(medium, float(dt))
        self._invalidate()
        self._retire()
        self._resample()
        self._check_death()
        self.age += float(dt)
        self.steps += 1

    def _ensure_resolution(self, medium) -> None:
        if self.seg_max is not None and self.seg_min is not None:
            return
        cell = float(getattr(medium, "cell_size", 1.0) or 1.0)
        if self.seg_max is None:
            self.seg_max = 2.0 * cell
        if self.seg_min is None:
            self.seg_min = 0.25 * cell
        self._probe_h = 0.5 * cell

    def _advect(self, medium, dt: float) -> None:
        """Midpoint RK2 on (position, heading) per vertex.

        RK2 rather than Euler because the check that matters — a constant
        gradient must produce a circle of radius c0/g — is a curvature
        check, and Euler's heading lags by half a step, which shows up as a
        systematically wrong radius rather than as noise. The substep count
        is chosen per vertex from how far it is about to turn, so a front
        crossing a violent gradient spends effort exactly where the water
        is violent and nowhere else."""
        P = self._P
        D = self._D
        E = self._E
        n = len(E)
        if n == 0:
            return

        freq = self.freq
        sound_speed = medium.sound_speed
        c_gradient = medium.c_gradient
        absorption = medium.absorption
        is_solid = medium.is_solid

        probe = self._probe_h
        max_turn = self.max_turn_per_step
        max_sub = self.max_substeps
        cos = math.cos
        sin = math.sin
        exp = math.exp
        hypot = math.hypot

        for i in range(n):
            e = E[i]
            if e <= 0.0:
                continue
            x = P[i, 0]
            y = P[i, 1]
            dx = D[i, 0]
            dy = D[i, 1]

            if is_solid(x, y):
                # Born inside rock, or driven there by a corner the normal
                # estimate could not resolve. Nothing physical to do: the
                # energy is in the rock, so it is heat now (§7.1).
                E[i] = 0.0
                continue

            gx, gy = c_gradient(x, y)
            turn = abs(gy * dx - gx * dy) * dt
            m = 1
            if turn > max_turn:
                m = int(turn / max_turn) + 1
                if m > max_sub:
                    m = max_sub
            sdt = dt / m

            for _ in range(m):
                c1 = sound_speed(x, y)
                g1x, g1y = c_gradient(x, y)
                # dtheta/dt = -(grad c . n_hat), n_hat = (-dy, dx).
                # The sign is the entire design doc: positive grad c to the
                # left means slower water to the right, so turn right.
                w1 = -(g1y * dx - g1x * dy)

                half = 0.5 * w1 * sdt
                ca = cos(half)
                sa = sin(half)
                mdx = dx * ca - dy * sa
                mdy = dx * sa + dy * ca
                hx = x + dx * c1 * sdt * 0.5
                hy = y + dy * c1 * sdt * 0.5

                c2 = sound_speed(hx, hy)
                g2x, g2y = c_gradient(hx, hy)
                w2 = -(g2y * mdx - g2x * mdy)

                a = w2 * sdt
                ca = cos(a)
                sa = sin(a)
                ndx = dx * ca - dy * sa
                ndy = dx * sa + dy * ca

                step_len = c2 * sdt
                nx = x + mdx * step_len
                ny = y + mdy * step_len

                alpha = absorption(hx, hy, freq)
                if alpha > 0.0:
                    e *= exp(-alpha * step_len)

                if is_solid(nx, ny):
                    # Bisect for the crossing, mirror about the surface
                    # normal, spend the rest of the step going the other
                    # way. Reflection is not a rule of its own — it is the
                    # limiting case of a density boundary (§7.2), and the
                    # front does not otherwise notice it happened.
                    lo = 0.0
                    hi = 1.0
                    sx = nx - x
                    sy = ny - y
                    for _ in range(10):
                        mid = 0.5 * (lo + hi)
                        if is_solid(x + sx * mid, y + sy * mid):
                            hi = mid
                        else:
                            lo = mid
                    hitx = x + sx * lo
                    hity = y + sy * lo
                    nrm = _solid_normal(is_solid, hitx, hity, probe)
                    if nrm is None:
                        e = 0.0
                        break
                    snx, sny = nrm
                    dot = ndx * snx + ndy * sny
                    if dot < 0.0:
                        ndx -= 2.0 * dot * snx
                        ndy -= 2.0 * dot * sny
                    backx = hitx + snx * probe * 0.25
                    backy = hity + sny * probe * 0.25
                    rem = (1.0 - lo) * step_len
                    tx = backx + ndx * rem
                    ty = backy + ndy * rem
                    if is_solid(tx, ty):
                        tx, ty = backx, backy
                    nx, ny = tx, ty

                inv = hypot(ndx, ndy)
                if inv < _EPS or not math.isfinite(inv):
                    e = 0.0
                    break
                dx = ndx / inv
                dy = ndy / inv
                x = nx
                y = ny

            P[i, 0] = x
            P[i, 1] = y
            D[i, 0] = dx
            D[i, 1] = dy
            E[i] = e

    # ------------------------------------------------------------------
    # retirement and death
    # ------------------------------------------------------------------

    def _retire(self) -> None:
        """Drop vertices that have stopped mattering.

        The test is *intensity*, not per-vertex energy, and intensity is
        taken over a floored arc length so that a vertex sitting on a
        caustic reads as maximally bright rather than as owning nothing.
        A well-resolved front splits its energy over more vertices without
        getting one bit
        quieter, so an energy threshold would execute the fronts that are
        being simulated most carefully. Intensity is the thing an ear or a
        rock would notice, so intensity is the thing that decides.

        Non-finite vertices are retired by the same pass. That is the only
        NaN policy in this file and it is deliberately blunt: a vertex that
        has gone infinite has no information left in it, and letting it
        survive would poison its neighbours' arc lengths."""
        n = len(self._E)
        if n == 0:
            return
        P = self._P
        finite = (
            np.isfinite(P[:, 0])
            & np.isfinite(P[:, 1])
            & np.isfinite(self._D[:, 0])
            & np.isfinite(self._D[:, 1])
            & np.isfinite(self._E)
        )
        lv = self._voronoi_lengths()
        inten = self._E / np.maximum(lv, _EPS)
        alive = (
            finite
            & (self._E > self.vertex_energy_floor)
            & (inten > self.intensity_floor)
        )
        if alive.all():
            return
        self._P = np.ascontiguousarray(P[alive])
        self._D = np.ascontiguousarray(self._D[alive])
        self._E = np.ascontiguousarray(self._E[alive])
        self._invalidate()

    def _check_death(self) -> None:
        n = len(self._E)
        floor = 3 if self._closed else 2
        if n < floor or float(self._E.sum()) <= self.death_energy:
            self._kill()

    def _kill(self) -> None:
        """Dead fronts must be cheap. Drop the arrays rather than keeping
        an empty husk of them: a game that fires hundreds of pings a minute
        wants the corpse to cost one flag, not three allocations."""
        self._dead = True
        self._P = np.zeros((0, 2), dtype=np.float64)
        self._D = np.zeros((0, 2), dtype=np.float64)
        self._E = np.zeros(0, dtype=np.float64)
        self._invalidate()

    # ------------------------------------------------------------------
    # adaptive resampling
    # ------------------------------------------------------------------

    def _resample(self) -> None:
        """Keep the polyline's resolution honest as it stretches and bunches.

        Two passes, in this order, each exactly energy-conserving on its own:

        **Merge** deletes a vertex from a too-short segment and hands its
        energy to its two surviving neighbours, half each. No surviving
        vertex moves. That detail is load-bearing and was learned the hard
        way: collapsing a pair into their midpoint instead is exactly
        energy-conserving but *not* intensity-conserving, because the
        endpoint of an open front owns only half a segment, so a collapse
        that pours a full segment's energy into it leaves a 50% bright rim
        that is pure artefact. Deleting-and-donating is exactly neutral on
        a uniform chain: the survivor's energy grows by precisely the arc
        it inherits. The arc still shortens by the chord it cuts, which is
        the real rise in intensity where a front bunches, and that part is
        supposed to happen.

        The ends of an open front are never deleted. They are the aperture
        edges, and their headings are the beam's angular extent — average
        them away and a shadow zone quietly moves.

        **Split** inserts midpoints into too-long segments. Positions do
        not move, so this pass keeps every vertex's intensity and merely
        re-derives its energy from the arc it now owns. Per segment the
        arithmetic telescopes back to the same total (the inserted
        vertices' intensities are a linear interpolation, whose mean over a
        symmetric sample set is the endpoint mean), so the front's energy
        is unchanged to floating-point.

        Splitting is capped by `max_vertices`. That cap is what makes a
        front crossing a shredding gradient bounded in memory: past it the
        front simply stops resolving finer, which reads on screen as a
        caustic that has saturated rather than one that has crashed."""
        if len(self._E) < 2:
            return
        if self._closed and len(self._E) >= 3:
            # A closed front's wrap-around segment is the one the merge
            # pass cannot see. Rotating the array one slot per step lets it
            # come round to a position where it can.
            self._roll = (self._roll + 1) % len(self._E)
            if self._roll == 0:
                self._P = np.ascontiguousarray(np.roll(self._P, 1, axis=0))
                self._D = np.ascontiguousarray(np.roll(self._D, 1, axis=0))
                self._E = np.ascontiguousarray(np.roll(self._E, 1))
                self._invalidate()
        self._merge_pass()
        self._split_pass()

    def _merge_pass(self) -> None:
        seg = self._segment_lengths()
        if len(seg) == 0:
            return
        seg_min = self.seg_min
        if seg_min is None or not bool((seg < seg_min).any()):
            return

        n = len(self._E)
        floor = 3 if self._closed else 2
        if n <= floor:
            return

        drop = np.zeros(n, dtype=bool)
        removed = 0
        for j in range(len(seg)):
            if seg[j] >= seg_min:
                continue
            if n - removed <= floor:
                break
            if self._closed:
                cand = (j + 1) % n
            elif j + 1 <= n - 2:
                cand = j + 1
            elif j >= 1:
                cand = j
            else:
                continue  # the front is two vertices long and both are ends
            prev = (cand - 1) % n
            nxt = (cand + 1) % n
            # Never delete two neighbours in one pass: the donation rule
            # below assumes both of a victim's neighbours survive to
            # receive, and that is also what keeps a pass from thinning the
            # front by more than half at once.
            if drop[cand] or drop[prev] or drop[nxt]:
                continue
            drop[cand] = True
            removed += 1

        if removed == 0:
            return

        E = self._E
        for k in np.nonzero(drop)[0]:
            half = 0.5 * E[k]
            E[(k - 1) % n] += half
            E[(k + 1) % n] += half

        keep = ~drop
        self._P = np.ascontiguousarray(self._P[keep])
        self._D = np.ascontiguousarray(self._D[keep])
        self._E = np.ascontiguousarray(E[keep])
        self._invalidate()

    def _split_pass(self) -> None:
        n = len(self._E)
        if n < 2:
            return
        seg = self._segment_lengths()
        if len(seg) == 0:
            return
        seg_max = self.seg_max
        if seg_max is None or seg_max <= 0.0:
            return

        budget = self.max_vertices - n
        if budget <= 0:
            return

        want = np.ceil(seg / seg_max).astype(np.int64) - 1
        np.maximum(want, 0, out=want)
        total_want = int(want.sum())
        if total_want == 0:
            return
        if total_want > budget:
            # Not enough room for everyone: hand the budget out in
            # proportion to how badly each segment is under-resolved.
            scaled = np.floor(want * (budget / total_want)).astype(np.int64)
            want = scaled
            if int(want.sum()) == 0:
                return

        lv = self._voronoi_lengths()
        inten = self._E / np.maximum(lv, _EPS)
        collapsed = lv <= _EPS

        P = self._P
        D = self._D
        E = self._E
        out_p = []
        out_d = []
        out_i = []
        # A vertex sitting exactly on a caustic owns no arc at all, so its
        # intensity is a division by a floor and cannot be multiplied back
        # into an energy. Carry its energy across verbatim instead; NaN is
        # the "derive me from intensity" marker.
        out_e = []
        count = n if self._closed else n - 1

        for j in range(n):
            out_p.append((P[j, 0], P[j, 1]))
            out_d.append((D[j, 0], D[j, 1]))
            out_i.append(inten[j])
            out_e.append(E[j] if collapsed[j] else math.nan)
            if j >= count:
                continue
            k = int(want[j])
            if k <= 0:
                continue
            nxt = (j + 1) % n
            i0 = inten[j]
            i1 = inten[nxt]
            for q in range(1, k + 1):
                t = q / (k + 1)
                px = P[j, 0] + (P[nxt, 0] - P[j, 0]) * t
                py = P[j, 1] + (P[nxt, 1] - P[j, 1]) * t
                ddx = D[j, 0] + (D[nxt, 0] - D[j, 0]) * t
                ddy = D[j, 1] + (D[nxt, 1] - D[j, 1]) * t
                m = math.hypot(ddx, ddy)
                if m < _EPS:
                    ddx, ddy = D[j, 0], D[j, 1]
                else:
                    ddx /= m
                    ddy /= m
                out_p.append((px, py))
                out_d.append((ddx, ddy))
                out_i.append(i0 + (i1 - i0) * t)
                out_e.append(math.nan)

        self._P = np.array(out_p, dtype=np.float64)
        self._D = np.array(out_d, dtype=np.float64)
        self._invalidate()
        new_lv = self._voronoi_lengths()
        energy = np.asarray(out_i, dtype=np.float64) * new_lv
        carried = np.asarray(out_e, dtype=np.float64)
        held = ~np.isnan(carried)
        if held.any():
            energy[held] = carried[held]
        self._E = energy
        self._invalidate()

    def __repr__(self) -> str:
        if self._dead:
            return "Front(dead)"
        return (
            f"Front(n={len(self._E)}, arc={self.arc_length():.3f}, "
            f"E={self.total_energy():.4g}, f={self.freq:.0f}Hz"
            f"{', closed' if self._closed else ''})"
        )
