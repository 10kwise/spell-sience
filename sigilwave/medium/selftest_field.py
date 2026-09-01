"""Proof that the medium's behaviour is emergent rather than asserted.

Everything §7 promises is a *consequence*: nowhere in field.py is there a
sound channel, a rising plume, or an acoustic mirror. The channel is what a
temperature profile and a pressure term do to one another; the plume is what
a density inversion does. So a test that only proved the code runs would
prove nothing worth knowing. Each check below measures the consequence and
prints the number, because a number that moves when a constant is tuned is
the only honest way to know whether the tuning helped.

    python -m sigilwave.medium.selftest_field

Unlike sigilwave/sim/selftest.py this runner does not stop at the first
failure. Those tests check algebra, where one wrong answer invalidates the
rest; these check six coupled physical systems, and knowing that bubbles
still rise while the sound channel has collapsed is information the first
failure would otherwise hide.
"""

import math
import time

import numpy as np

from .field import (
    C_FLOOR,
    GRADIENT_EXAGGERATION,
    MINNAERT_CONSTANT,
    Medium,
    default_temperature_profile,
)

FAILURES = []


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        FAILURES.append(name)


def note(text: str) -> None:
    print(f"       {text}")


def flat(temp: float):
    return lambda depth_fraction: temp


def column_of_c(medium: Medium, x: float):
    return np.array([medium.sound_speed(x, float(d)) for d in medium.depth_m[:, 0]])


def weighted_mean(values, weights) -> float:
    total = float(weights.sum())
    return float((values * weights).sum() / total) if total > 0 else 0.0


def trace_ray(medium: Medium, x: float, y: float, dx: float, dy: float, steps: int = 700):
    """Integrate one ray with unit steps and return where it ends up.

    The turn law is front.py's -- the direction rotates by the component of
    grad c perpendicular to travel, toward slower water -- restated in four
    lines rather than imported, because this file tests the water and must not
    pass or fail on the marcher's behaviour."""
    for _ in range(steps):
        c = medium.sound_speed(x, y)
        gx, gy = medium.c_gradient(x, y)
        dot = gx * dx + gy * dy
        dx -= (gx - dot * dx) / c
        dy -= (gy - dot * dy) / c
        norm = math.hypot(dx, dy)
        dx, dy = dx / norm, dy / norm
        x += dx
        y += dy
    return x, y


def test_sound_speed_has_an_interior_minimum() -> None:
    """§7.3, the channel. Temperature falls fast near the surface and beats
    the pressure term, so c falls; deep down the temperature has flattened and
    only pressure is left, so c rises. Neither branch is authored, and the
    minimum between them is the sound channel."""
    medium = Medium(1200, 800)
    profile = column_of_c(medium, 600.0)
    low = int(np.argmin(profile))

    depth = float(medium.depth_m[low, 0])
    check(
        f"c has a minimum at an interior depth, not an endpoint "
        f"(row {low} of {medium.ny}, {depth:.0f} m, {depth / medium.height:.0%} of the way down)",
        0 < low < medium.ny - 1,
    )
    note(
        f"c: {profile[0]:.0f} px/s at the surface, {profile[low]:.0f} at the axis, "
        f"{profile[-1]:.0f} at the seabed (exaggeration {GRADIENT_EXAGGERATION:g}x)"
    )
    check(
        "the minimum is a real trough, not numerical noise "
        f"(surface is {profile[0] - profile[low]:.0f} px/s faster, "
        f"seabed {profile[-1] - profile[low]:.0f} px/s faster)",
        profile[0] - profile[low] > 20.0 and profile[-1] - profile[low] > 20.0,
    )

    steepest = float(np.abs(np.gradient(medium.c_field, medium.cell_size, axis=0)).max())
    turning_radius = float(profile.mean()) / steepest
    note(
        f"steepest vertical gradient {steepest:.2f} 1/s -> a horizontal ray turns "
        f"on a radius of {turning_radius:.0f} px in a {medium.width:.0f}x{medium.height:.0f} room"
    )
    check(
        f"bending is dramatic at this scale (turning radius {turning_radius:.0f} px "
        f"is inside the domain)",
        turning_radius < medium.width,
    )


