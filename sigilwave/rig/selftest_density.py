"""The go/no-go. RIGS.md 12 and 14.

Two questions, and either one is allowed to kill the design. They are asked
here rather than argued about, because the whole point of building the
evaluator headless first was to be able to ask them for a day's work instead
of a month's.

**Test 1, density.** Ten chains that produce ten nameable, meaningfully
different results, using only the eleven modules and touching no transform
code. If a twelfth module is needed to reach ten results, the vocabulary is
wrong and no amount of art will fix it.

**Test 2, solution diversity.** RIGS.md 14's real metric, and the one that
separates a system from a puzzle. CAMPANARY's harness measured `masher 2/33 ->
founder 31/33` and called it success, which proves one correct answer exists
and that knowledge finds it -- the shape of a puzzle. The question that
matters is different: for one task, how many STRUCTURALLY DIFFERENT machines
solve it, and how far apart are they in cost? A system where one build wins is
decoration with extra steps.

Both are measured by search rather than by listing chains chosen to pass,
which would prove nothing. The search touches no transform code and invents no
module.

Run:  python -m sigilwave.rig.selftest_density
"""

import itertools
import random
import time

from .chain import Chain, ambient_at
from .modules import ORDER

_passed = 0
_failed = []


def check(name, condition, detail=""):
    global _passed
    if condition:
        _passed += 1
        print(f"  ok   {name}")
    else:
        _failed.append((name, detail))
        print(f"  FAIL {name}   {detail}")


def _report(name, value, unit=""):
    print(f"       {name}: {value}{unit}")


# The body of a chain. INTAKE and PORT are the brackets and are always present,
# because a chain without them is one of the four failures rather than a
# machine, and "it does nothing" is not an interesting outcome class.
BODY = tuple(k for k in ORDER if k not in ("INTAKE", "PORT"))


def _bucket(v, edges):
    """Discretise a measured output. Coarse on purpose: two machines that
    differ by a tenth of a degree are the same machine, and counting them
    separately would inflate the density number into meaninglessness."""
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def signature(chain, result):
    """What this machine DOES, coarsely enough that only real differences count.

    Deliberately built from measured outputs rather than from the modules
    used, so two different chains that do the same thing collapse to one class
    -- which is the conservative direction. An outcome class here is a thing a
    player could name.
    """
    if result.fault:
        return ("fault", result.fault.kind)
    return (
        chain.name(result),
        _bucket(result.delta_temp, (-8.0, -1.5, 1.5, 8.0, 30.0)),
        _bucket(result.out_speed, (0.5, 6.0, 20.0)),
        _bucket(result.out_acoustic, (1.0, 1e3, 1e4)),
        _bucket(result.ledger.tank_gas, (1e-4, 1.0, 40.0)),
        _bucket(result.ledger.heat_to_ocean, (1.0, 1e6, 1e7)),
        bool(result.tore),
    )


def _search(depth, max_body, samples, seed):
    """Every short chain exhaustively, then a random sample of longer ones.

    Exhaustive up to three body modules is 9 + 81 + 729 chains and costs
    nothing; past that the space is too big to enumerate and a sample is the
    honest answer. The seed is fixed so the numbers in this file are
    reproducible.

    `max_body` reaches 12 rather than 7 for a reason the first run found: IT
    BOILS takes ten squeezes and IT FREEZES takes a comparable run of
    expansions, so a search capped at seven modules reported that a
    well-formed machine could only ever stall. The failures were reachable all
    along; the search simply could not see that far.
    """
    amb = ambient_at(depth)
    seen = {}
    order = []

    def consider(kinds):
        chain = Chain(("INTAKE",) + tuple(kinds) + ("PORT",))
        r = chain.evaluate(amb)
        sig = signature(chain, r)
        if sig not in seen:
            seen[sig] = (chain, r)
            order.append(sig)
        return sig

    for n in range(1, 4):
        for kinds in itertools.product(BODY, repeat=n):
            consider(kinds)

    rng = random.Random(seed)
    for _ in range(samples):
        n = rng.randint(4, max_body)
        consider(tuple(rng.choice(BODY) for _ in range(n)))

    return seen, order, amb


# --- test 1 -----------------------------------------------------------------


