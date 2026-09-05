# CLADE

*a clade of one*

An underwater survival horror metroidvania about a made thing, in a drowned
place, looking for another of its kind.

```
pip install -r requirements.txt
python play.py
```

---

## You are built out of what you kill

That is the whole game, seen from four sides.

You do not craft items. You have a **body with empty sockets**, and you fill
them with **organs** taken from the dead. Organs have no effects — they have
intakes and vents, and what they *do* is decided by what you plumb them
into. You route a chain through adjacent sockets:

```
INTAKE  →  transform  →  transform  →  VENT
```

Each transform rewrites a four-part humour vector **in place**, so the order
is the design:

| chain | result |
|---|---|
| `Salt Node → Kiln` | doubles the weight, then burns the doubled weight. **a lance.** |
| `Kiln → Salt Node` | burns the weight first, then doubles a weight that is no longer there. **a cough.** |

Same two organs. Measured, a 3.7× difference in damage. Nothing in the code
special-cases either arrangement; it falls out of running the functions in
the order you laid them.

## The four humours

Everything that flows through you, through every creature, and through the
water itself is a mixture of four things.

| | | |
|---|---|---|
| `~` | **BRINE** | mass, density, pressure. force. sinking. |
| `*` | **ICHOR** | metabolic fuel. heat. light — and light is being seen. |
| `.` | **SILT** | sediment. obscurity, and slow decay. |
| `!` | **SPARK** | nerve. speed, precision, and pain. |

**There is no effect table anywhere in this game.** What a mixture does is
computed from the vector — force from brine, heat from ichor, murk from
silt, jolt from spark, rot from ichor×silt, and so on. A mixture nobody
designed still behaves sensibly, and two players who reach the same vector
by different routes get identical results. That is the difference between a
system you can *learn* and one you can only memorise.

## Divergence: the two-sided key

**Divergence** measures how far a mixture is from equal parts, and it is the
spine of everything.

- **A spike** — one humour, nearly pure — is powerful and **loud**.
  `loudness = magnitude × divergence`, which is also very nearly the formula
  for a weapon.
- **A balance** — all four in rough proportion — does no damage at all, is
  silent, and is what living tissue answers to.

The doors in this place are alive. You cannot force them. Progression gates
are not keys; they are the sentence *"build a body capable of gentleness"* —
which is mechanically the opposite of everything twelve hours of combat will
have taught you. Making a key costs a wide intake and three or four organs,
because the two organs that even out a mixture both destroy magnitude doing
it, and gentleness scales with magnitude.

## Chains you fire, and chains you *run*

Four chains are bound to keys and thrown at the world. **Two are standing:
no vent, always on, and what they make happens to you.** They are read off
the same effect rules as the weapons, which is why they do exactly what
their organs say:

| standing chain | what it does to you |
|---|---|
| `siphon → kiln → ember gland` | you burn. it keeps the cold out — and it lights you up |
| `siphon → settling sac → silt bloom` | you trail sediment. hidden, and grounded |
| `siphon → harmonic` | you tend yourself. slow, real regeneration |
| `siphon → mirror sac → salt node` | you haul yourself upward. **traversal, designed at the Bench** |
| `siphon → ganglion → spine` | everything about you cycles faster, and hurts more |

Every one costs upkeep, and every one costs a socket a weapon could have
used. That is the whole economy: what you can *do* against what you can
*survive*, competing for the same body.

## Nothing is free

You burn reserve continuously just by being awake, and more for every
standing chain. **Ambient water covers the base rate and nothing beyond
it** — everything else has to come out of something that was alive.

So there is exactly one answer to running low, and it is hunting. `hold F`
on a corpse and take what it was made of. The verb the whole build system
hangs on is also the verb that keeps you breathing.

And **depth multiplies all of it**. The Sill costs nearly twice what the
Nursery does to be alive in, before you have paid for a single standing
chain — and the Sill is the region that demands one.