def test_c_rises_with_temperature_salinity_and_pressure() -> None:
    """The sign of all three is the load-bearing part of the formula; the
    channel exists only because the temperature term and the depth term pull
    the same variable in opposite directions as you descend."""
    medium = Medium(400, 400, cell_size=16.0)
    medium.set_temperature_profile(flat(10.0))

    base = medium.sound_speed(200.0, 200.0)
    medium.temp += 5.0
    medium._dirty = True
    warmer = medium.sound_speed(200.0, 200.0)
    medium.temp -= 5.0
    medium.salinity += 2.0
    medium._dirty = True
    saltier = medium.sound_speed(200.0, 200.0)
    medium.salinity -= 2.0
    medium._dirty = True
    deeper = medium.sound_speed(200.0, 390.0)

    check(f"c rises with temperature (+5 C -> {warmer - base:+.1f} px/s)", warmer > base)
    check(f"c rises with salinity (+2 psu -> {saltier - base:+.1f} px/s)", saltier > base)
    check(f"c rises with pressure (+190 m -> {deeper - base:+.1f} px/s)", deeper > base)

    scan = Medium(64, 64, cell_size=16.0)
    speeds = []
    for t in range(0, 90, 10):
        scan.set_temperature_profile(flat(float(t)))
        speeds.append(scan.sound_speed(32.0, 32.0))
    check(
        "c rises with temperature monotonically across 0-80 C "
        "(the cubic term keeps dc/dT positive where a quadratic fit would invert it)",
        all(b > a for a, b in zip(speeds, speeds[1:])),
    )


def test_heat_spreads_and_is_conserved() -> None:
    """§7.1: heat diffuses. Nothing removes it, so the total may only move
    around -- and it has to be exact, because the acoustic mirror is built by
    accumulating heat and a leaky integrator would quietly erase it."""
    medium = Medium(640, 480)
    medium.set_temperature_profile(flat(10.0))
    medium.carve(0, 400, 640, 80)

    fluid = ~medium.solid
    before = float(medium.temp[fluid].sum())
    medium.add_heat(320.0, 160.0, 200.0)
    seeded = float(medium.temp[fluid].sum())
    row, col = medium._cell(320.0, 160.0)
    peak_before = float(medium.temp[row, col])

    for _ in range(240):
        medium.step(1.0 / 60.0)

    peak_after = float(medium.temp[row, col])
    neighbours = [
        float(medium.temp[row, col - 1]),
        float(medium.temp[row, col + 1]),
        float(medium.temp[row + 1, col]),
    ]
    check(
        f"heat leaves the cell it was added to ({peak_before - 10.0:.1f} C above ambient "
        f"-> {peak_after - 10.0:.1f} C after 4 s)",
        peak_after < peak_before,
    )
    check(
        f"and arrives at the neighbours (left/right/below now "
        f"{', '.join(f'{n - 10.0:+.2f}' for n in neighbours)} C)",
        all(n > 10.0 + 1e-9 for n in neighbours),
    )

    after = float(medium.temp[fluid].sum())
    drift = abs(after - seeded) / abs(seeded - before)
    check(
        f"total heat conserved with nothing leaving (relative drift {drift:.2e} of what was added)",
        drift < 1e-12,
    )
    check(
        "rock neither warms nor cools (zero-flux boundary, so a wall stores nothing)",
        np.allclose(medium.temp[medium.solid], 10.0),
    )


def test_warm_rises_and_cold_sinks() -> None:
    """§7.2: warm rises -> currents. The only rule behind this is that an
    inverted vertical pair swaps part of its contents; the motion is what that
    rule looks like from a distance."""
    for label, anomaly, start_y in (("warm", +8.0, 600.0), ("cold", -8.0, 200.0)):
        medium = Medium(640, 800)
        medium.set_temperature_profile(flat(10.0))
        for dx in (-16.0, 0.0, 16.0):
            for dy in (-16.0, 0.0, 16.0):
                medium.add_heat(320.0 + dx, start_y + dy, anomaly)

        ys = medium.depth_m[:, 0].reshape(-1, 1) * np.ones((1, medium.nx))

        def centre_of_mass():
            weights = np.maximum((medium.temp - 10.0) * np.sign(anomaly), 0.0)
            return weighted_mean(ys, weights)

        before = centre_of_mass()
        for _ in range(600):
            medium.step(1.0 / 60.0)
        after = centre_of_mass()
        moved = after - before

        if anomaly > 0:
            check(
                f"a {label} blob rises (centre of mass {before:.0f} m -> {after:.0f} m, "
                f"{-moved:+.1f} m upward in 10 s)",
                moved < -1.0,
            )
        else:
            check(
                f"a {label} blob sinks (centre of mass {before:.0f} m -> {after:.0f} m, "
                f"{moved:+.1f} m downward in 10 s)",
                moved > 1.0,
            )


