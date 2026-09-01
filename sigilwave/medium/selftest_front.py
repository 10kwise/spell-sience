"""Proof that SUBMERGED §7.3 is a law and not a feature list.

    python -m sigilwave.medium.selftest_front

Every check in here is aimed at the same claim: the only rule in
`front.py` is *a wavefront bends toward slower water*, and refraction,
sound channels, shadow zones, caustics and the inverse relationship
between width and punch are consequences of it. Nothing below is allowed
to pass because the code special-cased it; the analytic media are chosen
precisely because ray theory already tells us the answer.

The media here are stubs implementing the same contract as
`sigilwave/medium/field.py` (`sound_speed`, `c_gradient`, `absorption`,
`is_solid`, `solid`, `cell_size`). They are analytic on purpose: a linear
gradient makes rays exact circles, a parabolic profile makes a channel,
and a checked answer beats a plausible picture.

Coordinate convention throughout: `x` is horizontal range, `y` is **depth,
increasing downward**. `front.py` itself has no opinion about this.

House style deviation, deliberately: `sigilwave/sim/selftest.py` exits on
the first failure. This file records failures and keeps going, because the
brief for this module is to report honestly on what does and does not
emerge, and one early failure hiding nine later results would defeat that.
The exit code is still non-zero if anything failed.
"""

import math
import time

import numpy as np

from .front import Front

_FAILURES = []


def check(name: str, condition: bool) -> None:
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        _FAILURES.append(name)


def note(text: str) -> None:
    print(f"       {text}")


# ----------------------------------------------------------------------
# analytic stand-ins for field.py
# ----------------------------------------------------------------------


class AnalyticMedium:
    """Satisfies the medium contract from closed-form functions.

    `solid` is a real boolean grid (the contract promises one) indexed
    [row = y/cell, col = x/cell], so the reflection check is exercising
    exactly the code path a gridded field would."""

    def __init__(self, c_fn, grad_fn, absorb_fn=None, cell_size=1.0, grid_shape=(8, 8)):
        self._c = c_fn
        self._g = grad_fn
        self._a = absorb_fn
        self.cell_size = float(cell_size)
        self.solid = np.zeros(grid_shape, dtype=bool)

    def sound_speed(self, x, y):
        return self._c(x, y)

    def c_gradient(self, x, y):
        return self._g(x, y)

    def absorption(self, x, y, freq):
        return 0.0 if self._a is None else self._a(x, y, freq)

    def is_solid(self, x, y):
        cs = self.cell_size
        j = int(math.floor(x / cs))
        i = int(math.floor(y / cs))
        h, w = self.solid.shape
        if i < 0 or j < 0 or i >= h or j >= w:
            return False
        return bool(self.solid[i, j])


def uniform_medium(c=1500.0, cell_size=1.0, absorb=None, grid_shape=(8, 8)):
    return AnalyticMedium(
        lambda x, y: c,
        lambda x, y: (0.0, 0.0),
        absorb,
        cell_size=cell_size,
        grid_shape=grid_shape,
    )


def linear_gradient_medium(g, c_ref=1500.0, y_ref=500.0, cell_size=10.0):
    """c = c_ref + g*(y - y_ref). Rays are exact circles of radius
    c(y_launch)/g centred at the depth where c extrapolates to zero.
    Pinning c at the launch depth means doubling g halves the radius with
    nothing else moving, which is the scaling the check wants."""
    return AnalyticMedium(
        lambda x, y: c_ref + g * (y - y_ref),
        lambda x, y: (0.0, g),
        cell_size=cell_size,
    )