def test_density():
    print("\n[1] TEST 1 -- ten nameable, meaningfully different results")
    t0 = time.time()
    seen, order, amb = _search(depth=200.0, max_body=12, samples=20000, seed=4242)
    elapsed = time.time() - t0

    working = {s: v for s, v in seen.items() if s[0] != "fault"}
    check("at least ten distinct outcome classes are reachable",
          len(working) >= 10,
          f"found {len(working)} working classes")
    # Every chain in this search is bracketed by INTAKE and PORT on purpose,
    # so IT DOES NOTHING cannot arise here -- it is a missing bracket, which
    # `selftest_conservation` covers. What this search can reach is the three
    # failures a WELL-FORMED machine can still commit, and it must reach all
    # of them or the vocabulary cannot express its own mistakes.
    # Probed rather than sampled, and the first version got this wrong in an
    # instructive way. IT BOILS takes eleven consecutive SQUEEZEs and IT
    # FREEZES nine consecutive EXPANDs; a uniform random search over nine
    # module kinds hits a specific run of eleven with probability 9^-11, so it
    # reported that a well-formed machine could only ever stall. The failures
    # were always reachable -- random search is simply the wrong instrument
    # for finding a needle you already know the shape of.
    probes = {}
    for kind in BODY:
        for n in range(1, 15):
            chain = Chain(("INTAKE",) + (kind,) * n + ("PORT",))
            r = chain.evaluate(amb)
            if r.fault:
                probes.setdefault(r.fault.kind, (kind, n))
    faults = set(probes) | {s[1] for s in seen if s[0] == "fault"}
    check("a well-formed machine can still boil, freeze and stall",
          faults >= {"IT BOILS", "IT FREEZES", "IT STALLS"},
          f"reached {sorted(faults)}")
    for kind, (mod_kind, n) in sorted(probes.items()):
        _report(f"{kind} first reached by", f"{n} x {mod_kind}")

    _report("water at 200 m", f"{amb.temp:.1f} C, {amb.pressure:.0f} bar")
    _report("chains examined", f"{len(order) + 20000}")
    _report("distinct working outcome classes", len(working))
    _report("distinct failure classes", len(seen) - len(working))
    _report("search time", f"{elapsed:.1f} s")

    print("\n       one example per class, shortest found:")
    rows = []
    for sig, (chain, r) in working.items():
        rows.append((len(chain), chain, r, sig))
    rows.sort(key=lambda t: (t[3][0], t[0]))
    shown = set()
    for _, chain, r, sig in rows:
        if sig[0] in shown and len(shown) >= 14:
            continue
        shown.add(sig[0])
        body = " ".join(k for k in chain.kinds() if k not in ("INTAKE", "PORT"))
        print(f"         {chain.name(r):<14s} {body:<44s} "
              f"dT{r.delta_temp:+7.1f}  v{r.out_speed:5.1f}  "
              f"gas{r.ledger.tank_gas:7.1f}  {r.cost:8.2f}u")

    names = sorted({s[0] for s in working})
    _report("distinct machine names", f"{len(names)} -- {', '.join(names)}")


# --- test 2 -----------------------------------------------------------------


COLD_TARGET = -8.0
TASK_DEPTH = 200.0


def test_solution_diversity():
    """RIGS.md 14. The metric that separates a system from a puzzle."""
    print("\n[2] TEST 2 -- how many different machines solve ONE task")
    print(f"       task: deliver water at least {-COLD_TARGET:.0f} C colder "
          f"than ambient at {TASK_DEPTH:.0f} m")

    amb = ambient_at(TASK_DEPTH)
    rng = random.Random(90210)
    solutions = {}
    examined = 0

    def consider(kinds):
        nonlocal examined
        examined += 1
        chain = Chain(("INTAKE",) + tuple(kinds) + ("PORT",))
        r = chain.evaluate(amb)
        if not r.runs or r.delta_temp > COLD_TARGET:
            return
        # Structurally different means a different BAG of modules, not a
        # reordering. Reorderings are counted separately below, because "does
        # order matter" and "are there different builds" are two questions and
        # conflating them would flatter the result.
        shape = tuple(sorted(kinds))
        if shape not in solutions or len(chain) < len(solutions[shape][0]):
            solutions[shape] = (chain, r)

    t0 = time.time()
    for n in range(1, 4):
        for kinds in itertools.product(BODY, repeat=n):
            consider(kinds)
    while time.time() - t0 < 25.0:
        n = rng.randint(4, 7)
        consider(tuple(rng.choice(BODY) for _ in range(n)))
    elapsed = time.time() - t0

    check("more than one structurally different machine solves it",
          len(solutions) >= 2, f"found {len(solutions)}")
    check("and there are genuinely many", len(solutions) >= 8,
          f"found {len(solutions)} -- a system where one build wins is "
          f"decoration with extra steps")

    costs = sorted(r.cost for _, r in solutions.values())
    if costs:
        spread = costs[-1] / max(costs[0], 1e-9)
        check("they are not all the same price", spread > 2.0,
              f"cheapest {costs[0]:.2f}u, dearest {costs[-1]:.2f}u")
        _report("chains examined", examined)
        _report("structurally distinct solutions", len(solutions))
        _report("cost range", f"{costs[0]:.2f} to {costs[-1]:.2f} units "
                              f"({spread:.1f}x spread)")
        _report("search time", f"{elapsed:.1f} s")

        print("\n       the ten cheapest solutions:")
        best = sorted(solutions.values(), key=lambda t: t[1].cost)[:10]
        for chain, r in best:
            body = " ".join(k for k in chain.kinds()
                            if k not in ("INTAKE", "PORT"))
            print(f"         {r.cost:8.2f}u  dT{r.delta_temp:+7.2f}  {body}")