def test_warm_patch_makes_a_density_boundary() -> None:
    """§7.2: a density boundary reflects and bends sound. The mirror in §7.3 is
    built by driving a mouth into still water, so what matters is not that
    density changes but that a *sharp horizontal edge* appears where there was
    none and survives long enough to aim through."""
    medium = Medium(1200, 800)
    background = float(np.abs(np.gradient(medium.density_field, axis=1)).max())

    for dx in (-16.0, 0.0, 16.0):
        for dy in (-16.0, 0.0, 16.0):
            medium.add_heat(600.0 + dx, 400.0 + dy, 10.0)

    def horizontal_edge() -> float:
        return float(np.abs(np.gradient(medium.density_field, axis=1)).max())

    peak = horizontal_edge()
    check(
        f"a stratified ocean has no horizontal density structure of its own "
        f"(background |d(rho)/dx| = {background:.2e} kg/m^3 per cell)",
        background < 1e-12,
    )
    check(
        f"heating a patch builds one ({peak:.3f} kg/m^3 per cell across the edge)",
        peak > 0.1,
    )

    for _ in range(60):
        medium.step(1.0 / 60.0)
    after_one_second = horizontal_edge()
    for _ in range(60 * 19):
        medium.step(1.0 / 60.0)
    after_twenty = horizontal_edge()

    check(
        f"the boundary persists long enough to use "
        f"({after_one_second:.3f} kg/m^3 per cell after 1 s, "
        f"{after_one_second / peak:.0%} of peak)",
        after_one_second > 0.35 * peak,
    )
    check(
        f"and then diffuses away ({after_twenty:.3f} after 20 s, "
        f"{after_twenty / peak:.0%} of peak)",
        after_twenty < 0.5 * after_one_second,
    )


def test_bubbles_rise_and_change_size() -> None:
    """§7.2: bubbles shrink with depth, and their note changes as they rise.
    Boyle's law is the whole of it -- a bubble holds a fixed amount of gas, so
    its radius goes as the cube root of the pressure it is under."""
    medium = Medium(1200, 800)
    seed_y = 700.0
    medium.add_bubbles(600.0, seed_y, 0.5, 0.001)

    ys = medium.depth_m[:, 0].reshape(-1, 1) * np.ones((1, medium.nx))
    depth_before = weighted_mean(ys, medium.bubbles)
    radius_before = weighted_mean(medium.bubble_radius, medium.bubbles)

    for _ in range(200):
        medium.step(1.0 / 60.0)

    depth_after = weighted_mean(ys, medium.bubbles)
    radius_after = weighted_mean(medium.bubble_radius, medium.bubbles)

    check(
        f"bubbles rise ({depth_before:.0f} m -> {depth_after:.0f} m in 3.3 s)",
        depth_after < depth_before - 5.0,
    )
    check(
        f"and grow on the way up as the pressure over them falls "
        f"({radius_before * 1000:.2f} mm -> {radius_after * 1000:.2f} mm)",
        radius_after > radius_before * 1.02,
    )

    born = []
    for depth in (100.0, 700.0):
        hot = Medium(1200, 800)
        for dx in (-16.0, 0.0, 16.0):
            hot.add_heat(600.0 + dx, depth, 60.0)
        for _ in range(30):
            hot.step(1.0 / 60.0)
        born.append(weighted_mean(hot.bubble_radius, hot.bubbles))
    shallow, deep = born
    check(
        f"gas shed at depth comes out as smaller bubbles than the same gas shed shallow "
        f"({shallow * 1000:.2f} mm at 100 m vs {deep * 1000:.2f} mm at 700 m)",
        deep < shallow * 0.8,
    )
    note("nothing in this model ever pushes a bubble downward, so descent is tested by")
    note("birth depth rather than by transport -- see the summary.")


