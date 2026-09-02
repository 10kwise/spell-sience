"""Energy comes from somewhere. SUBMERGED.md 3.

*Energy is never created. It is somewhere, and you move it.* This is the rule
that turns the drawing into a system instead of a spell list, and 3.1 says
how the progression curve is carried by one number: casting off your own body
always works and always costs air, so **hour one you burn your lungs casting
and hour twenty you are running off a vent three rooms away.** Nobody has to
teach "transmit, do not generate" -- the air bar teaches it.

A source is three facts and nothing else: a rate, a note, and a place.
"""

import math

import pygame

V = pygame.Vector2

# How much air one unit of drive costs when it comes out of you. Set so an
# unbroken minute of casting is most of a tank -- expensive enough to be felt
# within one dive, cheap enough that experimenting is never punished.
AIR_PER_DRIVE = 0.55
AIR_MAX = 100.0
AIR_IDLE = 0.6            # breathing, per second


class Source:
    """Something in the water with energy in it."""

    def __init__(self, pos, rate, freq, reach, name):
        self.pos = V(pos)
        self.rate = rate
        self.freq = freq
        self.reach = reach
        self.name = name

    def available_at(self, pos) -> float:
        """A source is not a switch. It falls off with distance like anything
        else radiating into water, so 'get closer' and 'build a better
        collector' are the same sentence -- which is the point of 8's
        TRANSFER verb existing at all."""
        d = (V(pos) - self.pos).length()
        if d >= self.reach:
            return 0.0
        return self.rate * (1.0 - d / self.reach) ** 2


class Body(Source):
    """You. Always available, never free.

    The one source that is not in the water: it is in you, and 3.1 makes it
    the whole difficulty curve. There is no upgrade that makes it cheaper,
    because the intended discovery is that you should stop using it."""

    def __init__(self):
        super().__init__((0, 0), rate=0.30, freq=600.0, reach=math.inf,
                         name="body")

    def available_at(self, pos) -> float:
        return self.rate


class Vent(Source):
    """Hydrothermal. Hot, loud, low, and it does not move.

    It is also a heat source in the medium, which means a vent quietly builds
    the warm column above it that 8.1 says bends sound away -- so the best
    place to stand for power is a place where your own pings behave oddly.
    Nobody wrote that interaction; it is what putting heat in water does."""

    def __init__(self, pos, rate=1.6, freq=180.0, reach=380.0):
        super().__init__(pos, rate, freq, reach, "vent")
        self.heat_rate = 9.0

    def warm(self, medium, dt):
        medium.add_heat(self.pos.x, self.pos.y - 8.0, self.heat_rate * dt)


class Economy:
    """The air bar, and what spends it."""

    def __init__(self):
        self.air = AIR_MAX
        self.spent_from_body = 0.0
        self.drawn_from_world = 0.0

    def draw_energy(self, want: float, sources, at, dt) -> tuple:
        """Take what the world will give first, and only then breathe.

        The ordering is the whole lesson and it is deliberately automatic:
        the player is never asked to choose, they simply notice that standing
        somewhere else makes the bar stop falling."""
        from_world = 0.0
        for s in sources:
            if isinstance(s, Body):
                continue
            from_world += s.available_at(at)
        from_world = min(from_world, want)
        shortfall = max(0.0, want - from_world)

        self.air -= (AIR_IDLE + shortfall * AIR_PER_DRIVE * 60.0) * dt
        self.air = max(0.0, min(AIR_MAX, self.air))
        self.spent_from_body += shortfall * dt
        self.drawn_from_world += from_world * dt
        return from_world + shortfall, shortfall

    @property
    def drowning(self) -> bool:
        return self.air <= 0.0

    def report(self) -> str:
        total = self.spent_from_body + self.drawn_from_world
        if total <= 1e-9:
            return "nothing drawn yet"
        share = self.drawn_from_world / total * 100.0
        return (f"{share:3.0f}% of your power came out of the water"
                f" and {100 - share:3.0f}% out of you")
