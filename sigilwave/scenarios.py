"""Preloadable scenarios — concrete stroke geometry + ink parameters + a
drive hint that reliably demonstrates one named emergent mechanic from the
design doc's §3 table ("How the promised feel emerges") and §10's success
criterion. Each one was found/verified via sigilwave/experiment.py; see
EXPERIMENT_REPORT.md for the measurements behind the chosen numbers.

Points are stored relative to a (0, 0) origin; sigil_lab.py's loader
translates them to wherever it wants to anchor the scenario on screen (see
SigilLab._load_scenario). Keeping this module free of any pygame-display
dependency (it only needs Vector2 math) means sigilwave/experiment.py can
also import it directly for headless regression checks.
"""

from dataclasses import dataclass

from .experiment import line_points, loop_with_tail_points
from .ink import InkType


@dataclass
class ScenarioStroke:
    points: list  # list[(x, y)], relative to the scenario's own origin
    ink: InkType


@dataclass
class Scenario:
    key: str  # keyboard key that preloads it, e.g. "1"
    name: str
    description: str
    strokes: list  # list[ScenarioStroke]
    drive_hint: str


# Ink presets named for the mechanic they're tuned to demonstrate, not for
# flavor — sigil_lab.py's preload just needs *an* InkType per stroke.
# Values below come from measured experiments — see experiment_reports/.
KINETIC_INK = InkType("kinetic-demo", impedance=50.0, rad_admittance_fraction=0.6)
THERMAL_INK = InkType("thermal-demo", impedance=50.0, rad_admittance_fraction=0.6)
OVERCHARGE_INK = InkType("overcharge-demo", impedance=50.0, nl_threshold=1.0, nl_asymmetry=0.35)
CHARGE_INK = InkType("charge-demo", impedance=50.0, rad_admittance_fraction=0.05)
SHIELD_FRONT_INK = InkType("shield-front", impedance=20.0)
SHIELD_BACK_INK = InkType("shield-back", impedance=180.0)
FIRE_RANGE_INK = InkType("fire-range-demo", broadband_gain_per_sample=0.998, lowpass_coef_per_sample=0.95)