def test_absorption_punishes_high_notes_and_bubbles() -> None:
    """§7.1: high dies fast, low carries far. §7.2: bubbles eat sound, and a
    bubble at your note rings with you."""
    medium = Medium(1200, 800)
    distance = 500.0

    low = medium.absorption(600.0, 400.0, 50.0)
    high = medium.absorption(600.0, 400.0, 8000.0)

    def survives(alpha: float) -> float:
        return float(np.exp(-alpha * distance))

    check(
        f"high frequency is absorbed far more than low over {distance:.0f} px "
        f"(50 Hz keeps {survives(low):.1%} of its amplitude, 8 kHz keeps {survives(high):.2%})",
        high > 50.0 * low,
    )

    # A patch rather than a single cell, so that sampling in the middle of it
    # reads the bubbles rather than a bilinear blend with the clear water next
    # door -- the same reason a real curtain has to be wider than the beam.
    bubbly = Medium(1200, 800)
    for dx in (-16.0, 0.0, 16.0):
        for dy in (-16.0, 0.0, 16.0):
            bubbly.add_bubbles(600.0 + dx, 400.0 + dy, 0.6, 0.002)
    clear_mid = medium.absorption(600.0, 400.0, 1000.0)
    murky_mid = bubbly.absorption(600.0, 400.0, 1000.0)
    check(
        f"a bubble field absorbs violently compared with clear water at the same note "
        f"({murky_mid / clear_mid:.0f}x, {survives(murky_mid):.1e} of amplitude left "
        f"over {distance:.0f} px)",
        murky_mid > 100.0 * clear_mid,
    )

    radius = bubbly._bilinear(bubbly.bubble_radius, 600.0, 400.0)
    resonant = MINNAERT_CONSTANT * np.sqrt(bubbly.pressure_at(400.0)) / radius
    on_note = bubbly.absorption(600.0, 400.0, float(resonant))
    off_note = bubbly.absorption(600.0, 400.0, float(resonant) / 4.0)
    check(
        f"and worst of all at the bubbles' own Minnaert note "
        f"({resonant / 1000.0:.1f} kHz absorbs {on_note / off_note:.0f}x harder than two "
        f"octaves below it)",
        on_note > 5.0 * off_note,
    )


def test_bubbles_collapse_the_sound_speed() -> None:
    """§7.2 says bubbles eat sound. They also bend it, and far harder: Wood's
    equation takes a bubbly mixture below the speed of sound in either water or
    air, so a curtain is a mirror as well as a wall. That is one system doing
    two jobs, and the rule is one sentence -- sound bends hard toward bubbles."""
    medium = Medium(1200, 800)
    medium.set_temperature_profile(flat(10.0))

    fractions = [0.0, 1e-3, 1e-2, 0.05, 0.1, 0.25, 0.5, 1.0]
    surface, seabed = [], []
    for f in fractions:
        medium.bubbles[:] = f
        medium._dirty = True
        surface.append(float(medium.c_field[0, 0]))
        seabed.append(float(medium.c_field[-1, 0]))

    check(
        "c collapses monotonically as the bubble fraction rises",
        all(b < a for a, b in zip(surface, surface[1:])),
    )
    for f, cs, cb in zip(fractions, surface, seabed):
        note(f"bubbles {f:<6g} c = {cs:7.1f} px/s at the surface, {cb:7.1f} at 800 m")
    check(
        f"and the collapse is violent, not cosmetic "
        f"({surface[0] / surface[-1]:.1f}x slower at saturation)",
        surface[-1] < 0.15 * surface[0],
    )
    check(
        f"deep bubbles bend less than shallow ones -- the gas spring stiffens with "
        f"pressure, so a bubble mirror is a shallow-water instrument "
        f"({surface[-1]:.0f} px/s at the surface vs {seabed[-1]:.0f} at 800 m)",
        seabed[-1] > 2.0 * surface[-1],
    )

    saturated = Medium(1200, 800)
    saturated.bubbles[:] = 1.0
    saturated._dirty = True
    slowest = float(saturated.c_field.min())
    check(
        f"c never reaches the documented floor: the slowest attainable water is "
        f"{slowest:.0f} px/s against a floor of {C_FLOOR:.0f}, so the clamp never "
        f"binds and never flattens the gradient",
        C_FLOOR < slowest,
    )