def channel_medium(cell_size=50.0):
    """§7.3's channel: c falls with depth near the surface (colder), rises
    with depth below (pressure), so there is a minimum in between. The two
    halves have different curvature because the real ocean's do — and the
    asymmetry is what makes 'launched outside the channel' mean something,
    since a shallow-launched ray's conjugate depth then falls below the
    seabed instead of turning back."""
    y0 = 500.0
    cmin = 1500.0
    a_up = 1.0e-4
    a_dn = 2.5e-5

    def c(x, y):
        d = y - y0
        return cmin + (a_up * d * d if d < 0.0 else a_dn * d * d)

    def g(x, y):
        d = y - y0
        return (0.0, 2.0 * (a_up if d < 0.0 else a_dn) * d)

    return AnalyticMedium(c, g, cell_size=cell_size)


def down_refracting_medium(g=0.2, c0=1500.0, cell_size=20.0):
    """c decreases with depth, so every ray bends downward. The upward
    limiting ray turns over at a computable height, and everything above
    that is shadow."""
    return AnalyticMedium(
        lambda x, y: c0 - g * y,
        lambda x, y: (0.0, -g),
        cell_size=cell_size,
    )


def violent_medium(cell_size=5.0, grid_shape=(400, 400)):
    """A shredding checkerboard of sound speed, plus scattered rock. Not
    physical; the point is to be the worst thing the integrator can be
    handed and still come out finite."""
    amp = 400.0
    kx = 1.0 / 37.0
    ky = 1.0 / 29.0

    def c(x, y):
        return 1500.0 + amp * math.sin(x * kx) * math.cos(y * ky)

    def g(x, y):
        return (
            amp * kx * math.cos(x * kx) * math.cos(y * ky),
            -amp * ky * math.sin(x * kx) * math.sin(y * ky),
        )

    med = AnalyticMedium(c, g, cell_size=cell_size, grid_shape=grid_shape)
    ii, jj = np.indices(grid_shape)
    med.solid[(ii // 13 + jj // 17) % 11 == 0] = True
    return med


def centroid(front):
    return np.average(front._P, axis=0, weights=None)


# ----------------------------------------------------------------------
# 1. uniform water
# ----------------------------------------------------------------------


def test_uniform_circle():
    """A ring launched into still water must stay a ring and grow at c.
    Nothing in `step` knows what a circle is; it holds because with zero
    gradient no vertex turns, so every one of them walks radially."""
    c = 1500.0
    med = uniform_medium(c, cell_size=1.0)
    r0 = 20.0
    f = Front.omni((0.0, 0.0), energy=1.0, freq=1000.0, radius=r0,
                   n_vertices=96, max_vertices=1024)
    e0 = f.total_energy()

    dt = 2.0e-4
    steps = 200
    for _ in range(steps):
        f.step(med, dt)

    r_expected = r0 + c * dt * steps
    radii = np.hypot(f._P[:, 0], f._P[:, 1])
    r_mean = float(radii.mean())
    circularity = float(radii.std() / r_mean)
    radius_err = abs(r_mean - r_expected) / r_expected

    note(f"radius {r_mean:.4f} m vs c*t prediction {r_expected:.4f} m "
         f"(rel err {radius_err:.2e}); {len(f)} vertices")
    check("uniform: point-source front stays circular (std/mean < 1e-3)",
          circularity < 1e-3)
    check("uniform: radius grows as c*t (rel err < 3e-3)", radius_err < 3e-3)

    drift = abs(f.total_energy() - e0) / e0
    note(f"energy drift over {steps} steps and "
         f"{len(f) - 96} inserted vertices: {drift:.2e}")
    check("uniform: energy conserved with no absorption (rel drift < 1e-9)",
          drift < 1e-9)


# ----------------------------------------------------------------------
# 2. refraction
# ----------------------------------------------------------------------


def _fit_circle(pts):
    """Kasa algebraic circle fit: x^2+y^2 = 2ax + 2by + c."""
    x = pts[:, 0]
    y = pts[:, 1]
    A = np.column_stack([2.0 * x, 2.0 * y, np.ones_like(x)])
    b = x * x + y * y
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy, cc = sol
    r = math.sqrt(max(cc + cx * cx + cy * cy, 0.0))
    return (cx, cy), r


def _ray_trace(g, steps=900, dt=0.02):
    med = linear_gradient_medium(g)
    f = Front((0.0, 500.0), (1.0, 0.0), arc_span=10.0, arc_curvature=0.0,
              energy=1.0, freq=1000.0, n_vertices=2)
    track = []
    for _ in range(steps):
        f.step(med, dt)
        track.append(centroid(f).copy())
    return f, np.array(track)


def test_refraction_matches_circular_ray():
    """Constant gradient, analytic answer: the ray is a circle of radius
    c(launch)/g. This is the single check that the bending law's magnitude
    and sign are both right — a wrong sign curves into fast water, a wrong
    factor gives a circle of the wrong size."""
    for g in (0.5, 1.0):
        f, track = _ray_trace(g)
        r_expected = 1500.0 / g
        (cx, cy), r_fit = _fit_circle(track)
        err = abs(r_fit - r_expected) / r_expected
        note(f"g={g}: fitted ray radius {r_fit:.2f} m vs analytic "
             f"c/g = {r_expected:.2f} m (rel err {err:.2e})")
        check(f"refraction: g={g} ray radius matches c/g (rel err < 1e-3)",
              err < 1e-3)
        check(f"refraction: g={g} front curves toward the slower (shallower) side",
              track[-1][1] < 499.0)

    _, t1 = _ray_trace(0.5)
    _, t2 = _ray_trace(1.0)
    r1 = _fit_circle(t1)[1]
    r2 = _fit_circle(t2)[1]
    ratio = r1 / r2
    note(f"curvature scales with gradient: R(g=0.5)/R(g=1.0) = {ratio:.4f} "
         f"(expected 2.0)")
    check("refraction: curvature scales linearly with gradient strength",
          abs(ratio - 2.0) < 0.02)


# ----------------------------------------------------------------------
# 3. the sound channel
# ----------------------------------------------------------------------


def _run_until_out_of_column(front, med, dt, max_steps, y_lo=0.0, y_hi=1000.0):
    for _ in range(max_steps):
        front.step(med, dt)
        if front.is_dead():
            break
        cy = float(centroid(front)[1])
        if not (y_lo <= cy <= y_hi):
            break
    return float(centroid(front)[0]) if not front.is_dead() else float("nan")


def test_sound_channel_traps():
    """The headline. Two identical fronts, one laid into the channel axis
    at a shallow angle and one launched at a depth whose conjugate depth is
    below the seabed. Nothing tells either of them about a channel; the one
    on the axis simply cannot find water slow enough to escape into."""
    med = channel_medium()
    dt = 0.05
    max_steps = 4000

    a = Front((0.0, 500.0), (math.cos(math.radians(2.0)), math.sin(math.radians(2.0))),
              arc_span=40.0, arc_curvature=0.0, energy=1.0, freq=200.0, n_vertices=4)
    depths = []
    range_a = 0.0
    for _ in range(max_steps):
        a.step(med, dt)
        if a.is_dead():
            break
        cy = float(centroid(a)[1])
        depths.append(cy)
        range_a = float(centroid(a)[0])
        if not (0.0 <= cy <= 1000.0):
            break

    b = Front((0.0, 100.0), (1.0, 0.0), arc_span=40.0, arc_curvature=0.0,
              energy=1.0, freq=200.0, n_vertices=4)
    range_b = _run_until_out_of_column(b, med, dt, max_steps)

    d = np.array(depths)
    swings = int(np.count_nonzero(np.diff(np.sign(np.diff(d))) != 0))
    note(f"axial front: depth oscillates between {d.min():.1f} m and "
         f"{d.max():.1f} m, {swings} turning points over {len(d)} steps")
    note(f"range trapped {range_a / 1000.0:.2f} km vs "
         f"untrapped {range_b / 1000.0:.2f} km")

    check("channel: axial front stays inside the channel (never leaves 350-750 m)",
          d.min() > 350.0 and d.max() < 750.0)
    check("channel: axial front oscillates about the axis (>= 4 turning points)",
          swings >= 4)

    ratio = range_a / range_b if range_b > 0 else float("inf")
    note(f"SOUND-CHANNEL RANGE RATIO = {ratio:.1f}x")
    check("channel: trapped front travels much further than the untrapped one (>= 5x)",
          ratio >= 5.0)


# ----------------------------------------------------------------------
# 4. shadow zone
# ----------------------------------------------------------------------


def test_shadow_zone():
    """Downward-refracting water, a 20-degree fan, and a probe point that a
    straight-line ocean would light up. The steepest upward ray turns over
    at c_s*(sec(theta0) - 1)/g above the source, and everything above that
    curve receives nothing. The uniform control is what makes it a shadow
    rather than an aiming error."""
    g = 0.2
    c0 = 1500.0
    y_src = 500.0
    theta = math.radians(10.0)
    c_src = c0 - g * y_src

    apex_rise = c_src * (1.0 / math.cos(theta) - 1.0) / g
    y_apex = y_src - apex_rise
    r_ray = c_src / (g * math.cos(theta))
    x_apex = r_ray * math.sin(theta)

    def build():
        r0 = 5.0
        return Front((0.0, y_src), (1.0, 0.0), arc_span=2.0 * theta * r0,
                     arc_curvature=1.0 / r0, energy=1.0, freq=500.0,
                     n_vertices=32)

    def sweep(med, steps, dt):
        f = build()
        shallowest = math.inf
        shallowest_at_probe = math.inf
        for _ in range(steps):
            f.step(med, dt)
            if f.is_dead():
                break
            P = f._P
            shallowest = min(shallowest, float(P[:, 1].min()))
            band = (P[:, 0] > x_apex - 40.0) & (P[:, 0] < x_apex + 40.0)
            if band.any():
                shallowest_at_probe = min(shallowest_at_probe,
                                          float(P[band, 1].min()))
        return shallowest, shallowest_at_probe

    dt = 0.01
    steps = 120
    refract_min, refract_probe = sweep(down_refracting_medium(g, c0), steps, dt)
    uniform_min, uniform_probe = sweep(uniform_medium(c_src, cell_size=20.0),
                                       steps, dt)

    note(f"limiting-ray apex: analytic {y_apex:.1f} m depth at range "
         f"{x_apex:.0f} m; measured shallowest {refract_min:.1f} m")
    note(f"at that range: refracting reaches {refract_probe:.1f} m, "
         f"uniform control reaches {uniform_probe:.1f} m")

    check("shadow: measured turning depth matches the analytic limiting ray (+/- 3 m)",
          abs(refract_min - y_apex) < 3.0)
    check("shadow: probe at 300 m depth is lit in uniform water",
          uniform_probe < 300.0)
    check("shadow: same probe receives nothing once the water refracts",
          refract_probe > 320.0)


# ----------------------------------------------------------------------
# 5. focusing
# ----------------------------------------------------------------------


def test_concave_front_focuses():
    """A concave arc converges because its vertices were born pointing at a
    common centre, and the arc between them shortens as they approach it.
    Intensity is energy over that shortening arc, so the gain is not
    applied anywhere — it is the same division as always."""
    med = uniform_medium(1500.0, cell_size=1.0)
    focal = 200.0
    f = Front((0.0, 0.0), (1.0, 0.0), arc_span=100.0, arc_curvature=-1.0 / focal,
              energy=1.0, freq=2000.0, n_vertices=128)
    launch = f.launch_intensity

    peak = launch
    peak_x = 0.0
    trail = []
    dt = 1.0e-3
    for _ in range(200):
        f.step(med, dt)
        if f.is_dead():
            break
        segs = f.segments()
        if not segs:
            break
        hi = max(s[2] for s in segs)
        trail.append(hi)
        if hi > peak:
            peak = hi
            peak_x = float(f._P[:, 0].mean())

    gain = peak / launch
    note(f"launch intensity {launch:.4g}, peak {peak:.4g} at x = {peak_x:.1f} m "
         f"(geometric focus at {focal:.0f} m)")
    note(f"FOCUSING GAIN = {gain:.1f}x")
    check("focusing: concave front's peak intensity rises above launch", gain > 5.0)
    check("focusing: the focus happens near the geometric focal distance",
          abs(peak_x - focal) < 0.35 * focal)
    if len(trail) > 20:
        check("focusing: intensity falls again after the focus",
              trail[-1] < peak * 0.9)


# ----------------------------------------------------------------------
# 6. the spreading law
# ----------------------------------------------------------------------


def test_convex_front_spreads():
    """§5's whole output vocabulary in one check: the same energy over more
    width hits softer. Also the bookkeeping identity — the sum of
    intensity times segment length must be the front's energy at every
    step, because that is what makes intensity a division and not a
    decoration."""
    med = uniform_medium(1500.0, cell_size=1.0)
    f = Front((0.0, 0.0), (1.0, 0.0), arc_span=10.0, arc_curvature=1.0 / 5.0,
              energy=1.0, freq=2000.0, n_vertices=64, max_vertices=1024)
    launch_arc = f.arc_length()
    launch_peak = max(s[2] for s in f.segments())

    worst_identity = 0.0
    monotone = True
    prev = launch_peak
    dt = 1.0e-3
    for _ in range(200):
        f.step(med, dt)
        segs = f.segments()
        if not segs:
            break
        recon = sum(s[2] * float(np.hypot(*(s[1] - s[0]))) for s in segs)
        e = f.total_energy()
        worst_identity = max(worst_identity, abs(recon - e) / e)
        hi = max(s[2] for s in segs)
        if hi > prev * 1.000001:
            monotone = False
        prev = hi

    arc = f.arc_length()
    note(f"arc {launch_arc:.2f} -> {arc:.2f} m ({arc / launch_arc:.1f}x wider), "
         f"peak intensity {launch_peak:.4g} -> {prev:.4g} "
         f"({launch_peak / prev:.1f}x softer)")
    note(f"worst |sum(I*len) - E| / E over the run: {worst_identity:.2e}")

    check("spreading: a convex front's arc grows", arc > launch_arc * 5.0)
    check("spreading: its intensity falls as the arc grows", monotone)
    check("spreading: intensity x width recovers energy (rel err < 1e-9)",
          worst_identity < 1e-9)
    check("spreading: width x intensity is conserved (E = I*L within 1%)",
          abs(prev * arc - f.total_energy()) / f.total_energy() < 0.01)


# ----------------------------------------------------------------------
# 7. reflection
# ----------------------------------------------------------------------


def test_reflection_off_flat_wall():
    """Mirror angle off a grid-aligned solid. The normal is read out of the
    solid field with a weighted 8-neighbour stencil, so a flat wall gives
    an exactly axial normal and the outgoing heading is the incoming one
    with its normal component negated."""
    med = uniform_medium(1500.0, cell_size=1.0, grid_shape=(200, 200))
    med.solid[100:, :] = True

    inc = math.radians(45.0)
    f = Front((50.0, 50.0), (math.cos(inc), math.sin(inc)), arc_span=2.0,
              arc_curvature=0.0, energy=1.0, freq=1000.0, n_vertices=4)
    dt = 1.0e-3
    for _ in range(120):
        f.step(med, dt)
        if f.is_dead():
            break

    d = f._D.mean(axis=0)
    d /= np.hypot(d[0], d[1])
    expect = np.array([math.cos(inc), -math.sin(inc)])
    align = float(d @ expect)
    out_angle = math.degrees(math.atan2(-d[1], d[0]))
    note(f"incident 45.0 deg from the wall normal, reflected {out_angle:.3f} deg; "
         f"heading alignment {align:.6f}")
    check("reflection: front leaves a flat solid at the mirror angle",
          align > 0.9999)
    check("reflection: the front survives the bounce", not f.is_dead())


# ----------------------------------------------------------------------
# 8. absorption
# ----------------------------------------------------------------------


def test_absorption_kills_high_frequency_first():
    """§7.1: high dies fast, low carries far. The front does not know which
    is which — it asks the medium for nepers per metre and multiplies by
    the distance it actually walked."""
    a0 = 3.0e-6

    def absorb(x, y, freq):
        return a0 * (freq / 1000.0) ** 2

    results = {}
    for freq in (500.0, 20000.0):
        med = uniform_medium(1500.0, cell_size=5.0, absorb=absorb)
        f = Front((0.0, 0.0), (1.0, 0.0), arc_span=20.0, arc_curvature=0.0,
                  energy=1.0, freq=freq, n_vertices=8)
        dt = 0.01
        steps = 334
        for _ in range(steps):
            f.step(med, dt)
        path = 1500.0 * dt * steps
        results[freq] = (f.total_energy(), math.exp(-absorb(0, 0, freq) * path))

    lo_e, lo_pred = results[500.0]
    hi_e, hi_pred = results[20000.0]
    note(f"over 5.0 km: 500 Hz keeps {lo_e:.4f} (analytic {lo_pred:.4f}), "
         f"20 kHz keeps {hi_e:.3e} (analytic {hi_pred:.3e})")
    check("absorption: low frequency survives a 5 km path",
          abs(lo_e - lo_pred) / lo_pred < 1e-6)
    check("absorption: high frequency matches Beer-Lambert over the same path",
          abs(hi_e - hi_pred) / hi_pred < 1e-6)
    check("absorption: high frequency dies markedly sooner than low",
          hi_e < lo_e * 0.01)


# ----------------------------------------------------------------------
# 9. stability
# ----------------------------------------------------------------------


def test_stability_under_violence():
    """Thousands of steps through a shredding gradient studded with rock.
    The front will fold, cross itself, and pile up; none of that is allowed
    to become a NaN or an unbounded vertex list."""
    med = violent_medium()
    cap = 192
    f = Front.omni((1000.0, 1000.0), energy=1.0, freq=800.0, radius=30.0,
                   n_vertices=48, max_vertices=cap)
    e0 = f.total_energy()

    steps = 3000
    peak_n = len(f)
    survived = 0
    for _ in range(steps):
        f.step(med, 0.005)
        if f.is_dead():
            break
        survived += 1
        peak_n = max(peak_n, len(f))
        if not (np.isfinite(f._P).all() and np.isfinite(f._D).all()
                and np.isfinite(f._E).all()):
            break

    finite = (np.isfinite(f._P).all() and np.isfinite(f._D).all()
              and np.isfinite(f._E).all())
    note(f"{survived} steps survived, peak vertex count {peak_n} (cap {cap}), "
         f"energy {f.total_energy():.4f} of {e0:.4f}")
    check("stability: no NaNs or infinities after thousands of violent steps", finite)
    check("stability: vertex count stays under the cap", peak_n <= cap)
    check("stability: energy never grows", f.total_energy() <= e0 * (1.0 + 1e-9))
    check("stability: the front is still alive after 3000 steps", survived == steps)


def test_fold_does_not_explode():
    """A strongly concave front folds through its own focus. That fold is a
    caustic and is physically real, so the policy is to let it happen: the
    polyline is allowed to be non-simple, and the only guard is that a
    collapsing segment gets merged rather than divided by."""
    med = uniform_medium(1500.0, cell_size=1.0)
    f = Front((0.0, 0.0), (1.0, 0.0), arc_span=300.0, arc_curvature=-1.0 / 60.0,
              energy=1.0, freq=2000.0, n_vertices=200, max_vertices=1024)
    e0 = f.total_energy()
    ok = True
    min_arc = math.inf
    peak_n = len(f)
    for _ in range(400):
        f.step(med, 1.0e-3)
        if f.is_dead():
            break
        min_arc = min(min_arc, f.arc_length())
        peak_n = max(peak_n, len(f))
        if not (np.isfinite(f._P).all() and np.isfinite(f._E).all()):
            ok = False
            break
        segs = f.segments()
        if segs and not all(math.isfinite(s[2]) for s in segs):
            ok = False
            break
    drift = abs(f.total_energy() - e0) / e0
    note(f"after folding through a 60 m focus: {len(f)} vertices "
         f"(peak {peak_n}), arc bottomed out at {min_arc:.3e} m, "
         f"energy {f.total_energy():.6f} of {e0:.6f}")
    check("fold: front folds through its focus without NaNs", ok)
    # These two are the reason the check exists. A front that quietly dies
    # at its own focus satisfies "no NaNs" and "no energy created" while
    # having destroyed everything, which is exactly the bug this caught.
    check("fold: the front survives its own caustic", not f.is_dead())
    check("fold: folding neither creates nor destroys energy (rel drift < 1e-9)",
          drift < 1e-9)
    check("fold: the front re-expands after the caustic", f.arc_length() > 10.0)


# ----------------------------------------------------------------------
# 10. performance
# ----------------------------------------------------------------------


def test_performance():
    """Cost of a frame with a few dozen live fronts in refracting water."""
    med = channel_medium(cell_size=5.0)
    n_fronts = 40
    fronts = []
    rng = np.random.default_rng(7)
    for _ in range(n_fronts):
        y = float(rng.uniform(200.0, 800.0))
        ang = float(rng.uniform(-0.3, 0.3))
        fronts.append(
            Front((0.0, y), (math.cos(ang), math.sin(ang)), arc_span=200.0,
                  arc_curvature=1.0 / 100.0, energy=1.0, freq=1000.0,
                  n_vertices=48, max_vertices=128)
        )

    dt = 0.01
    for _ in range(10):  # warm the resolution and let them reach the cap
        for f in fronts:
            f.step(med, dt)

    steps = 150
    t0 = time.perf_counter()
    for _ in range(steps):
        for f in fronts:
            f.step(med, dt)
    elapsed = time.perf_counter() - t0

    live = [f for f in fronts if not f.is_dead()]
    verts = sum(len(f) for f in live)
    ms = 1000.0 * elapsed / steps
    note(f"{len(live)} live fronts, {verts} vertices total")
    note(f"MS/STEP = {ms:.2f} ms for the whole batch "
         f"({1000.0 * elapsed / (steps * max(verts, 1)) * 1000.0:.2f} us/vertex)")
    check("performance: a 40-front frame costs under 40 ms", ms < 40.0)


def test_death_is_cheap():
    """A front that has spent itself must stop costing anything."""
    med = uniform_medium(1500.0, cell_size=5.0,
                         absorb=lambda x, y, f: 1.0e-3)
    f = Front((0.0, 0.0), (1.0, 0.0), arc_span=20.0, arc_curvature=0.0,
              energy=1.0, freq=1000.0, n_vertices=16)
    for _ in range(4000):
        f.step(med, 0.01)
        if f.is_dead():
            break
    note(f"front died after {f.steps} steps; {len(f)} vertices retained, "
         f"segments() -> {len(f.segments())}")
    check("death: a spent front reports dead", f.is_dead())
    check("death: a dead front holds no vertices", len(f) == 0)
    check("death: stepping a dead front is a no-op", (f.step(med, 0.01) is None))


def main() -> None:
    tests = [
        test_uniform_circle,
        test_refraction_matches_circular_ray,
        test_sound_channel_traps,
        test_shadow_zone,
        test_concave_front_focuses,
        test_convex_front_spreads,
        test_reflection_off_flat_wall,
        test_absorption_kills_high_frequency_first,
        test_stability_under_violence,
        test_fold_does_not_explode,
        test_performance,
        test_death_is_cheap,
    ]
    for t in tests:
        print(f"\n--- {t.__name__} ---")
        t()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} check(s) FAILED:")
        for name in _FAILURES:
            print(f"  - {name}")
        raise SystemExit(1)
    print("all checks passed.")


if __name__ == "__main__":
    main()