def test_order_matters():
    """The claim RIGS.md 6 rests on, measured rather than asserted.

    If the same bag of modules in different orders gives the same result, the
    list is a set and the whole reading-order argument collapses.
    """
    print("\n[3] the same modules in a different order are a different machine")
    amb = ambient_at(TASK_DEPTH)
    bag = ("SQUEEZE", "COIL", "EXPAND")
    outcomes = {}
    for perm in itertools.permutations(bag):
        chain = Chain(("INTAKE",) + perm + ("PORT",))
        r = chain.evaluate(amb)
        outcomes[perm] = (chain.name(r), r.delta_temp, r.cost)

    names = {v[0] for v in outcomes.values()}
    temps = [v[1] for v in outcomes.values()]
    check("one bag of three modules gives more than one machine",
          len(names) >= 2, f"names {sorted(names)}")
    check("and the spread in what they do is large",
          max(temps) - min(temps) > 5.0,
          f"{min(temps):+.2f} to {max(temps):+.2f} C")
    for perm, (name, dT, cost) in outcomes.items():
        _report(" ".join(perm), f"{name:<14s} dT{dT:+7.2f}  {cost:7.2f}u")

    # The stronger version: the cascade's own try_this claim.
    good = Chain(("INTAKE", "SQUEEZE", "COIL", "SQUEEZE", "COIL",
                  "EXPAND", "EXPAND", "PORT")).evaluate(amb)
    bad = Chain(("INTAKE", "SQUEEZE", "SQUEEZE", "EXPAND", "EXPAND",
                 "COIL", "COIL", "PORT")).evaluate(amb)
    check("interleaved coils beat coils moved to the end",
          good.delta_temp < bad.delta_temp - 3.0,
          f"{good.delta_temp:+.2f} C vs {bad.delta_temp:+.2f} C")
    _report("cascade, coils between", f"{good.delta_temp:+.2f} C")
    _report("cascade, coils at the end", f"{bad.delta_temp:+.2f} C")


def test_the_vocabulary_is_not_padded():
    """The inverse check, and the one that would embarrass the design.

    If a module can be deleted from the vocabulary without losing any outcome
    class, it is not pulling its weight and RIGS.md 5's claim that eleven is
    the right number is wrong.
    """
    print("\n[4] every module earns its place")
    amb = ambient_at(TASK_DEPTH)
    rng = random.Random(1337)

    def classes(allowed):
        seen = set()
        for n in range(1, 4):
            for kinds in itertools.product(allowed, repeat=n):
                chain = Chain(("INTAKE",) + kinds + ("PORT",))
                seen.add(signature(chain, chain.evaluate(amb)))
        for _ in range(1500):
            kinds = tuple(rng.choice(allowed) for _ in range(rng.randint(4, 6)))
            chain = Chain(("INTAKE",) + kinds + ("PORT",))
            seen.add(signature(chain, chain.evaluate(amb)))
        return seen

    full = classes(BODY)
    dead = []
    for drop in BODY:
        reduced = tuple(k for k in BODY if k != drop)
        lost = len(full) - len(full & classes(reduced))
        if lost == 0:
            dead.append(drop)
        _report(f"without {drop}", f"{lost} outcome classes become unreachable")
    check("no module can be removed without losing something", not dead,
          f"dead weight: {dead}")


def main():
    print("=" * 72)
    print("RIGS -- the go/no-go (RIGS.md 12, 14)")
    print("=" * 72)
    test_density()
    test_solution_diversity()
    test_order_matters()
    test_the_vocabulary_is_not_padded()

    print("\n" + "=" * 72)
    total = _passed + len(_failed)
    print(f"{_passed}/{total} checks passed")
    for name, detail in _failed:
        print(f"  FAILED: {name}  {detail}")
    print("=" * 72)
    return 0 if not _failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