def test_a_curtain_edge_is_steep_but_continuous() -> None:
    """A cliff in c is the one thing that could still hurt the marcher.
    Bilinear sampling spreads the transition across a cell, so the edge of a
    curtain is a very steep ramp rather than a step -- steep enough to turn a
    ray inside a couple of cells, which is exactly what makes it a mirror."""
    medium = Medium(1200, 800)
    medium.set_temperature_profile(flat(10.0))
    edge_col = 40
    medium.bubbles[:, edge_col:] = 0.6
    medium._dirty = True
    edge_x = edge_col * medium.cell_size

    xs = np.linspace(edge_x - 80.0, edge_x + 80.0, 1601)
    ys = np.full_like(xs, 400.0)
    gx, _ = medium.c_gradient_at(xs, ys)
    speeds = medium.sound_speed_at(xs, ys)

    spacing = float(xs[1] - xs[0])
    biggest_jump = float(np.abs(np.diff(speeds)).max())
    total_drop = float(speeds[0] - speeds[-1])
    check(
        f"c is continuous across the curtain edge, not a cliff: the largest step "
        f"between samples {spacing:.2f} px apart is {biggest_jump:.2f} px/s, "
        f"{biggest_jump / total_drop:.2%} of the {total_drop:.0f} px/s drop overall",
        biggest_jump < 0.02 * total_drop,
    )
    check("and its gradient is finite everywhere across it", bool(np.isfinite(gx).all()))

    steepest = float(np.abs(gx).max())
    at_steepest = float(speeds[int(np.argmax(np.abs(gx)))])
    check(
        f"the edge is steep enough to be a mirror (max |dc/dx| {steepest:.1f} 1/s, "
        f"ray turning radius {at_steepest / steepest:.0f} px, against 193 px for the "
        f"steepest thermocline)",
        at_steepest / steepest < 60.0,
    )

    # The field is piecewise bilinear; the gradient is a central difference of
    # the cell field, then interpolated. At a feature exactly one cell wide the
    # central difference straddles it and reads half the true slope. Reported
    # rather than corrected: the alternative -- differentiating the bilinear
    # interpolant directly -- gives the true slope but is piecewise constant,
    # so it hands the marcher a gradient that jumps at every cell boundary. A
    # continuous gradient that under-reports the sharpest edges is the better
    # trade for a ray integrator, but a caller sizing a substep from it should
    # know the edge can be twice as sharp as it looks.
    measured_slope = biggest_jump / spacing
    note(
        f"the interpolated gradient reads {steepest:.1f} 1/s where the field's own "
        f"slope is {measured_slope:.1f} 1/s -- a central difference halves a "
        f"one-cell feature; see the comment in this test"
    )


def test_a_curtain_refracts_as_well_as_absorbs() -> None:
    """The absorbing half is already checked above. This is the new half: a ray
    that would fly dead straight is pulled bodily into the bubbles.

    The curtain is vertical and the ray is launched vertically, which isolates
    the effect exactly -- the pressure term in c is parallel to travel and so
    bends nothing, and any sideways deflection at all is therefore the gas."""
    clear = Medium(1200, 800)
    clear.set_temperature_profile(flat(10.0))
    curtain = Medium(1200, 800)
    curtain.set_temperature_profile(flat(10.0))
    curtain.bubbles[:, 40:] = 0.6
    curtain._dirty = True

    start_x = 40 * curtain.cell_size - 8.0
    straight = trace_ray(clear, start_x, 80.0, 0.0, 1.0)[0] - start_x
    bent = trace_ray(curtain, start_x, 80.0, 0.0, 1.0)[0] - start_x

    check(
        f"a vertical ray in clear water is not deflected at all ({straight:+.3f} px)",
        abs(straight) < 1e-6,
    )
    check(
        f"the same ray launched beside a curtain is dragged into it "
        f"({bent:+.1f} px sideways over 700 px of travel)",
        bent > 20.0,
    )


