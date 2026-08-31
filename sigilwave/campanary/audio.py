"""Every sound in the game is synthesised from the number that made it.

This is not decoration. The old build asked the player to read a note off a
coloured bar, which is a translation step between the system and the person,
and translation steps are where understanding leaks out. Pitch does not need
translating: a player who has heard a BOURDON once knows a BOURDON forever,
and can hear that the thing across the room is humming a TREBLE without
looking at it, without a scan, and without a tutorial line.

So `hz_for(note)` is the only bridge, and it is exact - the simulation's
notes are exact octaves, so the audio is exact octaves, A1 through A5. What
you hear is what you drew, transposed into the range a speaker can carry.

Bell partials are the real ones (hum, prime, tierce, quint, nominal), which
is why these read as bells rather than as sine beeps: a struck bell's
signature is that its partials are *not* a harmonic series, and the minor
third in there is where the whole mournful quality comes from.

Everything degrades to silence rather than to an exception - a machine with
no audio device is a machine that should still be able to play the game.
"""

import math

from . import notes

# hum, prime, tierce (minor third!), quint, nominal, and two upper partials.
BELL_PARTIALS = [
    (0.5, 0.32, 2.6),     # (ratio, amplitude, decay rate)
    (1.0, 1.00, 2.0),
    (1.2, 0.55, 3.0),
    (1.5, 0.30, 3.6),
    (2.0, 0.40, 3.2),
    (2.5, 0.16, 5.5),
    (3.0, 0.10, 6.5),
]

SR = 44100
_ready = False
_cache = {}
_master = 0.55
_enabled = True


def init() -> bool:
    """Bring the mixer up. Returns False if this machine has no audio, in
    which case every other function here becomes a no-op."""
    global _ready
    if _ready:
        return True
    try:
        import pygame

        pygame.mixer.pre_init(SR, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(24)
        _ready = True
    except Exception:
        _ready = False
    return _ready


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = bool(on)


def enabled() -> bool:
    return _enabled and _ready


def _render(freq, length, partials, gain, noise=0.0, attack=0.002):
    import numpy as np

    n = max(2, int(SR * length))
    t = np.linspace(0, length, n, endpoint=False)
    wave = np.zeros(n)
    for ratio, amp, decay in partials:
        f = freq * ratio
        if f > SR * 0.45:
            continue
        wave += amp * np.sin(2 * np.pi * f * t) * np.exp(-decay * t)
    if noise > 0.0:
        rng = np.random.default_rng(int(freq * 7919) & 0xFFFF)
        wave += noise * rng.standard_normal(n) * np.exp(-16.0 * t)

    peak = float(np.max(np.abs(wave))) or 1.0
    wave = wave / peak * gain
    # A couple of milliseconds of fade-in so nothing clicks, which is the
    # difference between a strike and a pop.
    a = max(1, int(SR * attack))
    wave[:a] *= np.linspace(0.0, 1.0, a)
    wave[-a:] *= np.linspace(1.0, 0.0, a)
    return np.ascontiguousarray(np.stack([wave, wave], axis=1) * 26000).astype(np.int16)


def _sound(key, factory):
    if not _ready:
        return None
    snd = _cache.get(key)
    if snd is None:
        try:
            import pygame

            snd = pygame.sndarray.make_sound(factory())
            _cache[key] = snd
        except Exception:
            return None
    return snd


def _play(snd, volume=1.0, pan=0.5):
    if snd is None or not _enabled:
        return
    try:
        import pygame

        ch = pygame.mixer.find_channel(True)
        if ch is None:
            return
        v = max(0.0, min(1.0, volume)) * _master
        left = v * min(1.0, 1.4 - pan)
        right = v * min(1.0, 0.4 + pan)
        ch.set_volume(left, right)
        ch.play(snd)
    except Exception:
        pass


# ------------------------------------------------------------------ voices

def toll(note: float, power: float = 1.0, pan: float = 0.5) -> None:
    """The bell. The single most important sound in the game: it is how the
    player learns what a note *is*."""
    q = max(0, min(notes.N_NOTES - 1, int(round(note * 2)) ))
    key = ("toll", q)
    freq = notes.hz_for(q / 2.0)
    _play(
        _sound(key, lambda: _render(freq, 1.7, BELL_PARTIALS, 0.85, noise=0.11)),
        0.30 + 0.55 * min(1.0, power),
        pan,
    )


def hum(note: int, pan: float = 0.5, volume: float = 0.25) -> None:
    """A foe, singing what it is weak to. Play this on a slow cycle and the
    room tells you its answer before you have looked at anything."""
    freq = notes.hz_for(note)
    _play(
        _sound(("hum", note), lambda: _render(
            freq, 1.1, [(1.0, 1.0, 1.4), (2.0, 0.22, 2.2), (1.2, 0.3, 1.8)], 0.5)),
        volume, pan,
    )


def shatter(note: float, pan: float = 0.5) -> None:
    """The payoff. Bright, short, and a fifth above the note that did it, so
    a shatter always resolves *upward* - the ear reads that as a win."""
    freq = notes.hz_for(max(0.0, min(4.0, note))) * 1.5
    _play(
        _sound(("shatter", int(note * 2)), lambda: _render(
            freq, 0.85,
            [(1.0, 1.0, 7.0), (2.02, 0.8, 8.0), (3.1, 0.6, 10.0), (4.7, 0.4, 12.0),
             (6.3, 0.25, 14.0)],
            0.95, noise=0.5, attack=0.001)),
        0.85, pan,
    )


def slam(pan: float = 0.5, power: float = 1.0) -> None:
    """Something heavy meeting something solid."""
    _play(
        _sound("slam", lambda: _render(
            72.0, 0.5, [(1.0, 1.0, 11.0), (1.6, 0.5, 15.0), (2.4, 0.25, 20.0)],
            0.9, noise=0.7, attack=0.001)),
        0.4 + 0.5 * min(1.0, power), pan,
    )


def crack(pan: float = 0.5) -> None:
    """Your own bell failing. Deliberately ugly."""
    _play(
        _sound("crack", lambda: _render(
            190.0, 0.7, [(1.0, 1.0, 9.0), (1.41, 0.9, 11.0), (2.17, 0.7, 13.0)],
            0.85, noise=0.9, attack=0.001)),
        0.8, pan,
    )


def dash(pan: float = 0.5) -> None:
    _play(
        _sound("dash", lambda: _render(
            520.0, 0.22, [(1.0, 0.5, 26.0), (2.0, 0.3, 30.0)], 0.5, noise=0.85,
            attack=0.001)),
        0.30, pan,
    )


def hurt(pan: float = 0.5) -> None:
    _play(
        _sound("hurt", lambda: _render(
            118.0, 0.42, [(1.0, 1.0, 9.0), (1.19, 0.7, 11.0)], 0.8, noise=0.4,
            attack=0.001)),
        0.6, pan,
    )


def tick(high: bool = False) -> None:
    """The metronome under the whole game."""
    _play(
        _sound(("tick", high), lambda: _render(
            1500.0 if high else 900.0, 0.07,
            [(1.0, 1.0, 40.0), (2.0, 0.4, 50.0)], 0.35, attack=0.001)),
        0.14 if high else 0.09,
    )


def ui(up: bool = True) -> None:
    _play(
        _sound(("ui", up), lambda: _render(
            660.0 if up else 440.0, 0.16, [(1.0, 1.0, 14.0), (2.0, 0.3, 18.0)], 0.4)),
        0.32,
    )