| | pressure | ambient | net, on a starting body |
|---|---|---|---|
| The Nursery | ×1.00 | 0.95/s | sustainable — you may idle here |
| The Cisterns | ×1.30 | 0.43/s *(clogged)* | −0.72/s → about two minutes a tank |
| The Lattice | ×1.60 | 0.95/s | −0.46/s |
| The Sill | ×1.95 | 0.95/s | −0.77/s |

## The world is trying to kill you, specifically

Below the Nursery you cannot simply survive *being somewhere*. Each region
applies a continuous pressure that exactly one standing build answers:

- **The Cisterns** clog your intakes with sediment. Everything you draw is
  halved until you run something gentle enough to keep yourself clear.
- **The Lattice** is live water, grounding through you continuously. Only a
  standing haze of sediment stops it.
- **The Sill** is cold, and the only answer is to be burning — in a region
  whose water has no heat in it at all, so you have to convert brine and
  pay the toll.

Which is what finally makes the Bench more than a gun menu. It is where you
go when you are stuck, and being stuck is usually a question about what
kind of animal you are rather than what you are holding.

## Every attack is windup → commit → recover

Nothing in this game fires instantly.

A creature **winds up** visibly, and while it does it stirs the water — in a
room you cannot see across, that pull is how something announces itself. At
the end of the windup **its heading locks and cannot be re-aimed**, so
moving actually works. Then it **recovers**, and recovery is a real
vulnerability window: armour drops to a quarter, damage more than doubles,
and landing a hit there staggers it.

That single rhythm is what turns a creature from a damage sponge into
something you play against. On top of it sit nine distinct verbs — a
**charger** that commits to a straight line and stuns itself on rock if you
move late, a **grappler** that latches on and drains you until you surge it
off, a **bulwark** that is armoured everywhere except the vents it opens
while recovering, an **ambusher** that is *genuinely undetectable while it
holds still*, a **screamer** that tells the room about you, and an **apex**
that goes to the loudest thing it heard and sweeps outward from there.

## Moving fast is the loudest thing you can do

Your wake scales with the **cube** of your speed. Cruising is quiet;
sprinting is a signal, and the Apex is listening for it. Holding still in
the dark makes you very nearly undetectable — which is a real option, and
an expensive one, because the clock is running the whole time.

## Heat closes the loop

An organ that works gets hot. Heat crawls to its **grid neighbours**, and
what does not crawl radiates into the water — where it becomes light, and
light is how you are found.

So the layout of your body is a thermal problem as much as a logical one.
Put the Ember Gland next to the Ganglion and the Ganglion seizes. Put it on
the rim and the room can see you. There is no correct layout, only the one
you can live with, and it changes every time you find a new organ.

Heat is not a balance tax bolted onto strong organs. It is one quantity
doing the same thing in three places.

## The water is a supply line

Four regions, four kinds of water, and your intakes pull whatever is around
you:

| region | water | |
|---|---|---|
| **The Nursery** | warm, organic, ichor-rich | *warm. it has not finished being alive.* |
| **The Cisterns** | thick with sediment | *thick. the light stops about an arm out.* |
| **The Lattice** | live, spark-rich | *it still has power. nobody has ever explained that.* |
| **The Sill** | cold, dense brine | *cold, and old, and it goes down further than the building.* |

And underneath the bestiary runs one ecological rule: **things are armoured
against the water they live in.** So in every region after the first, the
humour the water hands you for free is the one the locals are hardest to
hurt with. The Lattice is thick with live water and everything in it shrugs
off nerve — the region gives you the wrong answer for nothing and charges
you a conversion toll for the right one.

Which makes your reserve a supply line. A body that fills up on warm Nursery
water and carries it down into the Cisterns is carrying ammunition that
cannot be bought locally.

## Traversal is buoyancy

Your brine fraction against neutral decides whether you sink or rise. Heavy
bodies walk the floor; light bodies climb shafts. The game's "double jump"
is a **negative number** — a Mirror Sac inverting brine — and nobody had to
write a jump button.

## The dark

