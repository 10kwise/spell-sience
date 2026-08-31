"""Headless balance and regression harness.

    python -m sigilwave.campanary.playtest

Four bots of increasing understanding play every wave in the game. The point
is not to check that the game can be beaten - it is to check that the gates
are **real**, which is the exact thing the old build could not demonstrate
about itself and the exact reason it could be brute-forced.

If a masher who ignores the note, the beat and the range clears the same
rooms as somebody who tunes, then the system is decoration and the numbers
need to move. That claim is now something this file either proves or fails.
"""

import math
import sys

import pygame

from sigilwave.ink import Stroke

from . import audio, notes, shapes
from .arena import Belfry, Player
from .bell import Bell
from .foes import GreatBell, Overtone, Twin
from .metals import BRONZE
from .run import WAVES, spec_for
from .starters import starting_bells

DT = 1 / 120.0


def bell_for(note, name=None):
    return Bell(name or notes.NOTE_NAMES[note].title(),
                [Stroke(points=shapes.ring_for_note(note), ink_type=BRONZE)])


class Bot:
    """A player made of rules, each rule one thing a person could know."""

    name = "bot"
    knows_beat = False
    knows_note = False
    knows_range = False
    can_cast = False
    can_swell = False

    def __init__(self):
        self.hold_t = 0.0

    def loadout(self, spec):
        return starting_bells()

    # ------------------------------------------------------------- playing

    def act(self, belfry):
        p = belfry.player
        foe = self._target(belfry)
        move = pygame.Vector2(0, 0)
        swap = None
        strike = False
        hold = False
        dash = False

        if foe is not None:
            to = foe.pos - p.pos
            d = to.length()

            if self.knows_note:
                swap = self._pick_bell(p, foe)
            bell = p.bells[swap if swap is not None else p.active]

            want = bell.reach * 0.55 if self.knows_range else 300.0
            if bell.is_empty or not bell.has_loop:
                want = 220.0

            # A bonded pair is not killed, it is taken apart - so stand
            # between them, where one ring pushes both outward along their
            # own line. Without this the bot simply tolled at something that
            # cannot be cracked until the clock ran out, which measures the
            # bot's blind spot rather than the game's difficulty.
            hold = None
            if self.knows_note and isinstance(foe, Twin) and foe.bonded:
                hold = (foe.pos + foe.bond.pos) * 0.5
            if hold is not None:
                gap = hold - p.pos
                if gap.length() > 40.0:
                    move = gap.normalize()
                else:
                    move = pygame.Vector2(0, 0)
            elif d > want and d > 1e-6:
                move = to / d
            elif d < want * 0.45 and d > 1e-6:
                move = -to / d

            # Dodge a committed wind-up. Everything in the game telegraphs
            # on its own note's clock, so a bot that reads the closing ring
            # is modelling a competent player rather than an omniscient one.
            for f in belfry.foes:
                if f.wind > 0.55 and (f.pos - p.pos).length() < 380.0:
                    dash = True
                    away = p.pos - f.pos
                    if away.length_squared() > 1e-9:
                        move = away.normalize()
                    break
            for w in belfry.waves:
                gap = (p.pos - w["pos"]).length() - w["r"]
                if 0.0 < gap < 120.0:
                    dash = True
                    away = p.pos - w["pos"]
                    if away.length_squared() > 1e-9:
                        move = away.normalize()
                    break

            if self.can_swell and isinstance(foe, Overtone) and d < 260.0:
                # Swell for about as long as the climb takes, then let go.
                # A bot that holds forever never fires, which is also the
                # mistake a new player makes exactly once.
                self.hold_t += DT
                hold = self.hold_t < 1.5
                if p.bell is not None and p.bell.char > 0.8:
                    hold = False
                if not hold:
                    self.hold_t = -0.5
            elif self._in_range(p, foe) or (
                    isinstance(foe, Twin) and foe.bonded):
                self.hold_t = 0.0
                if self.knows_beat:
                    strike = p.bell is not None and p.bell.on_beat()
                else:
                    strike = True

        if self.knows_note:
            answer = self._answer(belfry)
            if answer is not None:
                swap, strike = answer, True

        return move, strike, hold, dash, swap

    def _target(self, belfry):
        p = belfry.player
        best, bd = None, 1e18
        for f in belfry.foes:
            d = (f.pos - p.pos).length_squared()
            # Go for something you can actually hurt first.
            if isinstance(f, Twin) and f.bonded:
                d *= 4.0
            if d < bd:
                best, bd = f, d
        return best

    def _in_range(self, p, foe):
        b = p.bell
        if b is None or b.is_empty:
            return False
        d = (foe.pos - p.pos).length()
        return d <= (b.reach if self.knows_range else 1e9)

    def _pick_bell(self, p, foe):
        if not foe.crackable:
            # Nothing rings dead metal, so bring the biggest shove there is.
            return max(range(len(p.bells)),
                       key=lambda i: p.bells[i].reach if p.bells[i].has_loop else 0)
        best, score = p.active, -1e9
        for i, b in enumerate(p.bells):
            if b.is_empty or not b.has_loop or b.cracked:
                continue
            s = -abs(b.note - foe.note)
            if s > score:
                best, score = i, s
        return best

    def _answer(self, belfry):
        """Meet an incoming toll with the same note."""
        p = belfry.player
        for r in belfry.hostile:
            gap = (r.origin - p.pos).length() - r.r
            if not (40.0 < gap < 190.0):
                continue
            for i, b in enumerate(p.bells):
                if b.has_loop and abs(b.note - r.note) < 0.5 and not b.cracked:
                    return i
        return None


