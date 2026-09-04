"""Headless playtest: drive the whole game with no window and no hands.

Two jobs. The first is crash-hunting — a mode machine plus five enemy types
plus a live wave sim has a lot of edges, and finding them by clicking is
slow. The second, and the reason this file is worth keeping, is that it
measures *balance* the way a player would experience it rather than the way
a spreadsheet would: it plays actual rooms with actual sigils and reports
how long they took and what the sigil was doing at the time.

Run it as:  python -m sigilwave.game.playtest
"""

import os
import functools
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

# Line-buffer stdout so a traceback lands where it happened rather than being
# flushed after every buffered print, which puts it at the top of a redirect
# and makes a crash look like a clean early exit.
print = functools.partial(print, flush=True)  # noqa: A001

from .bands import vulnerability_curve  # noqa: E402
from .combat import resonance_quality  # noqa: E402
from .field import Field, Player  # noqa: E402
from .rooms import room_spec  # noqa: E402
from .shapes import radius_for_band_px, ring_with_tail  # noqa: E402
from .run import Run, from_share_string, share_string  # noqa: E402

DT = 1 / 120.0


class Bot:
    """A deliberately mediocre player: walks toward the nearest enemy, keeps
    its distance, taps on cooldown, and switches focus when the thing it is
    shooting is clearly not responding. It does not know the physics.

    That is the point — if the bot can clear the early rooms, the game is
    learnable without understanding, which is the "not impossibly hard"
    requirement. If the bot stalls on the later ones, the gates are real.
    """

    def __init__(self, field, tier="naive"):
        self.f = field
        self.tier = tier
        self.smart = tier in ("aware", "expert", "wright")
        self.expert = tier in ("expert", "wright")
        self.tap_cd = 0.0
        self.switch_cd = 0.0
        self.venting = False

    def step(self, dt):
        f = self.f
        p = f.player
        if not f.enemies:
            return pygame.Vector2()

        target = min(f.enemies, key=lambda e: (e.pos - p.pos).length())
        to = target.pos - p.pos
        d = to.length()
        if d > 1e-6:
            p.aim = to.normalize()

        # A smart bot picks the focus whose current output best matches the
        # target's vulnerability — the whole game, reduced to one line.
        self.switch_cd -= dt
        if self.smart and self.switch_cd <= 0:
            best, bq = p.active, -1.0
            for i, sig in enumerate(p.foci):
                if sig.is_empty or sig.disabled:
                    continue
                # Judge each instrument by the band its geometry predicts,
                # not by what it happens to have emitted recently. An unused
                # sigil has emitted nothing, and scoring that as a flat
                # spectrum makes every unused sigil look identically mediocre
                # - which is exactly how the bot ended up never once reaching
                # for the heat sigil it was carrying the whole time.
                band = sig.predicted_band
                probe = vulnerability_curve(band) if band is not None else [1.0] * 6
                q = resonance_quality(probe, target.vuln)
                if q > bq:
                    best, bq = i, q
            if best != p.active:
                p.switch(best)
            self.switch_cd = 0.9

        # Both bots move identically except for one thing: the aware one
        # walks *in* on a hot-banded target, because it knows heat does not
        # travel. Everything else is held constant so the comparison measures
        # system knowledge and not pathfinding.
        hot_target = target.resonance >= 3.5 or getattr(target, "kind", "") == "anchor"
        ideal = 120.0 if (self.smart and hot_target) else 260.0
        move = pygame.Vector2()
        if d > ideal + 40:
            move = to.normalize()
        elif d < ideal - 40:
            move = -to.normalize()

        # Every tier dodges: a bot that stands in incoming fire underrates
        # every shooter in the game, and the balance numbers read off it come
        # out systematically pessimistic. Sidestep the nearest closing mote,
        # else shove off anything in contact.
        if p.dash_cd <= 0:
            threat = None
            for q in self.f.hostile:
                off = q.pos - p.pos
                dist = off.length()
                if dist < 150 and off.dot(q.vel) < 0:
                    threat = off
                    break
            if threat is not None and threat.length_squared() > 1e-6:
                p.try_dash(pygame.Vector2(-threat.y, threat.x).normalize())
            elif d < 90:
                p.try_dash(-to.normalize() if d > 1e-6 else pygame.Vector2(1, 0))

        # The naive bot only taps. The aware one sustains when it is holding
        # a hot instrument, because a small ring barely rings from a strike
        # and needs to be driven — which is the single biggest thing a real
        # player has to work out.
        focus = p.focus
        # Sustain anything but a big slow ring. Measured: a 262px ring gives
        # 27 damage from one strike and 112 from three seconds of driving,
        # but a 137px ring gives 6 and 216 - a 33x gap. Small rings store
        # almost nothing, so a strike barely rings them and they have to be
        # *driven*. Threading that as "under 120px" made the bot tap the one
        # instrument that most needed holding.
        hot_rig = (focus is not None and not focus.is_empty and focus.loops
                   and focus.loops[0].circumference < 210)

        if self.expert and hot_rig:
            # The expert difference, and the whole point of the third tier:
            # it does not stop holding at the first sign of char. It drives
            # the ring deep into saturation because that is the only way to
            # make harmonics, waits for the ink to cool, and goes again.
            # Everything a locked Anchor requires is in those two sentences.
            if focus.char > 0.95:
                self.venting = True
            elif focus.char < 0.30:
                self.venting = False
            wants_hold = not self.venting and not focus.disabled
        else:
            wants_hold = (
                self.smart and focus is not None and not focus.is_empty
                and not focus.disabled and focus.char < 0.72 and hot_rig
            )
        if wants_hold:
            p.set_hold(True)
        else:
            if p.holding:
                p.set_hold(False)
            self.tap_cd -= dt
            if self.tap_cd <= 0:
                self.tap_cd = 0.45 if p.try_tap() else 0.15
        return move