def test_bubbles_do_not_disturb_the_channel() -> None:
    """Wood's collapse multiplies the finished field and returns exactly 1.0
    where there is no gas, so a curtain on one side of the room has to leave
    the sound channel on the other side untouched -- bit for bit, not nearly."""
    medium = Medium(1200, 800)
    quiet_x = 300.0
    before = column_of_c(medium, quiet_x)
    row_before = int(np.argmin(before))

    medium.bubbles[:, 60:] = 0.5
    medium._dirty = True
    after = column_of_c(medium, quiet_x)
    row_after = int(np.argmin(after))

    check(
        f"the channel is where it was: row {row_before} -> {row_after}, "
        f"{medium.depth_m[row_after, 0]:.0f} m",
        row_before == row_after,
    )
    check(
        "and the whole column away from the curtain is bit-identical",
        np.array_equal(before, after),
    )


def test_batched_sampling_matches_the_scalar_methods() -> None:
    """The marcher may not see different water depending on which entry point
    it asked through, so this is exact equality and not a tolerance. The
    awkward coordinates matter more than the random ones: out of bounds on
    every side, exactly on a cell boundary, and exactly on a cell centre."""
    rng = np.random.default_rng(20240901)
    medium = Medium(1200, 800)
    medium.carve(200, 600, 300, 120)
    for _ in range(40):
        medium.add_bubbles(rng.uniform(0, 1200), rng.uniform(0, 800), 0.4, 0.002)

    awkward = [
        (0.0, 0.0), (-1e6, -1e6), (1e6, 1e6), (1200.0, 800.0), (-0.0, -0.0),
        (16.0, 16.0), (8.0, 8.0), (-320.0, 400.0), (600.0, -320.0), (1e9, 1e9),
    ]
    xs = np.concatenate([rng.uniform(-400, 1600, 590), [a for a, _ in awkward]])
    ys = np.concatenate([rng.uniform(-400, 1200, 590), [b for _, b in awkward]])

    scalar_c = np.array([medium.sound_speed(float(a), float(b)) for a, b in zip(xs, ys)])
    check(
        f"sound_speed_at is bit-identical to sound_speed over {len(xs)} points",
        np.array_equal(medium.sound_speed_at(xs, ys), scalar_c),
    )

    scalar_g = np.array([medium.c_gradient(float(a), float(b)) for a, b in zip(xs, ys)])
    gx, gy = medium.c_gradient_at(xs, ys)
    check(
        "c_gradient_at is bit-identical to c_gradient on both axes",
        np.array_equal(gx, scalar_g[:, 0]) and np.array_equal(gy, scalar_g[:, 1]),
    )

    for freq in (50.0, 1200.0, 9000.0):
        scalar_a = np.array([medium.absorption(float(a), float(b), freq) for a, b in zip(xs, ys)])
        check(
            f"absorption_at is bit-identical to absorption at {freq:.0f} Hz, "
            f"through clear water and bubbles alike",
            np.array_equal(medium.absorption_at(xs, ys, freq), scalar_a),
        )

    scalar_s = np.array([medium.is_solid(float(a), float(b)) for a, b in zip(xs, ys)])
    check(
        "is_solid_at is bit-identical to is_solid, rock included",
        np.array_equal(medium.is_solid_at(xs, ys), scalar_s),
    )