class Masher(Bot):
    name = "masher: one bell, no beat, no range, no idea"


class Ringer(Bot):
    name = "ringer: plays on the beat, still one bell"
    knows_beat = True


class Tuner(Bot):
    name = "tuner: swaps to the matching note and closes to its reach"
    knows_beat = True
    knows_note = True
    knows_range = True


class Founder(Tuner):
    name = "founder: also casts a bell for the room, and swells for the octave"
    can_cast = True
    can_swell = True

    def loadout(self, spec):
        from .run import notes_in
        want = [n for n in notes_in(spec) if n >= 0]
        bells = starting_bells()
        have = {round(b.note) for b in bells if b.has_loop}
        for n in want:
            if n in have or n >= 4:
                continue
            if len(bells) < 3:
                bells.append(bell_for(n))
                have.add(n)
            else:
                bells[-1] = bell_for(n)
                have.add(n)
        return bells


def play(bot, spec, seed, limit=95.0):
    limit = 120.0 if 'greatbell' in spec.get('foes', {}) else limit
    bells = bot.loadout(spec)
    player = Player(pygame.Vector2(0, 0), bells)
    b = Belfry(player, spec, seed=seed)
    t = 0.0
    while t < limit and not b.cleared and not b.failed:
        move, strike, hold, dash, swap = bot.act(b)
        b.update(DT, move, strike, hold, dash, swap)
        t += DT
    return b.cleared, round(t, 1), round(max(0.0, player.hp), 1)


def main():
    pygame.init()
    audio.set_enabled(False)
    bots = [Masher(), Ringer(), Tuner(), Founder()]
    seeds = (3, 41, 907)
    specs = [spec_for(i) for i in range(len(WAVES))]

    print("=" * 76)
    print("CAMPANARY playtest")
    print("=" * 76)

    table = {}
    for bot in bots:
        print(f"\n[{bot.name}]")
        for spec in specs:
                wins, times, hps = 0, [], []
                for s in seeds:
                    ok, t, hp = play(bot, spec, s)
                    wins += ok
                    times.append(t)
                    hps.append(hp)
                key = spec["name"]
                table.setdefault(key, {})[bot.name.split(":")[0]] = wins
                avg = sum(times) / len(times)
                print(f"   {key:18s} {wins}/{len(seeds)}   {avg:5.1f}s   hp {sum(hps)/len(hps):5.1f}")

    print("\n" + "=" * 76)
    print("does understanding actually pay?")
    print("=" * 76)
    names = [b.name.split(":")[0] for b in bots]
    print(f"   {'wave':20s}" + "".join(f"{n:>10s}" for n in names))
    totals = {n: 0 for n in names}
    for wave, row in table.items():
        line = f"   {wave:20s}"
        for n in names:
            line += f"{row.get(n, 0):>7d}/{len(seeds)}"
            totals[n] += row.get(n, 0)
        print(line)
    print(f"   {'TOTAL':20s}" + "".join(f"{totals[n]:>7d}/{len(table) * len(seeds)}" for n in names))

    ok = True
    if totals[names[0]] >= totals[names[-1]]:
        print("\n  !! a masher does as well as a founder - the system is decoration")
        ok = False
    if totals[names[-1]] < len(table) * len(seeds) * 0.7:
        print("\n  !! even a founder cannot clear the game")
        ok = False

    print("\n" + "=" * 76)
    print("frame cost, worst room")
    import time as _time
    spec = spec_for(len(WAVES) - 2)
    bells = Founder().loadout(spec)
    player = Player(pygame.Vector2(0, 0), bells)
    b = Belfry(player, spec, seed=5)
    bot = Founder()
    for _ in range(240):
        b.update(DT, *bot.act(b)[:1], True, False, False, None)
    t0 = _time.perf_counter()
    n = 600
    for _ in range(n):
        m, s_, h, d, w = bot.act(b)
        b.update(DT, m, s_, h, d, w)
    ms = (_time.perf_counter() - t0) / n * 1000
    print(f"   {ms:.3f} ms/step   ({ms / (DT * 1000) * 100:.1f}% of an {DT * 1000:.1f}ms step)")
    print(f"   live: {len(b.foes)} foes, {len(b.rings)} rings, {len(b.hostile)} hostile")

    print("\n" + "=" * 76)
    print("no problems found" if ok else "PROBLEMS FOUND")
    print("=" * 76)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