def build_for_room(index, run):
    """What a player does between rooms: look at what is in there, and go
    draw a ring the right size for it.

    This is the tier that matters. The first three tiers vary how well the
    bot *operates* what it was handed; this one varies whether it authored
    the right instrument in the first place. If the authoring layer is real,
    this is where the hard rooms open — and if it is not, the Forge is
    decoration and the whole design is wrong.
    """
    from sigilwave.ink import Stroke

    from .bands import BAND_LOOP_PX
    from .enemies import ENEMY_TYPES
    from .inks import CHALK, QUICKSILVER
    from .sigil import Sigil

    spec = room_spec(index)
    probes = []
    for kind, count in spec.get("enemies", {}).items():
        cls = ENEMY_TYPES.get(kind)
        if cls is not None:
            probes.append(cls(pygame.Vector2(0, 0)))
    if not probes:
        return

    # Build for the *wall*, not for the crowd. Tuning to whatever is most
    # numerous is the intuitive move and it is the wrong one: the trash was
    # never the problem, and a player who spends their ink on it arrives at
    # the thing that actually blocks them holding a sigil that cannot touch
    # it. Pick the toughest thing in the room and answer that.
    wall = max(probes, key=lambda e: e.max_hp)
    want = wall.resonance

    # ...and if the wall is phase-locked, its resonance is a decoy. Damage
    # is not what is stopping you, the lock is, and the lock only opens to
    # the top band — which no ring is small enough to ring at directly. The
    # answer is the smallest ring that will parse, driven into saturation
    # until its harmonics reach up there. Understanding that is the whole
    # content of the room.
    if getattr(wall, "kind", "") == "anchor":
        want = 4

    r = radius_for_band_px(BAND_LOOP_PX[int(round(want))])
    ring = ring_with_tail((0, 0), r, max(24.0, r * 0.9), attach_deg=0.0, clockwise=True)
    strokes = [Stroke(points=[pygame.Vector2(q) for q in ring], ink_type=CHALK)]
    # Tip it with a wide-open ink so it actually lets go of what it stores -
    # the composite lesson, applied.
    tip = pygame.Vector2(r + max(24.0, r * 0.9), 0)
    tail = [tip + pygame.Vector2(i * 4.0, 0) for i in range(15)]
    strokes.append(Stroke(points=tail, ink_type=QUICKSILVER))

    built = Sigil(f"Tuned b{int(round(want))}", strokes)
    if len(run.foci) < run.max_foci:
        run.foci.append(built)
    else:
        run.foci[-1] = built