You see by your own glow, and your glow is a readout of what you are
carrying. A body full of heat burns orange and can be seen across a room. A
body full of sediment is nearly invisible and nearly blind.

Things outside your light are not drawn as shapes. They are drawn as **holes
in the water** — darker than the ground, moving. You do not see the Silt
Mother. You see the place where the water stops telling you anything, and
you watch that place move.

## Death

You do not reload. You **regress**: two organs come out of you and stay
where you fell, your reserve empties, and you wake at the last quiet pocket.
The organs are recoverable if you go back — unless something has eaten them,
in which case that thing now has your organs and is using them the same way
you would have.

It never takes your last intake or your last vent. It takes what it can
spare.

---

## Controls

| | |
|---|---|
| `WASD` | swim |
| mouse | aim |
| `LMB` `RMB` `Q` `E` | fire chains 1–4 |
| `SHIFT` / `SPACE` | surge — a shove out of your own back. costs brine. loud. |
| hold `F` | **feed.** put your mouth on a dead thing and take what it was made of. |
| `TAB` | the Bench — surgery and the Assay |
| `C` | the codex |
| `M` | the map |
| `ESC` | back |

### At the Bench

| | |
|---|---|
| right-click a socket | **removes it. always** — in every mode, with no exceptions |
| left-click a socket | selects it, and extends the chain you are editing |
| left-click a socket already in the path | steps the path back to there |
| `1`–`4` | edit a chain you **fire** |
| `5`–`6` | edit a chain you **run** |
| `R` | route it for you, if you are fighting the mouse |
| `X` / `BACKSPACE` | clear the path / undo one step |
| `ENTER` | keep it · `ESC` cancel |
| `SPACE` | the **Assay** |
| `L` | the **Shelf** — sixteen prebuilt chains that work |
| `F1` | the tutorial, nine steps, advances as you do things |

There is no state you can get into where a button stops meaning what it
meant a second ago. The status bar at the bottom always says what you are
doing and what to press next.

**Every organ tells you what it does, measured rather than written down:**

```
Salt Node    +brine    multiplies brine by about 3.0 — less the more of it
                       you already have
Kiln         b>ichor   brine becomes ichor, with 70% of it surviving the trip
Sieve        evens     flattens the mixture toward even in all four by
                       cutting the largest part down to the size of the
                       next largest
Mirror Sac   inverts   reverses ichor, so it pulls where it used to push —
                       and pointed at yourself, that is lift
Knot         repeats   runs everything before it a second time — including
                       the heat
```

Those lines are generated by *running the organ*, so they cannot drift out
of step with the simulation. There is a real difference between what you
could find out in four seconds at a free test bench (a Salt Node multiplies
brine) and what takes a hundred hours to notice (it therefore belongs
*before* the Kiln and not after). Being coy about the first kind was not
mystery, it was friction, and it stopped anyone reaching the second kind.

The **Assay** still never prints a damage number for an organ. It shows the
vector after every stage, and what the finished chain would do as labelled
bars. The last step is yours, and the last step is the game.

### The Shelf

`L` opens sixteen prebuilt chains. They exist to be tested, and to teach by
contrast — **LANCE** and **FIZZLE** are the same five organs in a different
order, and assaying both is the fastest way to understand the whole system:

```
LANCE    siphon > salt node > kiln > ember gland > spiracle    21.3 damage
FIZZLE   siphon > ember gland > kiln > salt node > spiracle      7.7 damage
```

The bottom five are standing chains, and three of them are the answers to
the three region hazards — so a player who cannot work out why the Sill is
killing them can load **FURNACE** and *then* work out why it helps.

```
python play.py --sandbox     one of every organ, every socket open
```

---

## The lore

A hatchery in a subduction trench. The surface did not burn — it
**suffocated**; the oceans stratified and went dead from the top down. The
last project was not to preserve humans, it was to preserve *the part that
had not decided yet*, and to let it become whatever the new world required.

