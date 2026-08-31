"""Stage 5 (§9): terminals radiate, the analyzer turns that into band
energy, the coupler turns that into a kinetic drive. Checks the pipeline
numerically, independent of any rendering.

Run with:

    python -m sigilwave.sim.selftest_terminal
"""

import pygame

from ..ink import DEFAULT_INK, Stroke
from .compiler import compile_graph
from .coupling import kinetic_drive_from_bands
from .filterbank import FilterBank
from .network import raised_cosine_burst
from .parser import parse_strokes


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def test_open_stroke_terminals_get_real_radiation() -> None:
    dx = 4.0
    stroke = Stroke(points=[pygame.Vector2(0, 0), pygame.Vector2(400, 0)], ink_type=DEFAULT_INK)
    graph = parse_strokes([stroke], dx)
    net = compile_graph(graph, dx)

    terminals = [nid for nid, n in graph.nodes.items() if n.is_terminal]
    check("open stroke has two terminals", len(terminals) == 2)
    check(
        "both terminals got nonzero Y_rad from the ink (not the old free-end default)",
        all(net.nodes[t].rad_admittance > 0 for t in terminals),
    )


def test_terminal_radiation_drives_kinetic_band() -> None:
    dx = 4.0
    stroke = Stroke(points=[pygame.Vector2(0, 0), pygame.Vector2(400, 0)], ink_type=DEFAULT_INK)
    graph = parse_strokes([stroke], dx)
    net = compile_graph(graph, dx)

    terminals = [nid for nid, n in graph.nodes.items() if n.is_terminal]
    inject_id, listen_id = terminals[0], terminals[1]

    bank = FilterBank()
    burst = raised_cosine_burst(24, amplitude=1.0)

    total_radiated = 0.0
    peak_drive = 0.0
    for i in range(3000):
        injections = {inject_id: burst[i]} if i < len(burst) else {}
        radiated = net.step(injections)
        total_radiated += radiated

        sample = net.nodes[listen_id].last_emitted
        bands = bank.process(sample)
        drive = kinetic_drive_from_bands(bands)
        peak_drive = max(peak_drive, drive)

    check(f"some energy actually radiated over the run (total={total_radiated:.5f})", total_radiated > 0)
    check(f"kinetic drive at the far terminal peaks above zero (peak={peak_drive:.6f})", peak_drive > 1e-6)


def main() -> None:
    for test in [test_open_stroke_terminals_get_real_radiation, test_terminal_radiation_drives_kinetic_band]:
        test()
    print("\n2 checks passed.")


if __name__ == "__main__":
    main()