def play_room(index, run, tier="naive", limit=90.0, verbose=False, seed=0):
    # Enemies jitter their own cooldowns and headings from the global RNG, so
    # without seeding here the same room is a different room every run and
    # this stops being a regression test.
    import random as _r

    _r.seed(seed * 1000003 + index)
    if tier == "wright":
        build_for_room(index, run)
    spec = room_spec(index)
    player = Player(pygame.Vector2(0, 0), run.foci)
    player.hp = run.player_hp
    field = Field(player, spec, seed=index * 733 + seed)
    bot = Bot(field, tier)

    t = 0.0
    while t < limit and not field.cleared and not field.failed:
        move = bot.step(DT)
        field.update(DT, move)
        t += DT

    outcome = "CLEAR" if field.cleared else ("DIED" if field.failed else "TIMEOUT")
    if verbose:
        print(f"    enemies left: {[e.label for e in field.enemies]}")
    return outcome, t, player.hp, len(field.friendly), len(field.hostile)


def main():
    pygame.init()
    failures = []

    print("=" * 74)
    print("WAVEWRIGHT headless playtest")
    print("=" * 74)

    # ---------------------------------------------------------------- sanity
    print("\n[1] serialisation round-trip")
    run = Run()
    for sig in run.foci:
        s = share_string(sig)
        back = from_share_string(s)
        same = len(back.graph.edges) == len(sig.graph.edges)
        print(f"    {sig.name:8} -> {len(s):4} chars -> "
              f"{len(back.graph.edges)} edges {'OK' if same else 'MISMATCH'}")
        if not same:
            failures.append(f"share string mismatch for {sig.name}")

    # ------------------------------------------------------------ the rooms
    # Three seeds per room. One run of one room is a coin flip — enemy
    # cooldowns and headings are random — and a balance conclusion drawn
    # from a coin flip is worse than no conclusion.
    SEEDS = (1, 2, 3)

    def sweep(tier, header):
        print(header)
        clears = []
        for i in range(5):
            outs = []
            for sd in SEEDS:
                r = Run()
                r.player_hp = 100.0
                outs.append(play_room(i, r, tier=tier, seed=sd))
            n = sum(1 for o in outs if o[0] == "CLEAR")
            clears.append(n)
            avg_t = sum(o[1] for o in outs) / len(outs)
            avg_hp = sum(max(0.0, o[2]) for o in outs) / len(outs)
            print(f"    room {i + 1} {room_spec(i)['name']:14} cleared {n}/{len(SEEDS)}  "
                  f"avg {avg_t:5.1f}s  hp left {avg_hp:5.1f}")
        return clears

    naive_results = sweep("naive", "\n[2] naive: taps whatever is equipped, never switches focus")
    smart_results = sweep("aware", "\n[3] aware: matches band, closes on hot targets, sustains")
    expert_results = sweep("expert", "\n[4] expert: also overdrives past char, vents, and goes again")
    wright_results = sweep("wright", "\n[5] wright: visits the Forge first and draws a ring for the room")

    # ------------------------------------------------------- the design test
    print("\n[4] does understanding the system actually pay?")
    naive_clears, smart_clears = sum(naive_results), sum(smart_results)
    expert_clears, wright_clears = sum(expert_results), sum(wright_results)
    total = len(naive_results) * 3
    print(f"    naive {naive_clears}/{total}   aware {smart_clears}/{total}   "
          f"expert {expert_clears}/{total}   wright {wright_clears}/{total}")
    for i in range(5):
        prior = max(naive_results[i], smart_results[i], expert_results[i])
        mark = ""
        if wright_results[i] > prior:
            mark = "  <-- DRAWING THE RIGHT SIGIL opens this"
        elif expert_results[i] > max(naive_results[i], smart_results[i]):
            mark = "  <-- overdrive opens this"
        elif smart_results[i] > naive_results[i]:
            mark = "  <-- band matching opens this"
        print(f"      room {i + 1} {room_spec(i)['name']:14} naive {naive_results[i]}/3  "
              f"aware {smart_results[i]}/3  expert {expert_results[i]}/3  "
              f"wright {wright_results[i]}/3{mark}")
    if naive_results[0] < 3:
        failures.append("room 1 is not reliably clearable without understanding anything")
    if naive_clears < 4:
        failures.append("naive play is too weak - the opening is not forgiving enough")
    # Deliberately not asserting that the wright tier beats the expert tier.
    # Both carry an instrument that can answer the room; past that point the
    # result turns on target priority, and these bots all pick the nearest
    # enemy. That is a statement about the bots, not about the game, and
    # writing it in as a pass condition would only invite tuning the game to
    # satisfy a bad bot. The claims worth asserting are the two gates below.
    if wright_clears < 12:
        failures.append(f"even a matched sigil only clears {wright_clears}/15 - too punishing")
    # Room 2's gate is graded on cost, not on clears. Once the right tool is
    # three or four times better rather than merely possible, a determined
    # player *can* grind a Ward down with the wrong band - and should be able
    # to. What must stay true is that it hurts: see the health comparison the
    # sweep prints. Asserting "naive cannot clear room 2" would be asserting
    # that the second room of the game is a hard wall, which is not the
    # design and would be a bad one.
    if max(naive_results[4], smart_results[4]) > 0 and expert_results[4] == 0:
        failures.append("the Anchor falls to grinding but not to overdrive - lock is inverted")

    # --------------------------------------------------------------- gating
    # ------------------------------------------------ the anti-brute-force rule
    # The single most important assertion in this file. Before glut existed,
    # a wrong-band hit was merely weak, weak is survivable, and so every gate
    # in the game was advisory — a player could grind anything down with
    # their opening sigil and never engage with the system at all. Both
    # directions get checked, because the failure modes are opposite and both
    # are silent: too lenient and brute force reopens, too strict and correct
    # play starts feeding the enemies it is beating.
    print("\n[5] glut: does the wrong band make things WORSE?")
    from .combat import Pulse as _P
    from .enemies import Cinder as _C, Ward as _W
    from .starters import shove, spark
    import sigilwave.game.library as _lib

    rows = []
    for tname, tfac, tband in (("Shove  (band 1)", shove, 1),
                               ("Needle (band 3.5)", _lib.BY_NAME["Needle"], 4)):
        for ename, ecls, eband in (("Cinder b1", _C, 1), ("Ward b4", _W, 4)):
            e = ecls(pygame.Vector2(0, 0))
            sig = tfac()
            sig.set_hold(True)
            for _ in range(500):
                for em in sig.advance(0.01):
                    e.take_pulse(
                        _P((0, 0), (1, 0), em.bands, em.kinetic_sign, em.thermal_sign), [])
            frac = max(0.0, e.hp) / e.max_hp
            correct = tband == eband
            rows.append((correct, frac, e.surges))
            print(f"    {tname:18} vs {ename:10} -> hp {frac * 100:5.1f}%  "
                  f"surges {e.surges:3}   {'(correct)' if correct else '(WRONG BAND)'}")

    if any(surges > 0 for correct, _f, surges in rows if correct):
        failures.append("correct-band fire is feeding enemies - glut threshold too strict")
    if any(f > 0.02 for correct, f, _s in rows if correct):
        failures.append("the correct band does not reliably kill")
    if any(f < 0.5 for correct, f, _s in rows if not correct):
        failures.append("the wrong band still grinds enemies down - brute force is open")
    if not any(s > 0 for correct, _f, s in rows if not correct):
        failures.append("wrong-band fire never triggers a surge - glut is inert")

    print("\n[6] band gating: right tool vs wrong tool, measured")
    from .enemies import Anchor, Cinder, Ward

    for ecls in (Cinder, Ward, Anchor):
        row = []
        for name, fac in (("Shove", shove), ("Spark", spark)):
            e = ecls(pygame.Vector2(0, 0))
            sig = fac()
            sig.tap()
            dmg = 0.0
            for _ in range(360):
                for em in sig.advance(0.01):
                    from .combat import Pulse

                    q = Pulse((0, 0), (1, 0), em.bands, em.kinetic_sign, em.thermal_sign)
                    dmg += q.damage_against(e.vuln)
            row.append((name, dmg, dmg / e.max_hp * 100))
        ratio = row[0][1] / max(row[1][1], 1e-9)
        print(f"    {ecls.__name__:8} (band {ecls(pygame.Vector2()).resonance:.0f}): "
              + "  ".join(f"{n}={d:7.1f} ({pc:5.1f}% hp)" for n, d, pc in row)
              + f"   ratio {ratio:6.2f}x")

    # --------------------------------------------------- the deepest gate
    # Content gated behind a mechanic is only good design if the mechanic
    # demonstrably opens it. The Anchor is locked behind the top band, which
    # is reachable only by driving a small ring into saturation. If a low
    # band could brute-force the lock the gate would be a lie; if the hot
    # band could not open it the gate would be a wall. Both failure modes
    # are silent from the inside, so they get a permanent test.
    print("\n[6] the phase gate: is it a lock, and is there a key?")
    from .combat import AIR_SURVIVAL, Pulse
    from .enemies import Anchor as _Anchor

    gate = {}
    for label, fac in (("low band (Shove, held 4s)", shove),
                       ("hot band (Spark, held 4s)", spark)):
        sig = fac()
        a = _Anchor(pygame.Vector2(0, 0))
        a.base_speed = 0
        sig.set_hold(True)
        ems = []
        for _ in range(400):
            ems += sig.advance(0.01)
        flight = 120 / 620.0
        for em in ems:
            bands = [b * (AIR_SURVIVAL[i] ** flight) for i, b in enumerate(em.bands)]
            a.take_pulse(Pulse((0, 0), (1, 0), bands, em.kinetic_sign, em.thermal_sign), [])
            a.phase = max(0.0, a.phase - 0.7 * 0.004)
        gate[label] = (a.phase, a.hp)
        print(f"    {label}: phase {a.phase:.2f}  hp {a.max_hp:.0f} -> {a.hp:6.1f}  "
              f"char {sig.char:.2f}  {'UNLOCKED' if a.phase > 0.5 else 'locked'}")

    if gate["low band (Shove, held 4s)"][0] > 0.5:
        failures.append("low band opens the phase lock - the gate is not a gate")
    if gate["hot band (Spark, held 4s)"][0] <= 0.5:
        failures.append("the hot band cannot open the phase lock - the gate is a wall")
    if gate["hot band (Spark, held 4s)"][1] > 340 * 0.6:
        failures.append("even unlocked, the Anchor barely takes damage")

    # ------------------------------------------------------------- perf
    print("\n[7] frame cost with a full room running")
    import time

    run3 = Run()
    player = Player(pygame.Vector2(0, 0), run3.foci)
    field = Field(player, room_spec(4), seed=1)
    bot = Bot(field, "expert")
    player.set_hold(True)
    for _ in range(240):
        field.update(DT, bot.step(DT))
    t0 = time.perf_counter()
    N = 600
    for _ in range(N):
        field.update(DT, bot.step(DT))
    el = (time.perf_counter() - t0) / N
    budget = DT
    print(f"    {el * 1000:.3f} ms/step   ({el / budget * 100:.1f}% of a {budget*1000:.1f}ms step)")
    print(f"    live: {len(field.enemies)} enemies, {len(field.friendly)} friendly, "
          f"{len(field.hostile)} hostile pulses")
    if el > budget * 0.75:
        failures.append(f"sim step too slow: {el*1000:.2f}ms vs {budget*1000:.2f}ms budget")

    # --------------------------------------------------------------- verdict
    print("\n" + "=" * 74)
    if failures:
        print(f"{len(failures)} PROBLEM(S):")
        for f in failures:
            print("  - " + f)
    else:
        print("no problems found")
    print("=" * 74)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
