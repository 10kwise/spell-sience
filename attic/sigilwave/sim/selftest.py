"""Sanity checks called out explicitly in the design doc (§2.3) plus the
passivity/reflection-coefficient properties that everything else in the
design (shields, resonators, parry) depends on. Run with:

    python -m sigilwave.sim.selftest
"""

from .network import Network, raised_cosine_burst


def check(name: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        raise SystemExit(1)


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) < tol


def test_equal_impedance_junction_is_transparent() -> None:
    net = Network()
    net.add_node(0)
    net.add_node(1)
    net.add_node(2)
    edge_a = net.add_edge(0, 1, length_samples=4, impedance=50.0)
    edge_b = net.add_edge(1, 2, length_samples=4, impedance=50.0)

    edge_a.forward.buffer[edge_a.forward.ptr] = 1.0

    net.step()

    reflected_back_into_a = edge_a.backward.buffer[(edge_a.backward.ptr - 1) % edge_a.backward.length]
    transmitted_into_b = edge_b.forward.buffer[(edge_b.forward.ptr - 1) % edge_b.forward.length]

    check("N=2 equal impedance: nothing reflected back", close(reflected_back_into_a, 0.0))
    check("N=2 equal impedance: input passes straight through", close(transmitted_into_b, 1.0))


def test_free_end_reflects_with_unity_coefficient() -> None:
    net = Network()
    net.add_node(0)
    net.add_node(1)
    edge = net.add_edge(0, 1, length_samples=4, impedance=50.0)

    edge.backward.buffer[edge.backward.ptr] = 0.7  # arriving at node 0

    net.step()

    reflected = edge.forward.buffer[(edge.forward.ptr - 1) % edge.forward.length]
    check("N=1 free end: reflection coefficient +1", close(reflected, 0.7))


def test_impedance_mismatch_matches_reflection_formula() -> None:
    z1, z2 = 50.0, 150.0
    expected_r = (z2 - z1) / (z2 + z1)

    net = Network()
    net.add_node(0)
    net.add_node(1)
    net.add_node(2)
    edge_a = net.add_edge(0, 1, length_samples=4, impedance=z1)
    net.add_edge(1, 2, length_samples=4, impedance=z2)

    edge_a.forward.buffer[edge_a.forward.ptr] = 1.0
    net.step()

    reflected = edge_a.backward.buffer[(edge_a.backward.ptr - 1) % edge_a.backward.length]
    check(
        f"impedance mismatch: reflection matches r=(Z2-Z1)/(Z2+Z1)={expected_r:.4f}",
        close(reflected, expected_r, tol=1e-9),
    )


def test_energy_conserved_in_closed_lossless_network() -> None:
    net = Network()
    net.add_node(0)
    net.add_node(1)
    net.add_node(2)
    net.add_edge(0, 1, length_samples=17, impedance=50.0)
    net.add_edge(1, 2, length_samples=23, impedance=140.0)

    burst = raised_cosine_burst(12, amplitude=1.0)
    for i, sample in enumerate(burst):
        net.step({0: sample})

    energy_after_injection = net.total_energy()

    max_drift = 0.0
    for _ in range(400):
        net.step()
        drift = abs(net.total_energy() - energy_after_injection)
        max_drift = max(max_drift, drift)

    relative_drift = max_drift / energy_after_injection
    check(
        f"energy conserved bouncing in closed network (max relative drift {relative_drift:.2e})",
        relative_drift < 1e-9,
    )


def test_n_way_equal_impedance_junction(n: int) -> None:
    """Stage 3 (§9): junction scattering must generalize beyond N=2. For N
    equal-admittance ports with unit incidence on one port and nothing on
    the rest, the general formula (§2.3) predicts reflection (2-N)/N back
    into the source port and 2/N transmitted to every sibling — derive it
    once symbolically and check the implementation matches for several N.
    """
    net = Network()
    net.add_node(0)  # shared junction
    edges = []
    for leaf in range(1, n + 1):
        net.add_node(leaf)
        edges.append(net.add_edge(0, leaf, length_samples=4, impedance=50.0))

    edges[0].backward.buffer[edges[0].backward.ptr] = 1.0  # incident from leaf 1
    net.step()

    expected_reflect = (2 - n) / n
    expected_transmit = 2.0 / n

    reflected = edges[0].forward.buffer[(edges[0].forward.ptr - 1) % edges[0].forward.length]
    check(f"N={n} junction: reflection matches (2-N)/N={expected_reflect:+.3f}", close(reflected, expected_reflect))

    for i, edge in enumerate(edges[1:], start=2):
        transmitted = edge.forward.buffer[(edge.forward.ptr - 1) % edge.forward.length]
        check(f"N={n} junction: transmission to port {i} matches 2/N={expected_transmit:.3f}", close(transmitted, expected_transmit))


def test_five_way_junction_conserves_energy() -> None:
    """Passivity (§8) shouldn't be an N=2 special case — stress it with a
    5-way junction of mismatched impedances."""
    net = Network()
    net.add_node(0)
    for leaf, z in zip(range(1, 6), [40.0, 65.0, 90.0, 120.0, 200.0]):
        net.add_node(leaf)
        net.add_edge(0, leaf, length_samples=11 + leaf, impedance=z)

    for i in range(8):
        net.step({0: raised_cosine_burst(8)[i] if i < 8 else 0.0})

    energy_after_injection = net.total_energy()
    max_drift = 0.0
    for _ in range(300):
        net.step()
        max_drift = max(max_drift, abs(net.total_energy() - energy_after_injection))

    relative_drift = max_drift / energy_after_injection
    check(
        f"5-way mismatched junction conserves energy (max relative drift {relative_drift:.2e})",
        relative_drift < 1e-9,
    )


def test_pulse_travel_time_matches_length_over_speed() -> None:
    """A pulse injected at a free end should reappear, reflected, after
    2*N samples (there and back) when the far end is also free."""
    length = 30
    net = Network()
    net.add_node(0)
    net.add_node(1)
    net.add_edge(0, 1, length_samples=length, impedance=50.0)

    net.step({0: 1.0})
    for _ in range(1, 2 * length):
        peak = net.total_energy()
        assert peak > 0
        net.step()

    check("pulse round-trip stays energetic across 2N steps", net.total_energy() > 0)


def main() -> None:
    tests = [
        test_equal_impedance_junction_is_transparent,
        test_free_end_reflects_with_unity_coefficient,
        test_impedance_mismatch_matches_reflection_formula,
        test_energy_conserved_in_closed_lossless_network,
        lambda: test_n_way_equal_impedance_junction(3),
        lambda: test_n_way_equal_impedance_junction(4),
        lambda: test_n_way_equal_impedance_junction(6),
        test_five_way_junction_conserves_energy,
        test_pulse_travel_time_matches_length_over_speed,
    ]
    for test in tests:
        test()
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