SCENARIOS: list[Scenario] = [
    Scenario(
        key="1",
        name="Straight shove",
        description="A plain open line. No loop, so chirality defaults to a "
        "plain outward push (see cycles.compute_chirality) — this is stage "
        "5's original 'something moves' demo.",
        strokes=[ScenarioStroke(line_points((-100, 0), (100, 0), n=24), KINETIC_INK)],
        drive_hint="SPACE once at the near end; token should slide away from the tap point.",
    ),
    Scenario(
        key="2",
        name="CW loop-with-tail (burn/push)",
        description="A closed loop can't radiate on its own — no terminal, "
        "no Y_rad port (§2.4) — so this is a loop with a short open tail: "
        "the loop supplies the resonance and the winding sign, the tail is "
        "what the world actually reads. CW pushes the token outward along "
        "the tail and warms it (§2.8). Load scenario 3 for the CCW mirror.",
        strokes=[ScenarioStroke(loop_with_tail_points((0, 0), 80, 40, clockwise=True), THERMAL_INK)],
        drive_hint="SPACE to tap (auto-targets the loop junction, not the tail); watch token velocity direction and rising temperature.",
    ),
    Scenario(
        key="3",
        name="CCW loop-with-tail (chill/pull)",
        description="The exact mirror of scenario 2 — same shape, opposite "
        "winding. Chirality flips sign (§2.8), so the same tap now pulls "
        "the token toward the loop and cools it instead of warming it. "
        "'Ice is what negative thermal coupling looks like' (§2.8).",
        strokes=[ScenarioStroke(loop_with_tail_points((0, 0), 80, 40, clockwise=False), THERMAL_INK)],
        drive_hint="SPACE to tap (auto-targets the loop junction); compare token motion/temperature against scenario 2.",
    ),
    Scenario(
        key="4",
        name="Evanescent tunnel",
        description="Two parallel strokes close enough to couple (§2.7) but "
        "not touching — energy injected in one shows up in the other with "
        "no drawn connection.",
        strokes=[
            ScenarioStroke(line_points((-100, -7), (100, -7), n=24), KINETIC_INK),
            ScenarioStroke(line_points((-100, 8), (100, 8), n=24), KINETIC_INK),
        ],
        drive_hint="SPACE on the first line; watch the shimmer and the second line light up.",
    ),
    Scenario(
        key="5",
        name="Overcharge (nonlinearity)",
        description="A small loop-with-tail whose ink saturates readily "
        "(nl_threshold=1.0, nl_asymmetry=0.35). A quick SPACE tap barely "
        "engages it — the nonlinearity needs a sustained drive at the "
        "loop's own resonance to actually saturate (§2.6), which a single "
        "broadband burst can't deliver.",
        strokes=[ScenarioStroke(loop_with_tail_points((0, 0), 30, 40, clockwise=True), OVERCHARGE_INK)],
        drive_hint="HOLD H — it locks to the loop's own f0 automatically. Watch the node flash "
        "(nonlinearity engaging) and temperature climb faster than a plain resonance would explain.",
    ),
    Scenario(
        key="6",
        name="Phase teleport (displacement)",
        description="A plain open line pointed at the arena wall. Holding H "
        "on an un-looped shape drives a low (kinetic) + high (phase) tone "
        "together — proven to be the minimum needed to actually cross "
        "PHASE_GHOST_THRESHOLD (a single tone alone never does). Phase "
        "ghosts the token while the kinetic component keeps shoving it, so "
        "it passes straight through where the wall would have stopped it.",
        strokes=[ScenarioStroke(line_points((0, 0), (300, 0), n=48), KINETIC_INK)],
        drive_hint="HOLD H and watch the token's phase ring (ghost halo) appear, then "
        "watch it cross the arena boundary without bouncing.",
    ),
    Scenario(
        key="7",
        name="Shield (impedance mismatch)",
        description="Two collinear segments of very different impedance "
        "(20 vs 180) meeting at a point. Most of an incoming pulse "
        "reflects at the junction instead of reaching the far side "
        "(r=(Z2-Z1)/(Z2+Z1), §2.2-2.3) — draw a hard ink underneath a soft "
        "one and the soft one is largely protected.",
        strokes=[
            ScenarioStroke(line_points((-200, 0), (0, 0), n=48), SHIELD_FRONT_INK),
            ScenarioStroke(line_points((0, 0), (200, 0), n=48), SHIELD_BACK_INK),
        ],
        drive_hint="SPACE at the far (low-impedance) end; the low-impedance side keeps most "
        "of the energy, the high-impedance side stays comparatively quiet.",
    ),
    Scenario(
        key="8",
        name="Charge-and-release",
        description="A nearly-closed loop (rad_admittance_fraction=0.05) — "
        "holds a charge instead of leaking it out immediately (§2.4). "
        "Compare against scenario 1's default ink, which discharges "
        "almost immediately after a single tap.",
        strokes=[ScenarioStroke(loop_with_tail_points((0, 0), 60, 40, clockwise=True), CHARGE_INK)],
        drive_hint="HOLD H for ~1-2 seconds to charge it at resonance, then release H and "
        "watch the tail keep glowing/discharging for a while after you stop.",
    ),
    Scenario(
        key="9",
        name="Range/element tradeoff",
        description="A 500px line with heavy high-band damping (a 'fire' "
        "ink). The traveling wave's own brightness is rendered along the "
        "stroke, so watch it visibly die out well before reaching the far "
        "end — measured 98% amplitude loss over this length. Compare "
        "against scenario 1's ink (near-lossless, stays bright edge to "
        "edge) at the same length (§2.5).",
        strokes=[ScenarioStroke(line_points((-250, 0), (250, 0), n=64), FIRE_RANGE_INK)],
        drive_hint="SPACE at one end; watch the bright pulse fade to background color long "
        "before it reaches the other end — a thermal sigil this long is starved by design.",
    ),
]


def scenario_by_key(key: str) -> Scenario | None:
    for s in SCENARIOS:
        if s.key == key:
            return s
    return None