def test_batched_sampling_is_worth_it() -> None:
    """Why the batched variants exist. A few hundred front vertices cost six
    scalar medium calls each per substep, and that per-call Python overhead --
    not the arithmetic inside it -- is the entire bill."""
    medium = Medium(1200, 800)
    rng = np.random.default_rng(11)
    count = 4000
    xs = rng.uniform(0.0, 1200.0, count)
    ys = rng.uniform(0.0, 800.0, count)
    freq = 1200.0

    def scalar_pass():
        for a, b in zip(xs, ys):
            medium.sound_speed(a, b)
            medium.c_gradient(a, b)
            medium.absorption(a, b, freq)
            medium.is_solid(a, b)

    def batched_pass():
        medium.sound_speed_at(xs, ys)
        medium.c_gradient_at(xs, ys)
        medium.absorption_at(xs, ys, freq)
        medium.is_solid_at(xs, ys)

    scalar_pass()
    start = time.perf_counter()
    for _ in range(3):
        scalar_pass()
    scalar_ms = (time.perf_counter() - start) / 3 * 1000.0

    batched_pass()
    start = time.perf_counter()
    for _ in range(50):
        batched_pass()
    batched_ms = (time.perf_counter() - start) / 50 * 1000.0

    speedup = scalar_ms / batched_ms
    check(
        f"{count} points through all four samplers: {scalar_ms:.1f} ms scalar vs "
        f"{batched_ms:.3f} ms batched -- {speedup:.0f}x",
        speedup >= 20.0,
    )
    note(
        f"per point {scalar_ms / count * 1000:.2f} us scalar, "
        f"{batched_ms / count * 1000:.3f} us batched"
    )

    # The speedup is a function of batch size, and that matters more than the
    # headline number: numpy's per-call overhead is a fixed cost amortised over
    # the batch, so one 252-vertex front on its own recovers only a fraction of
    # what is available. The advice this measurement exists to give a caller is
    # to concatenate every live front into a single pair of coordinate arrays
    # per substep rather than calling once per front.
    note("speedup by batch size (all four samplers):")
    for size in (64, 252, 1000, 4000, 16000):
        bx = rng.uniform(0.0, 1200.0, size)
        by = rng.uniform(0.0, 800.0, size)

        def one_scalar():
            for a, b in zip(bx, by):
                medium.sound_speed(a, b)
                medium.c_gradient(a, b)
                medium.absorption(a, b, freq)
                medium.is_solid(a, b)

        def one_batched():
            medium.sound_speed_at(bx, by)
            medium.c_gradient_at(bx, by)
            medium.absorption_at(bx, by, freq)
            medium.is_solid_at(bx, by)

        reps = max(1, 20000 // size)
        one_scalar()
        start = time.perf_counter()
        for _ in range(reps):
            one_scalar()
        per_scalar = (time.perf_counter() - start) / reps / size * 1e6

        reps = max(20, 400000 // size)
        one_batched()
        start = time.perf_counter()
        for _ in range(reps):
            one_batched()
        per_batched = (time.perf_counter() - start) / reps / size * 1e6

        note(
            f"  {size:6d} pts: {per_scalar:6.2f} us/pt scalar, "
            f"{per_batched:6.3f} us/pt batched -> {per_scalar / per_batched:3.0f}x"
        )


def test_step_cost() -> None:
    """The medium is background furniture -- it has to leave essentially the
    whole frame for the waveguide network, the marcher and the render."""
    medium = Medium(1200, 800)
    medium.set_temperature_profile(default_temperature_profile)
    for _ in range(20):
        medium.step(1.0 / 60.0)

    steps = 500
    start = time.perf_counter()
    for _ in range(steps):
        medium.step(1.0 / 60.0)
    per_step = (time.perf_counter() - start) / steps * 1000.0

    budget = 1000.0 / 60.0
    check(
        f"{medium.nx}x{medium.ny} cells over 1200x800 px costs {per_step:.3f} ms/step "
        f"({per_step / budget:.1%} of a 60 Hz frame)",
        per_step < 0.1 * budget,
    )
    note(f"headroom: {int(budget / per_step)} medium steps would fit in one frame")


def main() -> None:
    tests = [
        test_sound_speed_has_an_interior_minimum,
        test_c_rises_with_temperature_salinity_and_pressure,
        test_heat_spreads_and_is_conserved,
        test_warm_rises_and_cold_sinks,
        test_warm_patch_makes_a_density_boundary,
        test_bubbles_rise_and_change_size,
        test_absorption_punishes_high_notes_and_bubbles,
        test_bubbles_collapse_the_sound_speed,
        test_a_curtain_edge_is_steep_but_continuous,
        test_a_curtain_refracts_as_well_as_absorbs,
        test_bubbles_do_not_disturb_the_channel,
        test_batched_sampling_matches_the_scalar_methods,
        test_batched_sampling_is_worth_it,
        test_step_cost,
    ]
    for test in tests:
        test()
    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed:")
        for name in FAILURES:
            print(f"  - {name}")
        raise SystemExit(1)
    print("\nall checks passed.")


if __name__ == "__main__":
    main()
