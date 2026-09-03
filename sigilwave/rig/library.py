"""Machines that already work, for taking apart. RIGS.md 6.

The tradition is inherited from `bench/presets.py` and it is the best idea in
the old build: Noita never explains a wand, it hands you one it made, lets you
fire it, and lets you pull one spell out and watch what changes. The rule
while writing these was the same too -- **a preset that cannot earn its
description gets its description changed or gets cut** -- and
`selftest_library` enforces it, because a library of machines that do not do
what they say teaches wrong rules from a source the player was told to trust.

Every preset carries `try_this`: one thing to change, and what will happen.
That is the part that actually teaches, because it turns a machine you were
given into an experiment you ran.
"""

from dataclasses import dataclass

from .chain import Chain


@dataclass
class Preset:
    name: str
    kinds: tuple
    summary: str      # what it is, one sentence
    why: str          # why it works, two or three
    try_this: str     # one change, and what happens

    def build(self) -> Chain:
        return Chain(self.kinds)


PRESETS = [
    Preset(
        name="the tapper",
        kinds=("INTAKE", "PORT"),
        summary="Water in, water out, nothing done to it.",
        why="The smallest thing that is not a failure. It proves the pipe is "
            "open at both ends, and it is the baseline every other machine "
            "here is a modification of.",
        try_this="Put a SQUEEZE in the middle. The water leaves hotter than it "
                 "arrived, and the bill arrives with it.",
    ),
    Preset(
        name="the cooler",
        kinds=("INTAKE", "SQUEEZE", "COIL", "EXPAND", "PORT"),
        summary="Cold water out the front, and a warm patch at the coil.",
        why="Squeeze it hot, dump that heat into the ocean through the coil, "
            "then expand what is left. It comes out colder than it went in "
            "because the heat went somewhere else -- which is the whole of "
            "law III, and the somewhere else is a place you chose.",
        try_this="Take the COIL out. It stops cooling and starts HEATING, "
                 "because you squeezed and expanded and never let the heat "
                 "leave. That is the second law, and it costs you every time.",
    ),
    Preset(
        name="the do-nothing",
        kinds=("INTAKE", "SQUEEZE", "EXPAND", "PORT"),
        summary="Spends energy and achieves nothing but a little heat.",
        why="A squeeze and an expansion are exact inverses on paper. They are "
            "not in a real machine: the compressor puts all of its work into "
            "the water and the turbine only gets some of it back, so the "
            "water comes out warmer than it started and you paid for the "
            "privilege.",
        try_this="Add a COIL between them. Now it is a cooler. One module, "
                 "and it is the difference between a machine and a bill.",
    ),
    Preset(
        name="the gill",
        kinds=("INTAKE", "EXPAND", "EXPAND", "FILTER", "PORT"),
        summary="Shakes breathable gas out of the water and keeps it.",
        why="Pressure holds gas in solution, so dropping it hard enough makes "
            "the gas come out as bubbles, and only then is there anything for "
            "a filter to catch. It has to make the bubbles before it can "
            "strain them, which is why the expansion comes first.",
        try_this="Take one EXPAND out. It catches far less, because the water "
                 "never got below what it could hold. Then take it to depth: "
                 "deep water carries more gas, so the same rig breathes "
                 "better exactly where it is trying to kill you.",
    ),
    Preset(
        name="the thruster",
        kinds=("INTAKE", "PUMP", "PUMP", "NARROW", "PORT"),
        summary="A fast jet, and a warm wake behind it.",
        why="Pumps put energy in as motion; the nozzle trades the pressure it "
            "is carrying for more speed. Momentum leaving the port is thrust, "
            "honestly -- there is no THRUST_PER_ENERGY here, only mass times "
            "velocity.",
        try_this="Add NARROWs one at a time and watch the thrust: 1359, 2719, "
                 "5438 newtons -- and then ZERO. The fourth one pulls the "
                 "throat below what holds water together, the flow tears, and "
                 "the collapse eats the jet that caused it. Every real "
                 "propeller has that cliff and every real designer works just "
                 "underneath it.",
    ),
    Preset(
        name="the charge",
        kinds=("INTAKE", "PUMP", "PUMP", "NARROW", "NARROW", "NARROW", "PORT"),
        summary="Tears the water open: a bang, a flash, and a cloud.",
        why="A nozzle buys speed with pressure. Buy enough and the absolute "
            "pressure falls below the tear point, the water fails "
            "mechanically, and the cavity collapses loudly and brightly. "
            "Sonoluminescence and the pistol shrimp, from Bernoulli alone.",
        try_this="Take it deeper. It stops working, because ambient pressure "
                 "has further to fall -- a machine tuned at the station "
                 "refuses to trip at depth, and you have to add nozzles. Then "
                 "take ONE nozzle off at the station: it stops banging and "
                 "starts pushing, 5438 N of it. This is the thruster with one "
                 "module too many, and you cannot have both.",
    ),
    Preset(
        name="the lamp",
        kinds=("INTAKE", "EXPAND", "EXPAND", "EXPAND", "EXPAND", "EXPAND", "PORT"),
        summary="Tears the water by expansion instead of by speed.",
        why="The same tear as the charge, reached the other way and far more "
            "expensively -- but it needs no pumps, so there was never a jet "
            "for the collapse to eat. Neither one pushes you: a machine that "
            "is cavitating is not a machine that is thrusting.",
        try_this="Count the EXPANDs you need at 40 m, then at 400 m. The "
                 "number is the depth, and that is the whole difficulty "
                 "curve in one reading.",
    ),
    Preset(
        name="sonar",
        kinds=("INTAKE", "RESONATOR", "WIDEN", "WIDEN", "PORT"),
        summary="A note thrown wide into the dark.",
        why="The old game, intact, as one build among eleven modules. The "
            "resonator sets the note and the widening spreads the aperture, "
            "which is soft at birth and coherent in flight -- so it carries.",
        try_this="Swap the WIDENs for NARROWs. The same energy leaves through "
                 "a smaller hole: brutal up close, and gone within a body "
                 "length.",
    ),
    Preset(
        name="the heater",
        kinds=("INTAKE", "SQUEEZE", "SQUEEZE", "PORT"),
        summary="Hot water out the front. A lift, a current, and a mirror.",
        why="No coil, so all the compression heat leaves with the water. Warm "
            "water is light and fast, so this rises, drags a current behind "
            "it, and bends sound away from wherever you pointed it.",
        try_this="Point it at a wall and hold it. You are building an "
                 "acoustic mirror out of temperature -- and lighting yourself "
                 "up for anything that hunts by heat.",
    ),
    Preset(
        name="the boiler",
        kinds=("INTAKE",) + ("SQUEEZE",) * 10 + ("PORT",),
        summary="Cooks itself, and you with it.",
        why="Ten squeezes and nowhere for the heat to go. This is the honest "
            "answer to 'why can I not just stack more' -- you can, and heat "
            "is never destroyed, so it ends up in the housing you are "
            "holding. Note how each squeeze buys less than the last: "
            "compressing water drives its gas back into solution, and the "
            "gas is what you were compressing.",
        try_this="Put a COIL after every second SQUEEZE. It stops boiling and "
                 "becomes the strongest cooler in the library, because each "
                 "stage starts from ambient instead of from the last one.",
    ),
    Preset(
        name="the cascade",
        kinds=("INTAKE", "SQUEEZE", "COIL", "SQUEEZE", "COIL",
               "EXPAND", "EXPAND", "PORT"),
        summary="Two stages of cooling. The cold end of the library.",
        why="Each squeeze-and-dump starts from ambient rather than from the "
            "last stage's heat, so the stages compound instead of fighting "
            "each other. Every real cryogenic plant is built this way and for "
            "this reason.",
        try_this="Move both COILs to the end. It stops cooling almost "
                 "entirely -- the heat has to leave BETWEEN the squeezes, not "
                 "after them. Order is the whole game.",
    ),
    Preset(
        name="the tap",
        kinds=("INTAKE", "THERMOPILE", "PORT"),
        summary="Three modules that cost nothing and hand energy back -- "
                "but only somewhere the water is not all one temperature.",
        why="A thermopile is a heat engine, and a heat engine needs two "
            "temperatures. Stand where the ocean is keeping a difference -- a "
            "vent, a cold layer, the edge of your own coil line -- and this "
            "takes a cut of the heat crossing between them. The size of the "
            "cut is Carnot, 1 minus cold over hot in kelvin, and nobody chose "
            "it.",
        try_this="Run it in still, even water. It makes EXACTLY zero, not a "
                 "little. That is not balance, it is the second law: there is "
                 "no work in one temperature however hot it is. Then walk to "
                 "the vent and watch the bill go negative.",
    ),
    Preset(
        name="the wellspring",
        kinds=("INTAKE", "THERMOPILE", "PUMP", "PUMP", "NARROW", "PORT"),
        summary="A thruster that pays for itself, if you launch from the "
                "right place.",
        why="The pile charges off the gradient, the pumps and the nozzle "
            "spend it, and beside a vent the first is bigger than the second. "
            "It is the same thruster as before with one module in front of "
            "it, and the module does not touch the water on its way past.",
        try_this="Swim away from the vent and keep running it. Nothing about "
                 "the machine changed and it is now costing you air, because "
                 "the gradient was never part of the machine -- it was part "
                 "of where you were standing.",
    ),
    Preset(
        name="the lance",
        kinds=("INTAKE", "EXPAND", "EXPAND", "EXPAND", "EXPAND",
               ("RESONATOR", "chirp"), "PORT"),
        summary="Tears the water with two or three fewer expansions than it "
                "would take alone, because the note does the rest.",
        why="Cavitation is about the LOWEST pressure the water sees, and a "
            "note is a pressure that is not in the pressure number. The "
            "expansions bring the mean down and the chirp swings it the rest "
            "of the way under. A resonator is worth two or three expansions "
            "at every depth in the game, and unlike the charge it leaves you "
            "nothing to be shoved by.",
        try_this="Take it to 400 m, then move the RESONATOR to the front. It "
                 "stops tearing and the bill goes from 0.49 to 37.75 -- "
                 "seventy-seven times worse for moving one module one place. "
                 "The pipe eats a chirp at 27% a module, so by the time it "
                 "arrives there is not enough of it left; and a chain that "
                 "very nearly tears has to pay to recompress everything a "
                 "collapse would have recompressed for free.",
    ),
    Preset(
        name="the horn",
        kinds=("INTAKE", ("RESONATOR", "swell"), "WIDEN", "WIDEN", "PORT"),
        summary="The long call. Low, wide, and it arrives.",
        why="Two rules pulling the same way. A swell is 117 Hz and the pipe "
            "barely touches it -- 0.3% a module against a chirp's 27% -- and "
            "the WIDENs drop the intensity so it cannot tear the water on the "
            "way out. Quiet enough to survive being loud.",
        try_this="Change the note to a chirp and count what comes out the "
                 "port. It loses three quarters of itself crossing the same "
                 "three modules, and the missing part is not missing -- it is "
                 "in the water as heat. High notes bite; low notes carry.",
    ),
    Preset(
        name="the hush",
        kinds=("INTAKE", "PUMP", "PUMP", "NARROW", "TURBINE", "PORT"),
        summary="The thruster, with the jet taken back out before it leaves.",
        why="A PORT throws whatever the slug has, and a jet is a wake, a "
            "noise, and an arrow pointing at you. The turbine takes the push "
            "back and hands 78% of it to the economy, so you arrive with "
            "nothing behind you.",
        try_this="Compare the thrust to `the thruster`: 2719 newtons becomes "
                 "zero. You cannot have the push AND the refund, and the "
                 "turbine is not for going anywhere -- it is for stopping "
                 "without saying so.",
    ),
]

BY_NAME = {p.name: p for p in PRESETS}


def get(name: str) -> Preset:
    if name not in BY_NAME:
        raise KeyError(f"no such preset: {name!r}")
    return BY_NAME[name]


def build(name: str) -> Chain:
    return get(name).build()