It grew candidates. It watched which ones persisted. It never intervened,
because intervening is how you get something that needs you.

Every creature down here is a candidate. So are you.

The full account is in [`LORE.md`](LORE.md) — including the ending, so do not
read it first.

There is also [`BENCH.md`](BENCH.md): a design report on what the Bench
affects today, the rule that governs what can be added to it, and the
concrete things I would build next — including the ones I would refuse.

---

## Verifying it

```
python -m clade.verify.selftest    # 115 assertions about the *design*
python -m clade.verify.inputs      # every key on every screen
python -m clade.verify.playtest    # four bots of increasing understanding
python -m clade.verify.shots       # renders the game to shots/ with no display
```

`selftest.py` does not check that the code runs. It checks the claims the
game makes to the player, each written as something that can fail — that
ordering still matters, that a balanced charge still opens tissue and still
does no damage, that the Muffle is still a good trade, that a focused attack
still feeds a Recursor, that the whole route from the tank to the sill can
still be walked. Those failures are invisible from playing for ten minutes
and fatal over twelve hours.

`inputs.py` exists because of a crash the rest of the suite could not have
caught: `shots.py` drew every screen and `selftest.py` checked every rule,
and both passed while pressing ESC at the Bench raised `AttributeError` on
the first frame a player reached it. Everything verified the *draw* path
and nothing verified the *input* path. So it now presses every key and
every mouse button on every screen, twice — 561 combinations — and asserts
nothing raises.

`playtest.py` runs four bots that differ **only in how much they
understand** — they share navigation, aim and reflexes:

| bot | knows |
|---|---|
| `flail` | nothing. fires at what is nearest, never feeds, never shuts up |
| `feeder` | that the reserve is not ammunition, it is the clock |
| `quiet` | that loudness is a resource, and that slowing down spends less of it than holding fire does |
| `plumber` | how to order its own organs, **and how to build the standing chain the region it is in demands** |

```
bot        rooms  regions  deep  deaths  organs  frags  kills  harv   noise
flail       10.2      2.0   3.2     2.4     6.0    5.0    2.0   0.0     1.1
feeder      10.2      2.0   3.2     2.2    26.4    5.0   17.0  16.8    16.2
quiet       10.6      2.0   3.6     0.0    22.6    5.0   11.2  11.2     4.1
plumber     10.0      2.0   3.0     0.4    30.6    5.0   16.8  16.2    28.1
```

Knowing that the reserve is a clock is worth four times the parts. Knowing
that loudness is a resource is worth **zero deaths at a quarter the
noise**. And the bot that never opens the Bench ends a five-minute run with
exactly the body it started with.

Only the robust claims are assertions; the rest is printed. A bot playing a
stealth game with a fixed policy is high-variance by nature, and a flaky
assertion is worse than none — it trains whoever runs this to ignore the
output.

---

## Layout

```
play.py                  entry point
clade/
  humours.py             the four humours, and divergence
  effects.py             what a mixture DOES — every rule, no tables
  organs.py              33 organs. the grammar.
  body.py                the socket grid, chain routing, heat, metabolism
  player.py              you. mostly buoyancy, feeding, and surging.
  creatures.py           17 species, all running the same organ grammar
  bestiary.py            the roster, and the ecology rule
  lore.py                18 fragments, and the codex that remembers them
  app.py                 states, input, death, and the two endings
  world/
    fields.py            heat, silt, current, charge — the water as state
    room.py              tile geometry, carving, doors and their locks
    atlas.py             39 rooms, 4 regions, and the gates between them
    live.py              the live world and the attention economy
  render/
    dark.py              the volumetric dark: lightmap, silhouettes, snow
    hud.py               four readouts, all of them things you can change
  screens/bench.py       surgery and the Assay
  verify/                selftest, playtest bots, screenshot renderer
attic/                   a previous, unrelated prototype. nothing imports it.
```

`attic/` is a wave-simulation game that used to live here. It is kept
because it was well built and self-tested, and it is untouched because
nothing in CLADE is built on it.
